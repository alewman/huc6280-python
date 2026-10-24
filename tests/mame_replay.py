"""Rung 4: replay MAME 0.285's trace of a real game through the core.

``scripts/mame_trace.py GAME --io`` leaves an ``error.log`` holding one line per instruction,
before it runs (``PC A X Y S P totalcycles``, then ``M MPR0 ... MPR7``; hex but the cycle count), and after each line the hardware-page reads that
instruction made (``[luaengine] R address value``; docs/mame-oracle.md). :class:`Replay` runs
the core in the minimal harness from the same reset and answers those reads from the log in
order, so the core sees what MAME's board gave MAME's CPU. After every instruction it compares
the registers and the mapping registers with MAME's next line, and the instruction's length in
7.16 MHz cycles with MAME's ``totalcycles`` delta.

MAME is emulator-derived (validation.md): a difference is a lead, never a verdict. What this
replay knows about MAME and adjusts for, each counted:

- **interrupts** come from MAME's board, not the harness's: when MAME's next line is at an
  interrupt vector's target with three bytes more on the stack, the replay asserts that line
  (IRQ2 ``$FFF6``, IRQ1 ``$FFF8``, TIQ ``$FFFA``, NMI ``$FFFC``), steps the entry and lets the
  line go before comparing. If the core's poll would have waited one instruction, the replay
  takes it anyway and counts it (``forced``).
- **B** is MAME's bit 4 in P (it reports a state register that holds B); the core never
  stores it, so it is not compared.
- **reads MAME did not log**: an instruction that reads the hardware page where nothing was
  logged is answered by the harness's stub and then the core takes MAME's registers after it
  (``adopted``), so a wrong guess cannot spread.
- **cycles**: MAME bills a constant per opcode in 7.16 MHz units, 4 per CPU cycle at 1.79
  MHz, 1 at 7.16 MHz, and 1 cycle more for an access to the VDC or VCE. The harness counts the
  same units in ``master_clocks / 3``. Differences are tallied by opcode in the report and
  matched to the C-items in docs/undocumented-behavior.md (C1, C3, C4, C7, C9).
"""

from __future__ import annotations

from collections import Counter, deque
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from huc6280.debug import BoundaryKind, next_boundary
from huc6280.harness import Harness

B_FLAG = 0x10
VECTORS = {"irq2": 0xFFF6, "irq1": 0xFFF8, "tiq": 0xFFFA, "nmi": 0xFFFC}
BLOCK_OPCODES = frozenset((0x73, 0xC3, 0xD3, 0xE3, 0xF3))
REGISTERS = ("pc", "a", "x", "y", "s", "p")


@dataclass(frozen=True, slots=True)
class Line:
    """One instruction of MAME's trace: the registers before it, the 7.16 MHz cycle count
    before it, and the hardware-page reads it made."""

    registers: tuple[int, ...]  # pc a x y s p, then MPR0-7
    cycles: int
    reads: tuple[tuple[int, int], ...]


def read_log(path: Path) -> Iterator[Line]:
    """MAME's trace lines with their reads, lazily, from an ``error.log``.

    Each instruction is two lines (``PC A X Y S P totalcycles`` and ``M MPR0 ... MPR7``,
    all hex but the last), then the hardware-page reads it made.
    """
    registers: tuple[int, ...] | None = None
    cycles = 0
    reads: list[tuple[int, int]] = []
    head: tuple[int, ...] | None = None
    with path.open("rb") as log:
        for raw in log:
            fields = raw.split()
            if len(fields) == 4 and fields[0] == b"[luaengine]" and fields[1] == b"R":
                reads.append((int(fields[2], 16), int(fields[3], 16)))
            elif len(fields) == 9 and fields[0] == b"M" and head is not None:
                try:
                    mpr = tuple(int(f, 16) for f in fields[1:])
                except ValueError:
                    continue
                if registers is not None:
                    yield Line(registers, cycles, tuple(reads))
                registers, cycles, reads = (*head[:6], *mpr), head[6], []
                head = None
            elif len(fields) == 7 and not raw.startswith(b"["):
                try:
                    head = (*(int(f, 16) for f in fields[:6]), int(fields[6]))
                except ValueError:
                    head = None
    if registers is not None:
        yield Line(registers, cycles, tuple(reads))


@dataclass
class Divergence:
    index: int  # MAME line number (0 = the first instruction)
    address: int  # logical address of the instruction that was stepped
    opcode: int
    differences: dict[str, tuple[int, int]]  # register: (core, MAME)


