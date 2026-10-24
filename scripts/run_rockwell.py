"""Run every SingleStepTests rockwell65c02 case of a shared opcode through the core.

    python -I scripts/run_rockwell.py [--jobs 24] [--limit N] [--json out.json]

The readings, exclusions and masks are tests/rockwell.py's. Prints one line per opcode with
failures, then totals including how many cases used each mask or exclusion.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))

import rockwell

LIMIT: int | None = None


def run_opcode(opcode: int) -> tuple[int, int, int, Counter, list[str]]:
    passed = failed = 0
    masks: Counter = Counter()
    first: list[str] = []
    for case in rockwell.load_cases(opcode)[:LIMIT]:
        problems, used = rockwell.run_case(case)
        masks.update(used)
        if problems:
            failed += 1
            if not first:
                first = [case["name"], *problems[:3]]
        elif not used["alias"]:
            passed += 1
    return opcode, passed, failed, masks, first


def init(limit: int | None) -> None:
    global LIMIT
    LIMIT = limit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--jobs", type=int, default=24)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--opcode", type=lambda text: int(text, 16), action="append")
    args = parser.parse_args()
    opcodes = args.opcode or sorted(rockwell.SHARED)
    passed = failed = 0
    masks: Counter = Counter()
    results = {}
    with multiprocessing.Pool(args.jobs, initializer=init, initargs=(args.limit,)) as pool:
        for opcode, ok, bad, used, first in pool.imap_unordered(run_opcode, opcodes):
            passed += ok
            failed += bad
            masks.update(used)
            results[f"{opcode:02X}"] = {"passed": ok, "failed": bad, "masks": dict(used)}
            if bad:
                print(f"{opcode:02X}: {bad} failing; {first}", flush=True)
    total = 256 * (args.limit or 10_000)  # 10,000 cases in each of the 256 files
    print(
        f"shared opcodes {len(opcodes)}, cases passed {passed}, failed {failed}, "
        f"not run: {total - passed - failed - masks['alias']} (opcodes not shared, BRK) "
        f"+ {masks['alias']} aliased; masks {dict(masks)}"
    )
    if args.json:
        args.json.write_text(json.dumps(results, indent=1, sort_keys=True))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
