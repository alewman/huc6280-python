# Start here: the HuC6280 as a core author needs it

The PC Engine, TurboGrafx-16 and SuperGrafx CPU is Hudson Soft's **HuC6280**
(the **HuC6280A** in the CoreGrafx and SuperGrafx: a "slightly revised" part,
reported as fixing minor audio faults; nothing found says its CPU differs).
It is a CMOS 6502-family core with Hudson's additions and, on the same die, a
memory mapper, a timer, an interrupt controller, an input port, an output port
and a six-channel sound generator. This repository builds the CPU alone. The
board (`/data/emu/pcengine-python`, prepared in parallel) owns everything
outside it, and [the boundary is a decision](handoff-brief.md#the-core-boundary).

Paths: `src/X` is `reference/src/X`, `docs/X` is `reference/docs/X`, all filled
by `scripts/fetch_references.py`. "HW" is Hudson's *HuC6280 CMOS 8-bit
Microprocessor Hardware Manual* (`docs/huc6280-hardware-manual.pdf`, 28 pages,
printed page numbers HB-n; it ends at the instruction map), "SW" is Hudson's
*Software Manual* (`docs/huc6280-software-manual.pdf`, 110 pages, SB-n), and
"pcetech" is Charles MacDonald's *TurboGrafx-16 Hardware Notes*
(`docs/pcetech.txt`, 2001-2002). Both manuals are scans; their OCR text has
errors (the instruction map in HW HB-25 is partly garbled), so every number
taken from them was checked against a second source or is marked. Each source's
tier is in [validation.md](validation.md); cycle detail is in
[timing.md](timing.md), quirks and contradictions in
[undocumented-behavior.md](undocumented-behavior.md).

Tier words: **hardware-captured** (recorded from a real console: Covell's
photographs), **hardware-verified** (a statement by an author who ran it on a
real console and says so: MacDonald), **manufacturer** (Hudson's manuals),
**research** (community documents), **emulator** (SingleStepTests huc6280 via
Mesen, MAME, Mednafen, ares, Geargrafx, Mesen2, the MiSTer VHDL). Full
definitions in validation.md. **Nothing here was run on hardware**; the user
has none.

## Registers (HW HB-2 to HB-6)

| Register | Width | Notes |
| --- | --- | --- |
| A, X, Y | 8 | random at power-up (pcetech) |
| S | 8 | the stack is **logical $2100-$21FF**: the address bus high byte is $21 (HW HB-3), so it goes through MPR1 |
| PC | 16 | logical; the MMU makes the 21-bit address |
| P | 8 | `N V T B D I Z C`, bit 7 to bit 0 |
| MPR0-MPR7 | 8 each | the mapping registers; not CPU-visible except through `TAM` and `TMA` |
| SH, DH, LH | 8 | invisible; the high bytes of a block transfer's source, destination and length (HW HB-6). `A`, `X`, `Y` are the low bytes while a block runs |

P's bits (HW HB-4 to HB-5; pcetech 2.3):

- **T** (bit 5, the memory operation flag) is set by `SET` and **cleared in the
  fetch cycle of the next instruction**. It affects only `ORA`, `AND`, `EOR`
  and `ADC` (SW; `SBC` is the Hudson manual's omission and an emulator
  guess, U4/C5): with T = 1 the accumulator is replaced by the **zero-page byte
  at X** (logical `$2000 + X`), the instruction computes `M(X) op operand` and
  stores the result back there, A untouched, for 3 more cycles. PHP and PLA
  read T as 0 (HW HB-5). An interrupt pushes P with T as it stands, so an
  interrupt between `SET` and its target leaves T set in the pushed byte and
  `RTI` restores it (HW HB-5, pcetech 2.3).
- **B** (bit 4) reads as 1 whenever P is read, except in the byte an IRQ or
  NMI pushes, which has B = 0; `BRK` pushes B = 1 (HW HB-4; pcetech).
- **D** is cleared by reset, interrupt entry and `BRK` (HW HB-4). With D = 1
  `ADC` and `SBC` add one cycle and leave **V unaffected** (SW, `ADC`/`SBC`).
- **I** is set by reset, interrupt entry and `BRK`; it masks IRQ1, IRQ2 and the
  timer but not NMI or `BRK`.

## Memory: 16-bit logical, 21-bit physical (HW HB-7 to HB-11)

The top three bits of a logical address pick MPR0 to MPR7; the 8-bit MPR value
replaces them to give A13-A20, so physical = `MPR[a >> 13] << 13 | a & $1FFF`
(2 MB, 256 pages of 8 KB). `TAMi` writes A to every MPR whose bit is set in its
operand byte (bit 0 = MPR0); operand $00 writes nothing. `TMAi` reads: one bit
reads that MPR; several bits combine in a way nobody has measured (C6); operand
$00 returns the last value moved by `TAM` or `TMA` (pcetech). Reset sets
**MPR7 = $00** (so the vector is read from physical `$001FFE`) and leaves
MPR0-MPR6 undefined (random, pcetech). `TAM` takes 5 cycles, `TMA` 4 (SW).

The usual map (pcetech section 3; Mesen2, MAME `pce.cpp`, emulator-confirmed):

| Pages | Contents |
| --- | --- |
| $00-$7F | HuCard ROM (mirrored when smaller than 1 MB) |
| $80-$F7 | unused, reads $FF (CD-ROM RAM on a CD system) |
| $F8-$FB | work RAM (8 KB, mirrored; SuperGrafx has 32 KB, ares `pce/cpu`) |
| $FC-$FE | unused, reads $FF |
| $FF | hardware page |

The hardware page, logical `$0000 + offset` with MPR0 = $FF (HW HB-24, pcetech):

| Offset | Device | Owner |
| --- | --- | --- |
| $0000-$03FF | HuC6270 VDC (registers every 4 bytes); `ST0`/`ST1`/`ST2` write offsets 0, 2, 3 | board |
| $0400-$07FF | HuC6260 VCE (every 8 bytes) | board |
| $0800-$0BFF | PSG (on the CPU die) | board (decision) |
| $0C00-$0FFF | timer: reload/counter (even), control (odd) | on-die |
| $1000-$13FF | input port K / output port O | on-die pins, board wires |
| $1400-$17FF | interrupt disable ($1402) and request/status ($1403) | on-die |
| $1800-$1FFF | CD-ROM interface (or $FF) | board |

"All of the address decoding is handled internally by the CPU" (pcetech); the
chip has chip-enable pins for VDC, VCE, PSG, timer, port, interrupt registers
and RAM (HW HB-9). The last value read or written at $0800-$17FF is kept in an
8-bit buffer that later reads of some of those addresses return in part or in
full (pcetech section 3 note 1; the buffer is on the die).

**Zero page and stack are not page 0 and page 1.** Every zero-page access
(`LDA zp`, `(zp),Y`, `TST`, the T-flag memory operand) is to logical
`$2000 + zp` and every stack access to `$2100 + S`, through MPR1 (HW HB-3,
pcetech: "ROM data can be read by using instructions that access the zero page
or stack"). MPR1 is $F8 in every game that wants RAM there.
`ST0`/`ST1`/`ST2` bypass the mapper and write physical `$1FE000`, `$1FE002`,
`$1FE003` (pcetech; HW Table 2-2-3 says A20 goes high and A1:A0 are 00, 10, 11).

## Reset and interrupts (HW HB-12 to HB-18)

| Source | Vector | Notes |
| --- | --- | --- |
| RESET | `$FFFE`/`$FFFF` | physical `$1FFE` (MPR7 = 0); low speed; timer stopped; interrupt disable register 0; I set, D and T clear; B reads 1 |
| NMI | `$FFFC` | edge triggered; pcetech: not connected on any PC Engine |
| TIQ (timer) | `$FFFA` | level, internal |
| IRQ1 | `$FFF8` | level, the VDC |
| IRQ2 and `BRK` | `$FFF6` | level; CD-ROM/ADPCM; tell them apart by B in the pushed P |

Priority: RESET > NMI > BRK > TIQ > IRQ1 > IRQ2 (HW HB-13, figure 2-4-1; all
the emulators agree). IRQ1, IRQ2 and TIQ are masked by I and by their bit in
the interrupt disable register. The disable register masks *taking* the
interrupt, not the request: the request register still shows the line
(pcetech 2.1; `$1403` bit 0 IRQ2, bit 1 IRQ1, bit 2 TIQ; `$1402` has the same
bit order and 1 = disabled).

Entry pushes PCH, PCL, then P (B = 0 for an IRQ, T as it stands), sets I,
clears D and T, and reads the vector (HW HB-14; pcetech: "I've tested the timer
and IRQ1"). The interrupts are **sampled in the last bus cycle** of an
instruction (HW HB-12); Mednafen samples both the lines and I at the start of
the last cycle (`LastCycle`), the same rule as 6502-python's frame (end of the
second-to-last cycle), so CLI, SEI and PLP take effect one instruction late
exactly as on the 6502. **The entry takes 8 cycles in Mesen, Mednafen,
Geargrafx and ares and 7 in MAME** (C3). A **block transfer cannot be
interrupted**: the interrupt is taken when it ends (pcetech; Mesen, MAME and
Mednafen all run it to completion).

`BRK` pushes the address of `BRK + 2` (the byte after it is skipped), P with
B = 1, and takes 8 cycles; the manual's own table lists it as 1 byte (C2).

## The clock (HW HB-1; pcetech 2.4)

The console's 21.477272 MHz master clock is divided by 3 for the high speed
(7.16 MHz) and by 12 for the low (1.79 MHz). **Reset selects low.** `CSH` and
`CSL` switch; each takes 3 cycles when the speed does not change (pcetech) and
nobody knows what they cost when it does (U10, C7). The timer and the PSG run
from the master clock and do not care. A board should therefore count in
**master clocks**: a CPU cycle is 3 or 12 of them, plus a **one-cycle stretch
on every access to the VDC or VCE** (pcetech 3, note 3; "reads and writes,
regardless of addressing mode, and instruction execution (jsr $0002)"; MAME
`check_vdc_vce_penalty`, Mednafen, Mesen2 all do it; the CD-ROM registers are
not stretched). Mednafen's comment: the bus extension is done by the board's
I/O handler "for speed reasons", i.e. it is not in the CPU model.

## The instruction set (SW; opcode grid in timing.md)

Bytes and cycles below are SW's unless a row says otherwise.

234 defined opcodes in 89 groups (HW HB-1; the grid has 23 `NOP` slots: 22 undefined
opcodes and the real `NOP` at $EA). Beyond the 65C02 (`BRA`, `STZ`, `TSB`, `TRB`, `PHX/PHY/PLX/PLY`, `INC A`,
`DEC A`, `BIT #`/`zp,X`/`abs,X`, `(zp)` for the eight ALU/load/store
instructions, `JMP (abs,X)`, and the Rockwell bit operations `RMB`/`SMB`/
`BBR`/`BBS`; no `WAI`, no `STP`):

| Group | Opcodes | Bytes / cycles (SW) |
| --- | --- | --- |
| swaps and clears | `SXY` 02, `SAX` 22, `SAY` 42; `CLA` 62, `CLX` 82, `CLY` C2 | 1 / 3 for swaps, 1 / 2 for clears |
| VDC stores | `ST0` 03, `ST1` 13, `ST2` 23 (`#imm`) | 2 / 4 (+1 for the VDC stretch) |
| mapper | `TMAi` 43, `TAMi` 53 (operand = bit mask) | 2 / 4, 2 / 5 |
| speed | `CSL` 54, `CSH` D4 | 1 / 3 (HW map HB-25; the software manual's text has no entry for them, U10) |
| memory-mode | `SET` F4 | 1 / 2 |
| subroutine | `BSR` 44 (relative) | 2 / 8 |
| test | `TST #imm,zp` 83, `#imm,zp,X` A3, `#imm,abs` 93, `#imm,abs,X` B3 | 3 / 7, 3 / 7, 4 / 8, 4 / 8 |
| block transfer | `TII` 73, `TDD` C3, `TIN` D3, `TIA` E3, `TAI` F3 | 7 bytes / 17 + 6n |

Cycle counts are the base: a taken branch adds 2, `BBR`/`BBS` are 6 and 8 when
taken, `ADC`/`SBC` add 1 in decimal mode, and `ORA`/`AND`/`EOR`/`ADC` add 3
with T set. There is **no extra cycle for a page-crossing index or branch**
(pcetech) because the cycle count does not depend on the crossing.

Almost every zero-page, absolute and indirect access costs **one more cycle
than on a 65C02**: `LDA zp` is 4 (65C02: 3), `LDA abs` 5 (4), `LDA (zp)` 7 (5),
`JSR` 7 (6), `RTS` 7 (6), `RTI` 7 (6), `BRK` 8 (7), `JMP (abs,X)` 7 (6) (SW;
measured against the Rockwell 65C02 corpus in timing.md). The SingleStepTests
`huc6280` corpus (Mesen) shows where the extra cycle sits: a bus cycle with no
read or write, after the operand fetch.

## The block transfers (HW HB-6; SW; pcetech)

All five push **Y, then A, then X** (three bytes of stack), load the 16-bit
source, destination and length from the three operand words, move one byte per
**six cycles**, pop X, A, Y, for 17 + 6n cycles in all (n = 0 means 65,536).

| Op | Source | Destination |
| --- | --- | --- |
| `TII` | +1 | +1 |
| `TDD` | -1 | -1 |
| `TIN` | +1 | fixed |
| `TIA` | +1 | alternates +1, -1, +1... |
| `TAI` | alternates +1, -1... | +1 |

The alternation adds then subtracts one, it does not invert bit 0 (pcetech).
Reads of the hardware page `$0800`-`$13FF` by a block transfer return **zero**
without touching the device or the I/O buffer; writes work (pcetech; this is
CPU behaviour, so the core owns it, U7). Registers `A`, `X`, `Y` are restored
at the end whatever happened to them in between. 17 + 6n is confirmed by the
manual (HW HB-6), pcetech, MAME and, over all 12,500 block cases, by the
SingleStepTests data (timing.md).

## What the core owns, and what it does not

Owned (this repository): the CPU and its instruction set, **the MMU** (MPR0-7,
`TAM`/`TMA`, the 21-bit address the callbacks receive, the zero page and stack
at `$2000`/`$2100`, `ST0`-`ST2` bypassing it), T, the block transfers (with
their zero-read rule and their uninterruptibility), CSL/CSH as a visible
`high_speed` state, the interrupt inputs (NMI, IRQ1, IRQ2, TIQ, reset) with
their vectors and priority, `BRK`.

Not owned: the VDC, VCE, PSG, CD-ROM and joypads; the one-cycle VDC/VCE stretch
(board: it decodes the address); **recommended board-owned, decision for
Aubrey**: the timer, the interrupt disable and request registers, the I/O
buffer and the ports. The reasoning (chip-extraction rule, RP2A03 precedent,
the alternative of an `onchip` helper in the core) is in the
[decisions](handoff-brief.md#the-core-boundary).

## The embedding contract (proposed; the build session may refine)

```python
cpu = HuC6280(read_byte, write_byte, idle)
#   read_byte(address) -> int      a bus read; address is the 21-bit physical address
#   write_byte(address, value)     a bus write
#   idle(address)                  a cycle with no data transfer; address is the
#                                  dummy-read address the corpus records, or None
# Inside any callback: cpu.kind is READ, DUMMY_READ, WRITE or IDLE; cpu.high_speed
# is the current speed; cpu.dummy_read says the access is Mesen's "r-d".
cycles = cpu.step()    # CPU cycles consumed == number of callbacks made
```

- The board advances its devices **inside** the callbacks, by 3 or 12 master
  clocks (by `cpu.high_speed`) plus its own VDC/VCE stretch, never by adding
  `step()`'s return on top; the same discipline as 65816-python's contract.
- A block transfer is **one `step()` per byte** (the chip does not refetch, so
  there is nothing to refetch: the step is "one iteration", the entry and exit
  sequences are the first and last steps) or one step for the whole transfer;
  an interrupt must still not be taken between iterations. The build session
  decides; the whole-instruction form is simplest and is what every emulator
  does, at the price of a long single call (up to 393,233 cycles).
- The interrupt API is 6502-python's (`request_maskable_interrupt`,
  `request_non_maskable_interrupt`, `request_reset`), extended with the three
  maskable sources as request bits ([handoff-brief.md](handoff-brief.md)).
- Plain integers in the hot path, no generators, so a `huc6280-rust` and
  `-fast` forks can transcribe it.
