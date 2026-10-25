"""Block transfers: TII TDD TIN TIA TAI (SW SB-88 to SB-100; HW HB-6; pcetech 2.0).

All five push Y, A, X, load the source, destination and length from the three
operand words, move one byte per six cycles, pop X, A, Y, for 17 + 6n cycles
(n = 0 means 65,536). The whole transfer is **one step** and cannot be
interrupted: the interrupt is taken when it ends (U6, pcetech). The shape is
Mesen's: 13 cycles of entry, ``i R i W i i`` a byte, 4 of exit (docs/timing.md).
"""

# U7: a block transfer's reads of the hardware page's $0800-$17FF (PSG, timer, port, interrupt
# registers) return 0 without touching the device, whatever is there; writes work (pcetech 2.0,
# hw-verified). The end is the parenthesis's reading, not the stated "$1400" (C9, issue 0001).
HARDWARE_ZERO_START = 0x1FE800
HARDWARE_ZERO_END = 0x1FF7FF


class BlockMixin:
    """Private block-transfer implementation."""

    #: C9: pcetech says reads of $0800-$17FF return 0 in a block transfer (hw-verified); MAME and
    #: Mednafen read the device. False reads the device like any access.
    block_reads_hardware_page_as_zero = True

    def _block_read(self, address: int) -> int:
        if (
            self.block_reads_hardware_page_as_zero
            and HARDWARE_ZERO_START <= self.physical(address) <= HARDWARE_ZERO_END
        ):
            self._dummy(address)  # the cycle happens; the device is not asked
            return 0
        return self._cycle_read(address)

    def _transfer(self, source_steps: tuple[int, ...], destination_steps: tuple[int, ...]) -> None:
        """Run one transfer; each step tuple is the per-byte increment, cycled (1, -1 alternates)."""
        self._implied()
        self._io()
        # HW HB-6: Y, then A, then X go on the stack; A, X and Y hold the low bytes while it
        # runs and come back at the end.
        self._push(self.y)
        self._push(self.a)
        self._push(self.x)
        source = self._fetch_word()
        destination = self._fetch_word()
        length = self._fetch_word() or 0x10000
        self._io()
        for index in range(length):
            self._io()
            value = self._block_read(source)
            self._io()
            self._cycle_write(destination, value)
            self._io()
            self._io()
            source = (source + source_steps[index % len(source_steps)]) & 0xFFFF
            destination = (destination + destination_steps[index % len(destination_steps)]) & 0xFFFF
        self._io()
        self.x = self._pull()
        self.a = self._pull()
        self.y = self._pull()

    def _op_tii(self) -> None:
        """TII -- transfer, source +1, destination +1 (SW SB-97)."""
        self._transfer((1,), (1,))

    def _op_tdd(self) -> None:
        """TDD -- transfer, source -1, destination -1 (SW SB-93)."""
        self._transfer((-1,), (-1,))

    def _op_tin(self) -> None:
        """TIN -- transfer, source +1, destination fixed (SW SB-99)."""
        self._transfer((1,), (0,))

    def _op_tia(self) -> None:
        """TIA -- transfer, source +1, destination alternating +1, -1 (SW SB-95)."""
        self._transfer((1,), (1, -1))

    def _op_tai(self) -> None:
        """TAI -- transfer, source alternating +1, -1, destination +1 (SW SB-88)."""
        self._transfer((1, -1), (1,))