@dataclass
class Report:
    instructions: int = 0
    interrupts: Counter[str] = field(default_factory=Counter)
    forced: Counter[str] = field(default_factory=Counter)
    forced_after: Counter[tuple[str, int]] = field(
        default_factory=Counter
    )  # (line, previous opcode)
    adopted: int = 0
    block_registers: int = 0  # block transfers whose A, X, Y are MAME's (C14)
    adopted_addresses: Counter[int] = field(default_factory=Counter)
    unread: int = 0  # logged reads the core did not make
    unread_addresses: Counter[int] = field(default_factory=Counter)
    divergences: list[Divergence] = field(default_factory=list)
    cycles_equal: int = 0
    cycles_skipped: int = 0  # steps that include an interrupt entry
    cycle_differences: Counter[tuple[int, int]] = field(
        default_factory=Counter
    )  # (opcode, MAME - core)
    entry_differences: Counter[int] = field(default_factory=Counter)  # MAME - core, entry steps
    samples: dict[tuple[int, int], list[tuple[int, tuple[int, ...]]]] = field(default_factory=dict)

    @property
    def unexplained(self) -> int:
        return sum(self.cycle_differences.values())

    def summary(self) -> str:
        compared = self.cycles_equal + self.unexplained
        lines = [
            f"instructions {self.instructions:,}; interrupts taken "
            + (", ".join(f"{k} {v:,}" for k, v in sorted(self.interrupts.items())) or "none")
            + "; taken a boundary earlier than the core's poll would: "
            + (", ".join(f"{k} {v:,}" for k, v in sorted(self.forced.items())) or "none"),
            (
                f"register divergences {len(self.divergences):,}; block transfers' A, X, Y "
                f"adopted {self.block_registers:,}; adopted MAME's registers after "
                f"{self.adopted:,} unlogged reads; {self.unread:,} logged reads not made"
            ),
            f"cycles equal {self.cycles_equal:,} of {compared:,}, differ {self.unexplained:,} "
            f"({self.cycles_skipped:,} steps with an interrupt entry compared apart: "
            + (
                ", ".join(f"{d:+d} x{n:,}" for d, n in sorted(self.entry_differences.items()))
                or "-"
            )
            + ")",
        ]
        by_opcode: Counter[int] = Counter()
        for (opcode, _), count in self.cycle_differences.items():
            by_opcode[opcode] += count
        for opcode, count in by_opcode.most_common(25):
            deltas = sorted((d, n) for (o, d), n in self.cycle_differences.items() if o == opcode)
            text = ", ".join(f"{d:+d} x{n:,}" for d, n in deltas)
            lines.append(f"  opcode {opcode:02X}: {count:,} differ (MAME - core: {text})")
        if self.unread_addresses:
            common = ", ".join(f"{a:06X} x{n:,}" for a, n in self.unread_addresses.most_common(8))
            lines.append(f"  logged reads not made: {common}")
        if self.adopted_addresses:
            common = ", ".join(f"{a:06X} x{n:,}" for a, n in self.adopted_addresses.most_common(8))
            lines.append(f"  unlogged reads: {common}")
        if self.forced_after:
            common = ", ".join(
                f"{n} after {o:02X} x{c:,}" for (n, o), c in self.forced_after.most_common(8)
            )
            lines.append(f"  taken early: {common}")
        for divergence in self.divergences[:20]:
            diffs = ", ".join(
                f"{name} core {core:X} MAME {mame:X}"
                for name, (core, mame) in divergence.differences.items()
            )
            lines.append(
                f"  line {divergence.index:,} at {divergence.address:04X}"
                f" (opcode {divergence.opcode:02X}): {diffs}"
            )
        return "\n".join(lines)


class Replay(Harness):
    """The minimal harness with MAME's board behind its hardware-page reads."""

    def __init__(self, rom: bytes) -> None:
        super().__init__(rom, io_read=self._answer, bank_read=self._answer_address)
        self.reads: deque[tuple[int, int]] = deque()
        self.guessed: int | None = None  # a hardware-page read nothing logged, this step
        self.line = 0  # the MAME line being replayed
        self.unread_addresses: Counter[int] = Counter()

    def _answer(self, offset: int) -> int:
        return self._answer_address(0x1FE000 | offset)

    def _answer_address(self, address: int) -> int:
        offset = address & 0x1FFF
        reads = self.reads
        if reads and reads[0][0] == address:
            return reads.popleft()[1]
        if reads and address in (a for a, _ in reads):
            # MAME logged other reads first (a block transfer's, say): skip them.
            while reads[0][0] != address:
                self.unread_addresses[reads.popleft()[0]] += 1
            return reads.popleft()[1]
        self.guessed = address
        return self._default_io_read(offset) if address >= 0x1FE000 else 0xFF


def _registers(cpu) -> tuple[int, ...]:
    return (cpu.pc, cpu.a, cpu.x, cpu.y, cpu.s, cpu.p & ~B_FLAG, *cpu.mpr)


