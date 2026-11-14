# 0005: interrupt edge cases the Rust port found

Raised 2026-11-12 by the huc6280-rust build (its `scripts/reference_notes.py` demonstrates the
first three on this core). Status: **closed** (2026-11-13): items 1-4 fixed, item 5 fixed in the
test tooling. Every fix is against the core's own stated rule; no default changed, no switch was
added, and one `CPUState` field was added (with a default). huc6280-rust reproduced each, so the
two cores agreed; the question was whether this core was right. None has a hardware source either
way, and none needed one: each contradicted a rule the core already states.

## The rule the items are judged against

The poll sees the interrupt requests as they stood at the end of an instruction's second-to-last
cycle; a change in the last cycle waits for the next instruction's poll. BRK, an interrupt entry
and reset do not poll. A request the host makes between steps counts at the next boundary.
(6502-python's frame, which this core subclasses, `CPUFrame.step` and its docstring; NESdev "CPU
interrupts", research tier, for the 6502; here U21 and U25's default `"second_to_last"`, and
start-here.md, "Reset and interrupts".) And `CPUState` is "complete CPU-owned state at an
instruction boundary": restoring a captured state continues exactly as the run that was never
interrupted (the board's save states rely on it: pcengine-python `state.py`).

## The items

1. **A vanished interrupt skipped the last-cycle rule.** When an entry found its source gone
   (`vanished_interrupt`, C18), `_enter_interrupt` returned `self._execute()` directly and bypassed
   `step()`'s deferred-to-polled bookkeeping: a line raised in that instruction's last cycle was
   taken at the next boundary, not one instruction later as everywhere else.
   **Decision: fix** (a plain bug against the rule: the instruction is an instruction like any
   other). `_enter_interrupt` now does after `_execute()` what `CPUFrame.step` does: a pending
   `_deferred` becomes `_polled`.
2. **A source swap in the last cycle was taken at once.** If TIQ dropped and IRQ1 rose in the same
   last cycle, the frame's `IRQ_LINE` never changed, nothing was deferred, and IRQ1 was entered
   although it rose after the poll. **Decision: fix** (against the rule: the poll saw TIQ, not
   IRQ1). The core now keeps the lines themselves at the poll, not only the frame's one bit: any
   change of the three lines arms the frame's "does an access follow?" watch (`_request` with the
   requests unchanged), each confirming access records the lines (`_lines_at_access`, in an
   override of `_confirm`), and `_execute` leaves `_polled_lines` set when the lines changed after
   the last access. The boundary decides on those lines. What the poll saw is then decided by
   C18's switch, unchanged: by default the timer has gone and is dropped, the instruction runs, and
   IRQ1 is taken after it (one instruction later, as any line rising in the last cycle);
   `"latched"` enters TIQ, as polled; `"drop"` enters TIQ (a source is still asserted).
