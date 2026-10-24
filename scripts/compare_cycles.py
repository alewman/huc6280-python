"""Compare per-opcode base cycle counts across the pinned sources.

    python -I scripts/compare_cycles.py            # opcodes where any two disagree
    python -I scripts/compare_cycles.py --all      # every opcode
    python -I scripts/compare_cycles.py --json out.json

Sources (all emulator-derived; the manuals' tables are compared by eye in
docs/timing.md, because they are scanned images):

- ``sst``: SingleStepTests huc6280 (Mesen): the smallest ``num_cycles`` over
  the corpus's 2,500 cases, which is the case with T = 0, D = 0, no branch taken.
- ``mame``: the constant in ``OP(op,XX) { h6280_cycles(N); ...`` (MAME 0.285).
  Branches, block moves and BSR charge inside their helpers; shown as None.
- ``gear``: Geargrafx ``k_huc6280_opcode_cycles`` (0 for the block moves).
- ``mdfn``: Mednafen pce_fast ``CycTable`` (block moves 17).

A source that does not state a number gives None and never counts as a
disagreement.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sst_reader import CORPUS, ROOT, tests

SRC = ROOT / "reference" / "src"


def table(path: Path, name: str, rows: int = 16) -> list[int]:
    text = path.read_text(encoding="utf-8", errors="replace")
    start = text.index(name)
    body = text[start : text.index("};", start)]
    numbers = [
        int(n)
        for line in body.splitlines()
        if re.match(r"\s*/\*\s*0x[0-9A-Fa-f]0\s*\*/", line)
        for n in re.findall(r"\b\d+\b", line.split("*/", 1)[1])
    ]
    assert len(numbers) == 256, (name, len(numbers))
    return numbers


def mame() -> list[int | None]:
    text = (SRC / "mame/src/devices/cpu/h6280/h6280.cpp").read_text(encoding="utf-8")
    out: list[int | None] = [None] * 256
    for opcode, cycles in re.findall(r"OP\(op,([0-9a-f]{2})\)\s*\{\s*h6280_cycles\((\d+)\)", text):
        out[int(opcode, 16)] = int(cycles)
    return out


def sst() -> list[int | None]:
    out: list[int | None] = [None] * 256
    for path in sorted(CORPUS.glob("*.json.bin")):
        out[int(path.name[:2], 16)] = min(test["num_cycles"] for test in tests(path))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    sources = {
        "sst": sst(),
        "mame": mame(),
        "gear": table(SRC / "Geargrafx/src/huc6280_timing.h", "k_huc6280_opcode_cycles"),
        "mdfn": table(SRC / "beetle-pce-fast/mednafen/pce_fast/huc6280.c", "CycTable"),
    }  # fmt: skip
    for opcode in range(0x100):
        if sources["gear"][opcode] == 0:
            sources["gear"][opcode] = None
    names = list(sources)
    print("op  " + "  ".join(f"{n:>4}" for n in names))
    shown = 0
    for opcode in range(0x100):
        row = [sources[n][opcode] for n in names]
        known = {v for v in row if v is not None}
        if args.all or len(known) > 1:
            shown += 1
            print(f"{opcode:02X}  " + "  ".join(f"{'-' if v is None else v:>4}" for v in row)
                  + ("" if len(known) < 2 else "  <-"))  # fmt: skip
    print(f"{shown} opcode(s) shown")
    if args.json:
        args.json.write_text(json.dumps(sources), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
