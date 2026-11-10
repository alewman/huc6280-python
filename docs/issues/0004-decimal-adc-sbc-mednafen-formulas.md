# 0004: decimal `ADC` and `SBC` with an invalid BCD digit: the default becomes Mednafen's formulas

Raised 2026-11-10 (Aubrey's decision, from a second reviewer's finding on C13).
Status: **done 2026-11-10, local commits, not released.** The default is `decimal_formula = "mednafen"`; Mesen's formulas stay as `"mesen"`. Results for valid digits, binary mode, V, cycles and the T flag do not change.

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
below is the only place the result is written down; it is a vote with a reason, not a capture.

The code (`src/pce/huc6280.cpp`, macros `ADC` and `SBC`, read from the pinned source):

```c
tmp = (A & 0x0F) + (x & 0x0F) + (P & 1);
if(tmp >= 0x0A)  tmp += 0x06;
tmp += (A & 0xF0) + (x & 0xF0);
if(tmp >= 0xA0)  tmp += 0x60;
P &= ~(Z_FLAG | N_FLAG | C_FLAG);
if(tmp & 0xFF00)  P |= C_FLAG;
A = tmp;  X_ZNT(A);  LastCycle();                       // the extra cycle

const uint8 m = (A & 0xF) - (x & 0xF) - ((P & 1) ^ 1);
const uint8 n = (A >> 4) - (x >> 4) - ((m >> 4) & 1);
uint8 res = (n << 4) | (m & 0xF);
P &= ~(Z_FLAG | N_FLAG | C_FLAG);
if(m & 0x10)  res -= 0x06;
if(n & 0x10)  res -= 0x60;
A = res;  P |= ((n >> 4) & 0x1) ^ 1;  X_ZNT(A);  LastCycle();
```

Mesen2's (`PceCpu::ADD`/`SUB`, `Core/PCE/PceCpu.Instructions.cpp`), the core's formula until now:
the low digit adjusts (+6 past 9) before its carry enters the high digit
(`result > 0x09 ? += 6`, then `+ (result > 0x0F ? 0x10 : 0) + (result & 0x0F)`), and `SUB` adds the
inverted operand and subtracts 6 and `$60` where no carry came out.

## What was re-derived (all 131,072 A x operand x carry combinations, D = 1)

Both formulas transcribed and run (tests/test_mednafen.py keeps the checks):

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
  131,072-combination check of the default against a transcription of Mednafen's C in the test
  (`tests/test_mednafen.py`).
- **Rung 4**: the six MAME games, 21.0 million instructions: 0 register divergences in the default;
  the six traces run 118 decimal `ADC` and no decimal `SBC`, none with an invalid digit, so neither
  mode can show here. Rung 4b was not rerun (traces are 155 MB each and not present); the same
  six games run no invalid-digit decimal operation, so it cannot move either.

## What is not claimed

No capture of a HuC6280 doing an invalid-digit decimal operation exists here. The ChangeLog line is the
whole evidence for Mednafen over Mesen. A test ROM run on a real console (a board's job) would decide;
until then `"mesen"` stays one switch away.
