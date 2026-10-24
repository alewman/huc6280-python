"""Side-effect-free structured disassembly for the HuC6280.

The decode table is built from the opcode map the core executes
(``_dispatch.OPCODES``), so the disassembler cannot disagree with the core about
which opcode is which instruction or how it addresses memory. Syntax is the
assembler's (PCEAS, MAME's ``6280dasm`` in upper case): ``LDA #$12``, ``LDA $12``
(zero page, logical ``$2000 + $12``), ``LDA $1234,X``, ``LDA ($12,X)``,
``LDA ($12),Y``, ``LDA ($12)``, ``JMP ($1234)``, ``JMP ($1234,X)``, ``TII
$1234,$5678,$9ABC`` (source, destination, length), ``BBR0 $12,$4567`` (zero-page
byte, branch target), ``TST #$12,$34`` and branches with their 16-bit target.

Addresses are 16-bit **logical** addresses: what the program counter holds before
the mapper (docs/start-here.md).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from huc6280._dispatch import FORM_BYTES, OPCODES

ByteReader = Callable[[int], int]

#: Addressing modes, as ``Instruction.mode`` reports them.
MODES = (
    "implied",
    "accumulator",
    "immediate",
    "zero_page",
    "zero_page_x",
    "zero_page_y",
    "zero_page_indirect",
    "zero_page_indexed_indirect",
    "zero_page_indirect_indexed",
    "absolute",
    "absolute_x",
    "absolute_y",
    "absolute_indirect",
    "absolute_indexed_indirect",
    "relative",
    "zero_page_relative",
    "block_transfer",
    "immediate_zero_page",
    "immediate_zero_page_x",
    "immediate_absolute",
    "immediate_absolute_x",
)

# The dispatch's operand form -> (mode, text template). "{}" is the first operand byte(s)
# as hex; the shapes with several operands are formatted by _decode.
_FORMS = {
    "imp": ("implied", None),
    "imm": ("immediate", "#${}"),
    "zp": ("zero_page", "${}"),
    "zpx": ("zero_page_x", "${},X"),
    "zpy": ("zero_page_y", "${},Y"),
    "zpind": ("zero_page_indirect", "(${})"),
    "idx": ("zero_page_indexed_indirect", "(${},X)"),
    "idy": ("zero_page_indirect_indexed", "(${}),Y"),
    "abs": ("absolute", "${}"),
    "abx": ("absolute_x", "${},X"),
    "aby": ("absolute_y", "${},Y"),
    "ind": ("absolute_indirect", "(${})"),
    "abxind": ("absolute_indexed_indirect", "(${},X)"),
    "rel": ("relative", None),
    "zprel": ("zero_page_relative", None),
    "block": ("block_transfer", None),
    "imzp": ("immediate_zero_page", None),
    "imzpx": ("immediate_zero_page_x", None),
    "imabs": ("immediate_absolute", None),
    "imabsx": ("immediate_absolute_x", None),
}


@dataclass(frozen=True, slots=True)
class Instruction:
    """One decoded instruction and the exact bytes it occupies."""

    address: int  # 16-bit logical
    data: bytes
    mnemonic: str
    operands: tuple[str, ...] = ()
    mode: str = "implied"
    #: The address the operand names -- zero-page offset, absolute address, pointer or branch
    #: target -- before any indexing; None for implied, immediate and block-transfer forms.
    target: int | None = None

    def __post_init__(self) -> None:
        if type(self.address) is not int or not 0 <= self.address <= 0xFFFF:
            raise ValueError("address must be an integer in range 0x0000..0xFFFF")
        if type(self.data) is not bytes or not self.data:
            raise ValueError("data must contain at least one byte")
        if type(self.mnemonic) is not str or not self.mnemonic:
            raise ValueError("mnemonic must not be empty")
        if type(self.operands) is not tuple or not all(type(o) is str for o in self.operands):
            raise ValueError("operands must be a tuple of strings")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")

    @property
    def size(self) -> int:
        """Number of encoded bytes."""
        return len(self.data)

    @property
    def next_address(self) -> int:
        """The address after the instruction: PC wraps at 16 bits."""
        return (self.address + self.size) & 0xFFFF

    @property
    def text(self) -> str:
        """Canonical human-readable assembly text."""
        return self.mnemonic if not self.operands else f"{self.mnemonic} {','.join(self.operands)}"


def _form(opcode: int) -> tuple[str, str, int, str | None]:
    """(mnemonic, mode, operand bytes, template) for one opcode."""
    _handler, _mode, mnemonic, form, _cycles = OPCODES[opcode]
    if opcode in (0x0A, 0x1A, 0x2A, 0x3A, 0x4A, 0x6A):
        return mnemonic, "accumulator", 0, "A"
    mode, template = _FORMS[form]
    if opcode == 0x00:
        return mnemonic, "immediate", 1, "#${}"  # BRK's signature byte
    return mnemonic, mode, FORM_BYTES[form] - 1, template


#: (mnemonic, mode, operand bytes, template) for each of the 256 opcodes.
DECODE_TABLE: tuple[tuple[str, str, int, str | None], ...] = tuple(
    _form(opcode) for opcode in range(256)
)


def operand_size(opcode: int) -> int:
    """Operand bytes after ``opcode``."""
    return DECODE_TABLE[opcode][2]


def _signed(value: int) -> int:
    return value - 0x100 if value & 0x80 else value


def _decode(data: bytes, address: int) -> Instruction:
    mnemonic, mode, _, template = DECODE_TABLE[data[0]]
    operand = int.from_bytes(data[1:], "little")
    operands: tuple[str, ...] = ()
    target = None
    if mode == "relative":
        target = (address + len(data) + _signed(data[1])) & 0xFFFF
        operands = (f"${target:04X}",)
    elif mode == "zero_page_relative":
        target = (address + len(data) + _signed(data[2])) & 0xFFFF
        operands = (f"${data[1]:02X}", f"${target:04X}")
    elif mode == "block_transfer":
        operands = tuple(f"${int.from_bytes(data[n : n + 2], 'little'):04X}" for n in (1, 3, 5))
    elif mode.startswith("immediate_"):
        operands = (f"#${data[1]:02X}",)
        rest = data[2:]
        suffix = ",X" if mode.endswith("_x") else ""
        wide = "absolute" in mode
        operands += (f"${int.from_bytes(rest, 'little'):0{4 if wide else 2}X}{suffix}",)
        target = int.from_bytes(rest, "little")
    elif template == "A":
        operands = ("A",)
    elif template is not None:
        # Split at the commas, as 6502-python does: "($12,X)" -> "($12", "X)".
        operands = tuple(template.format(f"{operand:0{2 * len(data[1:])}X}").split(","))
        if mode != "immediate":
            target = operand
    return Instruction(address, bytes(data), mnemonic, operands, mode, target)


def disassemble(reader: ByteReader, address: int) -> Instruction:
    """Decode the instruction at logical ``address`` using only ``reader``.

    ``reader`` must be side-effect-free (a peek, not the host's bus read) and take a
    logical address. The bytes after the opcode wrap at 16 bits, as the program counter does.
    """
    if type(address) is not int or not 0 <= address <= 0xFFFF:
        raise ValueError("address must be an integer in range 0x0000..0xFFFF")
    opcode = _byte(reader, address)
    size = operand_size(opcode)
    data = bytes((opcode, *(_byte(reader, (address + n) & 0xFFFF) for n in range(1, size + 1))))
    return _decode(data, address)


def disassemble_bytes(data: Sequence[int] | bytes, address: int = 0) -> Instruction:
    """Decode exactly one instruction from ``data``, whose first byte sits at ``address``."""
    copy = bytes(data)
    if not copy:
        raise ValueError("data must not be empty")
    size = operand_size(copy[0])
    if len(copy) != 1 + size:
        raise ValueError(f"opcode ${copy[0]:02X} takes {size} operand bytes, not {len(copy) - 1}")
    return _decode(copy, address)


def disassemble_range(reader: ByteReader, address: int, count: int) -> list[Instruction]:
    """Decode ``count`` consecutive instructions."""
    listing = []
    for _ in range(count):
        instruction = disassemble(reader, address)
        listing.append(instruction)
        address = instruction.next_address
    return listing


def _byte(reader: ByteReader, address: int) -> int:
    value = reader(address)
    if type(value) is not int or not 0 <= value <= 0xFF:
        raise ValueError(f"byte reader returned a non-byte value at 0x{address:04X}")
    return value


__all__ = [
    "DECODE_TABLE",
    "MODES",
    "ByteReader",
    "Instruction",
    "disassemble",
    "disassemble_bytes",
    "disassemble_range",
    "operand_size",
]