def _take_interrupt(replay: Replay, line: Line, report: Report, previous: int = 0) -> str | None:
    """If MAME's next line is an interrupt handler's first instruction, step the entry."""
    cpu = replay.cpu
    if line.registers[4] != (cpu.s - 3) & 0xFF:
        return None
    for name, vector in VECTORS.items():
        target = replay.peek(cpu.physical(vector)) | replay.peek(cpu.physical(vector + 1)) << 8
        if target == line.registers[0]:
            break
    else:
        return None
    if name == "nmi":
        cpu.request_non_maskable_interrupt()
    else:
        cpu.set_irq_lines(name == "irq1", name == "irq2", name == "tiq")
    if cpu.pc == line.registers[0]:
        return None
    if next_boundary(cpu.capture_state()) is BoundaryKind.INSTRUCTION:
        # The core's poll would wait an instruction (CLI, SEI or PLP before it, or an entry):
        # MAME took the interrupt now, so make the poll see the current I and count it.
        # (U21: MAME takes it right after CLI; Mesen and Mednafen, like the core, a step later.)
        cpu._polled_i = None
        cpu._polled = None
        report.forced[name] += 1
        report.forced_after[(name, previous)] += 1
    cpu.step()
    if name != "nmi":
        cpu.set_irq_lines(False, False, False)
    return name


def replay(rom: bytes, log: Path, limit: int | None = None, max_divergences: int = 50) -> Report:
    report = Report()
    harness = Replay(rom)
    cpu = harness.cpu
    cpu.step()  # the reset sequence
    iterator = read_log(log)
    line = next(iterator, None)
    index = 0
    #: The previous instruction's cycles are settled once we know whether an interrupt entry
    #: followed it (MAME's delta to the next line holds the entry).
    pending: tuple[int, int, int, int, tuple[int, ...]] | None = None
    while line is not None and (limit is None or index < limit):
        following = next(iterator, None)
        entered = None
        entry_clocks = 0
        if _registers(cpu)[:6] != (*line.registers[:5], line.registers[5] & ~B_FLAG):
            mark = harness.master_clocks
            entered = _take_interrupt(harness, line, report, pending[1] if pending else 0)
            entry_clocks = harness.master_clocks - mark
            if entered:
                report.interrupts[entered] += 1
        if pending is not None:
            last_index, last_opcode, mame, core, last_registers = pending
            if entered:
                report.cycles_skipped += 1
                report.entry_differences[mame - core - entry_clocks // 3] += 1
            elif mame == core:
                report.cycles_equal += 1
            else:
                key = (last_opcode, mame - core)
                report.cycle_differences[key] += 1
                samples = report.samples.setdefault(key, [])
                if len(samples) < 3:
                    samples.append((last_index, last_registers))
            pending = None
        mine = _registers(cpu)
        want = (*line.registers[:5], line.registers[5] & ~B_FLAG, *line.registers[6:])
        if mine != want:
            names = (*REGISTERS, *(f"mpr{n}" for n in range(8)))
            differences = {
                name: (a, b) for name, a, b in zip(names, mine, want, strict=True) if a != b
            }
            report.divergences.append(
                Divergence(index, want[0], harness.peek(cpu.physical(want[0])), differences)
            )
            if len(report.divergences) >= max_divergences:
                break
            # Take MAME's registers so one divergence does not spread.
            for name in ("a", "x", "y", "s", "pc"):
                setattr(cpu, name, want[REGISTERS.index(name)])
            cpu.p = want[5]
            cpu.mpr[:] = want[6:]
        harness.line = index  # for a debugger watching the run
        harness.reads = deque(line.reads)
        harness.guessed = None
        opcode = harness.peek(cpu.physical(cpu.pc))
        start = harness.master_clocks
        cpu.step()
        report.instructions += 1
        if harness.reads:
            report.unread += len(harness.reads)
            for address, _ in harness.reads:
                report.unread_addresses[address] += 1
        if opcode in BLOCK_OPCODES and following is not None:
            # C14: MAME's block transfers keep A, X and Y in the CPU and never push them;
            # the core (like Mesen and Mednafen) pushes and pops them (HW HB-6), so a
            # transfer over the stack gives them back overwritten. MAME's are adopted.
            report.block_registers += 1
            for name in ("a", "x", "y"):
                setattr(cpu, name, following.registers[REGISTERS.index(name)])
        if harness.guessed is not None and following is not None:
            report.adopted += 1
            report.adopted_addresses[harness.guessed] += 1
            nxt = following.registers
            for name in ("a", "x", "y", "s", "pc"):
                setattr(cpu, name, nxt[REGISTERS.index(name)])
            cpu.p = nxt[5] & ~B_FLAG
        if following is not None:
            pending = (
                index,
                opcode,
                following.cycles - line.cycles,
                (harness.master_clocks - start) // 3,
                want,
            )
        line = following
        index += 1
    return report
