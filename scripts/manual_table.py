"""Read per-opcode bytes and cycles out of Hudson's software manual and compare them.

    python -I scripts/manual_table.py            # disagreements and what could not be read
    python -I scripts/manual_table.py --all      # every opcode the OCR text yielded

The manual (``reference/docs/huc6280-software-manual.pdf``) is a scan; its text
layer (``pdftotext -layout``) is noisy. A row is taken when it has an addressing
mode column, a machine-code field that starts with two hex digits, and ends
with two integers (bytes, cycles). Opcodes of the ``SMBi``/``RMBi``/``BBRi``/
``BBSi``/``TMAi``/``TAMi`` families are written ``10i + 87`` in the manual and
expanded here. Whatever the OCR garbled is reported as unread, never guessed.
Compared with ``compare_cycles.sst()`` (the smallest cycle count over the
corpus) and Geargrafx's sizes.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_cycles import ROOT, SRC, sst, table

PDF = ROOT / "reference" / "docs" / "huc6280-software-manual.pdf"
ROW = re.compile(
    r"^\s*(?P<mode>[A-Z(][A-Z ,()]*?)\s{2,}\S*\s*(?P<mnem>[A-Za-z0-9~' .\-_]+?)\s{2,}"
    r"(?P<code>[0-9A-Fa-f]{2}(?:\s*[,+].*?)?)\s+(?P<bytes>\d)\s+(?P<cycles>\d{1,2})\s*$"
)


def rows() -> dict[int, tuple[int, int, str]]:
    text = subprocess.run(
        ["pdftotext", "-layout", str(PDF), "-"], capture_output=True, text=True, check=True
    ).stdout
    found: dict[int, tuple[int, int, str]] = {}
    for line in text.splitlines():
        match = ROW.match(line)
        if not match:
            continue
        opcode = int(match["code"][:2], 16)
        found.setdefault(opcode, (int(match["bytes"]), int(match["cycles"]), line.strip()))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    manual = rows()
    sizes = table(SRC / "Geargrafx/src/huc6280_timing.h", "k_huc6280_opcode_sizes")
    cycles = sst()
    agree = differ = 0
    for opcode in sorted(manual):
        size, cyc, line = manual[opcode]
        ok = size == sizes[opcode] and cyc == cycles[opcode]
        agree += ok
        differ += not ok
        if args.all or not ok:
            print(f"{opcode:02X}  manual {size}b/{cyc}c  emulators {sizes[opcode]}b/{cycles[opcode]}c"
                  f"{'' if ok else '  <-'}   | {line[:90]}")  # fmt: skip
    print(f"{len(manual)} opcodes read from the manual: {agree} agree, {differ} differ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
