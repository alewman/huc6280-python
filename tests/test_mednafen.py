"""Rung 4b: Mednafen 1.32.1 as a third emulator-tier vote (docs/mednafen-oracle.md).

Two checks. The decimal ADC/SBC macros of ``src/pce/huc6280.cpp`` (transcribed below; read from the
source, not run) are the independent reference the core's default decimal formula is checked
against over all 131,072 inputs (C13, docs/issues/0004), and, where the Rockwell corpus is fetched,
with that chip's results. And the first part of each trace made with
``scripts/mednafen_trace.py`` replays on the core with no register divergence beyond line 0, the
reset S, and with the core's own A, X, Y after block transfers (C14). Skipped without traces.
"""

from pathlib import Path

import pytest
from mame_replay import replay
from rockwell import corpus_present, load_cases

from huc6280._alu import add, subtract

N, V, Z, C = 0x80, 0x40, 0x02, 0x01

TRACES = Path(__file__).resolve().parent / "mednafen_traces"
GAMES = sorted(p for p in TRACES.glob("*") if (p / "error.log").is_file())


def mednafen_adc(a: int, x: int, carry: int) -> tuple[int, int]:
    """Mednafen's decimal ADC (huc6280.cpp, macro ADC): (result, carry)."""
    tmp = (a & 0x0F) + (x & 0x0F) + carry
    if tmp >= 0x0A:
        tmp += 0x06
    tmp += (a & 0xF0) + (x & 0xF0)
    if tmp >= 0xA0:
        tmp += 0x60
    return tmp & 0xFF, int(bool(tmp & 0xFF00))


def mednafen_sbc(a: int, x: int, carry: int) -> tuple[int, int]:
    """Mednafen's decimal SBC (macro SBC): (result, carry)."""
    m = ((a & 0xF) - (x & 0xF) - (carry ^ 1)) & 0xFF
    n = ((a >> 4) - (x >> 4) - ((m >> 4) & 1)) & 0xFF
    result = ((n << 4) | (m & 0xF)) & 0xFF
    if m & 0x10:
        result = (result - 0x06) & 0xFF
    if n & 0x10:
        result = (result - 0x60) & 0xFF
    return result, ((n >> 4) & 1) ^ 1


def valid(a: int, x: int) -> bool:
    return all(digit < 10 for digit in (a & 15, a >> 4, x & 15, x >> 4))


def test_the_default_formula_is_mednafens_in_every_a_operand_carry_combination() -> None:
    """All 131,072 combinations of A, operand and C, the core's default against the transcription."""
    for a in range(256):
        for x in range(256):
            for carry in (0, 1):
                for ours, theirs in ((add, mednafen_adc), (subtract, mednafen_sbc)):
                    p_in = 0x08 | V | carry  # V set going in: decimal leaves it alone
                    result, p = ours(a, x, p_in)
                    want, want_carry = theirs(a, x, carry)
                    assert (result, p & C) == (want, want_carry), (ours.__name__, a, x, carry)
                    assert p & V and bool(p & Z) == (want == 0) and bool(p & N) == bool(want & 0x80)


def test_mesen_mode_differs_from_mednafens_only_with_an_invalid_digit() -> None:
    different = {"adc": 0, "sbc": 0, "adc_c": 0}
    for a in range(256):
        for x in range(256):
            for carry in (0, 1):
                for name, ours, theirs in (
                    ("adc", add, mednafen_adc),
                    ("sbc", subtract, mednafen_sbc),
                ):
                    result, p = ours(a, x, 0x08 | carry, "mesen")
                    if (result, p & C) != theirs(a, x, carry):
                        assert not valid(a, x), (name, a, x, carry)
                    if result != theirs(a, x, carry)[0]:
                        different[name] += 1
                    if name == "adc" and p & C != theirs(a, x, carry)[1]:
                        different["adc_c"] += 1
    assert different == {"adc": 9216, "sbc": 9216, "adc_c": 324}


@pytest.mark.skipif(not corpus_present(), reason="rockwell65c02 not fetched")
def test_mednafens_decimal_sbc_is_the_rockwell_chips_and_so_is_the_cores_default() -> None:
    cases = [c for c in load_cases(0xE9) if c["initial"]["p"] & 8]
    for case in cases:
        initial, final = case["initial"], case["final"]
        x = dict(initial["ram"])[initial["pc"] + 1]
        want = (final["a"], final["p"] & 1)
        assert mednafen_sbc(initial["a"], x, initial["p"] & 1) == want
        result, p = subtract(initial["a"], x, 0x08 | initial["p"] & 1)
        assert (result, p & 1) == want


@pytest.mark.skipif(not GAMES, reason="no traces: python -I scripts/mednafen_trace.py GAME")
@pytest.mark.parametrize("game", GAMES, ids=lambda path: path.name)
def test_mednafen_trace_replays_with_no_divergence_beyond_reset(game: Path) -> None:
    report = replay(
        (game / "cart.pce").read_bytes(), game / "error.log", 150_000, adopt_block=False
    )
    assert [d.index for d in report.divergences] == [0], report.summary()
    assert set(report.divergences[0].differences) == {"s"}
