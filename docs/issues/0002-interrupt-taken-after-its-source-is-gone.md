# 0002: an interrupt polled one cycle early is entered after its source has gone, through the IRQ2 vector

Raised 2026-10-24 by `pcengine-python` M2 (first ten library titles against Mesen2 and Beetle PCE).
Status: **closed** (2026-10-24, "Fix issue 0002"): `vanished_interrupt` class attribute, default Mesen2's split rule (timer re-checked and dropped, IRQ1/IRQ2 taken as polled); `"latched"` (the HDL) and `"drop"` are the other modes; no mode falls through to `$FFF6`. See C18 in undocumented-behavior.md; rung-3 tests `test_c18_*`.

## What happens

*After Burner II (Japan)* (`After Burner II (Japan) (En).pce`, 512 KiB, plain card) runs normally
in Mesen2 and Beetle PCE and executes garbage on the board with this core. The trace, from reset:

- the game's timer handler (TIQ vector `$FFFA` -> `$E8A2`) re-enables interrupts with `CLI` and then
  acknowledges the timer with `STZ $1403` at `$E8D2`;
- the core polls at the end of the instruction's second-to-last cycle (6502-python frame, U21), when
  TIQ is still asserted, so the request is set;
- the write to `$1403` in the instruction's last cycle lowers TIQ (`set_irq_lines(..., tiq=False)`),
  and the frame clears its `IRQ_LINE` request, but the poll had already seen it;
- the entry therefore happens at the next boundary, `_maskable_vector` finds no enabled source
  asserted and falls through to `VECTOR_IRQ2`; the game's `$FFF6` points at `$EE7B`, which is
  data (`BRK ...`). The next instructions are garbage.

`_enter_interrupt` picks the vector at entry from `_lines`; `_maskable_vector`'s last `return` is
the default for "nothing asserted".

## What the other emulators do (tier 5)

Mesen2 (`Core/PCE/PceCpu.cpp`, `ProcessIrq`) decides the vector from the sources *pending at the
poll* and treats the two sources differently, with this comment:

- timer: "'D&D: Order of the Griffon' expects the timer IRQ to NOT occur after the STA [`CLI`;
  `STA $1403`] despite the IRQ being active until the last cycle of the STA instruction": the
  timer source is re-checked live (`HasIrqSource(TimerIrq)`) and the interrupt is dropped when it
  has gone;
- VDC (IRQ1): "Games expect the VDC IRQ to occur after the LDA [`CLI`; `LDA $0000`]" because it was
  active before the last cycle ("Jackie Chan" and "Final Soldier" shake otherwise): taken, through
  its own vector.

Mesen2's comment says this "has not been tested on hardware". No tier 1-3 source here covers it.

## Reading and options

| Option | Effect on After Burner II | Basis |
| --- | --- | --- |
| drop an interrupt whose sources are all gone at the boundary | runs (experiment in `pcengine-python/scripts/m2_ours.py --drop-vanished-irq`) | Mesen2's timer rule, applied to every source |
| remember which sources the poll saw and enter through the highest of *those* | runs; keeps Mesen2's VDC behaviour; the timer case would then take TIQ once more | an interrupt acknowledged in its last cycle was already requested |
| Mesen2's split rule (timer live, VDC latched) | runs; matches the one emulator that documents the cases | the comment above |

The choice between them is **undecidable here** (tier 5 only, and Mesen2's own caveat). What is not
defensible is the present fall-through to the IRQ2 vector, which no source describes.

## Proposed change

Do not take the interrupt when no enabled source is asserted at entry (the smallest change; the
experiment above), or adopt Mesen2's split rule if Aubrey prefers a documented tier-5 reference;
add a rung-3 directed test (`CLI; STZ $1403` with TIQ asserted must not vector to `$FFF6`) and a
U/C entry for the choice. Re-certify rungs 1, 1b, 3 and 4 (the six MAME-replayed games take the
interrupt from MAME's own board, so they should not move).

Found by: `pcengine-python` `scripts/m2_compare.py`, After Burner II at frame 300.
