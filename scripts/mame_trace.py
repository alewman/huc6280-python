#!/usr/bin/env python3
"""Record MAME 0.285's per-instruction HuC6280 trace of a PC Engine / TurboGrafx-16 / SuperGrafx ROM.

Runs the recipe in docs/mame-oracle.md in a fresh directory (default
``tests/mame_traces/<rom stem>``, gitignored) and leaves ``error.log`` there.
MAME's ``pce``, ``tg16`` and ``sgx`` drivers need no BIOS for a HuCard, so no
substitute ROM is written (unlike 65816-python's SNES recipe).

    python -I scripts/mame_trace.py game.pce
    python -I scripts/mame_trace.py game.7z --seconds 5 --io
    python -I scripts/mame_trace.py game.pce --seconds 10 --no-trace --snapshot 590

``error.log`` then holds one line per instruction, before it executes, all
hex except the last: ``PC A X Y S P MPR0-3 MPR4-7 totalcycles``. The two MPR
words pack four mapping registers each, MPR0 (or MPR4) in the low byte.
``PC`` is the 16-bit logical program counter. ``totalcycles`` is MAME's
``h6280_device`` count in units of one 7.16 MHz cycle: a CPU cycle costs 4 of
them in low speed (1.79 MHz) and 1 in high speed (h6280.cpp
``m_clocks_per_cycle``), plus 1 per access to the VDC/VCE, so SEI at reset
advances it by 8.

With ``--io`` it also logs, as ``R physical-address value``, every read of the
hardware page ($1FE000-$1FFFFF: VDC, VCE, PSG, timer, I/O port, interrupt
registers) (prefixed by MAME with ``[luaengine] ``) right after the trace line of the instruction that made it, for a
harness to answer the core's reads with. MAME saves a PNG of the screen under
``snap/<driver>/`` at frame ``--snapshot`` (default: the last whole frame of
``--seconds``; about 59.8 frames a second) and exits.
"""

from __future__ import annotations

import argparse
import shutil
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAME = "/usr/games/mame"
FPS = 59.8261  # the screen's refresh as MAME 0.285 reports it for the pce driver

TRACE_LUA = """\
local dbg = manager.machine.debugger
dbg.visible_cpu = manager.machine.devices[":maincpu"]
dbg:command('trace cpu.trace,,noloop,{logerror "%X %X %X %X %X %X %d\\\\n",\
pc,a,x,y,s,p,totalcycles; logerror "M %X %X %X %X %X %X %X %X\\\\n",mpr0,mpr1,mpr2,mpr3,mpr4,mpr5,mpr6,mpr7}')
dbg:command("go")
"""

# A read tap on the hardware page. MAME 0.285's debugger watchpoints do not work
# here: ``wpset 1FE000,2000,r,...`` fires for every read of the program space
# (addresses from $0 up: the instruction stream itself) and a write
# watchpoint on RAM never fires, so the range is ignored on this 21-bit space
# (checked 2026-10-23). ``install_read_tap`` honours its range. The callback
# writes into error.log with ``machine:logerror``, which MAME prefixes
# with "[luaengine] ", after the trace line of the instruction making the read.
# The tap must stay in a global or it is garbage-collected.
IO_LUA = """\
io_tap = manager.machine.devices[":maincpu"].spaces["program"]:install_read_tap(
  0x1FE000, 0x1FFFFF, "io",
  function(offset, data, mask)
    manager.machine:logerror(string.format("R %X %X\\n", offset, data))
  end)
-- MAME's pce driver always has a CD-ROM unit's backup RAM at $1EE000 (HuCards that look for
-- the "HUBM" header read it), so those reads are logged too.
bram_tap = manager.machine.devices[":maincpu"].spaces["program"]:install_read_tap(
  0x1EE000, 0x1EFFFF, "bram",
  function(offset, data, mask)
    manager.machine:logerror(string.format("R %X %X\\n", offset, data))
  end)
"""

# Notifier subscriptions are unsubscribed when garbage-collected: keep them in globals.
# ``video:snapshot()`` saves an all-black PNG for these drivers under -video none
# (checked 2026-10-23, while ``screen:pixels()`` held the picture), so the
# frame is written raw (4 bytes a pixel, B G R A) and converted by png() below.
SNAP_LUA = """\
local frames = 0
snap_sub = emu.add_machine_frame_notifier(function()
  frames = frames + 1
  if frames == {frame} then
    local screen = manager.machine.screens[":screen"]
    local file = io.open("frame.bgra", "wb")
    file:write(screen:pixels())
    file:close()
    io.open("frame.size", "w"):write(screen.width .. " " .. screen.height)
    manager.machine:exit()
  end
end)
"""


