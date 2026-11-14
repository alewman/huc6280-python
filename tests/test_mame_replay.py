"""Rung 4: the first part of each recorded MAME trace replays with no register divergence.

``scripts/mame_trace.py GAME --io`` makes the traces (tests/mame_traces/, gitignored; docs/
mame-oracle.md); the whole of each is ``scripts/mame_replay.py``. Skipped when none exist.
"""

from pathlib import Path

import pytest
from mame_replay import Line, Replay, Report, _take_interrupt, read_log, replay

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


def test_take_interrupt_at_the_handler_already_leaves_no_line_asserted() -> None:
    # Issue 0005 item 5: when PC already equals the handler there is no entry to make, and the
    # line the replay would have asserted for it must not stay asserted.
    rom = bytearray(0x2000)
    rom[0x1FFE:0x2000] = bytes([0x00, 0xE0])  # reset -> $E000
    rom[0x1FF8:0x1FFA] = bytes([0x00, 0xE1])  # IRQ1 -> $E100
    harness = Replay(bytes(rom))
    cpu = harness.cpu
    cpu.step()  # the reset sequence
    cpu.pc = 0xE100
    line = Line((0xE100, 0, 0, 0, (cpu.s - 3) & 0xFF, 0x04, *cpu.mpr), 0, ())
    assert _take_interrupt(harness, line, Report()) is None
    assert cpu.irq_lines == (False, False, False)


@pytest.mark.skipif(not GAMES, reason="no MAME traces: python -I scripts/mame_trace.py GAME --io")
@pytest.mark.parametrize("game", GAMES, ids=lambda path: path.name)
def test_trace_replays_without_divergence(game: Path) -> None:
    report = replay((game / "cart.pce").read_bytes(), game / "error.log", LIMIT)
    assert not report.divergences, report.summary()
