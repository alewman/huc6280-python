"""Hudson's HuC6280 Software Manual, instruction by instruction: manufacturer tier.

Typed from the manual's own instruction pages (``reference/docs/
huc6280-software-manual.pdf``, "SB-n" page labels; the scan's OCR text has
damaged mnemonics and some machine-code digits, but its byte and cycle
columns read cleanly) and from section 4's tables. This is the judge of
rung 0; the opcode map in ``huc6280._dispatch`` is checked against it, not
the other way round, and no value here was taken from an emulator.

Each row is ``(mnemonic, mode, machine code, bytes, cycles, page)``. The mode
is the manual's own abbreviation (SW section 3). Machine code is one opcode,
or for the families written ``10i + 87`` an opcode for bit 0 (the others are
that plus ``0x10 * i``). Cycles are the manual's base figure: it adds 2 for a
taken branch, 1 for ``ADC``/``SBC`` in decimal mode, 3 for the T-flag forms of
``ORA``/``AND``/``EOR``/``ADC``, and the block transfers are ``17 + 6n``.

``CSL`` and ``CSH`` have no entry in SW's text: their rows come from the
hardware manual's instruction map (HW HB-25), which gives the opcodes, and
from pcetech 2.4 for the 3 cycles (U10), and are marked ``HW``.
"""

