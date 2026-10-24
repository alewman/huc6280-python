"""Hudson's additions: SXY SAX SAY CLA CLX CLY ST0 ST1 ST2 TMA TAM CSL CSH SET TST.

None exists on the 65C02; all but the swaps and clears are about the chip's own
extras: the VDC ports, the mapper, the clock switch and the T flag.
"""

from huc6280._core import N, T, V, Z

# U12: ST0-ST2 write physical $1FE000, $1FE002 and $1FE003 whatever the mapper holds (HW HB-8,
# Table 2-2-3: A20 high, A1:A0 = 00, 10, 11; pcetech 2.0). The VDC's registers are every 4 bytes.
VDC_ADDRESS = 0x1FE000


class HudsonMixin:
    """Private implementation of the Hudson instructions."""

    def _op_sxy(self) -> None:
        """SXY -- swap X and Y (SW SB-87)."""
        self._implied()
        self._io()
        self.x, self.y = self.y, self.x

    def _op_sax(self) -> None:
        """SAX -- swap A and X (SW SB-72)."""
        self._implied()
        self._io()
        self.a, self.x = self.x, self.a

    def _op_say(self) -> None:
        """SAY -- swap A and Y (SW SB-73)."""
        self._implied()
        self._io()
        self.a, self.y = self.y, self.a

    def _op_cla(self) -> None:
        """CLA -- 00 -> A, no flags (SW SB-34)."""
        self._implied()
        self.a = 0

    def _op_clx(self) -> None:
        """CLX -- 00 -> X, no flags (SW SB-39)."""
        self._implied()
        self.x = 0

    def _op_cly(self) -> None:
        """CLY -- 00 -> Y, no flags (SW SB-40)."""
        self._implied()
        self.y = 0

    def _store_vdc(self, offset: int) -> None:
        value = self._fetch()
        self._io()
        self._cycle_write_physical(VDC_ADDRESS + offset, value)

    def _op_st0(self) -> None:
        """ST0 -- immediate -> VDC register 0, physical $1FE000 (U12) (SW SB-80)."""
        self._store_vdc(0)

    def _op_st1(self) -> None:
        """ST1 -- immediate -> VDC register 2, physical $1FE002 (U12) (SW SB-81)."""
        self._store_vdc(2)

    def _op_st2(self) -> None:
        """ST2 -- immediate -> VDC register 3, physical $1FE003 (U12) (SW SB-82)."""
        self._store_vdc(3)

    #: C6: TMA with several mask bits. Mesen ORs the registers, MAME takes the highest bit's;
    #: pcetech: "combined together... I have not figured out exactly how this works".
    #: ``"or"`` (default, emulator tier), ``"highest"`` or ``"lowest"``.
    tma_multiple = "or"

    def _op_tma(self) -> None:
        """TMAi -- the mapping register named by the mask -> A (SW SB-101)."""
        mask = self._fetch()
        self._io()
        self._io()
        if mask == 0:
            # U11: an operand of $00 returns the last value moved by TAM or TMA (pcetech 2.0).
            self.a = self._mpr_latch
            return
        chosen = [self.mpr[bit] for bit in range(8) if mask >> bit & 1]
        if self.tma_multiple == "or":
            value = 0
            for register in chosen:
                value |= register
        elif self.tma_multiple == "highest":
            value = chosen[-1]
        else:
            value = chosen[0]
        self._mpr_latch = self.a = value

    def _op_tam(self) -> None:
        """TAMi -- A -> every mapping register the mask names (SW SB-90)."""
        mask = self._fetch()
        self._io()
        self._io()
        self._io()
        if mask == 0:
            return  # U11: a mask of $00 writes nothing and leaves the latch alone
        self._mpr_latch = self.a
        for bit in range(8):
            if mask >> bit & 1:
                self.mpr[bit] = self.a

    def _speed(self, high: bool) -> None:
        self._implied()
        # C7: the new speed holds for the instruction's last cycle (Mesen, Mednafen); MAME
        # applies it after. 3 cycles when the speed does not change (pcetech 2.4, U10).
        self.high_speed = high
        self._io()

    def _op_csl(self) -> None:
        """CSL -- select the low clock speed, 1.79 MHz (HW HB-25; pcetech 2.4)."""
        self._speed(False)

    def _op_csh(self) -> None:
        """CSH -- select the high clock speed, 7.16 MHz (HW HB-25; pcetech 2.4)."""
        self._speed(True)

    def _op_set(self) -> None:
        """SET -- 1 -> T, for the next instruction only (SW SB-78)."""
        self._implied()
        # U4: the next instruction's fetch clears it again.
        self.p |= T

    def _op_tst(self, mode) -> None:
        """TST -- immediate AND M sets Z; M bits 7 and 6 -> N and V (SW SB-104)."""
        mask = self._fetch()
        address = mode(self)
        self._io()
        value = self._cycle_read(address)
        self._io()
        # U19: N and V come from the memory operand, Z from the AND.
        self.p = (self.p & ~(N | V | Z)) | (value & (N | V)) | (0 if value & mask else Z)
