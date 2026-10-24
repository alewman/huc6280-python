"""Readability contract for the instruction core, enforced the way correctness is.

Following 65816-python's, 6502-python's and z80-python's tests/test_readability.py:
every opcode handler must be findable by the mnemonic a HuC6280 programmer would
grep for, live in the module that owns its instruction family, and say where its
rule comes from. Checked from the source with :mod:`ast`, without importing it:

1. Every ``_op_*`` method's docstring headline is ``MNEMONIC[ form] -- text
   (SOURCE).`` where SOURCE is ``SW SB-n``, the page of Hudson's software manual
   that describes the instruction (tests/manual.py), or ``HW HB-25`` for ``CSL``
   and ``CSH`` (the hardware manual's instruction map).
2. The page is the right one, as the manual prints it.
3. The handler lives in the module that owns that mnemonic and is named after it,
   and every mnemonic has a handler.
4. Every opcode's handler exists and takes the mode argument exactly when the
   table says it has one.
"""

import ast
import inspect
import re
from pathlib import Path

import pytest
from manual import ROWS

from huc6280._dispatch import OPCODES
from huc6280.cpu import HuC6280

SRC = Path(__file__).resolve().parents[1] / "src" / "huc6280"

#: SW's page of each mnemonic (tests/manual.py), the family names without the bit number.
PAGES = {mnemonic: page for mnemonic, _mode, _code, _size, _cycles, page in ROWS}
OWNERS: dict[str, frozenset[str]] = {
    module: frozenset(mnemonics.split())
    for module, mnemonics in {
        "_alu.py": "ADC SBC AND ORA EOR CMP CPX CPY BIT",
        "_loads.py": "LDA LDX LDY STA STX STY STZ TAX TAY TXA TYA TSX TXS INX INY DEX DEY",
        "_shifts.py": "ASL LSR ROL ROR INC DEC",
        "_bits.py": "RMB SMB BBR BBS TSB TRB",
        "_block.py": "TII TDD TIN TIA TAI",
        "_hudson.py": "SXY SAX SAY CLA CLX CLY ST0 ST1 ST2 TMA TAM CSL CSH SET TST",
        "_control.py": "BPL BMI BVC BVS BCC BCS BNE BEQ BRA JMP JSR BSR RTS RTI PHA PHX PHY PHP "
        "PLA PLX PLY PLP CLC SEC CLD SED CLV CLI SEI NOP BRK",
    }.items()
}
HEADLINE = re.compile(r"^(?P<mnemonic>[A-Z][A-Z0-9]{2})(?P<form>[^-]*?) -- (?P<text>.+)$")
CITATION = re.compile(r"\((?P<source>SW SB-(?P<page>\d+)|HW HB-25[^)]*)\)\.$")
BIT_FAMILIES = ("BBR", "BBS", "RMB", "SMB", "TMA", "TAM")


def family(mnemonic: str) -> str:
    """The mnemonic without a bit number or the docs' trailing ``i`` (BBR0, BBRi -> BBR)."""
    return mnemonic[:3] if mnemonic[:3] in BIT_FAMILIES else mnemonic


def handlers() -> list[tuple[str, ast.FunctionDef]]:
    found = []
    for path in sorted(SRC.glob("_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for cls in (node for node in tree.body if isinstance(node, ast.ClassDef)):
            found += [
                (path.name, node)
                for node in cls.body
                if isinstance(node, ast.FunctionDef) and node.name.startswith("_op_")
            ]
    assert found
    return found


HANDLERS = handlers()


def headline(node: ast.FunctionDef) -> str:
    docstring = ast.get_docstring(node) or ""
    return " ".join(docstring.split("\n\n")[0].split())


@pytest.mark.parametrize(("module", "node"), HANDLERS, ids=[node.name for _, node in HANDLERS])
def test_handler_headline_names_mnemonic_and_cites_its_page(
    module: str, node: ast.FunctionDef
) -> None:
    line = headline(node)
    match = HEADLINE.match(line)
    assert match, f"{node.name}: headline must read 'MNEMONIC -- text (SOURCE).', got {line!r}"
    mnemonic = family(match["mnemonic"])
    citation = CITATION.search(line)
    assert citation, f"{node.name}: headline must end with (SW SB-n). or (HW HB-25...)."
    if mnemonic in ("CSL", "CSH"):
        assert citation["source"].startswith("HW HB-25")
    else:
        assert f"SB-{citation['page']}" == PAGES[mnemonic], (
            f"{node.name}: {mnemonic} is on SW {PAGES[mnemonic]}"
        )


@pytest.mark.parametrize(("module", "node"), HANDLERS, ids=[node.name for _, node in HANDLERS])
def test_handler_lives_in_its_module_and_is_named_after_its_mnemonic(
    module: str, node: ast.FunctionDef
) -> None:
    group = family(HEADLINE.match(headline(node))["mnemonic"])
    assert group in OWNERS[module], f"{node.name}: {group} belongs elsewhere"
    assert node.name.removeprefix("_op_").split("_")[0] == group.lower()


def test_every_mnemonic_has_a_handler_and_no_handler_is_defined_twice() -> None:
    names = [node.name for _, node in HANDLERS]
    assert len(names) == len(set(names)), "a duplicate would be shadowed by the MRO"
    claimed = {family(HEADLINE.match(headline(node))["mnemonic"]) for _, node in HANDLERS}
    defined = {family(OPCODES[opcode][2]) for opcode in range(256)}
    assert claimed == defined, claimed ^ defined
    assert set().union(*OWNERS.values()) == defined


@pytest.mark.parametrize("opcode", range(256), ids=lambda opcode: f"{opcode:02x}")
def test_every_opcode_has_a_handler_that_takes_its_mode(opcode: int) -> None:
    handler, mode, *_ = OPCODES[opcode]
    function = getattr(HuC6280, f"_op_{handler}")
    parameters = list(inspect.signature(function).parameters)
    assert parameters == (["self"] if mode is None else ["self", "mode"]), (handler, mode)
    if mode is not None:
        assert callable(getattr(HuC6280, f"_ea_{mode}"))
