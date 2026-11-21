<!-- SPDX-License-Identifier: MIT -->
# Changelog

Releases are git tags; install one with
`pip install "huc6280-python @ git+https://github.com/alewman/huc6280-python@v0.4.0"`.
The package is not on PyPI (it depends on 6502-python by git commit).

## Unreleased

The clean rewrite ([docs/restart.md](docs/restart.md)): the parts the provenance audit marked
rewrite or unclear are replaced or re-established from closed-box runs and permissive sources; no
GPL source was read and the replaced code was moved aside unread.

- **C13 decimal `ADC`/`SBC`**: `_decimal_add`/`_decimal_subtract` rewritten from two result tables
  recorded closed box (`scripts/decimal_tables.py`: Mednafen 1.32.1 traced, 262,144 operations;
  SingleStepTests' 11,346 decimal cases). Results identical for every input of both formulas (the
  recorded digests match). No default changed.
- **Behaviour change (switches):** `vanished_interrupt = "latched"` and `irq_poll_cycle =
  "mednafen"` are withdrawn and raise `ValueError`. The defaults (`"mesen2"`,
  `"second_to_last"`), `"drop"` and `"last"` behave as before; their code is new.
  `_boundary_interrupt` now clears `_polled_lines` (the lines exist until the next boundary only,
  as `cpu.py` and `CPUState` say), so a capture right after an entry reports `polled_irq_lines =
  None`.
- **Behaviour change (harness, test tooling only):** HuCard mirroring is MAME's (`bank_offsets`,
  ported from BSD-3 `pce_slot.cpp`, NOTICE.md): 512 KB cards repeat whole, 192 KB images map
  `0 1 2 2 0 1 2 2`.
- C18's default, U25 `"last"`, C3, C6, C7, C12, C16, U8 re-established closed box or re-cited
  (Mesen2's library, the traced Mednafen, srg320's VHDL under GHDL, MAME BSD-3, ares ISC); new
  probe tools in `validation/` and `tests/huc6280_vhdl/tb_vanish.vhd`; a C16 test.
- Documents: issues 0002 and 0004 rewritten; quotes of GPL code and comments and GPL internal
  names removed everywhere; SPDX headers on every touched file; `docs/provenance.md` verdicts
  updated item by item.
- Judges, before (`75f4585`) and after: identical. Quick suite 1,598 -> 1,601 passed (1 skipped) on
  CPython 3.14 and PyPy 3.11 (three tests added, the withdrawn modes' tests replaced). Rung 1
  SingleStepTests 640,000 of 640,000 in both formulas (`--formula mesen` no mask; default 1,552
  counted as `decimal_formula`), masks unchanged. Rung 1b Rockwell 2,089,891 passed, 0 failed, both
  formulas, masks unchanged. Rung 2 Dormann: success at `$5675` after 20,936,652 instructions.
  Rung 4: the six MAME replays unchanged (0 register divergences each). Rung 5 (VHDL, 7,554 cases):
  identical report. pcengine-python's quick suite: 253 passed with the pinned core and with this one.

## 0.4.0 (2026-11-14)

Interrupt edge cases the Rust port found ([issue 0005](docs/issues/0005-interrupt-edge-cases-found-by-the-rust-port.md)),
each a bug against the core's own poll rule (the poll sees the lines as they stood at the end of
an instruction's second-to-last cycle; BRK, entries and reset do not poll; a capture and restore
changes nothing). No default changed and no switch was added.

- **Behaviour change:** the instruction an entry runs when its source has gone (C18) now does
  the bookkeeping any instruction does: a line raised in its last cycle waits one more
  instruction instead of being taken at the next boundary.
- **Behaviour change:** the poll keeps each of the three lines, not only "an enabled line is
  asserted": a source that drops in an instruction's last cycle while another rises (TIQ for
  IRQ1, say) is decided on what the poll saw. By default the gone timer is dropped (C18) and the
  new source waits for the next poll; `vanished_interrupt = "latched"` takes the polled one.
- **Behaviour change:** `BRK` does not poll, like an interrupt entry (the code now does what
  `CPUState`'s docstring said). Visible only through NMI, which no PC Engine connects: BRK sets I.
- **State format:** `CPUState.polled_irq_lines` (`int | None`, default `None`): the lines the last
  poll saw, IRQ2/IRQ1/TIQ in bits 0-2, when a line changed after it; `None` when the poll saw the
  lines as they stand. A state without it (default `None`) loads as before. `capture_state` and
  `restore_state` carry it, so a round trip at any boundary is now exact.
- `debug.next_boundary` decides the vector from the polled lines and drops a vanished timer, as
  the default class attributes do (it fell through to `IRQ2` before).
- Rung 4's replay (`tests/mame_replay.py`) no longer leaves a line asserted when MAME's next line
  is already the handler.

## 0.3.0 (2026-11-12)

- **Behaviour change:** decimal `ADC` and `SBC` with an invalid BCD digit follow Mednafen's
  formulas by default (its changelog says they were corrected "per tests on a HuC6280");
  `decimal_formula = "mesen"` restores the previous results. Valid digits, binary mode, V, cycles
  and the T flag are unchanged ([issue 0004](docs/issues/0004-decimal-adc-sbc-mednafen-formulas.md)).
- Rung 5's bus comparison runs the core with the corpus's own decimal formula.
- **Provenance:** the decimal routines of the first version of this change (commits d575521 to
  9c47c98, never tagged) were transcriptions of Mednafen's (GPL-2.0) and Mesen2's (GPL-3.0) code.
  They are rewritten from a description in words, the test keeps only digests of the result
  tables, and the quoted code is gone from the issue; the results are bit-identical.
- `tools/mednafen-trace.patch` is marked GPL-2.0-or-later (it is a patch to Mednafen).

## 0.2.0 (2026-11-07)

- `irq_poll_cycle` (U25): where an instruction polls its interrupts, as a named switch; the
  default is unchanged ([issue 0003](docs/issues/0003-interrupt-sampling-point-and-the-covell-spread.md)).
- `HuC6280.opcode`: a public, read-only accessor for embedders.
- Rung 4b: Mednafen 1.32.1 as a second emulator referee (six games, 20.4 million instructions).

## 0.1.0 (2026-10-24)

- The core: rungs 0, 1, 1b, 2, 3, 4 and 5 ([docs/validation.md](docs/validation.md)).
- Block transfers read zero over `$0800-$17FF` ([issue 0001](docs/issues/0001-block-read-range-reaches-irq-registers.md)).
- An interrupt whose source has gone before its entry is dropped, `vanished_interrupt = "mesen2"`
  ([issue 0002](docs/issues/0002-interrupt-taken-after-its-source-is-gone.md)).
