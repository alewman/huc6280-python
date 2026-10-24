"""Run every SingleStepTests huc6280 case through the core, a process per opcode.

    python -I scripts/run_single_step.py [--jobs 24] [--limit N] [--json out.json]

The readings and masks are tests/single_step.py's (it is imported from there).
Prints one line per opcode with failures, then totals including how many cases
used each mask. The quick check is pytest; this is the whole of rung 1.
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

import single_step  # noqa: E402

LIMIT: int | None = None


CHUNK = 250  # cases per task: block transfers take minutes a case batch, the rest seconds


def run_chunk(task: tuple[int, int]) -> tuple[int, int, int, Counter, list[str]]:
    opcode, start = task
    passed = failed = 0
    masks: Counter = Counter()
    first: list[str] = []
    for number, case in enumerate(single_step.load_cases(opcode)):
        if number < start:
            continue
        if number >= start + CHUNK or (LIMIT is not None and number >= LIMIT):
            break
        problems, used = single_step.run_case(case)
        masks.update(used)
        if problems:
            failed += 1
            if not first:
                first = [case["name"], *problems[:3]]
        else:
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
    opcodes = args.opcode or range(256)
    tasks = [(opcode, start) for opcode in opcodes for start in range(0, args.limit or 2500, CHUNK)]
    passed = failed = 0
    masks: Counter = Counter()
    results: dict[str, dict] = {}
    with multiprocessing.Pool(args.jobs, initializer=init, initargs=(args.limit,)) as pool:
        for opcode, ok, bad, used, first in pool.imap_unordered(run_chunk, tasks):
            passed += ok
            failed += bad
            masks.update(used)
            entry = results.setdefault(f"{opcode:02X}", {"passed": 0, "failed": 0, "masks": {}})
            entry["passed"] += ok
            entry["failed"] += bad
            for name, count in used.items():
                entry["masks"][name] = entry["masks"].get(name, 0) + count
            if bad:
                print(f"{opcode:02X}: {bad} failing; {first}", flush=True)
    print(
        f"opcodes {len(results)}, cases passed {passed}, failed {failed}; masks used {dict(masks)}"
    )
    if args.json:
        args.json.write_text(json.dumps(results, indent=1, sort_keys=True))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
