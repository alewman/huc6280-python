"""Survey the SingleStepTests huc6280 corpus: cycle counts and bus shapes per opcode.

    python -I scripts/survey_sst.py            # one line per opcode
    python -I scripts/survey_sst.py --json out.json

For each opcode: the distinct total cycle counts (``num_cycles``) with how many
cases had each, and the distinct *shapes* (the string of cycle kinds: ``R`` a
read, ``W`` a write, ``d`` a read the corpus marks dummy (the next opcode
byte read and thrown away), ``i`` an internal cycle with no bus access). The
corpus is Mesen's output (emulator-derived): this is what Mesen does, not what
the chip does.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sst_reader import CORPUS, tests


def shape(cycles) -> str:
    out = []
    for _address, _data, kind in cycles:
        if kind == "r":
            out.append("R")
        elif kind == "w":
            out.append("W")
        elif kind == "rd":
            out.append("d")
        elif kind == "":
            out.append("i")
        else:
            out.append("?")
    return "".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    result = {}
    for path in sorted(CORPUS.glob("*.json.bin")):
        counts: Counter[int] = Counter()
        shapes: Counter[str] = Counter()
        for test in tests(path):
            counts[test["num_cycles"]] += 1
            shapes[shape(test["cycles"])] += 1
        opcode = int(path.name[:2], 16)
        result[opcode] = {"cycles": dict(counts), "shapes": dict(shapes.most_common(6))}
        top = ", ".join(f"{n}x{c}" for n, c in sorted(counts.items()))
        print(f"{opcode:02X}  {top:40s} {', '.join(list(shapes)[:3])}")
    if args.json:
        args.json.write_text(json.dumps(result, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
