"""Arithmetic, logic, compare and bit test: ADC SBC AND ORA EOR CMP CPX CPY BIT.

``ORA``, ``AND``, ``EOR`` and ``ADC`` honour the T flag (U4): with T set the
accumulator is replaced by the zero-page byte at X (logical ``$2000 + X``),
the result goes back there, A is untouched and the instruction takes three
more cycles (read, internal, write). ``SBC`` does not (C5: SW's entry has no T
clause; MAME's yes is a guess), unless ``sbc_honours_t`` is set.

Decimal mode (U14, HW HB-4, SW ``ADC``): one more cycle, N, Z and C taken from
the decimal result, **V left alone**. The digit adjust below is Mesen's
(``PceCpu::ADD``/``SUB``, emulator tier), checked against the 640,000-case
corpus at rung 1: neither manual says how invalid digits adjust.
"""

from huc6280._core import ZERO_PAGE, C, D, N, V, Z, nz


def add(a: int, operand: int, p: int) -> tuple[int, int]:
    """A + operand + C, binary or decimal; return (result, P)."""
    carry = p & C
    if p & D:
        # U14: low digit adjusted (+6 past 9) before its carry enters the high digit.
        low = (a & 0x0F) + (operand & 0x0F) + carry
        if low > 0x09:
            low += 0x06
        result = (a & 0xF0) + (operand & 0xF0) + (0x10 if low > 0x0F else 0) + (low & 0x0F)
        if result > 0x9F:
            result += 0x60
        p &= ~(N | Z | C)  # V is unchanged in decimal mode (U14)
    else:
        result = a + operand + carry
        p &= ~(N | V | Z | C)
        if ~(a ^ operand) & (a ^ result) & 0x80:
            p |= V
    if result > 0xFF:
        p |= C
    return result & 0xFF, p | nz(result)


def subtract(a: int, operand: int, p: int) -> tuple[int, int]:
    """A - operand - (1 - C), binary or decimal; return (result, P)."""
    carry = p & C
    inverted = ~operand & 0xFF
    if p & D:
        # U14: Mesen's SUB; the adjust subtracts 6 and $60 where no carry came out.
        low = (a & 0x0F) + (inverted & 0x0F) + carry
        if low <= 0x0F:
            low -= 0x06
        result = (a & 0xF0) + (inverted & 0xF0) + (0x10 if low > 0x0F else 0) + (low & 0x0F)
        if result <= 0xFF:
            result -= 0x60
        p &= ~(N | Z | C)
    else:
        result = a + inverted + carry
        p &= ~(N | V | Z | C)
        if ~(a ^ inverted) & (a ^ result) & 0x80:
            p |= V
    if result > 0xFF:
        p |= C
    return result & 0xFF, p | nz(result)


class ALUMixin:
    """Private arithmetic, logic and compare implementation."""

    #: C5: whether SBC honours T like ADC (False: SW and pcetech list only ORA AND EOR ADC).
    sbc_honours_t = False

    def _memory_mode(self, operand: int, operation, extra_cycle: bool = False) -> None:
        """U4: T set, so the operation's other operand is M($2000 + X) and the result goes back.

        The three extra cycles are a read, an internal cycle (two in decimal
        mode, where the adjust takes one more) and a write.
        """
        address = ZERO_PAGE | self.x
        memory = self._cycle_read(address)
        self._io()
        if extra_cycle:
            self._io()
        result = operation(memory, operand)
        self._set_nz(result)
        self._cycle_write(address, result)

    def _op_ora(self, mode) -> None:
        """ORA -- A OR M -> A, or M(X) OR M -> M(X) with T set (SW SB-58)."""
        operand = self._load(mode(self))
        if self._t:
            self._memory_mode(operand, lambda memory, value: memory | value)
        else:
            self.a = self._set_nz(self.a | operand)

    def _op_and(self, mode) -> None:
        """AND -- A AND M -> A, or M(X) AND M -> M(X) with T set (SW SB-18)."""
        operand = self._load(mode(self))
        if self._t:
            self._memory_mode(operand, lambda memory, value: memory & value)
        else:
            self.a = self._set_nz(self.a & operand)

    def _op_eor(self, mode) -> None:
        """EOR -- A EOR M -> A, or M(X) EOR M -> M(X) with T set (SW SB-47)."""
        operand = self._load(mode(self))
        if self._t:
            self._memory_mode(operand, lambda memory, value: memory ^ value)
        else:
            self.a = self._set_nz(self.a ^ operand)

    def _arithmetic(self, mode, operation, uses_t: bool) -> None:
        operand = self._load(mode(self))
        decimal = bool(self.p & D)
        if uses_t and self._t:

            def combine(memory: int, value: int) -> int:
                result, self.p = operation(memory, value, self.p)
                return result

            # The adjust's extra cycle (U14) sits among the memory-mode cycles.
            self._memory_mode(operand, combine, extra_cycle=decimal)
            return
        if decimal:
            # U14: the extra cycle. A dummy read at the next opcode, or an internal cycle for
            # SBC while T is set (it does not use the memory mode but keeps its cycle; Mesen).
            self._io() if self._t else self._dummy(self.pc)
        self.a, self.p = operation(self.a, operand, self.p)

    def _op_adc(self, mode) -> None:
        """ADC -- A + M + C -> A, or M(X) + M + C -> M(X) with T set (SW SB-17)."""
        self._arithmetic(mode, add, uses_t=True)

    def _op_sbc(self, mode) -> None:
        """SBC -- A - M - (1 - C) -> A; T is ignored (C5) (SW SB-74)."""
        self._arithmetic(mode, subtract, uses_t=self.sbc_honours_t)

    def _compare(self, register: int, operand: int) -> None:
        difference = register - operand
        p = self.p & ~(N | Z | C)
        if register >= operand:
            p |= C
        self.p = p | nz(difference)

    def _op_cmp(self, mode) -> None:
        """CMP -- A - M, flags only (SW SB-41)."""
        self._compare(self.a, self._load(mode(self)))

    def _op_cpx(self, mode) -> None:
        """CPX -- X - M, flags only (SW SB-42)."""
        self._compare(self.x, self._load(mode(self)))

    def _op_cpy(self, mode) -> None:
        """CPY -- Y - M, flags only (SW SB-43)."""
        self._compare(self.y, self._load(mode(self)))

    def _bit_flags(self, operand: int, mask_with: int) -> None:
        # U19: N and V come from the operand, Z from the AND; HW HB-5, SW BIT.
        p = (self.p & ~(N | V | Z)) | (operand & (N | V))
        if not mask_with & operand:
            p |= Z
        self.p = p

    def _op_bit(self, mode) -> None:
        """BIT -- A AND M sets Z; M bits 7 and 6 -> N and V, immediate form too (U19) (SW SB-25)."""
        self._bit_flags(self._load(mode(self)), self.a)
