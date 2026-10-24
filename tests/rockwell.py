"""Rung 1b: SingleStepTests 65x02 `rockwell65c02`, semantic only (emulator tier, a detector).

The Rockwell 65C02 is the HuC6280's closest relative among the corpora (it has the bit
instructions and no `WAI`/`STP`), but it cannot judge this chip's **cycles or bus shapes**
(`LDA zp` is 3 cycles there, 4 here), nor any opcode whose meaning differs. It can judge
**results**: A X Y S P PC and the bytes in memory afterwards, for the opcodes the two chips
share, if the memory is mapped so that the 65C02's flat 64 KB looks the same through the
HuC6280's mapper (docs/validation.md, "Rung 1b"):

- MPR0 and MPR1 map the **same** bank, so absolute ``$00xx``/``$01xx`` (which the case
  addresses) and the HuC6280's zero page and stack at ``$20xx``/``$21xx`` (which the core
  uses) meet. MPR2-MPR7 map six further banks, so the rest of the 64 KB is distinct.
- A case that lists two addresses of ``$0000-$3FFF`` that differ by ``$2000`` (they would
  alias) is **excluded** and counted (``alias``).
- ``P``: bit 5 is the HuC6280's T and bit 4 (B) is never stored, so both are cleared on the
  way in and not compared on the way out (the 65C02 holds bit 5 at 1). A pushed P differs in
  bit 5 for the same reason (``PHP``'s byte is compared without it).
- Opcodes the two chips do not share are excluded (every case counted): ``BRK`` (a different
  vector and its own P), the 24 Hudson opcodes, the 65C02 multi-byte ``NOP``s and the rest of
  the undefined slots (`SHARED` below).
- Documented differences between the chips that change a result, masked and counted:
  ``BIT #imm`` sets N and V on the HuC6280 (U19), ``TSB``/``TRB`` take Z from the stored result
  (C12), and decimal ``ADC``/``SBC`` leave V alone (U14).

Every exclusion and mask is counted by name in the returned Counter.
"""

import json
from collections import Counter
from functools import cache
from pathlib import Path

from huc6280 import HuC6280

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "reference" / "src" / "65x02" / "rockwell65c02" / "v1"
FETCH_HINT = "rockwell65c02 not fetched: python -I scripts/fetch_references.py"

