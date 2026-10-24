"""Print the HuC6280 opcode map as the pinned emulators agree on it.

    python -I scripts/opcode_map.py            # one line per opcode
    python -I scripts/opcode_map.py --grid     # 16 x 16 mnemonic grid
    python -I scripts/opcode_map.py --cycles   # 16 x 16 grid of base cycle counts

Mnemonic and addressing mode come from Mesen2's tables (``PceCpu.cpp``
``_opTable``, ``_addrMode``), operand length from Geargrafx's
``k_huc6280_opcode_sizes`` (the block moves are 7 bytes), and the cycle counts
are the smallest ``num_cycles`` in SingleStepTests huc6280 (T = 0, D = 0, no
branch taken; ``compare_cycles.py`` shows where the other sources differ).
Emulator-derived: rung 0 checks every row against Hudson's software manual.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_cycles import SRC, sst, table

ALIASES = {"CPA": "CMP", "NOP": "NOP"}
MODE_TEXT = {
    "Imp": "implied", "Acc": "A", "Imm": "#imm", "Zero": "zp", "ZeroX": "zp,X", "ZeroY": "zp,Y",
    "Abs": "abs", "AbsX": "abs,X", "AbsY": "abs,Y", "Ind": "(abs)", "IndX": "(zp,X)",
    "IndY": "(zp),Y", "ZInd": "(zp)", "AbsXInd": "(abs,X)", "Rel": "rel", "ZeroRel": "zp,rel",
    "Block": "src,dst,len", "ImZero": "#imm,zp", "ImZeroX": "#imm,zp,X", "ImAbs": "#imm,abs",
    "ImAbsX": "#imm,abs,X", "None": "JSR abs",
}  # fmt: skip


def parse() -> tuple[list[str], list[str]]:
    text = (SRC / "Mesen2/Core/PCE/PceCpu.cpp").read_text(encoding="utf-8")
    ops = text[text.index("_opTable[]") : text.index("typedef PceAddrMode")]
    names = re.findall(r"&C::(\w+)", ops)
    modes = re.findall(
        r"M::(\w+)", text[text.index("_addrMode[]") : text.index("#ifndef DUMMYCPU")]
    )
    assert len(names) == len(modes) == 256, (len(names), len(modes))
    return names, modes


def mnemonic(raw: str, opcode: int) -> str:
    base = raw.split("_")[0]
    if base in ("ASL", "LSR", "ROL", "ROR", "INC", "DEC") and raw.endswith("Acc"):
        base += " A"
    if base in ("BBR", "BBS", "RMB", "SMB"):
        base += str((opcode >> 4) & 7)
    if base in ("TMA", "TAM"):
        base += "n"
    return ALIASES.get(base, base)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--grid", action="store_true")
    parser.add_argument("--cycles", action="store_true")
    args = parser.parse_args()
    names, modes = parse()
    sizes = table(SRC / "Geargrafx/src/huc6280_timing.h", "k_huc6280_opcode_sizes")
    cycles = sst()
    if args.cycles:
        print("     " + " ".join(f"{c:<3X}" for c in range(16)))
        for row in range(16):
            print(f"{row:X}0   " + " ".join(f"{cycles[row * 16 + c]:<3}" for c in range(16)))
        return 0
    if args.grid:
        print("     " + " ".join(f"{c:<8X}" for c in range(16)))
        for row in range(16):
            cells = [mnemonic(names[row * 16 + c], row * 16 + c) for c in range(16)]
            print(f"{row:X}0   " + " ".join(f"{cell:<8}" for cell in cells))
        return 0
    for opcode in range(256):
        print(
            f"{opcode:02X}  {mnemonic(names[opcode], opcode):<7} "
            f"{MODE_TEXT.get(modes[opcode], modes[opcode]):<13} {sizes[opcode]} bytes  "
            f"{cycles[opcode]} cycles"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
