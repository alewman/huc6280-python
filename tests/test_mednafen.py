"""Rung 4b: Mednafen 1.32.1 as a third emulator-tier vote (docs/mednafen-oracle.md).

Two checks. The core's decimal ``ADC`` and ``SBC`` (C13, docs/issues/0004) against **recorded
result tables**: a SHA-256 over the result and P of all 131,072 inputs per operation, for the
default formula (the results of Mednafen's HuC6280) and for ``"mesen"`` (Mesen's). The digests were
recorded on 2026-11-10 from implementations that had been compared with each emulator's source
over every input; no emulator code is kept here, only what it computes (and, where the Rockwell
corpus is fetched, that chip's own results). And the first part of each trace made with
``scripts/mednafen_trace.py`` replays on the core with no register divergence beyond line 0, the
reset S, and with the core's own A, X, Y after block transfers (C14). Skipped without traces.
"""

import hashlib
from pathlib import Path

import pytest
from mame_replay import replay
from rockwell import corpus_present, load_cases

from huc6280._alu import add, subtract

N, V, Z, C, D = 0x80, 0x40, 0x02, 0x01, 0x08

TRACES = Path(__file__).resolve().parent / "mednafen_traces"
GAMES = sorted(p for p in TRACES.glob("*") if (p / "error.log").is_file())

# SHA-256 of bytes(result, P) for A in 0..255, operand in 0..255, C in 0, 1 (P in = D | V | C).
TABLES = {
    ("mednafen", "adc"): "8cab5bb9f099d03a303693c068cb6da02a28bcb380b65bacec2de6e34952f74d",
    ("mednafen", "sbc"): "a7c9d521dc69b9c1235a055e12a5cb2c087ddfae08f82d39000b1fe464e5d2bc",
    ("mesen", "adc"): "49349cc23fb154f38820c2a25ff84589b1398c6a6138e470e44fb552284fe68e",
    ("mesen", "sbc"): "2dbad136c84387771f349b8f87f38199e8c5ffcfab69dbba11b59a7ef20d1185",
}
OPERATIONS = {"adc": add, "sbc": subtract}


def valid(a: int, x: int) -> bool:
    return all(digit < 10 for digit in (a & 15, a >> 4, x & 15, x >> 4))


@pytest.mark.parametrize(("formula", "name"), sorted(TABLES))
def test_the_decimal_results_are_the_recorded_table_in_every_combination(formula, name) -> None:
    digest = hashlib.sha256()
    for a in range(256):
        for x in range(256):
            for carry in (0, 1):
                result, p = OPERATIONS[name](a, x, D | V | carry, formula)
                assert p & V  # decimal leaves V alone
                assert bool(p & Z) == (result == 0) and bool(p & N) == bool(result & 0x80)
                digest.update(bytes((result, p)))
    assert digest.hexdigest() == TABLES[formula, name]


def test_the_examples_of_issue_0004() -> None:
    """The stated cases: what each emulator answers for an invalid digit."""
    assert subtract(0x00, 0x0A, D)[0] == 0x8F and subtract(0x00, 0x0A, D, "mesen")[0] == 0x9F
    assert add(0x0A, 0x0F, D | C)[0] == 0x20 and add(0x0A, 0x0F, D | C, "mesen")[0] == 0x10
    assert add(0x19, 0x28, D | C) == add(0x19, 0x28, D | C, "mesen") == (0x48, D)  # valid digits


def test_mesen_mode_differs_from_the_default_only_with_an_invalid_digit() -> None:
    different = {"adc": 0, "sbc": 0, "adc_c": 0}
    for a in range(256):
        for x in range(256):
            for carry in (0, 1):
                for name, operation in OPERATIONS.items():
                    result, p = operation(a, x, D | carry, "mesen")
                    want, want_p = operation(a, x, D | carry)
                    if (result, p & C) != (want, want_p & C):
                        assert not valid(a, x), (name, a, x, carry)
                    if result != want:
                        different[name] += 1
                    if name == "adc" and p & C != want_p & C:
                        different["adc_c"] += 1
    assert different == {"adc": 9216, "sbc": 9216, "adc_c": 324}


@pytest.mark.skipif(not corpus_present(), reason="rockwell65c02 not fetched")
def test_the_default_decimal_sbc_is_the_rockwell_chips() -> None:
    cases = [c for c in load_cases(0xE9) if c["initial"]["p"] & 8]
    for case in cases:
        initial, final = case["initial"], case["final"]
        x = dict(initial["ram"])[initial["pc"] + 1]
        result, p = subtract(initial["a"], x, 0x08 | initial["p"] & 1)
        assert (result, p & 1) == (final["a"], final["p"] & 1)


@pytest.mark.skipif(not GAMES, reason="no traces: python -I scripts/mednafen_trace.py GAME")
@pytest.mark.parametrize("game", GAMES, ids=lambda path: path.name)
def test_mednafen_trace_replays_with_no_divergence_beyond_reset(game: Path) -> None:
    report = replay(
        (game / "cart.pce").read_bytes(), game / "error.log", 150_000, adopt_block=False
    )
    assert [d.index for d in report.divergences] == [0], report.summary()
    assert set(report.divergences[0].differences) == {"s"}