#: R65C02 mnemonic and mode for each opcode both chips define, from the Rockwell R65C02
#: data sheet's opcode map (research tier). It is independent of the HuC6280 table: the
#: test below checks that the two agree for every opcode in it.
R65C02 = {
    0x00: "BRK", 0x01: "ORA idx", 0x04: "TSB zp", 0x05: "ORA zp", 0x06: "ASL zp",
    0x08: "PHP", 0x09: "ORA imm", 0x0A: "ASL A", 0x0C: "TSB abs", 0x0D: "ORA abs",
    0x0E: "ASL abs",
    0x10: "BPL", 0x11: "ORA idy", 0x12: "ORA zpind", 0x14: "TRB zp", 0x15: "ORA zpx",
    0x16: "ASL zpx", 0x18: "CLC", 0x19: "ORA aby", 0x1A: "INC A", 0x1C: "TRB abs",
    0x1D: "ORA abx", 0x1E: "ASL abx",
    0x20: "JSR", 0x21: "AND idx", 0x24: "BIT zp", 0x25: "AND zp", 0x26: "ROL zp",
    0x28: "PLP", 0x29: "AND imm", 0x2A: "ROL A", 0x2C: "BIT abs", 0x2D: "AND abs",
    0x2E: "ROL abs",
    0x30: "BMI", 0x31: "AND idy", 0x32: "AND zpind", 0x34: "BIT zpx", 0x35: "AND zpx",
    0x36: "ROL zpx", 0x38: "SEC", 0x39: "AND aby", 0x3A: "DEC A", 0x3C: "BIT abx",
    0x3D: "AND abx", 0x3E: "ROL abx",
    0x40: "RTI", 0x41: "EOR idx", 0x45: "EOR zp", 0x46: "LSR zp", 0x48: "PHA",
    0x49: "EOR imm", 0x4A: "LSR A", 0x4C: "JMP abs", 0x4D: "EOR abs", 0x4E: "LSR abs",
    0x50: "BVC", 0x51: "EOR idy", 0x52: "EOR zpind", 0x55: "EOR zpx", 0x56: "LSR zpx",
    0x58: "CLI", 0x59: "EOR aby", 0x5A: "PHY", 0x5D: "EOR abx", 0x5E: "LSR abx",
    0x60: "RTS", 0x61: "ADC idx", 0x64: "STZ zp", 0x65: "ADC zp", 0x66: "ROR zp",
    0x68: "PLA", 0x69: "ADC imm", 0x6A: "ROR A", 0x6C: "JMP ind", 0x6D: "ADC abs",
    0x6E: "ROR abs",
    0x70: "BVS", 0x71: "ADC idy", 0x72: "ADC zpind", 0x74: "STZ zpx", 0x75: "ADC zpx",
    0x76: "ROR zpx", 0x78: "SEI", 0x79: "ADC aby", 0x7A: "PLY", 0x7C: "JMP abxind",
    0x7D: "ADC abx", 0x7E: "ROR abx",
    0x80: "BRA", 0x81: "STA idx", 0x84: "STY zp", 0x85: "STA zp", 0x86: "STX zp",
    0x88: "DEY", 0x89: "BIT imm", 0x8A: "TXA", 0x8C: "STY abs", 0x8D: "STA abs",
    0x8E: "STX abs",
    0x90: "BCC", 0x91: "STA idy", 0x92: "STA zpind", 0x94: "STY zpx", 0x95: "STA zpx",
    0x96: "STX zpy", 0x98: "TYA", 0x99: "STA aby", 0x9A: "TXS", 0x9C: "STZ abs",
    0x9D: "STA abx", 0x9E: "STZ abx",
    0xA0: "LDY imm", 0xA1: "LDA idx", 0xA2: "LDX imm", 0xA4: "LDY zp", 0xA5: "LDA zp",
    0xA6: "LDX zp", 0xA8: "TAY", 0xA9: "LDA imm", 0xAA: "TAX", 0xAC: "LDY abs",
    0xAD: "LDA abs", 0xAE: "LDX abs",
    0xB0: "BCS", 0xB1: "LDA idy", 0xB2: "LDA zpind", 0xB4: "LDY zpx", 0xB5: "LDA zpx",
    0xB6: "LDX zpy", 0xB8: "CLV", 0xB9: "LDA aby", 0xBA: "TSX", 0xBC: "LDY abx",
    0xBD: "LDA abx", 0xBE: "LDX aby",
    0xC0: "CPY imm", 0xC1: "CMP idx", 0xC4: "CPY zp", 0xC5: "CMP zp", 0xC6: "DEC zp",
    0xC8: "INY", 0xC9: "CMP imm", 0xCA: "DEX", 0xCC: "CPY abs", 0xCD: "CMP abs",
    0xCE: "DEC abs",
    0xD0: "BNE", 0xD1: "CMP idy", 0xD2: "CMP zpind", 0xD5: "CMP zpx", 0xD6: "DEC zpx",
    0xD8: "CLD", 0xD9: "CMP aby", 0xDA: "PHX", 0xDD: "CMP abx", 0xDE: "DEC abx",
    0xE0: "CPX imm", 0xE1: "SBC idx", 0xE4: "CPX zp", 0xE5: "SBC zp", 0xE6: "INC zp",
    0xE8: "INX", 0xE9: "SBC imm", 0xEA: "NOP", 0xEC: "CPX abs", 0xED: "SBC abs",
    0xEE: "INC abs",
    0xF0: "BEQ", 0xF1: "SBC idy", 0xF2: "SBC zpind", 0xF5: "SBC zpx", 0xF6: "INC zpx",
    0xF8: "SED", 0xF9: "SBC aby", 0xFA: "PLX", 0xFD: "SBC abx", 0xFE: "INC abx",
}  # fmt: skip
for _bit in range(8):  # the Rockwell bit instructions: RMBi zp, SMBi zp, BBRi, BBSi
    R65C02[0x07 + 0x10 * _bit] = f"RMB{_bit} zp"
    R65C02[0x87 + 0x10 * _bit] = f"SMB{_bit} zp"
    R65C02[0x0F + 0x10 * _bit] = f"BBR{_bit} zprel"
    R65C02[0x8F + 0x10 * _bit] = f"BBS{_bit} zprel"

