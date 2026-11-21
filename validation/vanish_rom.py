# SPDX-License-Identifier: MIT
"""C18 probe HuCards: an interrupt whose source goes away in the last cycle of the instruction that
polled it, on real board sources, for closed-box runs (validation/vanish_probe.py).

Each card waits, with I set, until the source shows in $1403, then runs ``CLI`` and an instruction
whose last cycle acknowledges the source, then marks that the main line went on. The handlers
record what they found. RAM (MPR1 = $F8, logical $2000):

    $2000  $22 when the TIQ handler ran      $2005  $33 when the IRQ2/BRK handler ran
    $2001  $11 once the main line passed     $2006  $44 when the IRQ1 handler ran
    $2002  $2001 as the handler found it     $2007  $99 when the main line finished
    $2003  return address the handler found (low, high at $2004)

Variants: ``tiq`` (timer at reload 0, acknowledged by ``STZ $1403``, a write in the last cycle:
the After Burner II timer handler's shape), ``irq1`` (the VDC's vertical-blank interrupt,
acknowledged by ``LDA $0000``, a status read in the last cycle), and ``tiq-held`` / ``irq1-held``
(the same with a ``NOP`` in place of the acknowledging instruction: the control, where the source
stays and must be taken). Register facts are pcetech's (timer $0C00/$0C01, $1402/$1403, the VDC's
CR bit 3 for the vertical-blank interrupt) and Hudson's manuals (opcodes, vectors).
"""

from __future__ import annotations

import sys
from pathlib import Path

ORIGIN = 0xE000
SITE_LABEL = "site"  # the acknowledging (or control) instruction
VARIANTS = ("tiq", "irq1", "tiq-held", "irq1-held")


class Assembler:
    def __init__(self) -> None:
        self.code = bytearray()
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple[int, str]] = []

    @property
    def here(self) -> int:
        return ORIGIN + len(self.code)

    def label(self, name: str) -> None:
        self.labels[name] = self.here

    def emit(self, *data: int) -> None:
        self.code += bytes(data)

    def abs(self, opcode: int, address: int) -> None:
        self.emit(opcode, address & 0xFF, address >> 8)

    def branch(self, opcode: int, target: str) -> None:
        self.emit(opcode, 0)
        self.fixups.append((len(self.code) - 1, target))

    def finish(self) -> bytes:
        for at, target in self.fixups:
            offset = self.labels[target] - (ORIGIN + at + 1)
            assert -128 <= offset < 128, target
            self.code[at] = offset & 0xFF
        return bytes(self.code)


SEI, CLI, CSH, NOP, RTI, TSX, TXS = 0x78, 0x58, 0xD4, 0xEA, 0x40, 0xBA, 0x9A
LDA_IMM, LDX_IMM, AND_IMM, TAM = 0xA9, 0xA2, 0x29, 0x53
LDA_ABS, STA_ABS, STZ_ABS, LDA_ABX = 0xAD, 0x8D, 0x9C, 0xBD
BEQ, BRA, ST0, ST1, ST2 = 0xF0, 0x80, 0x03, 0x13, 0x23
TIMER_RELOAD, TIMER_CONTROL, IRQ_DISABLE, IRQ_STATUS = 0x0C00, 0x0C01, 0x1402, 0x1403


def build(variant: str) -> tuple[bytes, dict[str, int]]:
    if variant not in VARIANTS:
        raise SystemExit(f"variant must be one of {VARIANTS}")
    source = variant.split("-")[0]
    a = Assembler()
    a.label("reset")
    a.emit(SEI, CSH, LDA_IMM, 0xFF, TAM, 0x01, LDA_IMM, 0xF8, TAM, 0x02, LDX_IMM, 0xFF, TXS)
    for address in range(0x2000, 0x2008):
        a.abs(STZ_ABS, address)
    # $1402: 1 masks (bit 0 IRQ2, bit 1 IRQ1, bit 2 TIQ); leave only the source under test.
    a.emit(LDA_IMM, 0x03 if source == "tiq" else 0x05)
    a.abs(STA_ABS, IRQ_DISABLE)
    if source == "tiq":
        a.abs(STZ_ABS, TIMER_RELOAD)
        a.emit(LDA_IMM, 0x01)
        a.abs(STA_ABS, TIMER_CONTROL)
    else:
        a.emit(ST0, 0x05, ST1, 0x08, ST2, 0x00)  # VDC CR: vertical-blank interrupt on
    a.label("wait")
    a.abs(LDA_ABS, IRQ_STATUS)
    a.emit(AND_IMM, 0x04 if source == "tiq" else 0x02)
    a.branch(BEQ, "wait")
    a.emit(CLI)
    a.label(SITE_LABEL)
    if variant == "tiq":
        a.abs(STZ_ABS, IRQ_STATUS)  # acknowledges the timer in its last cycle (a write)
    elif variant == "irq1":
        a.abs(LDA_ABS, 0x0000)  # VDC status read in its last cycle acknowledges IRQ1
    else:
        a.emit(NOP)
    a.label("after")
    a.emit(LDA_IMM, 0x11)
    a.abs(STA_ABS, 0x2001)
    # Eight NOPs before SEI: room for an emulator that enters later than at the next boundary.
    a.emit(*[NOP] * 8)
    a.emit(SEI)
    if source == "tiq":
        a.abs(STZ_ABS, TIMER_CONTROL)
        a.abs(STZ_ABS, IRQ_STATUS)
    else:
        a.emit(ST0, 0x05, ST1, 0x00, ST2, 0x00)
        a.abs(LDA_ABS, 0x0000)
    a.emit(LDA_IMM, 0x99)
    a.abs(STA_ABS, 0x2007)
    a.label("spin")
    a.branch(BRA, "spin")

    def record(marker: int, at: int) -> None:
        a.abs(LDA_ABS, 0x2001)
        a.abs(STA_ABS, 0x2002)
        a.emit(TSX)
        a.abs(LDA_ABX, 0x2102)
        a.abs(STA_ABS, 0x2003)
        a.abs(LDA_ABX, 0x2103)
        a.abs(STA_ABS, 0x2004)
        a.emit(LDA_IMM, marker)
        a.abs(STA_ABS, at)

    a.label("tiq_handler")
    record(0x22, 0x2000)
    a.abs(STZ_ABS, TIMER_CONTROL)
    a.abs(STZ_ABS, IRQ_STATUS)
    a.emit(RTI)
    a.label("irq1_handler")
    record(0x44, 0x2006)
    a.emit(ST0, 0x05, ST1, 0x00, ST2, 0x00)
    a.abs(LDA_ABS, 0x0000)
    a.emit(RTI)
    a.label("irq2_handler")
    record(0x33, 0x2005)
    a.emit(RTI)
    a.label("nmi_handler")
    a.emit(RTI)
    code = a.finish()
    rom = bytearray(b"\xff" * 8192)
    rom[: len(code)] = code
    vectors = {
        0x1FF6: "irq2_handler", 0x1FF8: "irq1_handler", 0x1FFA: "tiq_handler",
        0x1FFC: "nmi_handler", 0x1FFE: "reset",
    }  # fmt: skip
    for offset, name in vectors.items():
        target = a.labels[name]
        rom[offset : offset + 2] = bytes([target & 0xFF, target >> 8])
    return bytes(rom), dict(a.labels)


