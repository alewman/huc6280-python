"""Registers, the memory mapper, the cycle primitives and the addressing modes.

Every CPU cycle is one callback, in the chip's order, internal cycles and
dummy reads included. A cycle is one of four kinds, readable as ``cpu.kind``
while the callback runs:

- ``"read"``: ``read_byte(address)``; the opcode fetch is the first cycle.
- ``"write"``: ``write_byte(address, value)``.
- ``"dummy"``: ``idle(address)``; a read the chip makes and throws away, at
  the address given (the byte after the opcode for an implied instruction).
- ``"idle"``: ``idle(None)``; an internal cycle with nothing on the bus.

The bus shapes (which cycle is which, and where the internal cycles sit) are
those of SingleStepTests huc6280 (docs/timing.md, "The bus cycles"): Mesen's
model, **emulator tier** (C8). Hudson's manual gives totals only.

The addresses the callbacks receive are 21-bit physical addresses: the
mapper is in the core (docs/handoff-brief.md, "The core boundary"). Logical
addresses are 16-bit; the top three bits pick one of eight mapping registers
(HW HB-7), whose 8-bit value replaces them (U1, HW HB-3; pcetech 2.0).
"""

from collections.abc import Callable

# P (HW HB-4, HB-5). B is never stored: it reads as 1 whenever P is pushed by
# PHP or BRK and as 0 when an interrupt pushes it (U5), and the corpus never
# sets it. T is bit 5, the memory-operation flag (U4).
N = 0x80
V = 0x40
T = 0x20
B = 0x10
D = 0x08
I = 0x04
Z = 0x02
C = 0x01

# Zero page and stack are logical pages $20 and $21, through MPR1 (U1; HW HB-3:
# the address bus high byte is $21 for the stack).
ZERO_PAGE = 0x2000
STACK_PAGE = 0x2100

# A cycle's kind, as cpu.kind shows it.
READ = "read"
WRITE = "write"
DUMMY = "dummy"
IDLE = "idle"

ReadByte = Callable[[int], int]
WriteByte = Callable[[int, int], None]
Idle = Callable[[int | None], None]


def nz(value: int) -> int:
    """N and Z for an 8-bit result."""
    return (value & N) | (0 if value & 0xFF else Z)


