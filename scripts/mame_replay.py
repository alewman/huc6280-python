"""Replay a MAME trace through the core and print where they differ (rung 4).

    python -I scripts/mame_trace.py game.pce --io --seconds 2 [--driver tg16]
    python -I scripts/mame_replay.py tests/mame_traces/<game> [--limit N]

The directory is one ``mame_trace.py --io`` left: ``cart.pce`` and ``error.log``. The report
counts interrupts taken, register divergences (MAME's registers are taken after each, up to
``--max-divergences``) and instruction lengths, equal or tallied by opcode (tests/mame_replay.py).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))

from mame_replay import replay


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("trace", type=Path, help="a mame_trace.py --io output directory")
    parser.add_argument("--limit", type=int, help="stop after this many instructions")
    parser.add_argument("--max-divergences", type=int, default=50)
    parser.add_argument(
        "--samples", action="store_true", help="show cases of each cycle difference"
    )
    args = parser.parse_args()
    began = time.monotonic()
    report = replay(
        (args.trace / "cart.pce").read_bytes(),
        args.trace / "error.log",
        args.limit,
        args.max_divergences,
    )
    print(report.summary())
    if args.samples:
        for (opcode, delta), samples in sorted(report.samples.items()):
            for index, registers in samples:
                text = " ".join(f"{v:X}" for v in registers)
                print(f"  {opcode:02X} {delta:+d} at line {index:,}: {text}")
    print(f"{time.monotonic() - began:.1f} s")
    return 1 if report.divergences or report.unexplained else 0


if __name__ == "__main__":
    sys.exit(main())
