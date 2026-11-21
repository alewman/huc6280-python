# SPDX-License-Identifier: MIT
"""C18 closed-box probe of srg320's HUC6280_CPU under GHDL (tests/huc6280_vhdl/tb_vanish.vhd).

    python -I validation/vanish_vhdl.py --ghdl-bin DIR      # DIR holds ghdl (oss-cad-suite/bin)

The VHDL is analysed and run, never read (docs/restart.md, rule 4). The program, at logical
$E000 (physical $000000 after reset):

    LDA #$F8; TAM #$02; LDX #$FF; TXS     ; I is set from reset
    CLI
    site: STZ $2010 | LDA $2010 | NOP     ; the write or read cycle at $1F0010 is the trigger
    NOP x 6; BRA *

with one interrupt input low from reset and released during the trigger cycle (the last cycle
of the site instruction), or never (the control, ``held``). The bus log shows the vector the
entry reads and the return address it pushes.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "reference" / "build" / "huc6280-vanish"
RTL = ROOT / "reference" / "src" / "TurboGrafx16_MiSTer" / "rtl" / "HUC6280"
UNITS = ("HUC6280_PKG", "AddSubBCD", "HUC6280_ALU", "HUC6280_AG", "HUC6280_MC", "HUC6280_CPU")
# The testbench elaborates with srg320's GPL core: a GPL tool outside this repository.
BENCH = Path(os.environ.get("HUC6280_GPL_TOOLS", ROOT / "tools")) / "huc6280_vhdl" / "tb_vanish.vhd"
SOURCES = {"irq2": 0, "irq1": 1, "tiq": 2}
VECTORS = {0x1FF6: "IRQ2", 0x1FF8: "IRQ1", 0x1FFA: "TIQ", 0x1FFC: "NMI", 0x1FFE: "RESET"}
SITE = 0xE008
TRIGGER = 0x1F0010
SITES = {
    "write": bytes([0x9C, 0x10, 0x20]),
    "read": bytes([0xAD, 0x10, 0x20]),
    "held": bytes([0xEA]),
}


def program(site: str) -> bytes:
    if site == "t-entry":
        # C16: CLA; CLX; CLI; SET; NOP...: the entry comes between SET and its target, and the
        # TIQ handler's first instruction is ORA #$0F (with T still set it would read and write
        # zero page $2000 + X, physical $1F0000).
        code = bytes([0xA9, 0xF8, 0x53, 0x02, 0xA2, 0xFF, 0x9A, 0x62, 0x82, 0x58, 0xF4])
        handlers = {0x80: bytes([0x09, 0x0F, 0x80, 0xFE])}
    else:
        code = bytes([0xA9, 0xF8, 0x53, 0x02, 0xA2, 0xFF, 0x9A, 0x58]) + SITES[site]
        handlers = {}
    code += bytes([0xEA] * 6) + bytes([0x80, 0xFE])
    rom = bytearray(b"\xff" * 8192)
    rom[: len(code)] = code
    for offset in (0x80, 0xA0, 0xC0):
        handler = handlers.get(offset, bytes([0x80, 0xFE]))  # by default each spins in place
        rom[offset : offset + len(handler)] = handler
    vectors = {0x1FF6: 0xE0C0, 0x1FF8: 0xE0A0, 0x1FFA: 0xE080, 0x1FFC: 0xE0C0, 0x1FFE: 0xE000}
    for offset, target in vectors.items():
        rom[offset : offset + 2] = bytes([target & 0xFF, target >> 8])
    return bytes(rom)


def build(ghdl_bin: Path) -> Path:
    executable = BUILD / "tb_vanish"
    if executable.exists() and executable.stat().st_mtime > BENCH.stat().st_mtime:
        return executable
    BUILD.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PATH=f"{ghdl_bin}:{os.environ['PATH']}")
    for source in [RTL / f"{unit}.vhd" for unit in UNITS] + [BENCH]:
        subprocess.run(["ghdl", "-a", "--std=08", "-fsynopsys", "-O2", str(source)],
                       cwd=BUILD, env=env, check=True)  # fmt: skip
    subprocess.run(["ghdl", "-e", "--std=08", "-fsynopsys", "tb_vanish"], cwd=BUILD, env=env,
                   check=True)  # fmt: skip
    return executable


def run(
    executable: Path,
    source: str,
    site: str,
    late: bool = False,
    release_at: int = -1,
    rise: bool = False,
) -> list[tuple[int, ...]]:
    with tempfile.TemporaryDirectory() as scratch:
        rom = Path(scratch) / "rom.txt"
        out = Path(scratch) / "bus.txt"
        rom.write_text("\n".join(str(b) for b in program(site)) + "\n")
        trigger = TRIGGER if site != "held" and release_at < 0 else -1
        subprocess.run(
            [str(executable), f"-grom={rom}", f"-goutput={out}", f"-gsource={SOURCES[source]}",
             f"-gtrigger={trigger}", f"-grelease_at={release_at}", "-gcycles=120", f"-glate={'true' if late else 'false'}", f"-grise={'true' if rise else 'false'}"],
            cwd=scratch, check=True, capture_output=True,
        )  # fmt: skip
        return [tuple(int(w) for w in line.split()) for line in out.read_text().splitlines()]


def summary(log: list[tuple[int, ...]]) -> str:
    """The first entry after reset: its vector and pushed return address, or none."""
    pushes = []
    released_at = next((c for c, *_rest, level in log if level), None)
    for cycle, address, value, we_n, _mcycle, _level in log:
        if we_n == 0 and 0x1F0100 <= address <= 0x1F01FF:
            pushes.append(value)
        if we_n == 1 and address in VECTORS and VECTORS[address] != "RESET" and len(pushes) >= 3:
            ret = pushes[0] << 8 | pushes[1]
            when = "" if released_at is None else f", line released at cycle {released_at}"
            return (
                f"entry through {VECTORS[address]} at cycle {cycle}, return address {ret:04X}{when}"
            )
    spin = log[-1][1]
    return f"no entry (last address {spin:06X})"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--ghdl-bin", type=Path, required=True)
    parser.add_argument("--late", action="store_true", help="answer reads after the rising edge")
    parser.add_argument(
        "--sweep",
        nargs=2,
        type=int,
        metavar=("FIRST", "LAST"),
        help="release in each cycle FIRST..LAST instead of at the trigger",
    )
    parser.add_argument(
        "--t-entry", action="store_true", help="C16: T after an entry that follows SET"
    )
    parser.add_argument("--rise", action="store_true", help="the line appears instead of going")
    parser.add_argument("--dump", nargs=2, metavar=("SOURCE", "SITE"), help="print one bus log")
    args = parser.parse_args()
    executable = build(args.ghdl_bin)
    if args.dump:
        for row in run(executable, *args.dump, late=args.late):
            print(*row)
        return 0
    print(f"site at ${SITE:04X}; the instruction after it at ${SITE + 3:04X} (write/read), "
          f"${SITE + 1:04X} (held)")  # fmt: skip
    if args.t_entry:
        log = run(executable, "tiq", "t-entry", args.late)
        entry = next(n for n, row in enumerate(log) if row[1] == 0x1FFA and row[3] == 1)
        pushed = [row[2] for row in log[:entry] if row[3] == 0 and 0x1F0100 <= row[1] <= 0x1F01FF]
        touched = [row for row in log[entry:] if row[1] == 0x1F0000]
        print(
            f"t-entry: entry at cycle {log[entry][0]}, pushed P ${pushed[-1]:02X}; handler "
            f"{'touched' if touched else 'did not touch'} $1F0000 (T {'still set' if touched else 'clear'})"
        )
        return 0
    for source in SOURCES:
        for site in SITES:
            if args.sweep:
                for cycle in range(args.sweep[0], args.sweep[1] + 1):
                    log = run(executable, source, site, args.late, cycle, args.rise)
                    print(f"{source:4} {site:5} release in cycle {cycle}: {summary(log)}")
            else:
                print(f"{source:4} {site:5}: {summary(run(executable, source, site, args.late))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