class CoreMixin:
    """Private register state, bus primitives, operand access and addressing modes."""

    def _init_registers(self) -> None:
        # Power-up values are random on hardware (A X Y S, MPR0-6; U2). Zero
        # makes traces reproducible; reset sets only what HW HB-18 lists.
        self.a = 0
        self.x = 0
        self.y = 0
        self.s = 0xFF
        self.pc = 0
        self.p = I
        #: MPR0-MPR7, the 8-bit mapping registers (physical A13-A20).
        self.mpr = [0] * 8
        #: The clock switch: False at 1.79 MHz (12 master clocks a cycle), True at
        #: 7.16 MHz (3). Reset selects low (U10).
        self.high_speed = False
        #: The last value TAM or TMA moved: what TMA with an operand of $00 returns (U11).
        self._mpr_latch = 0
        self._opcode = 0
        #: T as the instruction fetch found it; the fetch clears it in P (U4).
        self._t = 0
        self._kind = IDLE
        self._cycles = 0

    @property
    def kind(self) -> str:
        """The current cycle's kind: ``"read"``, ``"write"``, ``"dummy"`` or ``"idle"``."""
        return self._kind

    # -- the mapper -------------------------------------------------------

    def physical(self, address: int) -> int:
        """The 21-bit physical address of a 16-bit logical one (HW HB-7)."""
        return self.mpr[address >> 13] << 13 | address & 0x1FFF

    # -- cycles ----------------------------------------------------------

    def _cycle_read(self, address: int) -> int:
        """A data or program read at a logical address."""
        self._kind = READ
        self._cycles += 1
        return self._read(self.mpr[address >> 13] << 13 | address & 0x1FFF)

    def _cycle_write(self, address: int, value: int) -> None:
        """A write at a logical address."""
        self._kind = WRITE
        self._cycles += 1
        self._write(self.mpr[address >> 13] << 13 | address & 0x1FFF, value)

    def _cycle_write_physical(self, address: int, value: int) -> None:
        """A write at a physical address, bypassing the mapper (ST0-ST2, U12)."""
        self._kind = WRITE
        self._cycles += 1
        self._write(address, value)

    def _dummy(self, address: int) -> None:
        """A read the chip makes and discards, at a logical address (C8)."""
        self._kind = DUMMY
        self._cycles += 1
        if self._deferred is not None:
            self._confirm()
        self._idle(self.mpr[address >> 13] << 13 | address & 0x1FFF)

    def _io(self) -> None:
        """An internal cycle: nothing on the bus (C8)."""
        self._kind = IDLE
        self._cycles += 1
        if self._deferred is not None:
            self._confirm()
        self._idle(None)

    def _implied(self) -> None:
        """The dummy read after an opcode that has no operand: PC, the byte after it."""
        self._dummy(self.pc)

    def _fetch(self) -> int:
        """One operand byte at PC."""
        pc = self.pc
        self.pc = (pc + 1) & 0xFFFF
        return self._cycle_read(pc)

    def _fetch_word(self) -> int:
        low = self._fetch()
        return self._fetch() << 8 | low

    # -- operands --------------------------------------------------------

    def _load(self, address: int) -> int:
        return self._cycle_read(address)

    def _store(self, address: int, value: int) -> None:
        self._cycle_write(address, value)

    def _modify(self, address: int, operation: Callable[[int], int]) -> None:
        """A read-modify-write: read, an internal cycle, write. No dummy write (docs/timing.md)."""
        value = self._cycle_read(address)
        self._io()
        self._cycle_write(address, operation(value))

    def _set_nz(self, value: int) -> int:
        self.p = (self.p & ~(N | Z)) | nz(value)
        return value

    # -- the stack (logical $2100 + S; S wraps in 8 bits) -----------------

    def _push(self, value: int) -> None:
        s = self.s
        self._cycle_write(STACK_PAGE | s, value)
        self.s = (s - 1) & 0xFF

    def _pull(self) -> int:
        s = (self.s + 1) & 0xFF
        self.s = s
        return self._cycle_read(STACK_PAGE | s)

    # -- addressing modes -------------------------------------------------
    # Each makes its addressing cycles and returns the operand's logical
    # address. Reads, writes and read-modify-writes share one shape: there is
    # no index cost and no page-crossing cost on this chip (pcetech 2.0, U9).

    def _ea_imm(self) -> int:
        """`#imm`: the operand is the byte at PC; the handler's load is its cycle."""
        pc = self.pc
        self.pc = (pc + 1) & 0xFFFF
        return pc

    def _ea_zp(self) -> int:
        """`zp`: logical $2000 + zp (U1), then an internal cycle."""
        zp = self._fetch()
        self._io()
        return ZERO_PAGE | zp

    def _ea_zpx(self) -> int:
        """`zp,X`: the sum wraps within the zero page."""
        zp = self._fetch()
        self._io()
        return ZERO_PAGE | (zp + self.x) & 0xFF

    def _ea_zpy(self) -> int:
        """`zp,Y` (LDX and STX only)."""
        zp = self._fetch()
        self._io()
        return ZERO_PAGE | (zp + self.y) & 0xFF

    def _ea_abs(self) -> int:
        """`abs`, then an internal cycle."""
        address = self._fetch_word()
        self._io()
        return address

    def _ea_abx(self) -> int:
        """`abs,X`: a 16-bit sum, no extra cycle for a page crossing (pcetech 2.0)."""
        address = self._fetch_word()
        self._io()
        return (address + self.x) & 0xFFFF

    def _ea_aby(self) -> int:
        """`abs,Y`."""
        address = self._fetch_word()
        self._io()
        return (address + self.y) & 0xFFFF

    # Named so a board or a later capture can change it: whether a pointer at
    # zero-page offset $FF takes its high byte from offset $00 (Mesen's
    # ReadZeroPageWrap, MAME's program_read16z; emulator tier, U8) or from
    # logical $2100.
    zero_page_pointer_wraps = True

    def _pointer(self, zp: int) -> int:
        """A two-byte pointer in the zero page (U8)."""
        low = self._cycle_read(ZERO_PAGE | zp)
        high_zp = (zp + 1) & 0xFF if self.zero_page_pointer_wraps else zp + 1
        return self._cycle_read(ZERO_PAGE + high_zp) << 8 | low

    def _ea_idx(self) -> int:
        """`(zp,X)`: the index is added before the pointer is read."""
        zp = self._fetch()
        self._io()
        pointer = self._pointer((zp + self.x) & 0xFF)
        self._io()
        return pointer

    def _ea_idy(self) -> int:
        """`(zp),Y`: the index is added after, 16 bits."""
        zp = self._fetch()
        self._io()
        pointer = self._pointer(zp)
        self._io()
        return (pointer + self.y) & 0xFFFF

    def _ea_ind(self) -> int:
        """`(zp)`, the 65C02 addition."""
        zp = self._fetch()
        self._io()
        pointer = self._pointer(zp)
        self._io()
        return pointer
