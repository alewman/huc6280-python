# 0003: where the core samples an interrupt (U21) is the common cause of four lockstep stops and the Covell spread

Raised 2026-11-04 by `pcengine-python` M1 and M5 (Covell calibration, Mednafen and MAME lockstep).
Status: **experiment done 2026-11-04, no mode adopted; the default is unchanged.** The modes stay as a named switch (`irq_poll_cycle`, U25). A question and an experiment, not a defect report; nothing here is shown wrong.

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

## Result (2026-11-04)

Core: `HuC6280.irq_poll_cycle` = `"second_to_last"` (default, unchanged), `"last"`, `"mednafen"` (U25 in
`undocumented-behavior.md`, which quotes Mednafen's `RunSub`/`LastCycle`). Directed tests in
`tests/test_directed.py` (U25: default, each mode, a line dropping in the last cycle, a timer against IRQ1,
an `RTI` return address: default and `mednafen` push `CODE+2`, `last` pushes `CODE+1`). Default mode:
every existing test is unchanged (see the commit message for the rung results).

Board, core working tree through a path override (the committed pin is unchanged). Covell calibration,
ours minus photograph, mean / spread over the 7 groups (dots; the default-mode rows reproduce
`m1-record.md`'s table exactly):

| `vblank_dots` | mode | RAM mean / spread | ROM mean / spread |
| --- | --- | --- | --- |
| -8 | second_to_last | +2.4 / 5.6 | +4.0 / 7.0 |
| -8 | last | +2.4 / 5.6 | +2.3 / 7.6 |
| -8 | mednafen | +2.4 / 5.6 | +4.0 / 7.0 |
| -9 | second_to_last | +0.7 / 5.6 | +0.5 / 3.8 |
| -9 | last | +0.7 / 5.6 | +0.5 / 3.8 |
| -9 | mednafen | +0.7 / 5.6 | +0.5 / 3.8 |
| -10 | second_to_last | +0.7 / 5.6 | +0.5 / 3.8 |
| -10 | last | -0.2 / 4.2 | -1.2 / 4.2 |
| -10 | mednafen | +0.7 / 5.6 | +0.5 / 3.8 |

No cell is inside 2.4 dots. `last` moves some groups' thresholds by about 1 dot (the two-level jump is
still there: RAM group 8 at -10 goes to -2.2, ROM groups 4 and 8 to -3.6/-3.2) and lowers the RAM spread
at -10 to 4.2; `mednafen` changes nothing in the Covell ROM. So the quantum is **not** the poll point.

Mednafen lockstep, first stop (equal instructions; flags "Full" + `--check-reads`; traces of 0.2 M to 3 M
instructions, R-Type to 3 M only):

| Game | second_to_last | last | mednafen |
| --- | --- | --- | --- |
| R-Type I | 3,000,000 (none) | 293,741 | 3,000,000 (none) |
| Gradius | 107,737 | 51,632 | 107,737 |
| Final Soldier | 630,583 | 17,357 | no stop in 700,000; next stop 830,985 (4 M trace) |
| After Burner II | 187 | 187 | 187 |
| Bomberman '94 | 343,164 | 220,419 | 343,164 |
| Bonk's Adventure | 235,057 | 175,519 | 235,057 |

`last` is worse everywhere (Mednafen does not count a line that rises in the last cycle for IRQ1/IRQ2).
`mednafen` moves only Final Soldier (its stops are timer entries), by 200 K instructions; Gradius, Bomberman
and Bonk are IRQ1 and do not move, so their cause is the VDC's rise time, not the CPU's poll rule.

Adoption rule not met (no Covell spread inside 2.4 dots in either mode), so the default stays. The 18-picture
gate was not run: nothing was adopted.