#: (mnemonic, mode, opcode, bytes, cycles, page)
ROWS: list[tuple[str, str, int, int, int, str]] = [
    ("ADC", "IMM", 0x69, 2, 2, "SB-17"), ("ADC", "ZP", 0x65, 2, 4, "SB-17"),
    ("ADC", "ZP,X", 0x75, 2, 4, "SB-17"), ("ADC", "(IND)", 0x72, 2, 7, "SB-17"),
    ("ADC", "(IND,X)", 0x61, 2, 7, "SB-17"), ("ADC", "(IND),Y", 0x71, 2, 7, "SB-17"),
    ("ADC", "ABS", 0x6D, 3, 5, "SB-17"), ("ADC", "ABS,X", 0x7D, 3, 5, "SB-17"),
    ("ADC", "ABS,Y", 0x79, 3, 5, "SB-17"),
    ("AND", "IMM", 0x29, 2, 2, "SB-18"), ("AND", "ZP", 0x25, 2, 4, "SB-18"),
    ("AND", "ZP,X", 0x35, 2, 4, "SB-18"), ("AND", "(IND)", 0x32, 2, 7, "SB-18"),
    ("AND", "(IND,X)", 0x21, 2, 7, "SB-18"), ("AND", "(IND),Y", 0x31, 2, 7, "SB-18"),
    ("AND", "ABS", 0x2D, 3, 5, "SB-18"), ("AND", "ABS,X", 0x3D, 3, 5, "SB-18"),
    ("AND", "ABS,Y", 0x39, 3, 5, "SB-18"),
    ("ASL", "ZP", 0x06, 2, 6, "SB-19"), ("ASL", "ZP,X", 0x16, 2, 6, "SB-19"),
    ("ASL", "ABS", 0x0E, 3, 7, "SB-19"), ("ASL", "ABS,X", 0x1E, 3, 7, "SB-19"),
    ("ASL", "ACC", 0x0A, 1, 2, "SB-19"),
    ("BBR", "ZP,REL", 0x0F, 3, 6, "SB-20"), ("BBS", "ZP,REL", 0x8F, 3, 6, "SB-21"),
    ("BCC", "REL", 0x90, 2, 2, "SB-22"), ("BCS", "REL", 0xB0, 2, 2, "SB-23"),
    ("BEQ", "REL", 0xF0, 2, 2, "SB-24"),
    ("BIT", "IMM", 0x89, 2, 2, "SB-25"), ("BIT", "ZP", 0x24, 2, 4, "SB-25"),
    ("BIT", "ZP,X", 0x34, 2, 4, "SB-25"), ("BIT", "ABS", 0x2C, 3, 5, "SB-25"),
    ("BIT", "ABS,X", 0x3C, 3, 5, "SB-25"),
    ("BMI", "REL", 0x30, 2, 2, "SB-26"), ("BNE", "REL", 0xD0, 2, 2, "SB-27"),
    ("BPL", "REL", 0x10, 2, 2, "SB-28"), ("BRA", "REL", 0x80, 2, 4, "SB-29"),
    # C2: the manual's table lists BRK as one byte; its own text and every emulator say two.
    ("BRK", "IMPLID", 0x00, 1, 8, "SB-30"),
    ("BSR", "REL", 0x44, 2, 8, "SB-31"),
    ("BVC", "REL", 0x50, 2, 2, "SB-32"), ("BVS", "REL", 0x70, 2, 2, "SB-33"),
    ("CLA", "IMPLID", 0x62, 1, 2, "SB-34"), ("CLC", "IMPLID", 0x18, 1, 2, "SB-35"),
    ("CLD", "IMPLID", 0xD8, 1, 2, "SB-36"), ("CLI", "IMPLID", 0x58, 1, 2, "SB-37"),
    ("CLV", "IMPLID", 0xB8, 1, 2, "SB-38"), ("CLX", "IMPLID", 0x82, 1, 2, "SB-39"),
    ("CLY", "IMPLID", 0xC2, 1, 2, "SB-40"),
    ("CMP", "IMM", 0xC9, 2, 2, "SB-41"), ("CMP", "ZP", 0xC5, 2, 4, "SB-41"),
    ("CMP", "ZP,X", 0xD5, 2, 4, "SB-41"), ("CMP", "(IND)", 0xD2, 2, 7, "SB-41"),
    ("CMP", "(IND,X)", 0xC1, 2, 7, "SB-41"), ("CMP", "(IND),Y", 0xD1, 2, 7, "SB-41"),
    ("CMP", "ABS", 0xCD, 3, 5, "SB-41"), ("CMP", "ABS,X", 0xDD, 3, 5, "SB-41"),
    ("CMP", "ABS,Y", 0xD9, 3, 5, "SB-41"),
    ("CPX", "IMM", 0xE0, 2, 2, "SB-42"), ("CPX", "ZP", 0xE4, 2, 4, "SB-42"),
    ("CPX", "ABS", 0xEC, 3, 5, "SB-42"),
    ("CPY", "IMM", 0xC0, 2, 2, "SB-43"), ("CPY", "ZP", 0xC4, 2, 4, "SB-43"),
    ("CPY", "ABS", 0xCC, 3, 5, "SB-43"),
    ("CSH", "IMPLID", 0xD4, 1, 3, "HW HB-25"), ("CSL", "IMPLID", 0x54, 1, 3, "HW HB-25"),
    ("DEC", "ZP", 0xC6, 2, 6, "SB-44"), ("DEC", "ZP,X", 0xD6, 2, 6, "SB-44"),
    ("DEC", "ABS", 0xCE, 3, 7, "SB-44"), ("DEC", "ABS,X", 0xDE, 3, 7, "SB-44"),
    ("DEC", "ACC", 0x3A, 1, 2, "SB-44"),
    ("DEX", "IMPLID", 0xCA, 1, 2, "SB-45"), ("DEY", "IMPLID", 0x88, 1, 2, "SB-46"),
    ("EOR", "IMM", 0x49, 2, 2, "SB-47"), ("EOR", "ZP", 0x45, 2, 4, "SB-47"),
    ("EOR", "ZP,X", 0x55, 2, 4, "SB-47"), ("EOR", "(IND)", 0x52, 2, 7, "SB-47"),
    ("EOR", "(IND,X)", 0x41, 2, 7, "SB-47"), ("EOR", "(IND),Y", 0x51, 2, 7, "SB-47"),
    ("EOR", "ABS", 0x4D, 3, 5, "SB-47"), ("EOR", "ABS,X", 0x5D, 3, 5, "SB-47"),
    ("EOR", "ABS,Y", 0x59, 3, 5, "SB-47"),
    ("INC", "ZP", 0xE6, 2, 6, "SB-48"), ("INC", "ZP,X", 0xF6, 2, 6, "SB-48"),
    ("INC", "ABS", 0xEE, 3, 7, "SB-48"), ("INC", "ABS,X", 0xFE, 3, 7, "SB-48"),
    ("INC", "ACC", 0x1A, 1, 2, "SB-48"),
    ("INX", "IMPLID", 0xE8, 1, 2, "SB-49"), ("INY", "IMPLID", 0xC8, 1, 2, "SB-50"),
    ("JMP", "ABS", 0x4C, 3, 4, "SB-51"), ("JMP", "(ABS)", 0x6C, 3, 7, "SB-51"),
    ("JMP", "(ABS,X)", 0x7C, 3, 7, "SB-51"),
    ("JSR", "ABS", 0x20, 3, 7, "SB-52"),
    ("LDA", "IMM", 0xA9, 2, 2, "SB-53"), ("LDA", "ZP", 0xA5, 2, 4, "SB-53"),
    ("LDA", "ZP,X", 0xB5, 2, 4, "SB-53"), ("LDA", "(IND)", 0xB2, 2, 7, "SB-53"),
    ("LDA", "(IND,X)", 0xA1, 2, 7, "SB-53"), ("LDA", "(IND),Y", 0xB1, 2, 7, "SB-53"),
    ("LDA", "ABS", 0xAD, 3, 5, "SB-53"), ("LDA", "ABS,X", 0xBD, 3, 5, "SB-53"),
    ("LDA", "ABS,Y", 0xB9, 3, 5, "SB-53"),
    ("LDX", "IMM", 0xA2, 2, 2, "SB-54"), ("LDX", "ZP", 0xA6, 2, 4, "SB-54"),
    ("LDX", "ZP,Y", 0xB6, 2, 4, "SB-54"), ("LDX", "ABS", 0xAE, 3, 5, "SB-54"),
    ("LDX", "ABS,Y", 0xBE, 3, 5, "SB-54"),
    ("LDY", "IMM", 0xA0, 2, 2, "SB-55"), ("LDY", "ZP", 0xA4, 2, 4, "SB-55"),
    ("LDY", "ZP,X", 0xB4, 2, 4, "SB-55"), ("LDY", "ABS", 0xAC, 3, 5, "SB-55"),
    ("LDY", "ABS,X", 0xBC, 3, 5, "SB-55"),
    ("LSR", "ZP", 0x46, 2, 6, "SB-56"), ("LSR", "ZP,X", 0x56, 2, 6, "SB-56"),
    ("LSR", "ABS", 0x4E, 3, 7, "SB-56"), ("LSR", "ABS,X", 0x5E, 3, 7, "SB-56"),
    ("LSR", "ACC", 0x4A, 1, 2, "SB-56"),
    ("NOP", "IMPLID", 0xEA, 1, 2, "SB-57"),
    ("ORA", "IMM", 0x09, 2, 2, "SB-58"), ("ORA", "ZP", 0x05, 2, 4, "SB-58"),
    ("ORA", "ZP,X", 0x15, 2, 4, "SB-58"), ("ORA", "(IND)", 0x12, 2, 7, "SB-58"),
    ("ORA", "(IND,X)", 0x01, 2, 7, "SB-58"), ("ORA", "(IND),Y", 0x11, 2, 7, "SB-58"),
    ("ORA", "ABS", 0x0D, 3, 5, "SB-58"), ("ORA", "ABS,X", 0x1D, 3, 5, "SB-58"),
    ("ORA", "ABS,Y", 0x19, 3, 5, "SB-58"),
    ("PHA", "IMPLID", 0x48, 1, 3, "SB-59"), ("PHP", "IMPLID", 0x08, 1, 3, "SB-60"),
    ("PHX", "IMPLID", 0xDA, 1, 3, "SB-61"), ("PHY", "IMPLID", 0x5A, 1, 3, "SB-62"),
    ("PLA", "IMPLID", 0x68, 1, 4, "SB-63"), ("PLP", "IMPLID", 0x28, 1, 4, "SB-64"),
    ("PLX", "IMPLID", 0xFA, 1, 4, "SB-65"), ("PLY", "IMPLID", 0x7A, 1, 4, "SB-66"),
    ("RMB", "ZP", 0x07, 2, 7, "SB-67"),
    ("ROL", "ZP", 0x26, 2, 6, "SB-68"), ("ROL", "ZP,X", 0x36, 2, 6, "SB-68"),
    ("ROL", "ABS", 0x2E, 3, 7, "SB-68"), ("ROL", "ABS,X", 0x3E, 3, 7, "SB-68"),
    ("ROL", "ACC", 0x2A, 1, 2, "SB-68"),
    ("ROR", "ZP", 0x66, 2, 6, "SB-69"), ("ROR", "ZP,X", 0x76, 2, 6, "SB-69"),
    ("ROR", "ABS", 0x6E, 3, 7, "SB-69"), ("ROR", "ABS,X", 0x7E, 3, 7, "SB-69"),
    ("ROR", "ACC", 0x6A, 1, 2, "SB-69"),
    ("RTI", "IMPLID", 0x40, 1, 7, "SB-70"), ("RTS", "IMPLID", 0x60, 1, 7, "SB-71"),
    ("SAX", "IMPLID", 0x22, 1, 3, "SB-72"), ("SAY", "IMPLID", 0x42, 1, 3, "SB-73"),
    ("SBC", "IMM", 0xE9, 2, 2, "SB-74"), ("SBC", "ZP", 0xE5, 2, 4, "SB-74"),
    ("SBC", "ZP,X", 0xF5, 2, 4, "SB-74"), ("SBC", "(IND)", 0xF2, 2, 7, "SB-74"),
    ("SBC", "(IND,X)", 0xE1, 2, 7, "SB-74"), ("SBC", "(IND),Y", 0xF1, 2, 7, "SB-74"),
    ("SBC", "ABS", 0xED, 3, 5, "SB-74"), ("SBC", "ABS,X", 0xFD, 3, 5, "SB-74"),
    ("SBC", "ABS,Y", 0xF9, 3, 5, "SB-74"),
    ("SEC", "IMPLID", 0x38, 1, 2, "SB-75"), ("SED", "IMPLID", 0xF8, 1, 2, "SB-76"),
    ("SEI", "IMPLID", 0x78, 1, 2, "SB-77"), ("SET", "IMPLID", 0xF4, 1, 2, "SB-78"),
    ("SMB", "ZP", 0x87, 2, 7, "SB-79"),
    ("ST0", "IMM", 0x03, 2, 4, "SB-80"), ("ST1", "IMM", 0x13, 2, 4, "SB-81"),
    ("ST2", "IMM", 0x23, 2, 4, "SB-82"),
    ("STA", "ZP", 0x85, 2, 4, "SB-83"), ("STA", "ZP,X", 0x95, 2, 4, "SB-83"),
    ("STA", "(IND)", 0x92, 2, 7, "SB-83"), ("STA", "(IND,X)", 0x81, 2, 7, "SB-83"),
    ("STA", "(IND),Y", 0x91, 2, 7, "SB-83"), ("STA", "ABS", 0x8D, 3, 5, "SB-83"),
    ("STA", "ABS,X", 0x9D, 3, 5, "SB-83"), ("STA", "ABS,Y", 0x99, 3, 5, "SB-83"),
    ("STX", "ZP", 0x86, 2, 4, "SB-84"), ("STX", "ZP,Y", 0x96, 2, 4, "SB-84"),
    ("STX", "ABS", 0x8E, 3, 5, "SB-84"),
    ("STY", "ZP", 0x84, 2, 4, "SB-85"), ("STY", "ZP,X", 0x94, 2, 4, "SB-85"),
    ("STY", "ABS", 0x8C, 3, 5, "SB-85"),
    ("STZ", "ZP", 0x64, 2, 4, "SB-86"), ("STZ", "ZP,X", 0x74, 2, 4, "SB-86"),
    ("STZ", "ABS", 0x9C, 3, 5, "SB-86"), ("STZ", "ABS,X", 0x9E, 3, 5, "SB-86"),
    ("SXY", "IMPLID", 0x02, 1, 3, "SB-87"),
    # Block transfers: 7 bytes, 17 + 6n cycles; the cycles column here is the fixed 17.
    ("TAI", "BLOCK", 0xF3, 7, 17, "SB-88"), ("TAM", "IMPLID", 0x53, 2, 5, "SB-90"),
    ("TAX", "IMPLID", 0xAA, 1, 2, "SB-91"), ("TAY", "IMPLID", 0xA8, 1, 2, "SB-92"),
    ("TDD", "BLOCK", 0xC3, 7, 17, "SB-93"), ("TIA", "BLOCK", 0xE3, 7, 17, "SB-95"),
    ("TII", "BLOCK", 0x73, 7, 17, "SB-97"), ("TIN", "BLOCK", 0xD3, 7, 17, "SB-99"),
    ("TMA", "IMPLID", 0x43, 2, 4, "SB-101"),
    ("TRB", "ZP", 0x14, 2, 6, "SB-102"), ("TRB", "ABS", 0x1C, 3, 7, "SB-102"),
    ("TSB", "ZP", 0x04, 2, 6, "SB-103"), ("TSB", "ABS", 0x0C, 3, 7, "SB-103"),
    ("TST", "IMM ZP", 0x83, 3, 7, "SB-104"), ("TST", "IMM ZP,X", 0xA3, 3, 7, "SB-104"),
    ("TST", "IMM ABS", 0x93, 4, 8, "SB-104"), ("TST", "IMM ABS,X", 0xB3, 4, 8, "SB-104"),
    ("TSX", "IMPLID", 0xBA, 1, 2, "SB-105"), ("TXA", "IMPLID", 0x8A, 1, 2, "SB-106"),
    ("TXS", "IMPLID", 0x9A, 1, 2, "SB-107"), ("TYA", "IMPLID", 0x98, 1, 2, "SB-108"),
]  # fmt: skip

#: The families written ``10i + code``: the opcode of bit ``i`` is ``code + 0x10 * i``.
BIT_FAMILIES = {"BBR", "BBS", "RMB", "SMB"}


def by_opcode() -> dict[int, tuple[str, str, int, int, str]]:
    """Every opcode the manual defines: (mnemonic with bit number, mode, bytes, cycles, page)."""
    table = {}
    for mnemonic, mode, opcode, size, cycles, page in ROWS:
        if mnemonic in BIT_FAMILIES:
            for bit in range(8):
                table[opcode + 0x10 * bit] = (f"{mnemonic}{bit}", mode, size, cycles, page)
        else:
            table[opcode] = (mnemonic, mode, size, cycles, page)
    return table
