"""A flat 2 MB host for the directed tests (rung 3): record every cycle, no hardware.

The default map puts work RAM (physical ``$1F0000``) behind MPR1, so zero page and
stack are real memory (U1), and code behind MPR2 at logical ``$4000``.
"""

from huc6280 import HuC6280

CODE = 0x4000  # logical; MPR2 = $01 puts it at physical $002000
CODE_PHYSICAL = 0x2000
RAM = 0x1F0000  # physical: MPR1 = $F8


class Host:
    """Memory, a cycle log and the core."""

    def __init__(self, *, mpr: tuple[int, ...] = (0x00, 0xF8, 0x01, 0x02, 0x03, 0x04, 0x05, 0x00)):
        self.memory = bytearray(0x200000)
        self.cycles: list[tuple[str, int | None, int | None]] = []
        self.cpu = HuC6280(self.read_byte, self.write_byte, self.idle)
        self.cpu.mpr[:] = mpr
        self.cpu.pc = CODE
        self.cpu.s = 0xFF
        self.cpu.p = 0x04

    def read_byte(self, address: int) -> int:
        self.cycles.append(("read", address, self.memory[address]))
        return self.memory[address]

    def write_byte(self, address: int, value: int) -> None:
        self.cycles.append(("write", address, value))
        self.memory[address] = value

    def idle(self, address: int | None) -> None:
        self.cycles.append(("dummy" if address is not None else "idle", address, None))

    def load(self, program: bytes, at: int = CODE_PHYSICAL) -> None:
        self.memory[at : at + len(program)] = program

    def step(self, count: int = 1) -> int:
        total = 0
        for _ in range(count):
            total += self.cpu.step()
        return total

    def ram(self, offset: int) -> int:
        return self.memory[RAM + offset]

    def kinds(self) -> str:
        """One letter a cycle: R read, W write, d dummy read, i internal."""
        return "".join(
            {"read": "R", "write": "W", "dummy": "d", "idle": "i"}[k] for k, *_ in self.cycles
        )