def png(out: Path) -> Path | None:
    """Convert the raw frame the Lua wrote to snap/frame.png (zlib only, no imaging library)."""
    raw, size = out / "frame.bgra", out / "frame.size"
    if not raw.exists() or not size.exists():
        return None
    width, height = (int(n) for n in size.read_text().split())
    data = raw.read_bytes()
    rows = bytearray()
    for y in range(height):
        rows.append(0)  # filter type: none
        line = data[y * width * 4 : (y + 1) * width * 4]
        for x in range(width):
            blue, green, red = line[x * 4], line[x * 4 + 1], line[x * 4 + 2]
            rows += bytes((red, green, blue))

    def chunk(kind: bytes, body: bytes) -> bytes:
        crc = zlib.crc32(kind + body)
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", crc)

    image = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(rows), 6))
        + chunk(b"IEND", b"")
    )
    lit = sum(1 for i in range(0, len(data), 4) if data[i : i + 3] != b"\0\0\0")
    print(f"  {lit:,} of {width * height:,} pixels are not black")
    target = out / "snap" / "frame.png"
    target.parent.mkdir(exist_ok=True)
    target.write_bytes(image)
    return target


def load_rom(path: Path) -> bytes:
    """The first .pce/.sgx/.bin of a .zip or .7z (via 7z), or the file itself; a 512-byte copier header dropped."""
    if path.suffix.lower() in (".7z", ".zip"):
        scratch = path.parent  # never extract beside the archive: use a pipe instead
        listing = subprocess.run(
            ["7z", "l", "-slt", str(path)], capture_output=True, text=True, check=True
        ).stdout
        names = [
            line.split(" = ", 1)[1]
            for line in listing.splitlines()
            if line.startswith("Path = ") and line.lower().endswith((".pce", ".sgx", ".bin"))
        ]
        if not names:
            raise SystemExit(f"{scratch / path.name}: no .pce/.sgx/.bin inside")
        data = subprocess.run(
            ["7z", "x", "-so", str(path), names[0]], capture_output=True, check=True
        ).stdout
    else:
        data = path.read_bytes()
    return data[512:] if len(data) % 8192 == 512 else data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("rom", type=Path)
    parser.add_argument("--seconds", type=int, default=3, help="emulated seconds")
    parser.add_argument("--no-trace", action="store_true", help="no debugger: result only")
    parser.add_argument("--io", action="store_true", help="also log hardware-page reads")
    parser.add_argument("--snapshot", type=int, metavar="FRAME")
    parser.add_argument("--driver", default="pce", choices=("pce", "tg16", "sgx"))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--mame", default=MAME)
    args = parser.parse_args()
    rom = args.rom.resolve()
    stem = rom.stem.replace(" ", "_")
    out = (args.out or ROOT / "tests" / "mame_traces" / stem).resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / "cart.pce").write_bytes(load_rom(rom))
    lua = "" if args.no_trace else TRACE_LUA
    if args.io and not args.no_trace:
        lua = IO_LUA + lua
    lua += SNAP_LUA.format(frame=args.snapshot or int(args.seconds * FPS) - 1)
    (out / "trace.lua").write_text(lua, encoding="utf-8")
    version = subprocess.run(
        [args.mame, "-version"], capture_output=True, text=True, check=True
    ).stdout.strip()
    debug = [] if args.no_trace else ["-debug", "-debugger", "none"]
    began = time.monotonic()
    # error.log lands in the working directory, not under -homepath.
    subprocess.run(
        [args.mame, args.driver, "-cart", "cart.pce",
         "-homepath", str(out),
         "-video", "none", "-sound", "none", "-nothrottle",
         "-noreadconfig", "-skip_gameinfo", *debug, "-log",
         "-seconds_to_run", str(args.seconds), "-autoboot_script", str(out / "trace.lua")],
        cwd=out, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )  # fmt: skip
    wall = time.monotonic() - began
    print(f"MAME {version}, {args.driver}, {wall:.1f} s wall: {out / 'error.log'}")
    if not args.no_trace:
        instructions = reads = 0
        with (out / "error.log").open("rb") as log:
            for line in log:
                fields = line.split()
                if line.startswith(b"[luaengine] R ") and len(fields) == 4:
                    reads += 1
                elif len(fields) == 7 and fields[0][:1].isalnum() and not line.startswith(b"["):
                    instructions += 1
        print(f"  {instructions:,} instructions, {reads:,} hardware-page reads")
    snapshot = png(out)
    if snapshot:
        print(f"  snapshot: {snapshot}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
