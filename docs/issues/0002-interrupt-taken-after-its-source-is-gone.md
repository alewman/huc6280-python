<!-- SPDX-License-Identifier: MIT -->
# 0002: an interrupt polled one cycle early is entered after its source has gone, through the IRQ2 vector

Raised 2026-10-24 by `pcengine-python` M2 (first ten library titles against Mesen2 and Beetle PCE,
run as closed boxes). Status: **closed** (2026-10-24, "Fix issue 0002"; rewritten and
re-established closed box 2026-11-19, docs/restart.md): `vanished_interrupt` class attribute,
default `"mesen2"` (the timer is dropped when it has gone, IRQ1 and IRQ2 are taken as the poll saw
them); `"drop"` is the other mode; no mode falls through to `$FFF6`. See C18 in
undocumented-behavior.md; rung-3 tests `test_c18_*`.

## What happens

*After Burner II (Japan)* (`After Burner II (Japan) (En).pce`, 512 KiB, plain card) runs normally
in Mesen2 and Beetle PCE and executed garbage on the board with this core. The trace, from reset:

- the game's timer handler (TIQ vector `$FFFA` -> `$E8A2`) re-enables interrupts with `CLI` and then
  acknowledges the timer with `STZ $1403` at `$E8D2`;
- the core polls at the end of the instruction's second-to-last cycle (6502-python frame, U21), when
  TIQ is still asserted, so the request is set;
- the write to `$1403` in the instruction's last cycle lowers TIQ, and the frame clears its
  `IRQ_LINE` request, but the poll had already seen it;
- the entry therefore happened at the next boundary, found no enabled source asserted and fell
  through to the IRQ2 vector; the game's `$FFF6` points at `$EE7B`, which is data. The next
  instructions were garbage.

## What the emulators do, run as closed boxes (2026-11-19)

`validation/vanish_rom.py` builds four HuCards. Each waits, with I set, until the source shows in
`$1403`, then runs `CLI` and an instruction whose last cycle acknowledges the source: the timer by
`STZ $1403` (a write, After Burner II's shape) and the VDC's vertical-blank interrupt by
`LDA $0000` (a status read). Two controls put a `NOP` there instead, so the source stays.
`validation/vanish_probe.py` runs them on Mesen2 2.1.1 (its library, read through Lua), the traced
Mednafen 1.32.1 build and MAME 0.285:

| Card | Mesen2 | Mednafen | MAME |
| --- | --- | --- | --- |
| timer acknowledged in the last cycle | no entry; the main line goes on | no entry | entered before the site (see below) |
| VDC acknowledged in the last cycle | IRQ1 entered, return address after the read | IRQ1 entered | entered before the site |
| timer held (control) | TIQ entered | TIQ entered | entered before the site |
| VDC held (control) | IRQ1 entered | IRQ1 entered | entered before the site |

MAME takes the interrupt at the boundary right after `CLI` (its I flag counts at once; U21), so the
situation never arises there on these cards. `validation/vanish_vhdl.py` runs srg320's
HUC6280_CPU under GHDL with the line released in a chosen cycle: it takes nothing when a line goes
in any cycle up to and including the instruction's last, and takes a line that appears in the last
cycle at that boundary, for all three sources alike. That is `irq_poll_cycle = "last"` (U25), not a
separate rule for a vanished source.

No hardware result is known.

## Resolution

| Option | Effect on After Burner II | Basis |
| --- | --- | --- |
| `"mesen2"` (default): the timer dropped when gone, IRQ1/IRQ2 taken as polled | runs | Mesen2 and Mednafen agree on every card (OBSERVED, emulator tier) |
| `"drop"`: every source must be polled and still asserted | runs | the timer rule applied to every source (a choice) |
| `irq_poll_cycle = "last"`: the levels at the boundary | runs | srg320's VHDL as a closed box; MAME's BSD-3 source decides on the levels at the boundary too |

The fall-through to the IRQ2 vector, which no source describes, is gone in every mode. A
`"latched"` mode (take every source as the poll saw it) was withdrawn on 2026-11-19: it was written
from the VHDL's source, and the VHDL run as a closed box behaves as `"last"` instead.

Found by: `pcengine-python` `scripts/m2_compare.py`, After Burner II at frame 300.
