# SPDX-License-Identifier: MIT
"""Arithmetic, logic and compare: ADC SBC AND ORA EOR CMP CPX CPY BIT.

C13, decimal ADC and SBC (rewritten 2026-11-19, docs/restart.md). Neither Hudson manual
says what the digit adjust does with a digit above 9, and no hardware result is known, so
two emulators' behaviour is kept, each written from its own result table alone:

- ``"mednafen"`` (default): the table recorded by running Mednafen 1.32.1 (patched for
  tracing only, ``$EMU_TOOLS_GPL2/tools/mednafen/patches/mednafen-trace.patch``) as a closed box over every A, operand and
  carry (``scripts/decimal_tables.py``). OBSERVED, provisional; closed-box measurement
  (emulator tier, Mednafen 1.32.1).
- ``"mesen"``: the 11,346 decimal ADC/SBC cases of SingleStepTests huc6280 (MIT test data
  recorded from Mesen). OBSERVED, provisional; closed-box measurement (emulator tier, the
  corpus's Mesen).

The two agree whenever both digits of both inputs are 0-9. In both tables V is left as it
was and N and Z come from the stored result (TEST ROM tier for the valid digits: the
corpus and the Mednafen run agree, and both pass Dormann's and Rockwell's decimal cases).
"""

from huc6280._core import ZERO_PAGE, C, D, N, V, Z, nz

DECIMAL_FORMULAS = ("mednafen", "mesen")


def _decimal_add(a: int, operand: int, carry: int, formula: str) -> tuple[int, bool]:
    """Decimal A + M + C: the 8-bit result and the carry out."""
    low = (a & 0x0F) + (operand & 0x0F) + carry
    if formula == "mesen":
        # Each digit on its own: above 9 it gains 6, and passes a carry of 1 to the next.
        if low > 9:
            low += 6
        high = (a >> 4) + (operand >> 4) + (low > 0x0F)
        if high > 9:
            high += 6
        return (high << 4 | low & 0x0F) & 0xFF, high > 0x0F
    # Mednafen: the binary sum, plus 6 when the low digits' sum is above 9, then plus $60
    # when what stands above the low digit is above 9 (so a low digit past $1F carries 2).
    total = a + operand + carry
    if low > 9:
        total += 0x06
    if total >> 4 > 9:
        total += 0x60
    return total & 0xFF, total > 0xFF


def _decimal_subtract(a: int, operand: int, carry: int, formula: str) -> tuple[int, bool]:
    """Decimal A - M - (1 - C): the 8-bit result and the carry out (no borrow)."""
    borrow = 1 - carry
    low = (a & 0x0F) - (operand & 0x0F) - borrow
    if formula == "mesen":
        # Each digit on its own: below 0 it loses 6, and takes a borrow of 1 from the next.
        if low < 0:
            low -= 6
        high = (a >> 4) - (operand >> 4) - (low < 0)
        if high < 0:
            high -= 6
        return (high << 4 | low & 0x0F) & 0xFF, high >= 0
    # Mednafen: the binary difference, minus 6 when the low digits borrow, minus $60 when
    # the whole subtraction borrows; the carry is the binary one.
    difference = a - operand - borrow
    result = difference
    if low < 0:
        result -= 0x06
    if difference < 0:
        result -= 0x60
    return result & 0xFF, difference >= 0


def _check(formula: str) -> None:
    if formula not in DECIMAL_FORMULAS:
        raise ValueError(f"decimal_formula must be one of {DECIMAL_FORMULAS}, not {formula!r}")


def add(a: int, operand: int, p: int, formula: str = "mednafen") -> tuple[int, int]:
    """ADC: (result, new P). Binary: N V Z C as the 6502 (SW SB-17); decimal: C13 above."""
    carry = p & C
    if p & D:
        _check(formula)
        result, carry_out = _decimal_add(a, operand, carry, formula)
        return result, (p & ~(N | Z | C)) | nz(result) | (C if carry_out else 0)
    total = a + operand + carry
    result = total & 0xFF
    overflow = ~(a ^ operand) & (a ^ result) & 0x80
    p = (p & ~(N | V | Z | C)) | nz(result) | (V if overflow else 0)
    return result, p | (C if total > 0xFF else 0)


def subtract(a: int, operand: int, p: int, formula: str = "mednafen") -> tuple[int, int]:
    """SBC: (result, new P). Binary: N V Z C as the 6502 (SW SB-74); decimal: C13 above."""
    carry = p & C
    if p & D:
        _check(formula)
        result, carry_out = _decimal_subtract(a, operand, carry, formula)
        return result, (p & ~(N | Z | C)) | nz(result) | (C if carry_out else 0)
    difference = a - operand - (1 - carry)
    result = difference & 0xFF
    overflow = (a ^ operand) & (a ^ result) & 0x80
    p = (p & ~(N | V | Z | C)) | nz(result) | (V if overflow else 0)
    return result, p | (C if difference >= 0 else 0)


class ALUMixin:
    """Private arithmetic, logic and compare implementation."""

    #: C5: whether SBC honours T like ADC (False: SW and pcetech list only ORA AND EOR ADC).
    sbc_honours_t = False

    #: C13: the decimal digit adjust of ADC and SBC, ``"mednafen"`` (default) or ``"mesen"``.
    decimal_formula = "mednafen"

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
                result, self.p = operation(memory, value, self.p, self.decimal_formula)
                return result

            # The adjust's extra cycle (U14) sits among the memory-mode cycles.
            self._memory_mode(operand, combine, extra_cycle=decimal)
            return
        if decimal:
            # U14: the extra cycle. A dummy read at the next opcode, or an internal cycle for
            # SBC while T is set (it does not use the memory mode but keeps its cycle; what the
            # SingleStepTests corpus records, emulator tier).
            self._io() if self._t else self._dummy(self.pc)
        self.a, self.p = operation(self.a, operand, self.p, self.decimal_formula)

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
