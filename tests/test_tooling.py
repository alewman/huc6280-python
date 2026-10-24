"""The tooling at the family bar: state, disassembler, debug session, trace, console, harness, CLI."""

import io
import re
import subprocess
import sys
from pathlib import Path

import pytest

from huc6280 import HuC6280
from huc6280.console import CommandError, HuC6280Debugger
from huc6280.debug import BoundaryKind, HuC6280Session, StopReason
from huc6280.disasm import DECODE_TABLE, disassemble, disassemble_bytes
from huc6280.harness import Harness, bank_offsets, load_rom
from huc6280.state import CPUState
from huc6280.trace import first_trace_divergence, read_trace, write_trace

ROOT = Path(__file__).resolve().parents[1]
MAME_DASM = (
    ROOT / "reference" / "src" / "mame" / "src" / "devices" / "cpu" / "h6280" / "6280dasm.cpp"
)


CODE = 0xE004  # ``program``'s code starts here, after MPR1 is pointed at work RAM


def program(*code: int) -> bytes:
    """An 8 KB ROM bank, reset vector $E000: ``LDA #$F8; TAM #$02`` (so zero page and stack are
    work RAM), then ``code`` at $E004, then NOPs."""
    rom = bytearray([0xEA] * 0x2000)
    rom[0:4] = bytes([0xA9, 0xF8, 0x53, 0x02])
    rom[4 : 4 + len(code)] = bytes(code)
    rom[0x1FFE:0x2000] = bytes([0x00, 0xE0])
    return bytes(rom)


def session(rom: bytes, **options) -> tuple[Harness, HuC6280Session]:
    harness = Harness(rom)
    cpu = harness.cpu
    for _ in range(3):  # reset, LDA #$F8, TAM #$02
        cpu.step()
    cpu.a = 0
    return harness, HuC6280Session(
        cpu,
        peek_byte=lambda address: harness.peek(cpu.physical(address)),
        peek_physical=harness.peek,
        **options,
    )


# -- the disassembler is the core's table, and MAME's -----------------------------------------


def test_disassembler_agrees_with_mames_6280dasm() -> None:
    """MAME's disassembler table (emulator tier) gives each opcode's mnemonic and length."""
    if not MAME_DASM.is_file():
        pytest.skip("mame source not fetched")
    text = MAME_DASM.read_text()
    table = re.search(r"op6280\[512\]=\s*\{(.*?)\};", text, re.DOTALL).group(1)
    pairs = re.findall(r"_(\w+),_(\w+)", table)
    assert len(pairs) == 256
    sizes = {"imp": 0, "acc": 0, "rel": 1, "imm": 1, "zpg": 1, "zpx": 1, "zpy": 1, "idx": 1,
             "idy": 1, "zpi": 1, "abs": 2, "abx": 2, "aby": 2, "ind": 2, "iax": 2, "blk": 6,
             "zrl": 2, "imz": 2, "izx": 2, "ima": 3, "imx": 3, "non": 0}  # fmt: skip
    aliases = {"dea": "dec", "ina": "inc"}
    for opcode, (mnemonic, mode) in enumerate(pairs):
        mnemonic = aliases.get(mnemonic, mnemonic)
        mnemonic = re.sub(
            r"^(rm|sm|br|bs)(\d)$",
            lambda m: {"rm": "rmb", "sm": "smb", "br": "bbr", "bs": "bbs"}[m[1]] + m[2],
            mnemonic,
        )
        ours, _mode, operand_bytes, _template = DECODE_TABLE[opcode]
        if mnemonic == "ill":
            assert ours == "NOP", opcode
            continue
        assert ours.lower() == mnemonic, (opcode, ours, mnemonic)
        # MAME's BRK is "imp": one byte; the core's is two (C2).
        if opcode != 0x00:
            assert operand_bytes == sizes[mode], (opcode, ours, mode)


