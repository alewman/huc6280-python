# 0003: where the core samples an interrupt (U21) is the common cause of four lockstep stops and the Covell spread

Raised 2026-11-04 by `pcengine-python` M1 and M5 (Covell calibration, Mednafen and MAME lockstep).
Status: **open**. A question and an experiment, not a defect report; nothing here is shown wrong.

## What the board sees

The core polls its interrupt lines at the end of the instruction's second-to-last cycle (the
6502-python frame's rule, U21). Against that rule, the board finds the same thing in two places.

### 1. The lockstep against Mednafen (tier 5), four of five stops

Replayed on the current board code, with every VDC and VCE read value equal up to each stop:

| Game | Equal instructions | The stop |
| --- | --- | --- |
| Gradius | 107,737 | IRQ1 rises at the very end of the instruction before the stop (the boundary); Mednafen enters there, the core one instruction later. Mednafen `E11C`, core `EB66` |
| Final Soldier | 630,583 | an entry one instruction apart after 2,607 entries; Mednafen `E29A`, core `E094` |
| Bomberman '94 | 343,164 | a late-visibility resync passed with registers equal but a different pushed address; the saved register select then differs |
| Bonk's Adventure | 235,057 | an `RTI` returns to `C8D1` where Mednafen returns to `C8CE`: same kind, the pushed address differs |

The board's `--resync-late` can absorb a late entry only when the instruction in between leaves
the registers alone. It cannot see the pushed return address, which is why the last two pass and
then fail. The raster placed 1 to 3 master clocks earlier (`--raster-shift 1|2|3`) makes the first
2,100,000 instructions of the Covell ROM match Mednafen with no stop: the tie is less than one
high-speed cycle.

### 2. The Covell calibration (tier 1)

Covell's photographs of a real console are the only tier-1 evidence. In `pcengine-python`
(`docs/m1-record.md`) the vblank position was swept from -16 to -4 dots in RAM and ROM modes. The
position moves the mean but not the spread: each group's split sits on one of two levels 4 to 6
dots apart and jumps a whole level at a threshold. The photographs show no such jump (spread 2.4
dots). At every position where the mean is good, the spread stays 3.8 to 5.6. So what is left is
the 4-dot quantum with which the wait loop takes the interrupt, not the vblank position.

Variants already tried on the board side, none of which removes it: a 7-cycle interrupt entry
(Mednafen's and MAME's figure, against the core's 8; C3 in `m1-record.md`), no VCE stretch cycle.
Both change the quantum's phase or the mean.

## The question

Does the quantum come from the core's poll point? If the real part samples its lines on a different
cycle, or lets a line that rises on the last cycle count, the core would enter at the boundary
Mednafen does, and the two-level split would shrink. The rule today is inherited from the 65C02
frame, not from a HuC6280 source.

## Experiment proposed (core side, behind a class attribute, default unchanged)

1. Add a class attribute for the poll point, for example `irq_poll_cycle` with the present rule as
   the default and the alternatives: the last cycle (a line that rises on it counts), and
   Mednafen's boundary rule.
2. A rung-3 directed test per mode, for example an `RTI` return address when a line rises on the
   last cycle of the instruction before the boundary.
3. Re-certify rungs 1, 1b, 3 and 4. The MAME- and Mednafen-replayed games take interrupts from
   the referees' own boards, so they may move; report which.
4. The board then reruns, per mode: the Covell calibration (spread against the 2.4-dot
   photographs: the judge), the six lockstep stops (detectors only), and the 18-picture gate.

A mode is adopted as the default only if the Covell spread falls inside 2.4 dots in both RAM and
ROM modes. If an emulator rule matches the lockstep but not Covell, it stays a named referee
switch.

## What is not claimed

No tier 1 to 3 source describes the HuC6280's poll cycle. Mednafen and MAME disagree with each
other on interrupt visibility at sub-instruction level, and MAME's is not repeatable from frame
to frame. Both are detectors.

Found by: `pcengine-python` `scripts/covell_calibrate.py`, `scripts/lockstep.py`
(`docs/m1-record.md`, `docs/m5-lockstep-record.md`).
