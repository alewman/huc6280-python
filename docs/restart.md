<!-- SPDX-License-Identifier: MIT -->
# The clean rewrite (2026-11-19)

The provenance audit of 2026-11-13 ([provenance.md](provenance.md)) marked parts of this core
**rewrite** (code or a rule whose only source was GPL code that had been read) or **unclear**.
On 2026-11-19, Aubrey asked for those parts to be rewritten: "rewrite the modules that used GPL
sources if we haven't already". This document gives the rules the pass followed (the PC Engine
family's, adapted from sn76489-python's [restart rules](../../sn76489-python/docs/restart.md) and the
family charter's provenance rules), what was replaced, and the judges before and after.

## The rules

1. **No GPL or LGPL source is read**: Mesen2, Mednafen and its Beetle ports, Geargrafx, srg320's
   TurboGrafx16 MiSTer VHDL, MAME's GPL files. Not to learn, not to check a constant, not when a
   comparison fails. Their trees sit under the git-ignored `reference/` so that they can be built
   and run; they are not opened, searched or grepped.
2. **The code being replaced is not read.** Before anything was written, the tainted lines were
   moved, unread, into the git-ignored `scratch/withdrawn/` with a helper (`_alu.py` lines 1-106:
   the decimal functions and the module head; `_control.py` lines 308-375: the two interrupt
   switches, `_boundary_interrupt` and `_maskable_vector`). The replacements were written from the
   evidence below. Call sites and the tests that define the interface were read; documents that
   quoted GPL code or named its internals were not used as sources and were rewritten.
3. **Permitted sources**: Hudson's manuals; MacDonald's pcetech; MAME's files whose first line
   says `license:BSD-3-Clause` (`h6280.cpp`, `bus/pce/pce_slot.cpp`); ares (ISC);
   SingleStepTests (MIT test data). What was ported from MAME carries its notice
   ([NOTICE.md](../NOTICE.md)).
4. **GPL emulators may be run as closed boxes**: Mesen2 2.1.1's library (`MesenCore.so`, through
   its exported functions and Lua), the traced Mednafen 1.32.1 build (`scripts/mednafen_trace.py`;
   the patch is a GPL-2.0-or-later tool file), and srg320's `HUC6280_CPU` under GHDL (driven only
   through its entity's ports). They are detectors and measuring instruments. A value taken from
   their outputs is marked as a closed-box measurement or OBSERVED, provisional, with the emulator
   named, and any document or hardware result overrules it.
5. **Every rule in the new code names its source** with an evidence tag, or says it is a choice.
6. **The gates are external**: SingleStepTests, the Rockwell corpus, Dormann, the MAME replays,
   the VHDL, and the closed-box runs. The withdrawn code's output is not a target; its results are
   recorded as "before".
7. Chip-level choices are not put to Aubrey: the best-supported option is taken and marked
   provisional.
8. House rules: only this repository is edited; no push, no tag.

## The closed-box tools written for this pass

