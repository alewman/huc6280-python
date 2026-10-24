"""Immutable values for capturing and restoring HuC6280 processor state."""

from dataclasses import dataclass


def _require_int(name: str, value: object, maximum: int) -> None:
    if type(value) is not int or not 0 <= value <= maximum:
        width = 2 if maximum == 0xFF else 4
        message = f"{name} must be an integer in range 0x{'0' * width}..0x{maximum:0{width}X}"
        raise ValueError(message)


def _require_bool(name: str, value: object) -> None:
    if type(value) is not bool:
        raise ValueError(f"{name} must be a bool")


@dataclass(frozen=True, slots=True)
class CPUState:
    """Complete CPU-owned state at an instruction boundary.

    Registers, the mapping registers, the clock switch, the three maskable interrupt
    inputs and their disable gate, and the frame's poll state (the requests the host has
    made and the core has not yet taken, and what decides the next ``step()``). Host
    memory, devices, scheduling and cycle counters are excluded: restoring this value
    restores the processor, not a machine. The fields from ``halted`` on are 6502-python's
    frame's, as in its ``CPUState``.
    """

    a: int = 0
    x: int = 0
    y: int = 0
    s: int = 0xFF
    pc: int = 0  # logical, 16 bits
    #: P as the core keeps it: T is bit 5, B (bit 4) is never stored (U4, U5).
    p: int = 0x04
    #: MPR0-MPR7.
    mpr: tuple[int, ...] = (0,) * 8
    high_speed: bool = False
    #: The last value TAM or TMA moved (what TMA #$00 returns; U11).
    mpr_latch: int = 0
    #: The IRQ1, IRQ2 and TIQ input levels and the disable register (IRQ2, IRQ1, TIQ; 1 = masked).
    irq1: bool = False
    irq2: bool = False
    tiq: bool = False
    irq_disable: int = 0
    halted: bool = False  # always False: the HuC6280 has no JAM, WAI or STP
    reset_pending: bool = False
    maskable_interrupt_pending: bool = False  # an enabled maskable source is asserted
    non_maskable_interrupt_pending: bool = False  # an NMI edge latched and not yet taken
    #: The I flag the last instruction's poll saw, when that differs in timing from P
    #: (CLI, SEI, PLP); None otherwise.
    polled_i: bool | None = None
    #: The IRQ line and the NMI latch as the last poll saw them, when that is not what the
    #: requests above say; None when the poll agrees with them.
    polled_maskable_interrupt: bool | None = None
    polled_non_maskable_interrupt: bool | None = None
    #: The last step was BRK, an interrupt entry or reset, which do not poll: the next
    #: boundary runs an instruction.
    skipped_poll: bool = False

    def __post_init__(self) -> None:
        for name in ("a", "x", "y", "s", "p", "mpr_latch"):
            _require_int(name, getattr(self, name), 0xFF)
        _require_int("pc", self.pc, 0xFFFF)
        _require_int("irq_disable", self.irq_disable, 7)
        if type(self.mpr) is list:  # a trace read back from JSON
            object.__setattr__(self, "mpr", tuple(self.mpr))
        if type(self.mpr) is not tuple or len(self.mpr) != 8:
            raise ValueError("mpr must be a tuple of eight values")
        for index, value in enumerate(self.mpr):
            _require_int(f"mpr[{index}]", value, 0xFF)
        for name in (
            "high_speed",
            "irq1",
            "irq2",
            "tiq",
            "halted",
            "reset_pending",
            "maskable_interrupt_pending",
            "non_maskable_interrupt_pending",
            "skipped_poll",
        ):
            _require_bool(name, getattr(self, name))
        for name in ("polled_i", "polled_maskable_interrupt", "polled_non_maskable_interrupt"):
            if getattr(self, name) is not None:
                _require_bool(name, getattr(self, name))
        if self.p & 0x10:
            raise ValueError("p must have B (bit 4) clear: B is not stored")


__all__ = ["CPUState"]
