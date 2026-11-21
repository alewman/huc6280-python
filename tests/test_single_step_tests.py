"""Rung 1: SingleStepTests huc6280, every file, a sample in the quick loop and all of it under -m slow.

The readings and masks (B, the ST0-ST2 write cycle, truncated block transfers, TMA
#$00, C12) are tests/single_step.py's.
"""

import pytest
from single_step import FETCH_HINT, corpus_present, load_cases, run_case

pytestmark = pytest.mark.skipif(not corpus_present(), reason=FETCH_HINT)

SAMPLE = 100
BLOCK_SAMPLE = 5


def run_opcode(opcode: int, limit: int | None) -> None:
    failures = []
    for number, case in enumerate(load_cases(opcode)):
        if limit is not None and number >= limit:
            break
        problems, _masks = run_case(case)
        if problems:
            failures.append(f"{case['name']}: {problems[:4]}")
    assert not failures, f"{len(failures)} failing, first: {failures[:3]}"


@pytest.mark.parametrize("opcode", range(256), ids=lambda opcode: f"{opcode:02x}")
def test_opcode_sample(opcode: int) -> None:
    block = opcode in (0x73, 0xC3, 0xD3, 0xE3, 0xF3)
    run_opcode(opcode, BLOCK_SAMPLE if block else SAMPLE)


@pytest.mark.slow
@pytest.mark.parametrize("opcode", range(256), ids=lambda opcode: f"{opcode:02x}")
def test_opcode_whole(opcode: int) -> None:
    run_opcode(opcode, None)
