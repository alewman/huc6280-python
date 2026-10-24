"""Rung 5: run SingleStepTests cases through srg320's HUC6280_CPU under GHDL.

    python -I scripts/build_referees.py huc6280-tb --oss DIR    # once: the testbench
    python -I scripts/run_vhdl.py                               # 30 cases per opcode
    python -I scripts/run_vhdl.py --cases 300 --opcode 73 --show 5

For each case the HDL's cycles are compared with the core's and with the corpus's
(tests/huc6280_vhdl.py), and every difference is counted by opcode and by what differs: the
cycle count, read or write, an internal cycle (``MCYCLE`` low in the HDL), the address of a
read or write, the address of a dummy read, a value. The report groups the cases by category
and by who stands alone: the HDL (the core and the corpus agree), the corpus (the HDL sides
with the core), the core (the HDL sides with the corpus), or all three differing.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))

import single_step
from huc6280_vhdl import (
    TESTBENCH,
    next_fetch_matches,
    physical,
    run_core,
    run_corpus,
    run_testbench,
    vote,
)

CATEGORY_NAMES = [
    f"{c}{s}" for s in ("", " (T)") for c in ("count", "writes", "reads", "idle_count", "pattern")
]
BLOCKS = {0x73, 0xC3, 0xD3, 0xE3, 0xF3}
#: ORA AND EOR ADC, in every mode: the instructions T changes (U4)
T_OPCODES = {
    n
    for n in range(256)
    if n & 0x1F in (1, 5, 9, 0xD, 0x11, 0x12, 0x15, 0x19, 0x1D) and n >> 5 in (0, 1, 2, 3)
}


def run_opcode(job: tuple[int, int]) -> tuple[int, int, Counter, dict]:
    """(opcode, cases run, Counter[(category, side)], {(category, side): example})."""
    opcode, limit = job
    cases = []
    for number, case in enumerate(single_step.load_cases(opcode)):
        if number >= limit:
            break
        cases.append(case)
    tally: Counter = Counter()
    examples: dict = {}
    hdl = run_testbench(cases)
    for case, cycles in zip(cases, hdl, strict=True):
        if cycles is None:
            tally["loader", "skipped"] += 1
            continue
        if cycles[0].address != physical(case["initial"]["mpr"], case["initial"]["pc"]):
            # The loader did not reach the case, or an earlier read of the JMP's physical address
            # (an alias through the MPRs) started the case early: dropped, counted.
            tally["loader", "failed"] += 1
            continue
        core, corpus = run_core(case), run_corpus(case)
        # The HDL logs one cycle more (the next fetch); the others have exactly the case's.
        if case["num_cycles"] != len(case["cycles"]):  # a truncated block transfer
            core = core[: len(corpus)]
        sides = vote(core, cycles[: len(core)], corpus)
        if not next_fetch_matches(case, cycles):
            sides["count"] = "HDL alone"
        # The HDL's cycles for the comparison: the case's own, and none of the next fetch.
        t_mode = bool(case["initial"]["p"] & 0x20) and opcode in T_OPCODES
        for category, side in sides.items():
            category = f"{category} (T)" if t_mode else category
            tally[category, side] += 1
            examples.setdefault((category, side), (case["name"], core, cycles, corpus))
        tally["cases", "run"] += 1
    return opcode, len(cases), tally, examples


def _print_example(name: str, core: list, hdl: list, corpus: list) -> None:
    rows = max(len(core), len(hdl), len(corpus))
    table = [[c[i].text() if i < len(c) else "-" for c in (core, hdl, corpus)] for i in range(rows)]
    first = next((i for i, row in enumerate(table) if len(set(row)) > 1), 0)
    start, end = max(first - 2, 0), min(first + 5, rows)
    print(f"  {name}: core / HDL / corpus, cycles {start}-{end - 1} of {rows}")
    for row in table[start:end]:
        print(f"    {row[0]:22} {row[1]:26} {row[2]:22}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--cases", type=int, default=30, help="cases per opcode")
    parser.add_argument("--jobs", type=int, default=24)
    parser.add_argument("--opcode", type=lambda t: int(t, 16), action="append")
    parser.add_argument("--show", type=int, default=0, help="examples per category and side")
    args = parser.parse_args()
    if not TESTBENCH.exists():
        raise SystemExit("testbench not built: python -I scripts/build_referees.py huc6280-tb")
    opcodes = args.opcode or range(256)
    jobs = [(opcode, min(args.cases, 5) if opcode in BLOCKS else args.cases) for opcode in opcodes]
    total: Counter = Counter()
    by_opcode: dict[int, Counter] = {}
    examples: dict = {}
    with ProcessPoolExecutor(args.jobs) as pool:
        for opcode, _, tally, found in pool.map(run_opcode, jobs):
            total.update(tally)
            by_opcode[opcode] = tally
            for key, value in found.items():
                examples.setdefault((key, opcode), value)
    print(
        f"cases run: {total['cases', 'run']:,}; loader failures: {total['loader', 'failed']:,};"
        f" skipped (no clear loader address): {total['loader', 'skipped']:,}"
    )
    names = CATEGORY_NAMES
    sides = sorted({side for (category, side) in total if category in names})
    print("category            " + "  ".join(f"{side:>13}" for side in sides))
    for category in names:
        counts = "  ".join(f"{total[category, side]:>13,}" for side in sides)
        print(f"{category:19} {counts}")
    print()
    for category in names:
        for side in sides:
            opcodes_hit = sorted(op for op, tally in by_opcode.items() if tally[category, side])
            if opcodes_hit:
                text = " ".join(f"{op:02X}" for op in opcodes_hit)
                print(f"{category} / {side}: {text}")
    shown: Counter = Counter()
    for (key, opcode), (name, core, hdl, corpus) in sorted(
        examples.items(), key=lambda item: (item[0][0], item[0][1])
    ):
        if shown[key] < args.show:
            shown[key] += 1
            print(f"{key[0]} / {key[1]}:")
            _print_example(name, core, hdl, corpus)
    return 0


if __name__ == "__main__":
    sys.exit(main())
