"""Bit instructions: RMB SMB BBR BBS TSB TRB.

``RMBi``/``SMBi``/``BBRi``/``BBSi`` take the bit number from the opcode
(``10i + code``, SW). They are the Rockwell/WDC 65C02 additions (U22); the cycle
counts are not the 65C02's.
"""

from huc6280._core import ZERO_PAGE, N, V, Z


class BitMixin:
    """Private bit-manipulation and bit-branch implementation."""

    @property
    def _bit_mask(self) -> int:
        return 1 << (self._opcode >> 4 & 7)

    def _bit_branch(self, branch_if_set: bool) -> None:
        zp = self._fetch()
        self._io()
        offset = self._fetch()
        self._io()
        value = self._cycle_read(ZERO_PAGE | zp)
        if bool(value & self._bit_mask) == branch_if_set:
            self._io()
            self._io()
            self.pc = (self.pc + offset - ((offset & 0x80) << 1)) & 0xFFFF

    def _op_bbr(self) -> None:
        """BBRi -- branch if bit i of the zero-page byte is 0 (SW SB-20)."""
        self._bit_branch(False)

    def _op_bbs(self) -> None:
        """BBSi -- branch if bit i of the zero-page byte is 1 (SW SB-21)."""
        self._bit_branch(True)

    def _bit_write(self, address: int, clear: bool) -> None:
        value = self._cycle_read(address)
        self._io()
        self._io()
        mask = self._bit_mask
        self._cycle_write(address, value & ~mask if clear else value | mask)

    def _op_rmb(self, mode) -> None:
        """RMBi -- clear bit i of the zero-page byte (SW SB-67)."""
        self._bit_write(mode(self), clear=True)

    def _op_smb(self, mode) -> None:
        """SMBi -- set bit i of the zero-page byte (SW SB-79)."""
        self._bit_write(mode(self), clear=False)

    #: C12: what TSB and TRB's Z reports. False (default): the stored result is zero (pcetech
    #: 2.0 "Z = If result is zero", MAME, Mednafen and Mesen2's current source). True: the 65C02's
    #: A AND M is zero, which is what the SingleStepTests corpus (an older Mesen) records.
    tsb_z_from_test = False

    def _test_and_modify(self, address: int, operation) -> None:
        # N and V from the memory byte before the change (HW HB-5, SW TSB).
        value = self._cycle_read(address)
        result = operation(value)
        zero = not (value & self.a) if self.tsb_z_from_test else not result
        self.p = (self.p & ~(N | V | Z)) | (value & (N | V)) | (Z if zero else 0)
        self._io()
        self._cycle_write(address, result)

    def _op_tsb(self, mode) -> None:
        """TSB -- A OR M -> M; N and V from M, Z from the result (U23) (SW SB-103)."""
        self._test_and_modify(mode(self), lambda value: value | self.a)

    def _op_trb(self, mode) -> None:
        """TRB -- (NOT A) AND M -> M; N and V from M, Z from the result (U23) (SW SB-102)."""
        self._test_and_modify(mode(self), lambda value: value & ~self.a & 0xFF)
