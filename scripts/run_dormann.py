"""Rung 2: build and run Dormann's 65C02 extended opcodes test on the core.

    python -I scripts/run_dormann.py [--limit N]

Prints where the program stopped: ``success`` at the address of its success trap, or ``trap`` at
the address of the first failed check (find it in reference/build/dormann/test.lst).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))

import dormann


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--limit", type=int, default=100_000_000)
    args = parser.parse_args()
    image, labels = dormann.build()
    began = time.monotonic()
    result = dormann.run(image, labels, args.limit)
    print(
        f"{result.reason} at ${result.pc:04X} after {result.instructions:,} instructions "
        f"(test case {result.test_case}); {time.monotonic() - began:.1f} s"
    )
    return 0 if result.reason == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
