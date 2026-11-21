"""Rung 0: the core's opcode map is Hudson's software manual's (SW, tests/manual.py).

``tests/manual.py`` transcribes the manual's instruction pages; every opcode
the manual defines must have, in ``huc6280._dispatch.OPCODES``, the same
mnemonic, an addressing mode that means the same, the same byte count and the
same base cycle count. The 22 opcodes the manual does not define are the
two-cycle one-byte ``NOP``s pcetech tested (U3). The exceptions are the
documented contradictions: ``BRK`` is two bytes (C2).
"""

import importlib.util
import sys
from pathlib import Path

import pytest
from manual import by_opcode

from huc6280._dispatch import FORM_BYTES, OPCODES

ROOT = Path(__file__).resolve().parents[1]

#: The manual's addressing-mode abbreviation and the core's operand form.
FORMS = {
    "IMM": "imm", "ZP": "zp", "ZP,X": "zpx", "ZP,Y": "zpy", "ABS": "abs", "ABS,X": "abx",
    "ABS,Y": "aby", "(IND)": "zpind", "(IND,X)": "idx", "(IND),Y": "idy", "(ABS)": "ind",
    "(ABS,X)": "abxind", "REL": "rel", "ZP,REL": "zprel", "BLOCK": "block",
    "IMM ZP": "imzp", "IMM ZP,X": "imzpx", "IMM ABS": "imabs", "IMM ABS,X": "imabsx",
    "ACC": "imp", "IMPLID": "imp",
}  # fmt: skip
MANUAL = by_opcode()
#: C2: the manual's table says one byte; its own text, pcetech and every emulator, two.
BYTE_EXCEPTIONS = {0x00}
#: TMA and TAM are IMPLID in the manual but carry a one-byte mask.
MASK_OPERAND = {0x43, 0x53}


def test_the_manual_defines_234_opcodes() -> None:
    """HW HB-1: 234 defined opcodes (SW's pages give 232; HW's map adds CSL and CSH)."""
    assert len(MANUAL) == 234
    assert sum(1 for row in MANUAL.values() if row[4].startswith("HW")) == 2


@pytest.mark.parametrize("opcode", sorted(MANUAL), ids=lambda opcode: f"{opcode:02x}")
def test_opcode_is_the_manuals(opcode: int) -> None:
    mnemonic, mode, size, cycles, _page = MANUAL[opcode]
    handler, _ea, core_mnemonic, form, core_cycles = OPCODES[opcode]
    assert core_mnemonic == mnemonic
    expected_form = "imm" if opcode in MASK_OPERAND else FORMS[mode]
    if opcode == 0x00:
        expected_form = "imm"  # the signature byte
    assert form == expected_form, (form, mode)
    if mode == "ACC":
        assert handler.endswith("_a")
    if opcode not in BYTE_EXCEPTIONS:
        assert FORM_BYTES[form] == size
    else:
        assert FORM_BYTES[form] == size + 1
    assert core_cycles == cycles


def test_the_undefined_opcodes_are_one_byte_two_cycle_nops() -> None:
    undefined = sorted(set(range(256)) - set(MANUAL))
    assert len(undefined) == 256 - len(MANUAL)
    for opcode in undefined:
        row = OPCODES[opcode]
        assert row == ("nop", None, "NOP", "imp", 2), opcode
    # pcetech 2.0 tested these 22 (U3); the 23rd NOP slot is the documented $EA.
    assert undefined == sorted(
        [0x0B, 0x1B, 0x2B, 0x33, 0x3B, 0x4B, 0x5B, 0x5C, 0x63, 0x6B, 0x7B, 0x8B, 0x9B, 0xAB,
         0xBB, 0xCB, 0xDB, 0xDC, 0xE2, 0xEB, 0xFB, 0xFC]
    )  # fmt: skip


def test_manual_transcription_agrees_with_the_scans_own_text() -> None:
    """The OCR text layer, where a row reads cleanly, says what tests/manual.py says."""
    pdf = ROOT / "reference" / "docs" / "huc6280-software-manual.pdf"
    if not pdf.is_file():
        pytest.skip("manual not fetched: python -I scripts/fetch_references.py")
    spec = importlib.util.spec_from_file_location(
        "manual_table", ROOT / "scripts" / "manual_table.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        spec.loader.exec_module(module)
        read = module.rows()
    except (FileNotFoundError, OSError):
        pytest.skip("pdftotext not available")
    finally:
        sys.path.remove(str(ROOT / "scripts"))
    # The scan's hex digits are damaged in places ($4D read as $40, $6D as $60, $B0 as $80,
    # $8D as $80) and BRK's byte count is C2; every other row it read agrees.
    known = {0x00, 0x40, 0x60, 0x80, 0x90, 0x70, 0x50}
    checked = 0
    for opcode, (size, cycles, line) in read.items():
        if opcode in known or opcode not in MANUAL:
            continue
        _mnemonic, _mode, want_size, want_cycles, _page = MANUAL[opcode]
        assert (size, cycles) == (want_size, want_cycles), (opcode, line)
        checked += 1
    assert checked > 90