3. **Capture and restore were not transparent at one kind of boundary.** `_lines_before` was not in
   `CPUState`: with IRQ1 dropped in an instruction's last cycle, the interrupt was entered without a
   restore and not entered after `restore_state(capture_state())`. **Decision: fix** (against
   `CPUState`'s own contract). New field **`CPUState.polled_irq_lines: int | None = None`**: the
   lines the last poll saw (bit 0 IRQ2, bit 1 IRQ1, bit 2 TIQ, the `$1403` layout, as
   `irq_disable`), set only when a line changed after the poll; `None` when the poll saw `irq1`,
   `irq2`, `tiq` as they stand. Validated as 0-7 or None. `capture_state` writes it,
   `restore_state` reads it. **Backward compatible:** a state saved before the field (a board's
   JSON without the key, `CPUState(**fields)`) gets `None`, which is what the old restore assumed
   for every state; the only states that load differently from how they were saved are those
   saved at exactly such a boundary, which the old core could not restore faithfully anyway. A
   state saved by the new core does not load into the old one (an unknown keyword).
4. **BRK and the poll.** `CPUState`'s docstring said BRK does not poll, but `_op_brk` never set
   `NO_POLL`. **Decision: the docstring is right; fix the code.** On the 6502 BRK is the interrupt
   sequence and does not poll (6502-python's `_interrupt` sets `NO_POLL` for BRK, IRQ and NMI;
   NESdev "CPU interrupts", research tier; the frame's docstring names BRK with entries and reset).
   On the HuC6280 the detectors say the same thing in their structure: Mesen2 runs BRK through
   the entry routine (`ProcessIrq(forBrk)`), and srg320's HDL enters an interrupt by forcing
   opcode `$00` (C16), so BRK and an entry are one microcode sequence and cannot differ in whether
   they poll. Emulator tier for the HuC6280 itself, but no source says otherwise. `_op_brk` now ends
   with `self._deferred = NO_POLL` (as 6502-python's does; `step()` moves it to `_polled`). Only an
   NMI shows the difference (BRK sets I, so no maskable source can be taken after it either way),
   and NMI is not connected on any PC Engine.
5. **Test tooling only.** `tests/mame_replay.py`'s `_take_interrupt` returned early with the line
   it had just asserted still asserted when PC already equalled the handler. **Decision: fix**:
   the check now comes before the line is asserted. The forced path also clears `_polled_lines`
   with `_polled` and `_polled_i` (MAME's board decided). Neither ever fired in the six traces: the
   rung-4 numbers are identical before and after.

Also: `debug.next_boundary` (the debugger's "what will the next step do") chose the vector from the
current lines and fell through to `IRQ2` with none left. It now decides from the polled lines and
drops a vanished timer, as the default class attributes do (the class attributes are not state).

## Tests (rung 3, `tests/test_directed.py`, "issue 0005")

Each fails on ea4fe2a and passes now:

- `test_0005_a_line_rising_in_a_vanished_entrys_instruction_waits_for_the_next_poll` (item 1:
  `CLI; NOP x4`, TIQ drops in cycle 3, IRQ1 rises in cycle 5; PC after each step
  `$4001 $4002 $4003 $4004 $6100`, as without the vanished entry; before: `$6100` one step early);
- `test_0005_a_source_swapped_in_the_last_cycle_is_not_taken_at_that_boundary` (item 2, default and
  `"latched"`);
- `test_0005_capture_and_restore_keep_the_lines_the_poll_saw` and
  `test_0005_a_round_trip_at_any_boundary_changes_nothing` (item 3: a capture and restore before
  every step of each of the three scenarios gives the same trail);
- `test_0005_a_state_from_before_the_field_loads_as_the_poll_agreeing` (the default and the range);
- `test_0005_brk_does_not_poll` (item 4: an NMI latched in BRK's second cycle is taken after the
  handler's first instruction; `skipped_poll` after BRK);
- `tests/test_mame_replay.py::test_take_interrupt_at_the_handler_already_leaves_no_line_asserted`
  (item 5).

huc6280-rust's `scripts/reference_notes.py` on this core now prints, for items 1-3: the same trail
after a vanished entry as after a plain instruction; `$4003` (the NOP ran) for the swap; `$5100` with
and without the round trip.

## Judges, before (ea4fe2a) and after

| Judge | Before | After |
| --- | --- | --- |
| Quick suite (CPython; PyPy after) | 1,589 passed, 1 skipped (no Mednafen traces) | 1,598 passed, 1 skipped, CPython and PyPy |
| Rung 1, SingleStepTests, PyPy | 640,000 of 640,000; masks as recorded | identical |
| Rung 2, Dormann | success at `$5675`, 20,936,652 instructions | identical |
| Rung 3, directed | in the quick suite | + 9 tests |
| Rung 4, MAME replays, six games, whole traces, PyPy | 0 register divergences; cycle and interrupt counts as recorded | every line identical |
| Rung 4b, Mednafen | not run: `tests/mednafen_traces/` is absent (gitignored, deleted after the 2026-10-24 run) | not run |

No SingleStepTests case has an interrupt line, so rung 1 cannot move; MAME's replays take
interrupts from MAME's own board, and none of the six landed on a last-cycle change the fix
treats differently.

## Downstream

- **huc6280-rust** (and the -fast fork) must carry: the vanished path's bookkeeping in
  `enter_interrupt`; the per-line poll state (`lines_at_access` refreshed on every confirm,
  `polled_lines` set at the end of `execute` when `deferred` is pending and the lines differ, used
  and cleared at the boundary, updated by a between-steps `set_irq_lines` bit by bit, cleared by
  reset); `set_irq_lines` returning early when nothing changed and arming the watch on any change;
  BRK's `NO_POLL`; the `polled_irq_lines` state field; `next_boundary`'s decision.
- **pcengine-python** embeds `CPUState` in its save states (`dataclasses.asdict` /
  `CPUState(**fields)`): a repin adds the key `polled_irq_lines` to new states; old states load.
  Checked 2026-11-13 without editing the board (5533552, this core by `PYTHONPATH`): its quick
  suite passes the same with the pinned core and this one (253 passed); the 18-title picture
  gate's runs (`scripts/m2_ours.py`, PyPy, 26 pictures at 300/450/600 frames) are
  **byte-identical** before and after, so the comparisons against Mesen2 and Beetle PCE stand.
  The board does run the changed paths (its devices call `set_irq_lines` from inside bus
  callbacks), so a picture could in principle move; on these titles none did.
