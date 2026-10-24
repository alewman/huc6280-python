"""Branches, jumps, calls, returns, the stack, flags, BRK, interrupts and reset.

Vectors (HW HB-12 to HB-18; start-here.md): RESET ``$FFFE``, NMI ``$FFFC``, TIQ
``$FFFA``, IRQ1 ``$FFF8``, IRQ2 and BRK ``$FFF6``, read through the mapper
(after reset MPR7 = 0, so physical ``$001FFE``).

The interrupt design is docs/handoff-brief.md's: the frame's ``IRQ_LINE`` means
"an enabled maskable source is asserted"; :meth:`set_irq_lines` and the
``irq_disable`` register (the ``$1402`` layout, 1 = disabled) feed it, and the
vector is chosen at entry from the lines in priority order TIQ, IRQ1, IRQ2.
The timer and the ``$1402``/``$1403`` registers themselves are the board's.
"""

from sixfiveohtwo.frame import IRQ_LINE, NMI_LATCH, NO_POLL

from huc6280._core import B, C, D, I, N, T, V, Z

VECTOR_RESET = 0xFFFE
VECTOR_NMI = 0xFFFC
VECTOR_TIQ = 0xFFFA
VECTOR_IRQ1 = 0xFFF8
VECTOR_IRQ2 = 0xFFF6  # also BRK (U15)

# The three maskable sources, in the layout of $1402/$1403 (pcetech 2.1).
IRQ2_BIT = 0x01
IRQ1_BIT = 0x02
TIQ_BIT = 0x04


