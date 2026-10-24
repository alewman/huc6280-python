"""Rung 4: the first part of each recorded MAME trace replays with no register divergence.

``scripts/mame_trace.py GAME --io`` makes the traces (tests/mame_traces/, gitignored; docs/
mame-oracle.md); the whole of each is ``scripts/mame_replay.py``. Skipped when none exist.
"""

from pathlib import Path

import pytest
from mame_replay import Line, read_log, replay

TRACES = Path(__file__).resolve().parent / "mame_traces"
GAMES = sorted(
    p for p in TRACES.glob("*") if (p / "error.log").is_file() and (p / "cart.pce").is_file()
)
LIMIT = 150_000


def test_read_log_pairs_the_two_lines_and_the_reads(tmp_path: Path) -> None:
    log = tmp_path / "error.log"
    log.write_bytes(
        b"\xef\xbb\xbf[:pce_cd:msm5205] /48 prescaler selected\nSoft reset\n"
        b"E000 0 0 0 FF 14 0\nM 0 0 0 0 0 0 0 0\n"
        b"E006 FF 0 0 FF 94 48\nM FF F8 0 0 0 0 0 0\n[luaengine] R 1FF000 3F\n\n"
        b"E009 3F 0 0 FF 14 68\nM FF F8 0 0 0 0 0 0\n"
    )
    lines = list(read_log(log))
    assert lines[0] == Line((0xE000, 0, 0, 0, 0xFF, 0x14, 0, 0, 0, 0, 0, 0, 0, 0), 0, ())
    assert lines[1].cycles == 48  # decimal, the debugger's %d
    assert lines[1].registers[6:8] == (0xFF, 0xF8)
    assert lines[1].reads == ((0x1FF000, 0x3F),)
    assert lines[2].registers[0] == 0xE009


@pytest.mark.skipif(not GAMES, reason="no MAME traces: python -I scripts/mame_trace.py GAME --io")
@pytest.mark.parametrize("game", GAMES, ids=lambda path: path.name)
def test_trace_replays_without_divergence(game: Path) -> None:
    report = replay((game / "cart.pce").read_bytes(), game / "error.log", LIMIT)
    assert not report.divergences, report.summary()
