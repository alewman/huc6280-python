<!-- SPDX-License-Identifier: MIT -->
# 0004: decimal `ADC` and `SBC` with an invalid BCD digit: the default becomes Mednafen's results

Raised 2026-11-10 (Aubrey's decision, from a second reviewer's finding on C13).
Status: **done 2026-11-10, released in 0.3.0; rewritten 2026-11-19** (docs/restart.md). The
default is `decimal_formula = "mednafen"`; Mesen's results stay as `"mesen"`. Results for valid
digits, binary mode, V, cycles and the T flag do not change.

This document was rewritten on 2026-11-19. Its earlier text restated two GPL emulators' code in
prose; that text is withdrawn, and so is the code written from it. What follows describes the two
emulators' **results**, recorded by running them as closed boxes, and the rules written from those
results alone.

## The question

No Hudson manual says what the digit adjust does when a digit of A or the operand is above 9, and
no hardware result is known. Two emulator results exist and differ only there.

## The tables (closed-box measurements, emulator tier)

`scripts/decimal_tables.py` records both:

- **Mednafen 1.32.1**, the traced build (scripts/mednafen_trace.py, run, never read): an 8 KB
  HuCard written here runs `ADC $00` and `SBC $00` with D set, carry clear and set, for every A and
  operand: all 262,144 operations. The trace gives the state before each instruction, so each
  result is the next line's A and P.
- **Mesen**, through SingleStepTests huc6280 (MIT test data recorded from Mesen): its 11,346
  decimal ADC/SBC cases with T clear, over the eighteen opcodes. A sample of the 131,072 inputs
  per operation.

What both tables show: V is never changed; N and Z follow the stored result; the only difference
between the two is the result and C when a digit is above 9.

## The rules, written from the tables

Mesen's table fits a rule that adjusts each digit on its own: a low digit sum above 9 gains 6 and
carries exactly 1 into the high digit, which then gains 6 above 9 and sets C above 15; for SBC a
low digit difference below 0 loses 6 and borrows exactly 1, and C is clear when the high digit goes
below 0.

Mednafen's table fits a rule on the binary result: for ADC, the binary sum, plus 6 when the low
digits' sum is above 9, plus $60 when what stands above the low digit is then above 9, C from bit 8;
for SBC, the binary difference, minus 6 when the low digits borrow, minus $60 when the whole
subtraction borrows, C the binary one. So a low digit past $1F carries 2 into the high digit, and
the high adjust of SBC follows the binary borrow, not the high digit's.

Examples: `SBC` of `$00 - $0A` with the borrow in gives `$8F` (Mednafen) and `$9F` (Mesen);
`ADC` of `$0A + $0F + 1` gives `$20` (Mednafen) and `$10` (Mesen); valid digits agree
(`$19 + $28 + 1 = $48`).

Over all 131,072 inputs per operation the two rules give different results for 9,216 (ADC) and
9,216 (SBC), and a different ADC carry for 324; every one has a digit above 9
(tests/test_mednafen.py).

## Checks

- Both rules reproduce their tables exactly (`scripts/decimal_tables.py`: 11,346 and 262,144
  recorded, 0 differ).
- The SHA-256 digests of the full result tables recorded on 2026-11-10 (tests/test_mednafen.py;
  outputs, which are facts) match the rules written on 2026-11-19, for both formulas and both
  operations. They were used only as the acceptance check, after the rules were written.
- SingleStepTests huc6280 passes whole with `--formula mesen`; with the default its 1,552
  disputed cases are counted as `decimal_formula` (rung 1).
- The Rockwell 65C02 set's decimal SBC cases agree with the default (tests/test_mednafen.py).

## Why the default is Mednafen's

Aubrey's decision of 2026-11-10, from a reviewer's finding; the earlier record cites Mednafen's
ChangeLog of 2015-04-29 as its author's statement of a hardware test. That statement was not
re-read in this pass, so the default stays **emulator tier, provisional**.

## What is not claimed

Neither rule is a hardware result. A test of decimal arithmetic with invalid digits on a real
console (a HuCard that stores the results of every input, compared with these tables) would settle
it.
