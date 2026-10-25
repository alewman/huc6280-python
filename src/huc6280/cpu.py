"""The public HuC6280 CPU class.

The host owns memory and every device: it passes ``read_byte(address)``,
``write_byte(address, value)`` and optionally ``idle(address)`` in, calls
:meth:`HuC6280.step`, and runs its devices inside the callbacks for as long
as each cycle lasts on its board. See docs/handoff-brief.md, "The bus contract".
"""

from sixfiveohtwo.frame import CPUFrame

from huc6280._alu import ALUMixin
from huc6280._bits import BitMixin
from huc6280._block import BlockMixin
from huc6280._control import ControlMixin
from huc6280._core import CoreMixin, Idle, ReadByte, T, WriteByte
from huc6280._dispatch import Entry, build_table
from huc6280._hudson import HudsonMixin
from huc6280._loads import LoadMixin
from huc6280._shifts import ShiftMixin
from huc6280.state import CPUState


def _no_idle(address: int | None) -> None:
    """The default ``idle``: a cycle with no data transfer touches nothing."""


class HuC6280(
    ALUMixin,
    LoadMixin,
    ShiftMixin,
    BitMixin,
    ControlMixin,
    HudsonMixin,
    BlockMixin,
    CoreMixin,
    CPUFrame,
):
    """A Hudson HuC6280 core whose bus is callables supplied by a host.

    ``read_byte(address)`` and ``write_byte(address, value)`` are the bus, with
    21-bit physical addresses (the mapper is in the core, ``mpr``);
    ``idle(address)`` is called for each cycle with no data transfer: with the
    address of the dummy read the chip makes (the byte after the opcode of an
    implied instruction), or with ``None`` for an internal cycle. Every cycle is
    exactly one callback, in the chip's order, and ``step()`` returns how many it
    made. Inside a callback ``kind`` (``"read"``, ``"write"``, ``"dummy"`` or
    ``"idle"``) and ``high_speed`` describe the cycle.

    Registers are plain attributes: ``a``, ``x``, ``y``, ``s``, ``pc`` (logical,
    16 bits), ``p`` (8 bits; B is not stored) and ``mpr`` (eight 8-bit mapping
    registers). The interrupt inputs, their poll and ``step()``'s skeleton are
    6502-python's :class:`~sixfiveohtwo.frame.CPUFrame`; the three maskable
    sources come in through :meth:`set_irq_lines` and ``irq_disable``.
    """

    _table: list[Entry]

    def __init__(
        self, read_byte: ReadByte, write_byte: WriteByte, idle: Idle | None = None
    ) -> None:
        super().__init__(read_byte, write_byte)
        self.idle = _no_idle if idle is None else idle
        self._init_registers()
        self._lines = 0
        self._lines_before = 0
        self._poll_lines = 0
        self._irq_disable = 0
        cls = type(self)
        if "_table" not in cls.__dict__:
            cls._table = build_table(cls)

    @property
    def idle(self) -> Idle:
        """The host's ``idle(address)``, called for every cycle with no data transfer."""
        return self._idle

    @idle.setter
    def idle(self, idle: Idle) -> None:
        if not callable(idle):
            raise TypeError(f"idle must be callable, not {type(idle).__name__}")
        self._idle = idle

    def _execute(self) -> int:
        self._cycles = 0
        pc = self.pc
        opcode = self._cycle_read(pc)
        self.pc = (pc + 1) & 0xFFFF
        self._opcode = opcode
        # U4: the memory-operation flag is cleared in the fetch cycle of the next instruction;
        # the handler sees what it was.
        self._t = self.p & T
        self.p &= ~T
        handler, mode = self._table[opcode]
        if mode is None:
            handler(self)
        else:
            handler(self, mode)
        return self._cycles

    # -- state -----------------------------------------------------------

    def capture_state(self) -> CPUState:
        """Return an immutable snapshot of all CPU-owned state at a boundary.

        No host reads, no side effects. Memory and devices are the host's and are not
        included.
        """
        irq1, irq2, tiq = self.irq_lines
        return CPUState(
            a=self.a,
            x=self.x,
            y=self.y,
            s=self.s,
            pc=self.pc,
            p=self.p,
            mpr=tuple(self.mpr),
            high_speed=self.high_speed,
            mpr_latch=self._mpr_latch,
            irq1=irq1,
            irq2=irq2,
            tiq=tiq,
            irq_disable=self._irq_disable,
            **self._poll_fields(),
        )

    def restore_state(self, state: CPUState) -> None:
        """Restore a captured CPU state without touching the host."""
        if type(state) is not CPUState:
            raise TypeError("state must be a huc6280 CPUState")
        for name in ("a", "x", "y", "s", "pc", "p"):
            setattr(self, name, getattr(state, name))
        self.mpr[:] = state.mpr
        self.high_speed = state.high_speed
        self._mpr_latch = state.mpr_latch
        self._lines = (0x02 if state.irq1 else 0) | (0x01 if state.irq2 else 0)
        self._lines |= 0x04 if state.tiq else 0
        self._lines_before = self._poll_lines = self._lines
        self._irq_disable = state.irq_disable
        self._restore_poll(state)


__all__ = ["HuC6280"]