#: Shared opcodes: the R65C02's, less BRK (different vector and P; excluded, counted).
SHARED = {opcode for opcode in R65C02 if opcode != 0x00}
#: Opcodes with a different 65C02 meaning, for the counts only.
BANK = (0x10, 0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16)  # MPR0 = MPR1: zero page meets $00xx
PUSHED_P = {0x08}  # PHP
BIT_IMMEDIATE = 0x89
TSB_TRB = {0x04, 0x0C, 0x14, 0x1C}
DECIMAL = {0x61, 0x65, 0x69, 0x6D, 0x71, 0x72, 0x75, 0x79, 0x7D}  # ADC
DECIMAL_SBC = {0xE1, 0xE5, 0xE9, 0xED, 0xF1, 0xF2, 0xF5, 0xF9, 0xFD}  # SBC
DECIMAL_OPS = DECIMAL | DECIMAL_SBC


def corpus_present() -> bool:
    return (CORPUS / "a9.json").is_file()


@cache
def load_cases(opcode: int) -> list[dict]:
    return json.loads((CORPUS / f"{opcode:02x}.json").read_text())


def physical(address: int) -> int:
    return BANK[address >> 13] << 13 | address & 0x1FFF


def run_case(case: dict) -> tuple[list[str], Counter]:
    """Run one case; return the differences (empty: it passes) and the masks it used."""
    initial, final = case["initial"], case["final"]
    opcode = case["name"].split()[0]
    opcode = int(opcode, 16)
    masks: Counter = Counter()
    # Two listed addresses that alias through MPR0 = MPR1 with different values.
    seen: dict[int, tuple[int, int]] = {}
    for section in (initial, final):
        for address, value in section["ram"]:
            cell = physical(address)
            if cell in seen and seen[cell][0] != address and seen[cell][1] != value:
                masks["alias"] += 1
                return [], masks
            seen[cell] = (address, value)
    memory: dict[int, int] = {}
    for address, value in initial["ram"]:
        memory[physical(address)] = value
    reads: list[int] = []
    values: list[int] = []

    def read_byte(address: int) -> int:
        reads.append(address)
        values.append(memory.get(address, 0))
        return values[-1]

    def write_byte(address: int, value: int) -> None:
        memory[address] = value

    cpu = HuC6280(read_byte, write_byte, lambda address: None)
    cpu.mpr[:] = BANK
    for name in ("a", "x", "y", "s", "pc"):
        setattr(cpu, name, initial[name])
    cpu.p = initial["p"] & ~0x30  # T and B are not the 65C02's bits 5 and 4
    cpu.step()

    problems: list[str] = []
    # SBC's operand is its last read.
    invalid_bcd = (
        opcode in DECIMAL_SBC
        and initial["p"] & 0x08
        and not all((v & 0xF) < 10 and (v >> 4) < 10 for v in (initial["a"], values[-1]))
    )
    if invalid_bcd:
        masks["sbc_decimal_invalid_digits"] += 1  # C13: A, N, Z, C not compared
    for name in ("a", "x", "y", "s", "pc"):
        if name == "a" and invalid_bcd:
            continue
        if getattr(cpu, name) != final[name]:
            problems.append(f"{name}: got ${getattr(cpu, name):X}, want ${final[name]:X}")
    mask = 0x30  # T and B
    if opcode == BIT_IMMEDIATE:
        mask |= 0xC0
        masks["bit_immediate"] += 1
    if opcode in TSB_TRB:
        mask |= 0xC2  # Z (C12), and N and V, which the 65C02 leaves alone (U19)
        masks["tsb_trb_flags"] += 1
    if opcode in DECIMAL_OPS and initial["p"] & 0x08:
        mask |= 0x40
        masks["decimal_v"] += 1
    if invalid_bcd:
        mask |= 0x8B  # N, Z, C (and V, which decimal leaves alone)
    if (cpu.p ^ final["p"]) & ~mask:
        problems.append(f"p: got ${cpu.p:02X}, want ${final['p']:02X} (mask ${mask:02X})")
    for address, value in final["ram"]:
        got = memory.get(physical(address), 0)
        want = value
        if opcode in PUSHED_P and address == 0x0100 | initial["s"]:
            got, want = got & ~0x20, want & ~0x20  # bit 5 is T here, 1 on the 65C02
            masks["pushed_p_bit5"] += 1
        if got != want:
            problems.append(f"ram ${address:04X}: got ${got:02X}, want ${want:02X}")
    listed = {physical(address) for address, _ in initial["ram"]}
    stray = [address for address in reads if address not in listed]
    if stray:
        problems.append(f"read of an address the case does not list: ${stray[0]:06X}")
    return problems, masks