| Tool | What it runs | What it settles |
| --- | --- | --- |
| `scripts/decimal_tables.py` | an 8 KB HuCard of every decimal `ADC $00`/`SBC $00` (262,144 operations) on the traced Mednafen; the SingleStepTests decimal cases (Mesen's output) | C13's two result tables |
| `validation/vanish_rom.py`, `validation/vanish_probe.py` | HuCards where a timer or VDC interrupt is acknowledged in the last cycle of the instruction that polled it, and their controls; a timer taken between `SET` and its target; on Mesen2, Mednafen and MAME | C18's default, C16 |
| `validation/vanish_vhdl.py`, `tests/huc6280_vhdl/tb_vanish.vhd` | srg320's VHDL under GHDL with an interrupt line released or raised in a chosen cycle; the `SET` entry; read data driven late | U25 `"last"`, the withdrawn `"latched"`, C16, C3, the testbench's port timing |
| `validation/mednafen_votes.py` | single instructions on the traced Mednafen | C4, C5, C6, C9, C12 votes |

## What was replaced, item by item

| Item | Before | After | Source of the new behaviour |
| --- | --- | --- | --- |
| C13 decimal `ADC`/`SBC` | functions written from a prose restatement of GPL code | `_decimal_add`/`_decimal_subtract` written from the two closed-box tables alone, before the recorded digests were looked at; the digests then matched for both formulas and both operations | closed-box measurement (emulator tier): Mednafen 1.32.1 (full table), Mesen via SingleStepTests (11,346 cases) |
| C18 `vanished_interrupt = "mesen2"` | read from Mesen2's source | the same behaviour, rewritten: IRQ1/IRQ2 as polled, the timer only if still asserted | OBSERVED, provisional: Mesen2 and Mednafen agree on all four probe cards |
| C18 `"latched"` | read from the VHDL's source | **withdrawn** (`ValueError`) | the VHDL under GHDL decides on the levels at the end of the last cycle for every source, which is U25 `"last"`; with `"last"`, `"latched"` and `"drop"` cannot differ |
| U25 `irq_poll_cycle = "mednafen"` | read from Mednafen's source (a quoted expression) | **withdrawn** (`ValueError`) | not re-established (see "Open" below) |
| U25 `"last"` | an own rule | kept, rewritten in `_boundary_interrupt`; now with evidence | OBSERVED: srg320's VHDL under GHDL; MAME's BSD-3 h6280 decides at the boundary too |
| C6 `TMA` several bits | "Mesen's, read from source" | unchanged (OR) | OBSERVED: all 2,418 multi-bit SingleStepTests cases; MAME (BSD-3) and Mednafen (closed box) take the highest bit |
| C7 `CSL`/`CSH` speed in the last cycle | Mesen and Mednafen comments | unchanged | OBSERVED: the traced Mednafen (4 + 4 + 1, 1 + 1 + 4) |
| C16 T cleared on an entry | unnamed emulator | unchanged; a test added | OBSERVED: Mesen2 and Mednafen closed box; ares (ISC); the VHDL dissents |
| C12 `TSB`/`TRB` Z | pcetech, MAME and GPL sources | unchanged | pcetech 2.0 (hw-verified); MAME (BSD-3); Mednafen (closed box) |
| U8 zero-page pointer wrap | MAME and a Mesen function | unchanged | MAME (BSD-3, notice in NOTICE.md); SingleStepTests' 226 cases at `$FF` |
| BRK as the interrupt sequence; C3 entry shape | GPL internals named | unchanged | SingleStepTests' `BRK` records; Mesen2's bus observed closed box (two reads at PC, three pushes, the vector, a cycle with no access: the core's order); ares (ISC) 8 cycles |
| Block-transfer shape | "Mesen's" | unchanged | SingleStepTests' records |
| Harness HuCard mirroring | Mesen2's (`bank_offsets`) | **changed**: MAME's `rom_map_setup` (BSD-3, ported with notice). 512 KB cards now repeat whole (blocks 0 1 2 3 0 1 2 3, before 0 1 2 3 2 3 2 3); 192 KB images map 0 1 2 2 0 1 2 2 (before: a plain repeat); 384 KB and 768 KB unchanged | MAME 0.285 `bus/pce/pce_slot.cpp`; pcetech 3 ("may be mirrored") |
| `tests/test_directed.py` comments, the documents | quoted GPL comments and code, named internals | rewritten as observed behaviour | the runs above |
| `tests/huc6280_vhdl/tb_huc6280.vhd` header | described the VHDL's insides | port timing, OBSERVED in simulation (`tb_vanish.vhd` `late`): data driven 1 ns after the rising edge is misread | GHDL run |

## Behaviour changes a transcription must carry (huc6280-rust)

- `vanished_interrupt`: only `"mesen2"` (default) and `"drop"`; `"latched"` raises `ValueError`.
  The default's behaviour is unchanged.
- `irq_poll_cycle`: only `"second_to_last"` (default) and `"last"`; `"mednafen"` raises
  `ValueError`. Behaviour of the two kept modes unchanged.
- `_boundary_interrupt` and `_maskable_vector` are new code with the old interface: the
  boundary records `_poll_lines` (the polled lines, or the live lines under `"last"`), and the
  vector is chosen from `_poll_lines` and the live lines, priority TIQ, IRQ1, IRQ2. No state
  field was added or removed.
- `_alu.add`/`subtract`: new code, identical results for every input of both formulas (the
  digests); `DECIMAL_FORMULAS = ("mednafen", "mesen")`. An unknown formula raises
  `ValueError` when a decimal `ADC`/`SBC` runs (what `test_c13_an_unknown_formula_is_refused`
  requires); binary-mode arithmetic does not look at the formula.
- `harness.bank_offsets`: 512 KB and 192 KB images map differently (above). Test tooling only;
  the core is unaffected.

## Open, and what would settle it

- **U25 `"mednafen"`** (timer counted at the boundary, IRQ1/IRQ2 sampled). The falling half is
  consistent with the closed-box C18 cards (Mednafen drops a timer acknowledged in the last cycle
  and takes a VDC interrupt acknowledged then). Issue 0003's Final Soldier lockstep, measured with
  the withdrawn mode, also moved its stop. What the cards cannot show is a timer that *appears*
  in the last cycle. Settling it needs the timer's phase measured independently of the interrupt:
  two cards identical up to a point, one reading `$1403` in a loop with I set (the cycle at which
  a read first sees the timer) and one with I clear (the boundary that takes it), both traced on
  Mednafen. If the mode is wanted back, write it from that description and re-run issue 0003's
  lockstep.
- **C16**: Mesen2, Mednafen and ares clear T for the handler, srg320's VHDL does not; no hardware
  result.
- **C6**: the corpus (Mesen) ORs, MAME and Mednafen take the highest bit; the default stays the
  corpus's.
- **C13**: neither table is a hardware result; a HuCard storing every decimal result, run on a
  console, would settle it.
- Nothing here was run on hardware.

## Judges, before (75f4585) and after

| Judge | Before | After |
| --- | --- | --- |
| quick suite, CPython 3.14 | 1,598 passed, 1 skipped | 1,601 passed, 1 skipped |
| quick suite, PyPy 3.11 | 1,598 passed, 1 skipped | 1,601 passed, 1 skipped |
| rung 1 SST, default formula | 640,000 / 640,000; 1,552 `decimal_formula` | the same, every mask count equal |
| rung 1 SST, `--formula mesen` | 640,000 / 640,000, no decimal mask | the same |
| rung 1 SST, `--formula mednafen` | 638,448 passed, the 1,552 decimal cases fail (expected) | the same |
| rung 1b Rockwell, both formulas | 2,089,891 passed, 0 failed (3,195 / 3,164 `decimal_formula`) | the same |
| rung 2 Dormann | success at `$5675`, 20,936,652 instructions | the same |
| rung 4 MAME replays (six games) | 0 register divergences; cycles as recorded | identical logs |
| rung 5 VHDL (30 cases per opcode) | 7,554 cases, categories as recorded | identical report (the testbench rebuilt from its new header) |
| pcengine-python quick suite | 253 passed (pinned 265df88) | 253 passed (this tree by `PYTHONPATH`) |

The three tests added: the MAME mirroring map, C16's entry between `SET` and its target, and the
refusal of the withdrawn modes (two cases replacing three mode tests).
