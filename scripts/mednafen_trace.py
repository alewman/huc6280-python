"""Record Mednafen 1.32.1's per-instruction HuC6280 trace of a HuCard (rung 4b).

    python -I scripts/build_mednafen.py                       # once
    python -I scripts/mednafen_trace.py GAME.7z [--count 3500000] [--out DIR]

Writes DIR/cart.pce and DIR/error.log in the format scripts/mame_replay.py reads (so
``scripts/mame_replay.py DIR`` replays it): ``PC A X Y S P cycles`` and ``M MPR0..7`` per instruction
and ``[luaengine] R address value`` for each hardware-page read (the format is MAME's by design;
nothing here is Lua). The patch (tools/mednafen-trace.patch) logs from inside the CPU; Mednafen
runs headless with SDL's dummy video and audio drivers and stops by itself after ``--count``
instructions. Cycles are 7.16 MHz units (master clocks / 3), like MAME's ``totalcycles``.
See docs/mednafen-oracle.md.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / "reference" / "build" / "mednafen-bin" / "bin" / "mednafen"
sys.path.insert(0, str(ROOT / "scripts"))

from mame_trace import load_rom


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("rom", type=Path)
    parser.add_argument("--count", type=int, default=3_500_000, help="instructions to log")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if not BINARY.exists():
        raise SystemExit("not built: python -I scripts/build_mednafen.py")
    stem = args.rom.stem.replace(" ", "_")
    out = (args.out or ROOT / "tests" / "mednafen_traces" / stem).resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / "cart.pce").write_bytes(load_rom(args.rom.resolve()))
    env = dict(os.environ)
    env.update(
        SDL_VIDEODRIVER="dummy",
        SDL_AUDIODRIVER="dummy",
        MEDNAFEN_HOME=str(out / "home"),
        MEDNAFEN_TRACE=str(out / "error.log"),
        MEDNAFEN_TRACE_COUNT=str(args.count),
    )
    subprocess.run(
        [str(BINARY), "-sound", "0", "-video.fs", "0", "-pce.stretch", "0", "-nothrottle", "1",
         "-filesys.path_firmware", str(out / "home"), str(out / "cart.pce")],
        env=env, cwd=out, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=900,
    )  # fmt: skip
    shutil.rmtree(out / "home", ignore_errors=True)
    size = (out / "error.log").stat().st_size if (out / "error.log").exists() else 0
    print(f"{out / 'error.log'}: {size:,} bytes")
    return 0 if size else 1


if __name__ == "__main__":
    sys.exit(main())