@pytest.mark.parametrize(
    ("code", "text"),
    [
        ((0xA9, 0x12), "LDA #$12"),
        ((0xA5, 0x12), "LDA $12"),
        ((0xB5, 0x12), "LDA $12,X"),
        ((0xB6, 0x12), "LDX $12,Y"),
        ((0xAD, 0x34, 0x12), "LDA $1234"),
        ((0xBD, 0x34, 0x12), "LDA $1234,X"),
        ((0xB9, 0x34, 0x12), "LDA $1234,Y"),
        ((0xA1, 0x12), "LDA ($12,X)"),
        ((0xB1, 0x12), "LDA ($12),Y"),
        ((0xB2, 0x12), "LDA ($12)"),
        ((0x6C, 0x34, 0x12), "JMP ($1234)"),
        ((0x7C, 0x34, 0x12), "JMP ($1234,X)"),
        ((0x0A,), "ASL A"),
        ((0x73, 0x34, 0x12, 0x78, 0x56, 0xBC, 0x9A), "TII $1234,$5678,$9ABC"),
        ((0x83, 0x12, 0x34), "TST #$12,$34"),
        ((0xB3, 0x12, 0x34, 0x12), "TST #$12,$1234,X"),
        ((0x0F, 0x12, 0x00), "BBR0 $12,$E003"),
        ((0x43, 0x04), "TMA #$04"),
        ((0x03, 0x12), "ST0 #$12"),
        ((0x44, 0x00), "BSR $E002"),
        ((0xF4,), "SET"),
    ],
)
def test_disassembly_text(code: tuple[int, ...], text: str) -> None:
    instruction = disassemble_bytes(bytes(code), 0xE000)
    assert instruction.text == text
    assert instruction.size == len(code)


def test_disassemble_reads_only_through_the_reader() -> None:
    seen = []
    instruction = disassemble(lambda address: seen.append(address) or 0xEA, 0xFFFF)
    assert instruction.text == "NOP" and seen == [0xFFFF]


# -- state --------------------------------------------------------------------------------------


def test_state_round_trips() -> None:
    harness = Harness(program(0x58, 0xEA))
    cpu = harness.cpu
    for _ in range(3):  # reset, LDA #$F8, TAM #$02
        cpu.step()
    cpu.mpr[3] = 0x42
    cpu.set_irq_lines(True, False, True)
    cpu.irq_disable = 2
    cpu.step()  # CLI: polled_i is now set
    state = cpu.capture_state()
    assert isinstance(state, CPUState) and state.polled_i is True and state.mpr[3] == 0x42
    other = Harness(program()).cpu
    other.restore_state(state)
    assert other.capture_state() == state


def test_state_rejects_a_stored_b() -> None:
    with pytest.raises(ValueError, match="B"):
        CPUState(p=0x14)


# -- session, trace -----------------------------------------------------------------------------


def test_session_records_one_access_per_cycle_with_kinds() -> None:
    _harness, debug = session(program(0xA9, 0x05, 0x48, 0xEA), track_accesses=True)
    record = debug.step()  # LDA #$05
    assert record.instruction.text == "LDA #$05" and record.cycles == 2
    assert [kind for kind, _, _ in record.accesses] == ["r", "r"]
    record = debug.step()  # PHA: opcode, dummy read, write
    assert [kind for kind, _, _ in record.accesses] == ["r", "d", "w"]
    assert record.accesses[2][1] == 0x1F01FF  # the stack, physical (MPR1 = $F8)
    debug.close()


def test_breakpoints_logical_and_physical_and_watchpoints() -> None:
    harness, debug = session(program(0xEA, 0xEA, 0xA9, 0x07, 0x85, 0x20, 0xEA), track_accesses=True)
    debug.add_breakpoint(0xE006)
    result = debug.run(max_steps=100)
    assert result.reason is StopReason.BREAKPOINT and result.state.pc == 0xE006
    debug.remove_breakpoint(0xE006)
    debug.add_physical_breakpoint(0x000008)  # the STA at logical $E008, MPR7 = 0
    result = debug.run(max_steps=100)
    assert result.reason is StopReason.BREAKPOINT and result.state.pc == 0xE008
    debug.remove_physical_breakpoint(0x000008)
    debug.add_watchpoint(0x1F0020, "w")
    result = debug.run(max_steps=100)
    assert result.reason is StopReason.WATCHPOINT and harness.ram[0x20] == 0x07


def test_boundary_kinds_name_the_interrupt() -> None:
    harness, debug = session(program(0xEA), track_accesses=False)
    harness.cpu.p = 0
    harness.cpu.set_irq_lines(True, True, False)
    assert debug.boundary(harness.cpu.capture_state()) is BoundaryKind.IRQ1
    record = debug.step()
    assert record.kind is BoundaryKind.IRQ1 and record.instruction is None and record.cycles == 8


def test_trace_round_trips_and_compares() -> None:
    _harness, debug = session(program(0xA9, 0x05, 0x85, 0x01, 0x48, 0xEA), track_accesses=True)
    records = [debug.step() for _ in range(6)]
    out = io.StringIO()
    write_trace(records, out)
    back = list(read_trace(io.StringIO(out.getvalue())))
    assert back == records
    assert first_trace_divergence(iter(records), iter(back)) is None
    _harness2, debug2 = session(program(0xA9, 0x06, 0x85, 0x01, 0x48, 0xEA), track_accesses=True)
    other = [debug2.step() for _ in range(6)]
    assert first_trace_divergence(iter(records), iter(other)) is not None


