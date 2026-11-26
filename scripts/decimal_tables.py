# SPDX-License-Identifier: MIT
"""C13: record the two decimal ADC/SBC result tables closed box and check the core against them.

    python -I scripts/build_mednafen.py          # once (emu-tools-gpl2's build)
    python -I scripts/decimal_tables.py [--out DIR]

Mednafen's table: an 8 KB HuCard written here runs ``ADC $00`` and ``SBC $00`` with D set, with
carry clear and set, for every A (X) and operand (Y, stored at $2000) - 262,144 operations - under
the traced Mednafen 1.32.1 build (scripts/mednafen_trace.py; run, never read). The trace gives the
state before each instruction, so a site's result is the next line's A and P.

Mesen's table: every case of SingleStepTests huc6280 (MIT test data recorded from Mesen) for the
eighteen ADC and SBC opcodes with D set and T clear; the operand is the last plain read before
the closing dummy read. 11,346 cases, a sample of the 131,072 inputs per operation.

The core's ``add`` and ``subtract`` must give exactly the recorded A and P for each formula.
The digit rules in src/huc6280/_alu.py were written from these two tables alone (docs/restart.md).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from itertools import pairwise
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from sst_reader import CORPUS, tests

from huc6280._alu import add, subtract

PROGRAM = bytes.fromhex(
    "78 A9F8 5302 F8 A200"  # E000 SEI; LDA #$F8; TAM #$02 (MPR1 = RAM); SED; LDX #0
    "A000"  # E008 outer: LDY #0
    "8400 18 8A 6500"  # E00A inner: STY $00; CLC; TXA; ADC $00   (site E00E)
    "38 8A 6500"  # E010 SEC; TXA; ADC $00                         (site E012)
    "18 8A E500"  # E014 CLC; TXA; SBC $00                         (site E016)
    "38 8A E500"  # E018 SEC; TXA; SBC $00                         (site E01A)
    "C8 D0EB E8 D0E6 80FE"  # INY; BNE inner; INX; BNE outer; BRA *
)
SITES = {0xE00E: (add, 0), 0xE012: (add, 1), 0xE016: (subtract, 0), 0xE01A: (subtract, 1)}
ADC = ["69", "65", "75", "6d", "7d", "79", "61", "71", "72"]
SBC = ["e9", "e5", "f5", "ed", "fd", "f9", "e1", "f1", "f2"]


def rom() -> bytes:
    image = bytearray(b"\xff" * 8192)
    image[: len(PROGRAM)] = PROGRAM
    for vector in range(0x1FF6, 0x2000, 2):
        image[vector : vector + 2] = b"\x00\xe0"
    return bytes(image)


def mednafen_rows(out: Path):
    """(operation, A, operand, P in, A out, P out) for every site in Mednafen's trace."""
    cart = out / "decimal.pce"
    cart.write_bytes(rom())
    subprocess.run(
        [sys.executable, "-I", str(ROOT / "scripts" / "mednafen_trace.py"), str(cart),
         "--count", "1100000", "--out", str(out / "trace")],
        check=True,
    )  # fmt: skip
    lines = [
        line.split()
        for line in (out / "trace" / "error.log").read_text().splitlines()
        if not line.startswith(("M ", "["))
    ]
    for here, after in pairwise(lines):
        site = SITES.get(int(here[0], 16))
        if site:
            a, _x, y, _s, p = (int(v, 16) for v in here[1:6])
            yield site[0], a, y, p, int(after[1], 16), int(after[5], 16)


def mesen_rows():
    for operation, opcodes in ((add, ADC), (subtract, SBC)):
        for opcode in opcodes:
            for case in tests(CORPUS / f"{opcode}.json.bin"):
                initial, final = case["initial"], case["final"]
                if initial["p"] & 0x08 and not initial["p"] & 0x20:
                    operand = [c for c in case["cycles"] if c[2] == "r"][-1][1]
                    yield operation, initial["a"], operand, initial["p"], final["a"], final["p"]


def check(formula: str, rows) -> int:
    count = wrong = 0
    for operation, a, operand, p, want_a, want_p in rows:
        count += 1
        if operation(a, operand, p, formula) != (want_a, want_p):
            wrong += 1
            if wrong <= 5:
                print(f"  {operation.__name__} A={a:02X} M={operand:02X} P={p:02X}: "
                      f"recorded {want_a:02X} {want_p:02X}")  # fmt: skip
    print(f"{formula}: {count:,} recorded, {wrong:,} differ")
    return wrong


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--out", type=Path, help="where the HuCard and trace go (default: a temp dir)"
    )
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as temp:
        out = (args.out or Path(temp)).resolve()
        out.mkdir(parents=True, exist_ok=True)
        wrong = check("mesen", mesen_rows()) + check("mednafen", mednafen_rows(out))
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
