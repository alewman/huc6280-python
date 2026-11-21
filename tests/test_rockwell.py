"""Rung 1b: SingleStepTests rockwell65c02, semantic; a sample in the quick loop, all under -m slow."""

import pytest
from rockwell import R65C02, SHARED, corpus_present, load_cases, run_case

from huc6280._dispatch import OPCODES

SAMPLE = 100


def test_the_r65c02_opcodes_mean_the_same_in_the_core_table() -> None:
    """The shared set is the Rockwell data sheet's map; the core's table must agree with it."""
    for opcode, text in R65C02.items():
        mnemonic, _, mode = text.partition(" ")
        _handler, _ea, core_mnemonic, form, _cycles = OPCODES[opcode]
        assert core_mnemonic == mnemonic, (opcode, text)
        if mode == "A":
            assert OPCODES[opcode][0].endswith("_a")
        elif mode:
            assert form == mode, (opcode, text, form)


pytestmark_corpus = pytest.mark.skipif(not corpus_present(), reason="rockwell65c02 not fetched")


def run_opcode(opcode: int, limit: int | None) -> None:
    failures = []
    for case in load_cases(opcode)[:limit]:
        problems, _masks = run_case(case)
        if problems:
            failures.append(f"{case['name']}: {problems[:3]}")
    assert not failures, f"{len(failures)} failing, first: {failures[:3]}"


@pytestmark_corpus
@pytest.mark.parametrize("opcode", sorted(SHARED), ids=lambda opcode: f"{opcode:02x}")
def test_opcode_sample(opcode: int) -> None:
    run_opcode(opcode, SAMPLE)


@pytestmark_corpus
@pytest.mark.slow
@pytest.mark.parametrize("opcode", sorted(SHARED), ids=lambda opcode: f"{opcode:02x}")
def test_opcode_whole(opcode: int) -> None:
    run_opcode(opcode, None)
