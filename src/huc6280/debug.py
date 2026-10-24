"""Execution control and structured debugging records for the HuC6280.

6502-python's :class:`~sixfiveohtwo.debug.DebugSession` and
:class:`~sixfiveohtwo.debug.StepRecord`, subclassed through their hooks (6502-python
docs/api-stability.md, "The tooling"): this core's :class:`~huc6280.state.CPUState`, its
boundary kinds and its disassembler, and the cycles that are not reads or writes tracked
beside them.

Two address spaces meet here (docs/start-here.md). **Breakpoints are on the logical PC**
(16 bits, what the program counter holds) and, with :meth:`HuC6280Session.add_physical_breakpoint`,
on the 21-bit physical address of the instruction (the mapper applied). **Watchpoints and tracked
accesses are physical**, as the bus callbacks see them. ``peek_byte`` takes a *logical* address.

A tracked access is ``(kind, address, value)`` with the kinds of the core's own callbacks:
``"r"`` a read, ``"w"`` a write, ``"d"`` a dummy read (``idle(address)``, value 0) and ``"i"``
an internal cycle (``idle(None)``, recorded at address 0, value 0). Watchpoints match the first
letter, so they see dummy and internal cycles only as what they are: neither reads nor writes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Self

from sixfiveohtwo.debug import Access, DebugSession, RunResult, StepRecord, StopReason

from huc6280._core import I
from huc6280.disasm import Instruction, disassemble, disassemble_bytes
from huc6280.state import CPUState


class BoundaryKind(Enum):
    """Kind of work performed by one ``HuC6280.step()`` call."""

    INSTRUCTION = "instruction"
    RESET = "reset"
    NMI = "nmi"
    IRQ1 = "irq1"
    IRQ2 = "irq2"
    TIQ = "tiq"


ACCESS_KINDS = frozenset(("r", "w", "d", "i"))


def next_boundary(state: CPUState) -> BoundaryKind:
    """What the next ``step()`` will do, decided exactly as ``HuC6280.step()`` decides."""
    if state.reset_pending:
        return BoundaryKind.RESET
    if state.skipped_poll:
        return BoundaryKind.INSTRUCTION
    nmi = state.polled_non_maskable_interrupt
    if state.non_maskable_interrupt_pending if nmi is None else nmi:
        return BoundaryKind.NMI
    irq = state.polled_maskable_interrupt
    masked = bool(state.p & I) if state.polled_i is None else state.polled_i
    if (state.maskable_interrupt_pending if irq is None else irq) and not masked:
        # The vector is chosen from the lines in priority order (HW HB-13).
        if state.tiq and not state.irq_disable & 4:
            return BoundaryKind.TIQ
        if state.irq1 and not state.irq_disable & 2:
            return BoundaryKind.IRQ1
        return BoundaryKind.IRQ2
    return BoundaryKind.INSTRUCTION


@dataclass(frozen=True, slots=True)
class HuC6280Record(StepRecord):
    """A :class:`~sixfiveohtwo.debug.StepRecord` of the HuC6280."""

    state_type = CPUState
    kind_type = BoundaryKind
    instruction_kind = BoundaryKind.INSTRUCTION
    halted_kinds = frozenset()
    instruction_type = Instruction
    access_kinds = ACCESS_KINDS
    address_mask = 0x1FFFFF

    @staticmethod
    def decode(data: bytes, address: int) -> Instruction:
        return disassemble_bytes(data, address)


class ProgramAddress(int):
    """The logical PC, carrying the physical address it maps to, for breakpoint matching."""

    physical: int

    def __new__(cls, logical: int, physical: int) -> Self:
        self = super().__new__(cls, logical)
        self.physical = physical
        return self


class Breakpoints(set):
    """Logical breakpoints (plain members) and physical ones (``physical`` set).

    ``program_address in breakpoints`` is true for either kind, which is how the base class's
    ``run()`` asks.
    """

    def __init__(self) -> None:
        super().__init__()
        self.physical: set[int] = set()

    def __contains__(self, key: object) -> bool:
        if isinstance(key, ProgramAddress) and key.physical in self.physical:
            return True
        return super().__contains__(int(key))  # type: ignore[call-overload]


class HuC6280Session(DebugSession):
    """A :class:`~sixfiveohtwo.debug.DebugSession` for a HuC6280 or a board around one.

    ``track_accesses=True`` wraps ``idle`` as well as ``read_byte`` and ``write_byte``, so a
    step's accesses are exactly one per cycle.
    """

    record_type = HuC6280Record

    def __init__(self, *args, peek_physical=None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.breakpoints = Breakpoints()
        #: Side-effect-free read of a 21-bit physical address (the ``physical`` command).
        self.peek_physical = peek_physical

    def boundary(self, state: CPUState) -> BoundaryKind:
        return next_boundary(state)

    def program_address(self, state: CPUState) -> ProgramAddress:
        return ProgramAddress(state.pc, state.mpr[state.pc >> 13] << 13 | state.pc & 0x1FFF)

    def decode(self, state: CPUState) -> Instruction:
        return disassemble(self.peek_byte, state.pc)

    def add_breakpoint(self, address: int) -> None:
        """Stop before executing the instruction at this logical (16-bit) PC."""
        if type(address) is not int or not 0 <= address <= 0xFFFF:
            raise ValueError("a logical breakpoint is an integer in range 0x0000..0xFFFF")
        self.breakpoints.add(address)

    def remove_breakpoint(self, address: int) -> None:
        self.breakpoints.discard(address)

    def add_physical_breakpoint(self, address: int) -> None:
        """Stop before executing the instruction whose opcode is at this 21-bit physical address."""
        self.breakpoints.physical.add(self._validate_address(address))

    def remove_physical_breakpoint(self, address: int) -> None:
        self.breakpoints.physical.discard(address)

    def _wrap_bus(self) -> None:
        cpu = self.cpu
        originals = (cpu.read_byte, cpu.write_byte, cpu.idle)
        read_byte, write_byte, idle = originals
        self._originals = originals
        log: list[Access] = []
        self._accesses = log

        def tracked_read_byte(address: int) -> int:
            value = read_byte(address)
            log.append(("r", address, value))
            return value

        def tracked_write_byte(address: int, value: int) -> None:
            log.append(("w", address, value))
            write_byte(address, value)

        def tracked_idle(address: int | None) -> None:
            log.append(("i", 0, 0) if address is None else ("d", address, 0))
            idle(address)

        cpu.read_byte = tracked_read_byte
        cpu.write_byte = tracked_write_byte
        cpu.idle = tracked_idle

    def _unwrap_bus(self, originals: tuple) -> None:
        cpu = self.cpu
        cpu.read_byte, cpu.write_byte, cpu.idle = originals


__all__ = [
    "ACCESS_KINDS",
    "BoundaryKind",
    "HuC6280Record",
    "HuC6280Session",
    "RunResult",
    "StopReason",
    "next_boundary",
]
