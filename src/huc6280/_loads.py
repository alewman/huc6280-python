"""Loads, stores, register transfers and the index counters: LDA LDX LDY STA STX STY STZ
TAX TAY TXA TYA TSX TXS INX INY DEX DEY.

The implied ones are two cycles, the opcode fetch and a dummy read of the byte after it.
"""


class LoadMixin:
    """Private load, store and transfer implementation."""

    def _op_lda(self, mode) -> None:
        """LDA -- M -> A (SW SB-53)."""
        self.a = self._set_nz(self._load(mode(self)))

    def _op_ldx(self, mode) -> None:
        """LDX -- M -> X (SW SB-54)."""
        self.x = self._set_nz(self._load(mode(self)))

    def _op_ldy(self, mode) -> None:
        """LDY -- M -> Y (SW SB-55)."""
        self.y = self._set_nz(self._load(mode(self)))

    def _op_sta(self, mode) -> None:
        """STA -- A -> M (SW SB-83)."""
        self._store(mode(self), self.a)

    def _op_stx(self, mode) -> None:
        """STX -- X -> M (SW SB-84)."""
        self._store(mode(self), self.x)

    def _op_sty(self, mode) -> None:
        """STY -- Y -> M (SW SB-85)."""
        self._store(mode(self), self.y)

    def _op_stz(self, mode) -> None:
        """STZ -- 00 -> M (SW SB-86)."""
        self._store(mode(self), 0)

    def _op_tax(self) -> None:
        """TAX -- A -> X (SW SB-91)."""
        self._implied()
        self.x = self._set_nz(self.a)

    def _op_tay(self) -> None:
        """TAY -- A -> Y (SW SB-92)."""
        self._implied()
        self.y = self._set_nz(self.a)

    def _op_txa(self) -> None:
        """TXA -- X -> A (SW SB-106)."""
        self._implied()
        self.a = self._set_nz(self.x)

    def _op_tya(self) -> None:
        """TYA -- Y -> A (SW SB-108)."""
        self._implied()
        self.a = self._set_nz(self.y)

    def _op_tsx(self) -> None:
        """TSX -- S -> X (SW SB-105)."""
        self._implied()
        self.x = self._set_nz(self.s)

    def _op_txs(self) -> None:
        """TXS -- X -> S; no flags (SW SB-107)."""
        self._implied()
        self.s = self.x

    def _op_inx(self) -> None:
        """INX -- X + 1 -> X (SW SB-49)."""
        self._implied()
        self.x = self._set_nz((self.x + 1) & 0xFF)

    def _op_iny(self) -> None:
        """INY -- Y + 1 -> Y (SW SB-50)."""
        self._implied()
        self.y = self._set_nz((self.y + 1) & 0xFF)

    def _op_dex(self) -> None:
        """DEX -- X - 1 -> X (SW SB-45)."""
        self._implied()
        self.x = self._set_nz((self.x - 1) & 0xFF)

    def _op_dey(self) -> None:
        """DEY -- Y - 1 -> Y (SW SB-46)."""
        self._implied()
        self.y = self._set_nz((self.y - 1) & 0xFF)
