# SPDX-License-Identifier: MIT
"""Directed card for docs/mednafen-oracle.md's votes: single instructions on the traced Mednafen.

    python -I validation/mednafen_votes.py [--out DIR]

Mednafen 1.32.1 (scripts/mednafen_trace.py) is run as a closed box. The trace gives the state
before each instruction, so each probe's result is the next line's registers. Probes: C6 ``TMA
#$0C`` with MPR2 = $81 and MPR3 = $42; C12 ``TSB`` of $0F with A = $F0 and ``TRB`` of $0F with
A = $0F; C5 ``SET; SBC #$01`` with A = $10 and M($2020) = $05; C4 opcode ``$63``'s length and
time; C9 ``TII $1000,$2030,1`` (a block read of the I/O port) against a plain ``LDA $1000``.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from itertools import pairwise
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = bytes.fromhex(
    "78 D4 A9FF5301 A9F85302 A9815304 A9425308"  # E000 SEI CSH; MPR0 $FF, MPR1 $F8, 2 $81, 3 $42
    "430C"  # E012 TMA #$0C
    "A90F8D1020 A9F00C1020"  # E014 M($2010) = $0F; E019 LDA #$F0; E01B TSB $2010
    "A90F8D1120 A90F1C1120"  # E01E M($2011) = $0F; E023 LDA #$0F; E025 TRB $2011
    "A220 A9058D2020 A910 38 F4 E901"  # X = $20, M($2020) = 5, A = $10, SEC, SET; E033 SBC #$01
    "63 EA"  # E035 $63; E036 NOP
    "73 0010 3020 0100"  # E037 TII $1000,$2030,1
    "AD3020 AD0010 80FE"  # E03E LDA $2030; E041 LDA $1000; E044 BRA *
)
SITES = {0xE012: "C6 TMA #$0C", 0xE01B: "C12 TSB", 0xE025: "C12 TRB", 0xE033: "C5 SBC with T",
         0xE035: "C4 $63", 0xE03E: "C9 the block-read byte", 0xE041: "C9 a plain read"}  # fmt: skip


def rom() -> bytes:
    image = bytearray(b"\xff" * 8192)
    image[: len(CODE)] = CODE
    for vector in range(0x1FF6, 0x2000, 2):
        image[vector : vector + 2] = b"\x00\xe0"
    return bytes(image)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as temp:
        out = (args.out or Path(temp)).resolve()
        out.mkdir(parents=True, exist_ok=True)
        (out / "votes.pce").write_bytes(rom())
        subprocess.run(
            [sys.executable, "-I", str(ROOT / "scripts" / "mednafen_trace.py"),
             str(out / "votes.pce"), "--count", "40", "--out", str(out / "trace")],
            check=True, stdout=subprocess.DEVNULL,
        )  # fmt: skip
        lines = [
            line.split()
            for line in (out / "trace" / "error.log").read_text().splitlines()
            if line and not line.startswith(("M ", "["))
        ]
    for here, after in pairwise(lines):
        name = SITES.get(int(here[0], 16))
        if name:
            pc, a, p, cycles = (
                int(after[0], 16),
                int(after[1], 16),
                int(after[5], 16),
                int(after[6]),
            )
            length = pc - int(here[0], 16)
            print(f"{name:24} then A=${a:02X} P=${p:02X} Z={p >> 1 & 1}; "
                  f"{length} bytes, {cycles - int(here[6])} units")  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
