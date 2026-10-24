"""A minimal PC Engine-shaped host for the core: a HuCard, work RAM and a stubbed hardware page.

Not a PC Engine (that is pcengine-python's job): no VDC, VCE, PSG, timer or CD-ROM,
and no interrupts of its own. It is what rungs 1 to 4 and ``python -m huc6280``
need (docs/validation.md, "The minimal harness"):

- a flat 2 MB physical space: HuCard ROM in pages ``$00-$7F`` (mirrored as Mesen2
  mirrors odd sizes; zero-filled when there is no ROM), work RAM in pages ``$F8-$FB``
  (8 KB mirrored four times, or 32 KB on a SuperGrafx), the hardware page in
  ``$FF``, and ``$FF`` read from everything else (start-here.md);
- page ``$F7`` (backup RAM on a CD-ROM unit) answered by ``bank_read``, ``$FF`` by default;
- the hardware page answered by ``io_read(offset)`` / ``io_write(offset, value)``
  callables (the defaults give a joypad port with nothing pressed and zeros from
  the video chips); rung 4 passes a callable that answers from MAME's log;
- MPR7 = 0 at reset, so the reset vector is read from physical ``$001FFE``;
- master-clock accounting: each callback is 12 master clocks at low speed and 3 at
  high speed (``cpu.high_speed``), plus the one-cycle stretch on a VDC or VCE access
  (pcetech 3 note 3; the board's job on a console, done here so the cycle counts can be
  compared with MAME's), in ``master_clocks``.

The ``.pce`` loader drops a 512-byte copier header (size = 512 mod 8,192) and takes the
first ``.pce``/``.sgx``/``.bin`` of a ``.zip`` or ``.7z``.
"""

from __future__ import annotations

import subprocess
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from huc6280.cpu import HuC6280

IoRead = Callable[[int], int]
IoWrite = Callable[[int, int], None]

HARDWARE_PAGE = 0x1FE000  # physical; offsets $0000-$1FFF within it
RAM_BASE = 0x1F0000
VDC_VCE_MASK = 0x1FF800  # (address & mask) == $1FE000: VDC ($0000-$03FF) and VCE ($0400-$07FF)
ROM_SUFFIXES = (".pce", ".sgx", ".bin")


@dataclass
class RunResult:
    """Why :meth:`Harness.run` stopped, and when."""

    reason: str  # "spin", "condition" or "cycles"
    cycles: int
    pc: int  # logical