class ControlMixin:
    """Private control-flow, stack, flag, interrupt and reset implementation."""

    # -- branches ----------------------------------------------------------

    def _branch(self, taken: int) -> None:
        offset = self._fetch()
        if not taken:
            return
        # A taken branch costs 2 more cycles whatever page it lands in (SW; pcetech 2.0, U9).
        self._dummy(self.pc)
        self._io()
        self.pc = (self.pc + offset - ((offset & 0x80) << 1)) & 0xFFFF

    def _op_bpl(self) -> None:
        """BPL -- branch if N = 0 (SW SB-28)."""
        self._branch(not self.p & N)

    def _op_bmi(self) -> None:
        """BMI -- branch if N = 1 (SW SB-26)."""
        self._branch(self.p & N)

    def _op_bvc(self) -> None:
        """BVC -- branch if V = 0 (SW SB-32)."""
        self._branch(not self.p & V)

    def _op_bvs(self) -> None:
        """BVS -- branch if V = 1 (SW SB-33)."""
        self._branch(self.p & V)

    def _op_bcc(self) -> None:
        """BCC -- branch if C = 0 (SW SB-22)."""
        self._branch(not self.p & C)

    def _op_bcs(self) -> None:
        """BCS -- branch if C = 1 (SW SB-23)."""
        self._branch(self.p & C)

    def _op_bne(self) -> None:
        """BNE -- branch if Z = 0 (SW SB-27)."""
        self._branch(not self.p & Z)

    def _op_beq(self) -> None:
        """BEQ -- branch if Z = 1 (SW SB-24)."""
        self._branch(self.p & Z)

    def _op_bra(self) -> None:
        """BRA -- branch always, always 4 cycles (SW SB-29)."""
        offset = self._fetch()
        self._io()
        self._io()
        self.pc = (self.pc + offset - ((offset & 0x80) << 1)) & 0xFFFF

    # -- jumps, calls, returns --------------------------------------------------

    def _op_jmp_abs(self) -> None:
        """JMP -- abs: AA -> PC (SW SB-51)."""
        self.pc = self._fetch_word()
        self._io()

    def _read_pointer(self, address: int) -> int:
        # U9: the high byte is at address + 1 even across a page; no NMOS bug (pcetech 2.0).
        low = self._cycle_read(address)
        return self._cycle_read((address + 1) & 0xFFFF) << 8 | low

    def _op_jmp_ind(self) -> None:
        """JMP -- (abs): the pointer's address, then the word there -> PC (SW SB-51)."""
        pointer = self._fetch_word()
        self._io()
        self.pc = self._read_pointer(pointer)
        self._io()

    def _op_jmp_idx(self) -> None:
        """JMP -- (abs,X): the pointer is at abs + X (SW SB-51)."""
        pointer = (self._fetch_word() + self.x) & 0xFFFF
        self._io()
        self.pc = self._read_pointer(pointer)
        self._io()

    def _op_jsr(self) -> None:
        """JSR -- push the address of the operand's last byte, then AA -> PC (SW SB-52)."""
        low = self._fetch()
        self._io()
        pc = self.pc  # the high byte's address, the last byte of JSR (U20)
        self._push(pc >> 8)
        self._push(pc & 0xFF)
        self.pc = self._fetch() << 8 | low
        self._io()

    def _op_bsr(self) -> None:
        """BSR -- push the address of the offset byte, then PC + offset (8 cycles) (SW SB-31)."""
        offset = self._fetch()
        self._io()
        pc = (self.pc - 1) & 0xFFFF  # U20: the last byte of BSR
        self._push(pc >> 8)
        self._push(pc & 0xFF)
        self._io()
        self._io()
        self._io()
        self.pc = (self.pc + offset - ((offset & 0x80) << 1)) & 0xFFFF

    def _op_rts(self) -> None:
        """RTS -- pull PC, then PC + 1 -> PC (SW SB-71)."""
        self._implied()
        self._io()
        low = self._pull()
        pc = self._pull() << 8 | low
        self._io()
        self._io()
        self.pc = (pc + 1) & 0xFFFF

    def _op_rti(self) -> None:
        """RTI -- pull P, then PC (SW SB-70)."""
        self._implied()
        self._io()
        self.p = self._pull() & ~B  # U20: P first, then PCL, PCH; B is not stored (U5)
        low = self._pull()
        self.pc = self._pull() << 8 | low
        self._io()

    # -- the stack ---------------------------------------------------------

    def _op_pha(self) -> None:
        """PHA -- push A (SW SB-59)."""
        self._implied()
        self._push(self.a)

    def _op_php(self) -> None:
        """PHP -- push P with B set and T clear (SW SB-60)."""
        self._implied()
        # U5: B reads as 1 in a pushed P. T reads as 0: the fetch cleared it (U4).
        self._push(self.p | B)

    def _op_phx(self) -> None:
        """PHX -- push X (SW SB-61)."""
        self._implied()
        self._push(self.x)

    def _op_phy(self) -> None:
        """PHY -- push Y (SW SB-62)."""
        self._implied()
        self._push(self.y)

    def _pull_register(self) -> int:
        self._implied()
        self._io()
        return self._pull()

    def _op_pla(self) -> None:
        """PLA -- pull A (SW SB-63)."""
        self.a = self._set_nz(self._pull_register())

    def _op_plx(self) -> None:
        """PLX -- pull X (SW SB-65)."""
        self.x = self._set_nz(self._pull_register())

    def _op_ply(self) -> None:
        """PLY -- pull Y (SW SB-66)."""
        self.y = self._set_nz(self._pull_register())

    def _op_plp(self) -> None:
        """PLP -- pull P; T can be set from the stack, B is not kept (SW SB-64)."""
        value = self._pull_register()
        # U21: the new I counts one instruction late, as on the 6502 (frame's _polled_i).
        self._polled_i = self.p & I
        self.p = value & ~B

    # -- flags and NOP -------------------------------------------------------

    def _op_clc(self) -> None:
        """CLC -- 0 -> C (SW SB-35)."""
        self._implied()
        self.p &= ~C

    def _op_sec(self) -> None:
        """SEC -- 1 -> C (SW SB-75)."""
        self._implied()
        self.p |= C

    def _op_cld(self) -> None:
        """CLD -- 0 -> D (SW SB-36)."""
        self._implied()
        self.p &= ~D

    def _op_sed(self) -> None:
        """SED -- 1 -> D (SW SB-76)."""
        self._implied()
        self.p |= D

    def _op_clv(self) -> None:
        """CLV -- 0 -> V (SW SB-38)."""
        self._implied()
        self.p &= ~V

    def _op_cli(self) -> None:
        """CLI -- 0 -> I, after this instruction's interrupt poll (SW SB-37)."""
        self._implied()
        self._polled_i = self.p & I  # U21
        self.p &= ~I

    def _op_sei(self) -> None:
        """SEI -- 1 -> I, after this instruction's interrupt poll (SW SB-77)."""
        self._implied()
        self._polled_i = self.p & I  # U21
        self.p |= I

    #: C4: pcetech tested opcode $63 as a two-cycle NOP; MAME bills four. Emulator-tier
    #: knob for a board that wants MAME's count.
    nop_63_cycles = 2

    def _op_nop(self) -> None:
        """NOP -- no operation; the 22 undefined opcodes are the same (U3) (SW SB-57)."""
        self._implied()
        if self._opcode == 0x63:
            for _ in range(self.nop_63_cycles - 2):
                self._io()

    # -- BRK, interrupts, reset ---------------------------------------------------

    def _op_brk(self) -> None:
        """BRK -- push PC + 2 and P with B set, jump through the IRQ2 vector (SW SB-30)."""
        self._fetch()  # C2: the signature byte is skipped, so BRK is two bytes
        self._interrupt(VECTOR_IRQ2, self.p | B)  # U15
        self._io()

    def _interrupt(self, vector: int, pushed_p: int) -> None:
        pc = self.pc
        self._push(pc >> 8)
        self._push(pc & 0xFF)
        self._push(pushed_p)
        # HW HB-14, pcetech 2.0: the entry sets I and clears D, and clears T.
        self.p = (self.p | I) & ~(D | T)
        low = self._cycle_read(vector)
        self.pc = self._cycle_read(vector + 1) << 8 | low

    #: C3: an interrupt entry takes 8 cycles in Mesen, Mednafen, Geargrafx and ares, 7 in MAME
    #: (emulator tier; no manual states it).
    interrupt_entry_cycles = 8

    def _enter_interrupt(self, kind: int) -> int:
        """Take NMI or the highest-priority enabled maskable source at a boundary."""
        self._cycles = 0
        self._polled_i = None
        if kind == NMI_LATCH:
            vector = VECTOR_NMI
            self._requests &= ~NMI_LATCH
        else:
            vector = self._maskable_vector()
        # Two dummy reads (the opcode and the byte after it, both discarded), the pushes,
        # the vector, and an internal cycle (Mesen's ProcessIrq; C3, C8).
        self._dummy(self.pc)
        self._dummy(self.pc)
        # U4, U5: P is pushed with B clear and T as it stands, so an interrupt between SET and
        # its target leaves T set in the pushed byte and RTI restores it.
        self._interrupt(vector, self.p & ~B)
        if self.interrupt_entry_cycles >= 8:
            self._io()
        # An entry does not poll: the handler's first instruction runs before anything
        # requested since is taken.
        self._polled = NO_POLL
        self._deferred = None
        return self._cycles

    def _maskable_vector(self) -> int:
        """The vector of the highest-priority source that is asserted and enabled (HW HB-13)."""
        pending = self._lines & ~self._irq_disable
        if pending & TIQ_BIT:
            return VECTOR_TIQ
        if pending & IRQ1_BIT:
            return VECTOR_IRQ1
        return VECTOR_IRQ2

    def _accept_reset(self) -> int:
        """The start sequence (HW HB-18; U2): MPR7 = 0, I set, D and T clear, low speed."""
        self._cycles = 0
        self._reset_pending = False
        self._polled_i = None
        self.mpr[7] = 0
        self.p = (self.p | I) & ~(D | T | B)
        self.high_speed = False
        self._irq_disable = 0
        # No source counts reset's cycles (docs/timing.md); the core makes five internal cycles
        # and the two vector reads, an arbitrary and unobserved choice (C8).
        for _ in range(5):
            self._io()
        low = self._cycle_read(VECTOR_RESET)
        self.pc = self._cycle_read(VECTOR_RESET + 1) << 8 | low
        self._sync_irq()
        self._polled = NO_POLL
        self._deferred = None
        return self._cycles

    def _halted(self) -> int:
        raise NotImplementedError("the HuC6280 has no halted state")

    # -- the interrupt lines ---------------------------------------------------

    def _sync_irq(self) -> None:
        """Assert the frame's IRQ_LINE when an enabled maskable source is asserted."""
        asserted = bool(self._lines & ~self._irq_disable & 7)
        if asserted != bool(self._requests & IRQ_LINE):
            if asserted:
                self.request_maskable_interrupt()
            else:
                self.clear_maskable_interrupt()

    def set_irq_lines(self, irq1: bool, irq2: bool, tiq: bool) -> None:
        """Set the three maskable inputs (levels: they stay until the device lets go).

        IRQ1 is the VDC's, IRQ2 the HuCard connector's and the CD-ROM's, TIQ the
        timer's (pcetech 2.1). A source masked by ``irq_disable`` is remembered, not taken.
        """
        self._lines = (
            (IRQ2_BIT if irq2 else 0) | (IRQ1_BIT if irq1 else 0) | (TIQ_BIT if tiq else 0)
        )
        self._sync_irq()

    @property
    def irq_lines(self) -> tuple[bool, bool, bool]:
        """The (IRQ1, IRQ2, TIQ) levels last set."""
        lines = self._lines
        return bool(lines & IRQ1_BIT), bool(lines & IRQ2_BIT), bool(lines & TIQ_BIT)

    @property
    def irq_disable(self) -> int:
        """The interrupt disable register's bits 2-0 (IRQ2, IRQ1, TIQ; 1 = masked), as ``$1402``."""
        return self._irq_disable

    @irq_disable.setter
    def irq_disable(self, value: int) -> None:
        self._irq_disable = value & 7
        self._sync_irq()
