"""Rung 5: srg320's HUC6280_CPU under GHDL agrees with the core on what is written and read.

The HDL is emulator tier (hand-written, FPGA-proven; docs/validation.md), a third opinion. What the
sample pins is where the three sources (core, SingleStepTests, HDL) agree and the only places the
HDL stands alone in the bytes that cross the bus: the count, the writes and the data reads of every
opcode but ``SBC abs`` in decimal mode (one cycle more in the HDL), ``BRK`` with T set (the HDL
pushes T, the corpus and the core push 0) and ``BBR``/``BBS`` (the HDL reads the zero-page byte
before the offset). The place of the internal cycles differs in many opcodes (C8) and is reported
by ``scripts/run_vhdl.py``, not asserted. Skipped when the testbench is not built.
"""

import pytest
from huc6280_vhdl import (
    BUILD_HINT,
    TESTBENCH,
    differences,
    next_fetch_matches,
    run_core,
    run_corpus,
    run_testbench,
    vote,
)
from single_step import corpus_present, load_cases

pytestmark = [
    pytest.mark.skipif(not TESTBENCH.exists(), reason=BUILD_HINT),
    pytest.mark.skipif(not corpus_present(), reason="SingleStepTests huc6280 not fetched"),
]

CASES = 12
BLOCKS = {0x73, 0xC3, 0xD3, 0xE3, 0xF3}
#: opcode: the categories (count, writes, reads) in which the HDL alone may differ
HDL_ALONE = {
    0xED: {"count"},
    0x00: {"writes"},
    **{op: {"reads"} for op in range(0x0F, 0x100, 0x10)},
}
CORPUS_ALONE = {0x03, 0x13, 0x23}  # the corpus's internal cycle where core and HDL write (C1)


@pytest.mark.parametrize("opcode", range(256), ids=lambda opcode: f"{opcode:02x}")
def test_hdl_and_core_move_the_same_bytes(opcode: int) -> None:
    limit = 3 if opcode in BLOCKS else CASES
    cases = []
    for number, case in enumerate(load_cases(opcode)):
        if number >= limit:
            break
        cases.append(case)
    allowed = HDL_ALONE.get(opcode, set())
    for case, hdl in zip(cases, run_testbench(cases), strict=True):
        if (
            hdl is None
            or hdl[0].address
            != case["initial"]["mpr"][case["initial"]["pc"] >> 13] << 13
            | case["initial"]["pc"] & 0x1FFF
        ):
            continue  # no loader address clear of the case, or a desynchronised start: not run
        core, corpus = run_core(case), run_corpus(case)
        if case["num_cycles"] != len(case["cycles"]):
            core = core[: len(corpus)]
        sides = vote(core, hdl[: len(core)], corpus)
        if not next_fetch_matches(case, hdl):
            sides["count"] = "HDL alone"
        for category in ("count", "writes", "reads"):
            side = sides.get(category)
            if side is None:
                continue
            if side == "HDL alone":
                assert category in allowed, (case["name"], category)
            elif side == "corpus alone":
                assert opcode in CORPUS_ALONE and category == "writes", (case["name"], category)
            else:
                pytest.fail(f"{case['name']}: {category} {side}")
    assert differences([], []) == set()
