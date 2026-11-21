"""Shifts, rotates, INC and DEC, on the accumulator and on memory: ASL LSR ROL ROR INC DEC.

The accumulator forms are two cycles; the memory forms read, spend an internal
cycle and write (no dummy write, unlike the NMOS 6502).
"""

from huc6280._core import C, N, Z, nz


class ShiftMixin:
    """Private shift, rotate, increment and decrement implementation."""

    def _shifted(self, result: int, carry: int) -> int:
        self.p = (self.p & ~(N | Z | C)) | nz(result) | carry
        return result & 0xFF

    def _asl(self, value: int) -> int:
        return self._shifted(value << 1, C if value & 0x80 else 0)

    def _lsr(self, value: int) -> int:
        return self._shifted(value >> 1, value & C)

    def _rol(self, value: int) -> int:
        return self._shifted(value << 1 | self.p & C, C if value & 0x80 else 0)

    def _ror(self, value: int) -> int:
        return self._shifted(value >> 1 | (self.p & C) << 7, value & C)

    def _inc(self, value: int) -> int:
        return self._set_nz((value + 1) & 0xFF)

    def _dec(self, value: int) -> int:
        return self._set_nz((value - 1) & 0xFF)

    def _accumulator(self, operation) -> None:
        self._implied()
        self.a = operation(self.a)

    def _op_asl(self, mode) -> None:
        """ASL -- shift M left, bit 7 -> C (SW SB-19)."""
        self._modify(mode(self), self._asl)

    def _op_asl_a(self) -> None:
        """ASL A -- shift A left, bit 7 -> C (SW SB-19)."""
        self._accumulator(self._asl)

    def _op_lsr(self, mode) -> None:
        """LSR -- shift M right, bit 0 -> C (SW SB-56)."""
        self._modify(mode(self), self._lsr)

    def _op_lsr_a(self) -> None:
        """LSR A -- shift A right, bit 0 -> C (SW SB-56)."""
        self._accumulator(self._lsr)

    def _op_rol(self, mode) -> None:
        """ROL -- rotate M left through C (SW SB-68)."""
        self._modify(mode(self), self._rol)

    def _op_rol_a(self) -> None:
        """ROL A -- rotate A left through C (SW SB-68)."""
        self._accumulator(self._rol)

    def _op_ror(self, mode) -> None:
        """ROR -- rotate M right through C (SW SB-69)."""
        self._modify(mode(self), self._ror)

    def _op_ror_a(self) -> None:
        """ROR A -- rotate A right through C (SW SB-69)."""
        self._accumulator(self._ror)

    def _op_inc(self, mode) -> None:
        """INC -- M + 1 -> M (SW SB-48)."""
        self._modify(mode(self), self._inc)

    def _op_inc_a(self) -> None:
        """INC A -- A + 1 -> A (SW SB-48)."""
        self._accumulator(self._inc)

    def _op_dec(self, mode) -> None:
        """DEC -- M - 1 -> M (SW SB-44)."""
        self._modify(mode(self), self._dec)

    def _op_dec_a(self) -> None:
        """DEC A -- A - 1 -> A (SW SB-44)."""
        self._accumulator(self._dec)