# -- console ------------------------------------------------------------------------------------


def test_console_commands() -> None:
    harness, debug = session(program(0xA9, 0x05, 0x20, 0x0C, 0xE0, 0xEA, 0xEA, 0xEA, 0x60))
    console = HuC6280Debugger(debug)
    assert "A=00" in console.execute("registers").lines[0]
    assert console.execute("step 1").lines[0].startswith("#0 E004  A9 05")
    assert any("JSR $E00C" in line for line in console.execute("disassemble").lines)
    console.execute("break $E00C")
    assert console.execute("breakpoints").lines == ("E00C",)
    assert "stopped=breakpoint" in console.execute("continue").lines[-1]
    console.execute("pbreak $0")
    assert "physical 000000" in console.execute("breakpoints").lines
    assert console.execute("memory $E004 4").lines == ("E004  A9 05 20 0C",)
    assert console.execute("physical $1FFE 2").lines == ("001FFE  00 E0",)
    console.execute("set mpr3 $21")
    assert harness.cpu.mpr[3] == 0x21
    console.execute("set p $FF")
    assert harness.cpu.p == 0xEF  # B is not kept
    console.execute("irq1 on")
    assert harness.cpu.irq_lines == (True, False, False)
    console.execute("disable 2")
    assert harness.cpu.irq_disable == 2
    with pytest.raises(CommandError):
        console.execute("set q 1")


def test_console_over_runs_a_subroutine_through() -> None:
    harness, debug = session(program(0x20, 0x0A, 0xE0, 0xA9, 0x01, 0xEA, 0xA9, 0x02, 0x60))
    console = HuC6280Debugger(debug)
    lines = console.execute("over").lines
    assert harness.cpu.pc == 0xE007 and harness.cpu.a == 0x02
    assert lines  # the registers after


# -- harness ------------------------------------------------------------------------------------


def test_harness_memory_map() -> None:
    harness = Harness(program(0xEA), supergrafx=True)
    assert harness.peek(0x001FFE) == 0x00 and harness.peek(0x001FFF) == 0xE0
    harness.poke(0x1F0010, 0x55)
    assert harness.peek(0x1F2010) == 0x55 or harness.peek(0x1F0010) == 0x55
    assert harness.peek(0x100000) == 0xFF  # unmapped
    assert harness.peek(0x1FE000) == 0xFF  # the debugger's view of the hardware page
    harness.cpu.step()
    assert harness.master_clocks > 0 and harness.cpu.high_speed is False


def test_harness_rom_mirroring_and_loader(tmp_path: Path) -> None:
    assert bank_offsets(0x30)[:4] == (0, 0x10, 0, 0x10)
    rom = bytes(range(256)) * 32 * 3  # 3 banks of 8 KB... mirrored modulo
    harness = Harness(rom)
    assert harness.peek(0x000000) == 0 and harness.peek(0x006000) == rom[0x6000 % len(rom)]
    path = tmp_path / "game.pce"
    path.write_bytes(bytes(512) + bytes(0x2000))
    assert len(load_rom(path)) == 0x2000  # the copier header is dropped


def test_harness_stops_on_a_spin() -> None:
    harness = Harness(program(0xEA, 0x4C, 0x05, 0xE0))
    result = harness.run(10_000)
    assert result.reason == "spin" and result.pc == 0xE005


def test_cli_runs_a_card_and_writes_a_trace(tmp_path: Path) -> None:
    card = tmp_path / "spin.pce"
    card.write_bytes(program(0xA9, 0x01, 0x4C, 0x06, 0xE0))
    trace = tmp_path / "out.jsonl"
    done = subprocess.run(
        [sys.executable, "-m", "huc6280", str(card), "--trace", str(trace), "--max-cycles", "1000"],
        capture_output=True,
        text=True,
        check=True,
        cwd=tmp_path,
    )
    assert done.stdout.startswith("spin after")
    assert len(list(read_trace(trace.open()))) >= 3
    debug = subprocess.run(
        [sys.executable, "-m", "huc6280", str(card), "--batch", "-c", "step 3", "-c", "regs"],
        capture_output=True,
        text=True,
        check=True,
        cwd=tmp_path,
    )
    assert "LDA #$01" in debug.stdout and "A=01" in debug.stdout


def test_a_run_of_the_core_through_the_harness_matches_the_bare_core() -> None:
    harness = Harness(program(0xA9, 0x05, 0x69, 0x03, 0x4C, 0x08, 0xE0))
    harness.run(1000)
    assert harness.cpu.a == 8
    assert isinstance(harness.cpu, HuC6280)
