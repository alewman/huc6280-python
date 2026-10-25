"""Rung 4b: Mednafen 1.32.1 as a third emulator-tier vote (docs/mednafen-oracle.md).

Two checks. The decimal ADC/SBC macros of ``src/pce/huc6280.cpp`` (transcribed below; read from the
source, not run) are compared with the core and, where the Rockwell corpus is fetched, with that
chip's results: this pins C13's finding. And the first part of each trace made with
``scripts/mednafen_trace.py`` replays on the core with no register divergence beyond line 0, the
reset S, and with the core's own A, X, Y after block transfers (C14). Skipped without traces.
"""

from pathlib import Path

import pytest
from mame_replay import replay
from rockwell import corpus_present, load_cases

from huc6280._alu import add, subtract

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


def test_mednafen_and_the_core_agree_on_decimal_with_valid_digits_only() -> None:
    different = {"adc": 0, "sbc": 0}
    for a in range(256):
        for x in range(256):
            for carry in (0, 1):
                for name, ours, theirs in (
                    ("adc", add, mednafen_adc),
                    ("sbc", subtract, mednafen_sbc),
                ):
                    result, p = ours(a, x, 0x08 | carry)
                    if (result, p & 1) != theirs(a, x, carry):
                        different[name] += 1
                        assert not valid(a, x), (name, a, x, carry)
    assert different == {"adc": 9216, "sbc": 9216}


@pytest.mark.skipif(not corpus_present(), reason="rockwell65c02 not fetched")
def test_mednafens_decimal_sbc_is_the_rockwell_chips_and_the_cores_is_not() -> None:
    cases = [c for c in load_cases(0xE9) if c["initial"]["p"] & 8]
    for case in cases:
        initial, final = case["initial"], case["final"]
        x = dict(initial["ram"])[initial["pc"] + 1]
        result, carry = mednafen_sbc(initial["a"], x, initial["p"] & 1)
        assert (result, carry) == (final["a"], final["p"] & 1)


@pytest.mark.skipif(not GAMES, reason="no traces: python -I scripts/mednafen_trace.py GAME")
@pytest.mark.parametrize("game", GAMES, ids=lambda path: path.name)
def test_mednafen_trace_replays_with_no_divergence_beyond_reset(game: Path) -> None:
    report = replay(
        (game / "cart.pce").read_bytes(), game / "error.log", 150_000, adopt_block=False
    )
    assert [d.index for d in report.divergences] == [0], report.summary()
    assert set(report.divergences[0].differences) == {"s"}
