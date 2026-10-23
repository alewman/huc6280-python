# Timing: every cycle, and where the sources disagree

A "cycle" here is one CPU cycle: 3 master clocks in high speed, 12 in low
(start-here.md). Everything below is **emulator-derived unless a row says
otherwise**: the only per-cycle record of the chip is SingleStepTests
`huc6280`, which Mesen generated, and nobody has put a logic analyser's trace
of a HuC6280 where it can be read per instruction (validation.md, "What does
not exist"). Hudson's manual gives each instruction's total cycles, not its
bus cycles.

Everything measured on this page was run on 2026-10-23 with `scripts/`:
`survey_sst.py`, `compare_cycles.py`, `opcode_map.py`, `manual_table.py`.

## The measured agreement

| Question | Result |
| --- | --- |
| SingleStepTests huc6280: opcodes, cases | 256 files x 2,500 cases = 640,000 (the README promises no number; the files hold 2,500 each) |
| Hudson's software manual vs Mesen/Geargrafx, bytes and cycles | `manual_table.py` reads 111 opcodes out of the scan; **107 agree**; 3 differ because the OCR misread the opcode ($4D as $40, $6D as $60, $B0 as $80); **1 differs for real**: `BRK`, 1 byte in the manual, 2 in every emulator (C2). The other ~120 opcodes sit in `i`-family rows or in OCR damage and were not read: rung 0 finishes that |
| Block transfers: total cycles = 17 + 6n | 12,500 of 12,500 cases (`TII` `TDD` `TIN` `TIA` `TAI`, n read from the operand bytes in the recorded cycles), against HW HB-6 |
| Four emulators' base cycle tables (`compare_cycles.py`) | 230 of 256 opcodes agree in every source that states a number; 26 differ, all explained in "Where the sources disagree" below |
| Corpus P register | B (bit 4) is never set in initial or final P, so B must be masked when comparing: the chip reads it as 1 (HW HB-5) |

## The opcode grid

Mnemonics from Mesen2's table (`opcode_map.py --grid`); the 23 `NOP`s are
$0B $1B $2B $33 $3B $4B $5B $5C $63 $6B $7B $8B $9B $AB $BB $CB $DB $DC $E2
$EA $EB $FB $FC (pcetech tested 22 of them and found them all 2-cycle NOPs; the
list is the same, C4 for the odd one out).

```text
     0        1        2        3        4        5        6        7        8        9        A        B        C        D        E        F
00   BRK      ORA      SXY      ST0      TSB      ORA      ASL      RMB0     PHP      ORA      ASL A    NOP      TSB      ORA      ASL      BBR0
10   BPL      ORA      ORA      ST1      TRB      ORA      ASL      RMB1     CLC      ORA      INC A    NOP      TRB      ORA      ASL      BBR1
20   JSR      AND      SAX      ST2      BIT      AND      ROL      RMB2     PLP      AND      ROL A    NOP      BIT      AND      ROL      BBR2
30   BMI      AND      AND      NOP      BIT      AND      ROL      RMB3     SEC      AND      DEC A    NOP      BIT      AND      ROL      BBR3
40   RTI      EOR      SAY      TMAn     BSR      EOR      LSR      RMB4     PHA      EOR      LSR A    NOP      JMP      EOR      LSR      BBR4
50   BVC      EOR      EOR      TAMn     CSL      EOR      LSR      RMB5     CLI      EOR      PHY      NOP      NOP      EOR      LSR      BBR5
60   RTS      ADC      CLA      NOP      STZ      ADC      ROR      RMB6     PLA      ADC      ROR A    NOP      JMP      ADC      ROR      BBR6
70   BVS      ADC      ADC      TII      STZ      ADC      ROR      RMB7     SEI      ADC      PLY      NOP      JMP      ADC      ROR      BBR7
80   BRA      STA      CLX      TST      STY      STA      STX      SMB0     DEY      BIT      TXA      NOP      STY      STA      STX      BBS0
90   BCC      STA      STA      TST      STY      STA      STX      SMB1     TYA      STA      TXS      NOP      STZ      STA      STZ      BBS1
A0   LDY      LDA      LDX      TST      LDY      LDA      LDX      SMB2     TAY      LDA      TAX      NOP      LDY      LDA      LDX      BBS2
B0   BCS      LDA      LDA      TST      LDY      LDA      LDX      SMB3     CLV      LDA      TSX      NOP      LDY      LDA      LDX      BBS3
C0   CPY      CMP      CLY      TDD      CPY      CMP      DEC      SMB4     INY      CMP      DEX      NOP      CPY      CMP      DEC      BBS4
D0   BNE      CMP      CMP      TIN      CSH      CMP      DEC      SMB5     CLD      CMP      PHX      NOP      NOP      CMP      DEC      BBS5
E0   CPX      SBC      NOP      TIA      CPX      SBC      INC      SMB6     INX      SBC      NOP      NOP      CPX      SBC      INC      BBS6
F0   BEQ      SBC      SBC      TAI      SET      SBC      INC      SMB7     SED      SBC      PLX      NOP      NOP      SBC      INC      BBS7
```

The addressing modes (`opcode_map.py` lists each opcode's): `(zp)` is column 2
of rows 1, 3, 5, 7, 9, B, D, F (`ORA` `AND` `EOR` `ADC` `STA` `LDA` `CMP`
`SBC`); `BIT` has `#imm` $89, `zp,X` $34, `abs,X` $3C; `JMP` has `(abs)` $6C and
`(abs,X)` $7C; `STZ` has zp $64, zp,X $74, abs $9C, abs,X $9E; `TSB`/`TRB` zp
and abs; `TST` four modes; `RMB`/`SMB` are zp, `BBR`/`BBS` zp,rel.

## Base cycles (T = 0, D = 0, no branch taken)

From SingleStepTests (smallest `num_cycles` per opcode; `opcode_map.py
--cycles`). Block transfers print their smallest random case (n >= 3); their
cost is 17 + 6n.

```text
     0   1   2   3   4   5   6   7   8   9   A   B   C   D   E   F
00   8   7   3   4   6   4   6   7   3   2   2   2   7   5   7   6
10   2   7   7   4   6   4   6   7   2   5   2   2   7   5   7   6
20   7   7   3   4   4   4   6   7   4   2   2   2   5   5   7   6
30   2   7   7   2   4   4   6   7   2   5   2   2   5   5   7   6
40   7   7   3   4   8   4   6   7   3   2   2   2   4   5   7   6
50   2   7   7   5   3   4   6   7   2   5   3   2   2   5   7   6
60   7   7   2   2   4   4   6   7   4   2   2   2   7   5   7   6
70   2   7   7   n   4   4   6   7   2   5   4   2   7   5   7   6
80   4   7   2   7   4   4   4   7   2   2   2   2   5   5   5   6
90   2   7   7   8   4   4   4   7   2   5   2   2   5   5   5   6
A0   2   7   2   7   4   4   4   7   2   2   2   2   5   5   5   6
B0   2   7   7   8   4   4   4   7   2   5   2   2   5   5   5   6
C0   2   7   2   n   4   4   6   7   2   2   2   2   5   5   7   6
D0   2   7   7   n   3   4   6   7   2   5   3   2   2   5   7   6
E0   2   7   2   n   4   4   6   7   2   2   2   2   5   5   7   6
F0   2   7   7   n   2   4   6   7   2   5   4   2   2   5   7   6
```

($73 $C3 $D3 $E3 $F3 are `n`; $80 `BRA` is always 4, never 2; the other
branches are 2 not taken and 4 taken.) Variants the corpus shows:

| Variant | Effect | Source |
| --- | --- | --- |
| branch taken (`BPL` etc., `BRA`) | +2 (always, whatever the page crossed) | SW; pcetech; corpus |
| `BBR`/`BBS` taken | 6 -> 8 | SW; corpus |
| D = 1 on `ADC`/`SBC` | +1 | HW HB-4; SW; corpus |
| T = 1 on `ORA`/`AND`/`EOR`/`ADC` | +3 (and +1 more with D on `ADC`) | SW; corpus: `ADC #` is 2, 3 (D), 5 (T), 6 (T and D) in 638, 635, 621, 606 cases |
| `ST0`/`ST1`/`ST2` | 4; the VDC stretch makes it 5 on a console | SW; pcetech; C1 |
| VDC or VCE access by any instruction | +1 per access | pcetech; MAME, Mednafen, Mesen2 |

## The bus cycles (Mesen's model, from the corpus)

Letters: `R` read, `W` write, `d` a read the corpus flags dummy (it reads
`PC + 1`, the byte after the opcode: checked, 2,500 of 2,500 `CLC` cases),
`i` an internal cycle with no bus access (the corpus records no address or
data for it). The first cycle is always the opcode fetch. These are the shapes
of the smallest case of each addressing mode (`survey_sst.py` prints every
shape).

| Mode | Read | Write | Read-modify-write |
| --- | --- | --- | --- |
| implied, `A` | `Rd` | | `Rd` |
| `#imm` | `RR` | | |
| zp | `RRiR` | `RRiW` | `RRiRiW` |
| zp,X (zp,Y for `LDX`/`STX`) | `RRiR` | `RRiW` | `RRiRiW` |
| abs | `RRRiR` | `RRRiW` | `RRRiRiW` |
| abs,X and abs,Y | `RRRiR` | `RRRiW` | `RRRiRiW` |
| (zp), (zp,X), (zp),Y | `RRiRRiR` | `RRiRRiW` | |
| `RMBi`/`SMBi` zp | | | `RRiRiiW` |
| `BBRi`/`BBSi` | `RRiRiR` (not taken) | | |
| branch | `RR` (not taken), `RRdi` (taken) | | |
| `JMP abs` / `(abs)` / `(abs,X)` | `RRRi` / `RRRiRRi` / `RRRiRRi` | | |
| `JSR` | `RRiWWRi` | | |
| `BSR` | `RRiWWiii` | | |
| `BRK` | `RRWWWRRi` | | |
| `PHA` `PHP` `PHX` `PHY` | | `RdW` | |
| `PLA` `PLP` `PLX` `PLY` | `RdiR` | | |
| `RTS` / `RTI` | `RdiRRii` / `RdiRRRi` | | |
| `SXY` `SAX` `SAY` / `CSH` `CSL` | `Rdi` | | |
| `ST0` `ST1` `ST2` / `TMAi` | `RRii` | | |
| `TAMi` | `RRiii` | | |
| `TST #,zp` / `#,abs` | `RRRiiRi` / `RRRRiiRi` | | |
| block transfer | `Rdi WWW RRRRRR ii` then per byte `i R i W i i`, then `i RRR` | | |

Two things to notice. **No index cost anywhere**: abs,X has the shape of abs,
and a page crossing changes nothing (pcetech). And **the internal cycle's place
is Mesen's choice**: the zero-page `LDA` is four cycles in the manual and four
in the corpus, but where the chip spends the fourth (before the data read, as
here, or after) is not documented anywhere found and is not observable from
the cycle count; a board can see it only if it distinguishes an idle cycle from
a read (C8). The block transfer's six cycles per byte are `i R i W i i` in
Mesen, and `ADDCYC(6)` before one read and one write in Mednafen: the same
count, different positions.

Block-transfer accounting (Mesen's `StartBlockTransfer`/`EndBlockTransfer`,
checked against the corpus's shape strings): the entry is 13 cycles (opcode
fetch, dummy read, one internal, three stack writes of Y, A, X, six operand
reads, one internal), each byte is the six cycles `i R i W i i`, and the exit
is one internal cycle and three stack reads (X, A, Y): 13 + 6n + 4 = 17 + 6n,
which is what the manual says and what every case in the corpus has.

## Against the 65C02 (Rockwell corpus, ten files sampled 2026-10-23)

`SingleStepTests/65x02` `rockwell65c02` (10,000 cases a file, per-cycle
`[address, value, read|write]`, not checked out beyond its README here; ten
files fetched into the scratchpad to measure this):

| Opcode | Rockwell 65C02 | HuC6280 |
| --- | --- | --- |
| $A5 `LDA zp` | 3 cycles | 4 |
| $20 `JSR` | 6 | 7 |
| $00 `BRK` | 7 | 8 |
| $6C `JMP (abs)` | 6 | 7 |
| $4C `JMP abs` | 3 | 4 |
| $7C `JMP (abs,X)` | 6 | 7 |
| $80 `BRA` | 3 (4 across a page) | 4 always |
| $0F `BBR0` | 5, 6 or 7 | 6 or 8 |
| $03 | 1-cycle `NOP` | `ST0` |
| $22 | 2-byte `NOP` | `SAX` |
| $44 | 2-byte `NOP` (3 cycles) | `BSR` |

So the 65C02 corpus cannot judge cycles or bus shapes of this chip at all, and
the opcodes whose meaning differs (the table above plus $02 $13 $23 $42 $43 $53
$54 $62 $73 $82 $83 $93 $A3 $B3 $C2 $C3 $D3 $D4 $E3 $F3 $F4, and the multi-byte
`NOP`s $5C $DC $FC) are not comparable. Its **final registers and memory** are
comparable for the instructions the chips share, with the memory mapped as
validation.md "Rung 1b" says.

## Interrupt, reset and speed

None of these is in the corpus (it has `BRK` and nothing else).

| Sequence | Cycles | Source |
| --- | --- | --- |
| IRQ1, IRQ2, TIQ, NMI entry | **8** | Mesen (`DummyRead` x2, 3 pushes, 2 vector reads, 1 internal), Mednafen ("Total: 8 cycles", `huc6280.cpp`), ares (3 idle, 3 pushes, 2 loads), Geargrafx (`m_cycles += 8`); **MAME 7** (`do_interrupt`, "7 cycles for an int") |
| `BRK` | 8 | SW; corpus |
| `RTI` | 7 | SW; corpus |
| reset | not counted by any source | |
| `CSL` / `CSH` | 3 when the speed is unchanged | pcetech (tested); HW map; MAME 3, Mesen 3, Mednafen 2 + the last cycle |

The speed change is applied **for the last cycle** of `CSL`/`CSH` in Mednafen
("CSL/CSH's speed timing changes take effect for the last CPU cycle") and in
Mesen ("last idle cycle is after the speed change takes effect"); MAME applies
it between instructions; pcetech says it "isn't known" what they cost when the
speed changes (U10, C7). The Covell test ROM's `CSH` page and the MiSTer
repository's `CSH timing.png` are the only published looks at it (both
board-level, validation.md).

## The timer's clock

The prescaler divides the master clock by 3 and then by 1024 (HW HB-20: "OSC1
divided by 3 ... further divided by 1,024"), so the counter ticks every **3,072
master clocks**, independent of the CPU speed, and the reload value N gives
N + 1 ticks per interrupt (pcetech; MAME `((data & 127) + 1) * 1024`; ares
`1024 * 3`). HW HB-21's "143 microseconds to 18.3 ms" is 1/6.99 kHz to 128 of
them. This is the board's clock if the timer is the board's (decision).

## Where the sources disagree (the 26 base-cycle rows)

`compare_cycles.py`'s output, with the reading of each:

| Opcodes | sst | mame | gear | mdfn | Reading |
| --- | --- | --- | --- | --- | --- |
| $03 $13 $23 (`ST0` `ST1` `ST2`) | 4 | 5 | 5 | 4 | the VDC stretch: SW says 4, pcetech says +1 on any VDC/VCE access; MAME and Geargrafx fold it into the table, the others add it on access. Not a disagreement about the chip (C1) |
| $0F $1F ... $FF (`BBRi` `BBSi`, 16 rows) | 6 | 4 | 6 | 6 | MAME charges 4 and adds the rest inside its helper; the total 6/8 agrees |
| $63 | 2 | **4** | 2 | 2 | MAME bills a `NOP` 4 cycles where pcetech tested 2: MAME's error (C4) |
| $73 $C3 $D3 $E3 $F3 | min 35 .. | - | - | 17 | blocks: the total is 17 + 6n everywhere |
| $80 `BRA` | 4 | - | 2 | 4 | Geargrafx's table holds the not-taken cost and adds 2; the total is the same |

## What is still open

- Bus-level positions of the internal cycle (C8) and of every dummy read:
  unobservable without a per-cycle capture. The SingleStepTests data is
  Mesen's model, which Mesen's own author calls unverified ("We're not even
  100% sure about dummy reads and writes").
- The 7- or 8-cycle interrupt entry (C3), the cost of a speed change (U10), the
  interrupt-vs-block-transfer ordering at the boundary (U6): no emulator
  behaviour is better than another's without hardware.
- Whether `(zp),Y` or `(zp,X)` pointer reads wrap inside page zero of the
  logical zero page (`$20FF` then `$2000`): Mesen wraps (`ReadZeroPageWrap`),
  MAME wraps (`program_read16z`), the manual says nothing (U8).