def load_rom(path: str | Path) -> bytes:
    """A HuCard image from a ``.pce``/``.sgx``/``.bin``, or the first one inside a ``.zip`` or
    ``.7z`` (7z through the ``7z`` program), without the 512-byte copier header."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            names = sorted(n for n in archive.namelist() if n.lower().endswith(ROM_SUFFIXES))
            if not names:
                raise ValueError(f"no .pce/.sgx/.bin in {path}")
            data = archive.read(names[0])
    elif suffix == ".7z":
        with tempfile.TemporaryDirectory() as scratch:
            subprocess.run(
                ["7z", "e", "-y", f"-o{scratch}", str(path)], check=True, stdout=subprocess.DEVNULL
            )
            inside = sorted(p for p in Path(scratch).iterdir() if p.suffix.lower() in ROM_SUFFIXES)
            if not inside:
                raise ValueError(f"no .pce/.sgx/.bin in {path}")
            data = inside[0].read_bytes()
    else:
        data = path.read_bytes()
    return data[512:] if len(data) % 8192 == 512 else data


def bank_offsets(banks: int) -> tuple[int, ...]:
    """Where in the ROM (in 8 KB banks) each sixteenth of the 128 ROM pages starts.

    Mesen2's mirroring (``PceMemoryManager``; emulator tier): 384 KB, 512 KB and 768 KB
    cards are mirrored in their conventional shapes, anything else repeats from the start.
    """
    if banks == 0x30:
        return (0, 0x10, 0, 0x10, 0x20, 0x20, 0x20, 0x20)
    if banks == 0x40:
        return (0, 0x10, 0x20, 0x30, 0x20, 0x30, 0x20, 0x30)
    if banks == 0x60:
        return (0, 0x10, 0x20, 0x30, 0x40, 0x50, 0x40, 0x50)
    return (0, 0x10, 0x20, 0x30, 0x40, 0x50, 0x60, 0x70)


class Harness:
    """Run a HuCard on a :class:`~huc6280.cpu.HuC6280` with RAM and a stubbed hardware page.

    ``cpu`` is the core with a reset requested, ready to :meth:`run` (the first
    ``step()`` runs the start sequence). ``ram`` is a bytearray the program's results can
    be read from; ``io_log`` collects every ``(physical address, value, "r"/"w")`` on the
    hardware page when ``log_io`` is set.
    """

    def __init__(
        self,
        rom: bytes = b"",
        *,
        io_read: IoRead | None = None,
        io_write: IoWrite | None = None,
        bank_read: Callable[[int], int] | None = None,
        supergrafx: bool = False,
        log_io: bool = False,
    ) -> None:
        self.rom = bytes(rom)
        self.ram = bytearray(0x8000 if supergrafx else 0x2000)
        self._ram_mask = len(self.ram) - 1
        self.io_read = io_read or self._default_io_read
        self.io_write = io_write or self._default_io_write
        #: Reads of page $F7 (``$1EE000-$1EFFFF``), where a CD-ROM unit's backup RAM sits and
        #: nothing else does on a bare HuCard system: a board's, answered by ``bank_read(address)``.
        self.bank_read = bank_read or (lambda address: 0xFF)
        self.log_io = log_io
        self.io_log: list[tuple[int, int, str]] = []
        self.open_bus = 0xFF
        self.cycles = 0
        self.master_clocks = 0
        banks = len(self.rom) // 0x2000
        offsets = bank_offsets(banks)
        self._rom_banks = (
            [(offsets[page >> 4] + (page & 0x0F)) % banks for page in range(0x80)] if banks else []
        )
        self.cpu = HuC6280(self.read_byte, self.write_byte, self.idle)
        self.cpu.request_reset()

    # -- the bus ---------------------------------------------------------

    def _tick(self, address: int | None) -> None:
        self.cycles += 1
        # 12 master clocks a CPU cycle at 1.79 MHz, 3 at 7.16 MHz (start-here.md, "The clock").
        per_cycle = 3 if self.cpu.high_speed else 12
        # The VDC/VCE stretch: one extra cycle on any access there (U18), the board's job.
        if address is not None and address & VDC_VCE_MASK == HARDWARE_PAGE:
            per_cycle *= 2
        self.master_clocks += per_cycle

    def read_byte(self, address: int) -> int:
        self._tick(address)
        value = self.peek(address, side_effects=True)
        self.open_bus = value
        return value

    def write_byte(self, address: int, value: int) -> None:
        self._tick(address)
        self.open_bus = value
        self.poke(address, value)

    def idle(self, address: int | None) -> None:
        self._tick(address)

    def peek(self, address: int, *, side_effects: bool = False) -> int:
        """The byte at a physical address as the bus would give it.

        ``side_effects=False`` (a debugger's view) answers the hardware page with
        ``$FF`` instead of asking ``io_read``.
        """
        page = address >> 13
        if page < 0x80:
            if not self._rom_banks:
                return 0xFF
            bank = self._rom_banks[page]
            return self.rom[bank << 13 | address & 0x1FFF]
        if 0xF8 <= page <= 0xFB:
            return self.ram[address & self._ram_mask]
        if page == 0xF7 and side_effects:
            return self.bank_read(address)
        if page == 0xFF:
            if not side_effects:
                return 0xFF
            value = self.io_read(address & 0x1FFF)
            if self.log_io:
                self.io_log.append((address, value, "r"))
            return value
        return 0xFF

    def poke(self, address: int, value: int) -> None:
        page = address >> 13
        if 0xF8 <= page <= 0xFB:
            self.ram[address & self._ram_mask] = value
        elif page == 0xFF:
            if self.log_io:
                self.io_log.append((address, value, "w"))
            self.io_write(address & 0x1FFF, value)

    # -- the hardware page stub ----------------------------------------------

    def _default_io_read(self, offset: int) -> int:
        if 0x1000 <= offset < 0x1400:
            return 0xBF  # port K: no button pressed, bit 6 set (a PC Engine, not a TurboGrafx-16)
        if offset < 0x0800:
            return 0  # VDC, VCE: nothing there
        return self.open_bus  # PSG, timer, interrupt registers: the I/O buffer (U13), roughly

    def _default_io_write(self, offset: int, value: int) -> None:
        """The stub discards writes."""

    # -- running -----------------------------------------------------------

    def run(
        self,
        max_cycles: int,
        until: Callable[[Harness], bool] | None = None,
        step: Callable[[], object] | None = None,
    ) -> RunResult:
        """Step until the program spins on a jump to itself, ``until(self)`` (checked after each
        instruction) or ``max_cycles`` more CPU cycles. ``step`` replaces ``cpu.step`` (a debug
        session's, to trace the run)."""
        cpu = self.cpu
        step = cpu.step if step is None else step
        limit = self.cycles + max_cycles
        reason = "cycles"
        while self.cycles < limit:
            before = cpu.pc
            step()
            if cpu.pc == before and self._spinning(before):
                reason = "spin"
                break
            if until is not None and until(self):
                reason = "condition"
                break
        return RunResult(reason, self.cycles, cpu.pc)

    def _spinning(self, pc: int) -> bool:
        """Whether the instruction at logical ``pc`` is a jump or branch to itself."""
        opcode = self.peek(self.cpu.physical(pc))
        return opcode in (0x4C, 0x80)  # JMP abs, BRA
