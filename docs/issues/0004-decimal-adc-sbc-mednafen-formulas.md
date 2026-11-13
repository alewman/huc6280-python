# 0004: decimal `ADC` and `SBC` with an invalid BCD digit: the default becomes Mednafen's formulas

Raised 2026-11-10 (Aubrey's decision, from a second reviewer's finding on C13).
Status: **done 2026-11-10, released in 0.3.0.** The default is `decimal_formula = "mednafen"`; Mesen's formulas stay as `"mesen"`. Results for valid digits, binary mode, V, cycles and the T flag do not change.

## What

C13 in `undocumented-behavior.md` recorded that the SingleStepTests huc6280 corpus (Mesen's formula,
which the core followed) and the Rockwell 65C02 corpus disagree for decimal `SBC` with an invalid BCD
digit, and left it *undecidable here*. A source with a stronger tier was in the tree but not read for
this: Mednafen's ChangeLog.

## Evidence

Mednafen 1.32.1, `ChangeLog` line 2239 (April 29, 2015):

> PCE, PCE_FAST: Corrected decimal-mode ADC and SBC behavior(especially for "illegal" input values), per tests on a HuC6280.

An author's statement that a console was tested, with no artefact to re-run: the **hardware-verified**
tier (validation.md), the same as pcetech, and above the SingleStepTests corpus, which is
emulator-derived (it records what Mesen does). The statement says no more than that, and the code
described below is the only place the result is written down; it is a vote with a reason, not a capture.

What that code does (`src/pce/huc6280.cpp`, macros `ADC` and `SBC`, read from the pinned source and
stated here in words; Mednafen is GPL-2.0 and its code is not reproduced in this repository):

- **`ADC`**: add the two ones digits and the carry; if that is 10 or more, add 6. Add sixteen times
  the sum of the two high digits (so everything the ones digit overflowed by is carried, however
  much). If the total is `$A0` or more, add `$60`. Carry out is set when the total passes `$FF`.
- **`SBC`**: subtract the operand's ones digit and the borrow from A's ones digit, then the
  operand's high digit and the first difference's borrow from A's high digit. Assemble the byte
  from the two differences' low four bits, then subtract 6 if the ones digit borrowed and `$60` if
  the high digit borrowed, modulo 256. Carry out is set when the high digit did not borrow.

In both, N and Z come from the result, V is left alone, and the instruction takes its extra cycle.

Mesen2's rule (`PceCpu::ADD`/`SUB`, `Core/PCE/PceCpu.Instructions.cpp`; GPL-3.0, likewise only
described), the core's until now: the ones digit adjusts (+6 past 9) and then passes at most one
carry to the high digit, keeping only its own low four bits; `SUB` adds the operand's complement and
subtracts 6 and `$60` where a digit produced no carry.

## What was re-derived (all 131,072 A x operand x carry combinations, D = 1)

Both rules run over every input (tests/test_mednafen.py keeps the result tables as digests):

| | `ADC` | `SBC` |
| --- | --- | --- |
| combinations where the result byte differs | 9,216 | 9,216 |
| ... of which the carry out differs | 324 | 0 |
| ... of which all four digits are valid | 0 | 0 |

With an invalid operand low digit Mesen's `SBC` is exactly `$10` higher: `$00 - $0A`, C clear: Mesen
`$9F`, Mednafen `$8F`. `ADC`: `$0A + $0F + 1`: Mesen `$10`, Mednafen `$20`; and `$0A + $8F + 1`: Mesen
`$90`, C clear, Mednafen `$00`, C set (an example where C differs).

