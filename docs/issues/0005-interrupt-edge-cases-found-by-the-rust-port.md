# 0005: interrupt edge cases the Rust port found (not yet decided)

Raised 2026-11-12 by the huc6280-rust build (its `scripts/reference_notes.py` demonstrates the
first three on this core). Status: **open; nothing changed.** huc6280-rust reproduces each, so the
two cores agree; the question is whether this core is right. None has a hardware source either way.

1. **A vanished interrupt skips the last-cycle rule.** When an entry finds its source gone
   (`vanished_interrupt`), `_enter_interrupt` returns `self._execute()` directly and bypasses
   `step()`'s deferred-to-polled bookkeeping: a line raised in that instruction's last cycle is
   taken at the next boundary, not one instruction later as everywhere else.
2. **A source swap in the last cycle is taken at once.** If TIQ drops and IRQ1 rises in the same
   last cycle, the frame's `IRQ_LINE` never changes, nothing is deferred, and IRQ1 is entered
   although it rose after the poll.
3. **Capture and restore are not transparent at one kind of boundary.** `_lines_before` is not in
   `CPUState`: with IRQ1 dropped in an instruction's last cycle, the interrupt is entered without
   a restore and not entered after `restore_state(capture_state())`. **This matters to save
   states** (pcengine-python `state.py` saves the CPU as `CPUState`): a state saved at exactly
   such a boundary continues differently. The round trips run so far (18 titles, the add-ons) did
   not land on one.
4. **BRK and the poll.** `CPUState`'s docstring says BRK does not poll, but `_op_brk` never sets
   `NO_POLL`.
5. **Test tooling only.** `tests/mame_replay.py`'s `_take_interrupt` returns early with the line
   it just asserted still asserted when PC already equals the handler.

Item 3 is the one with a consequence outside the core; the fix would add the missing field to
`CPUState` (a state format change in the boards). Any change here is repinned through the boards
and transcribed into huc6280-rust.