def build_t_entry() -> tuple[bytes, dict[str, int]]:
    """C16 probe: the timer is taken between SET and its target (CLI's I counts one instruction
    late, so SET's boundary is the first that can enter). The handler's first instruction is
    ``ORA #$0F`` with A = X = 0: with T still set it would write $0F to $2000 and leave A at 0.

        $2003  A after the handler's ORA      $2004  $2000 after it
        $2005  P as pushed by the entry       $2006  $22 when the handler ran
        $2001  $11 once the main line passed  $2007  $99 when the main line finished
    """
    a = Assembler()
    a.label("reset")
    a.emit(SEI, CSH, LDA_IMM, 0xFF, TAM, 0x01, LDA_IMM, 0xF8, TAM, 0x02, LDX_IMM, 0xFF, TXS)
    for address in range(0x2000, 0x2008):
        a.abs(STZ_ABS, address)
    a.emit(LDA_IMM, 0x03)
    a.abs(STA_ABS, IRQ_DISABLE)
    a.abs(STZ_ABS, TIMER_RELOAD)
    a.emit(LDA_IMM, 0x01)
    a.abs(STA_ABS, TIMER_CONTROL)
    a.label("wait")
    a.abs(LDA_ABS, IRQ_STATUS)
    a.emit(AND_IMM, 0x04)
    a.branch(BEQ, "wait")
    a.emit(0x62, 0x82, CLI, 0xF4)  # CLA; CLX; CLI; SET
    a.label(SITE_LABEL)
    a.emit(NOP)
    a.label("after")
    a.emit(LDA_IMM, 0x11)
    a.abs(STA_ABS, 0x2001)
    a.emit(*[NOP] * 8)
    a.emit(SEI)
    a.abs(STZ_ABS, TIMER_CONTROL)
    a.abs(STZ_ABS, IRQ_STATUS)
    a.emit(LDA_IMM, 0x99)
    a.abs(STA_ABS, 0x2007)
    a.label("spin")
    a.branch(BRA, "spin")
    a.label("tiq_handler")
    a.emit(0x09, 0x0F)  # ORA #$0F
    a.abs(STA_ABS, 0x2003)
    a.abs(LDA_ABS, 0x2000)
    a.abs(STA_ABS, 0x2004)
    a.emit(TSX)
    a.abs(LDA_ABX, 0x2101)
    a.abs(STA_ABS, 0x2005)
    a.emit(LDA_IMM, 0x22)
    a.abs(STA_ABS, 0x2006)
    a.abs(STZ_ABS, TIMER_CONTROL)
    a.abs(STZ_ABS, IRQ_STATUS)
    a.emit(RTI)
    a.label("irq1_handler")
    a.label("irq2_handler")
    a.label("nmi_handler")
    a.emit(RTI)
    code = a.finish()
    rom = bytearray(b"\xff" * 8192)
    rom[: len(code)] = code
    vectors = {
        0x1FF6: "irq2_handler", 0x1FF8: "irq1_handler", 0x1FFA: "tiq_handler",
        0x1FFC: "nmi_handler", 0x1FFE: "reset",
    }  # fmt: skip
    for offset, name in vectors.items():
        target = a.labels[name]
        rom[offset : offset + 2] = bytes([target & 0xFF, target >> 8])
    return bytes(rom), dict(a.labels)


def main() -> int:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for variant in VARIANTS:
        rom, labels = build(variant)
        (out / f"vanish-{variant}.pce").write_bytes(rom)
        print(variant, {k: f"{v:04X}" for k, v in labels.items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