The other emulators and the MiSTer VHDL were **not** re-run here (the second reviewer's claim: Mesen,
Geargrafx and MAME use the NMOS 6502 formula, i.e. Clark's sequence 3 for `SBC`; Mednafen, ares and
the Rockwell corpus use Clark's sequence 4; MiSTer has its own per-digit adder). Nothing in this
issue depends on it.

### What the two corpora actually differ in (C13's count corrected)

C13 said 38,004. That number is how many Rockwell decimal `SBC` cases with an invalid digit rung 1b
**masked** (its `A, N, Z, C` was not compared in any of them). Run without the mask:

| Rockwell 65C02 corpus, decimal cases (D = 1: 44,881 `ADC`, 44,848 `SBC`) | `ADC` differs | `SBC` differs |
| --- | --- | --- |
| core with Mesen's formula | **0** | **3,164** |
| core with Mednafen's formula | **3,195** | **0** |

So the Rockwell chip does decimal `SBC` as Mednafen does (all 44,848 cases, exact) and decimal `ADC`
as Mesen does. That is a different chip (a 65C02); it is neither a judge for the HuC6280 nor a
contradiction of Mednafen's `ADC`, whose author tested a HuC6280. Against the HuC6280 corpus
(Mesen-generated, 640,000 cases) the default differs in **1,552** cases, all decimal `ADC`/`SBC`.

## Flags, T and timing: Mednafen against the core

No difference was found, each checked in the macros above:

- **V**: left alone in decimal mode by both (Mednafen clears only Z, N, C before the adjust).
- **N, Z**: from the low 8 bits of the result (`X_ZNT(A)`), as the core's `nz`. **C**: Mednafen's `ADC`
  `tmp & 0xFF00`, `SBC` `((n >> 4) & 1) ^ 1`; the core's carry is the same bit of the same value.
- **Extra cycle**: one (`LastCycle()`); the core's dummy read at the next opcode (U23) is the same count.
- **T flag**: `ADC` goes through `TPREFIX`/`TPOSTFIX` (memory at `$2000 + X`, result written back, A
  restored, three more cycles), `SBC` does not (C5); both as in the core. Mednafen clears T after
  every instruction. (`TAM` is not involved.)

## Options

1. Keep Mesen's (the corpus, emulator tier 5): no change; leaves C13 as a recorded disagreement.
2. Mednafen's as the default, Mesen's as a named switch (**chosen**): follows the one source that says
   a HuC6280 was tested; the corpus run keeps an exact-match claim in `"mesen"` mode.
3. The Rockwell formulas (`SBC` as Mednafen, `ADC` as Mesen): rejected, a different chip.

## The change

`HuC6280.decimal_formula` (class attribute, `"mednafen"` default, `"mesen"`), in `_alu.py`. The Mesen
code path is the one that was there. An unknown name raises `ValueError` when a decimal `ADC` or `SBC`
runs. C13 and the Mednafen vote in `undocumented-behavior.md` and `mednafen-oracle.md` are rewritten.

Re-certification (2026-11-10):

- **Rung 1**, `--formula mesen`: **640,000 of 640,000, no decimal mask**; default: 640,000 of 640,000
  with `decimal_formula` **1,552** cases counted (each fails the default and passes in `"mesen"` mode;
  only decimal `ADC`/`SBC`, hence with an invalid digit).
- **Rung 1b**: default, 2,089,891 of 2,089,891 with `decimal_formula` 3,195 (`ADC`) counted; `"mesen"`,
  2,089,891 of 2,089,891 with 3,164 (`SBC`) counted. The old wide `SBC` mask (38,004 cases) is gone.
- **Rung 3**: directed tests for both modes (`tests/test_directed.py`, C13), and an exhaustive
  131,072-combination check of both modes against recorded result tables
  (`tests/test_mednafen.py`). **2026-11-12:** the first version of this change transcribed Mednafen's
  macros into the core and the test and quoted them here; the core's two rules were rewritten from
  the description above, the test keeps only digests of the result tables, and the tables are
  bit-identical before and after.
- **Rung 4**: the six MAME games, 21.0 million instructions: 0 register divergences in the default;
  the six traces run 118 decimal `ADC` and no decimal `SBC`, none with an invalid digit, so neither
  mode can show here. Rung 4b was not rerun (traces are 155 MB each and not present); the same
  six games run no invalid-digit decimal operation, so it cannot move either.

- **Rung 5** (`tests/test_huc6280_vhdl.py`): the bus-bytes comparison runs the core with `"mesen"`
  (the corpus's formula; the full run caught `ADC` with T set writing different bytes under the new
  default), so it stays a test of what crosses the bus; decimal results are C13's question.
- **Full pytest** (CPython 3.14 and PyPy 3.11, slow tests included): 2,048 passed, 1 skipped (the Mednafen
  traces, absent), plus the three rung 5 cases above after that fix; ruff check and format clean.
- **Board** (`pcengine-python`, not modified, not repinned; `PYTHONPATH` to this working tree): 236 passed,
  1 skipped (PIL), 2 deselected. The Mednafen lockstep stops were not rerun.

## What is not claimed

No capture of a HuC6280 doing an invalid-digit decimal operation exists here. The ChangeLog line is the
whole evidence for Mednafen over Mesen. A test ROM run on a real console (a board's job) would decide;
until then `"mesen"` stays one switch away.
