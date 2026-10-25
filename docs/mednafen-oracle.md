# Mednafen 1.32.1 as an emulator-derived referee (rung 4b)

Mednafen's `src/pce/huc6280.cpp` is, with Mesen's, one of the two CPU models the community calls
accurate (Covell's page). It is **emulator tier**: a third vote where MAME and Mesen2 disagree, never
a judge ([validation.md](validation.md)). Everything here was run on 2026-10-24.

## The recipe

```text
python -I scripts/build_mednafen.py                     # fetch (SHA-256 checked), patch, configure, build: ~2 minutes
python -I scripts/mednafen_trace.py GAME.7z --count 3400000
python -I scripts/mame_replay.py tests/mednafen_traces/GAME [--no-adopt-block]
```

- `scripts/build_mednafen.py` downloads the pinned `mednafen-1.32.1.tar.xz` into `reference/build/`
  (gitignored), applies **`tools/mednafen-trace.patch`** (the only thing committed: about 30 changed
  lines in `src/pce/huc6280.cpp`, `huc6280.h`, `pce.cpp`) and builds a PC Engine-only binary
  (`--enable-pce`, every other system and the debugger off). SDL2's development files are installed
  here; **`libflac` development files are not, so it needs `--without-libflac`** (the configure
  script otherwise stops with "libflac >= 1.3.0 not found"); ALSA/JACK are off. No sudo.
- The patch writes, from inside the CPU, what `scripts/mame_trace.py` makes from MAME's debugger:
  `PC A X Y S P cycles` and `M MPR0 ... MPR7` before each instruction, and
  `[luaengine] R address value` for each hardware-page read (the line format is MAME's on purpose,
  so `tests/mame_replay.py` reads it unchanged). It stops the process after
  `MEDNAFEN_TRACE_COUNT` instructions (`_exit` after a flush), so no frame count is needed.
- `scripts/mednafen_trace.py` runs it with `SDL_VIDEODRIVER=dummy`, `SDL_AUDIODRIVER=dummy`,
  `-sound 0 -nothrottle 1` and a private `MEDNAFEN_HOME`: 3.4 million instructions in under a second,
  about 155 MB of log per game (`tests/mednafen_traces/`, gitignored; delete when done).

## Traps

- **`timestamp` is not a running total**: it is in master clocks (a cycle is 3 high, 12 low) and
  Mednafen subtracts it every frame. The patch keeps its own counter in `ADDCYC`/`ADDCYC_MASTER`
  and prints it divided by 3, MAME's 7.16 MHz units.
- **Reset leaves S = 0** (MAME and the core: $FF); the first replay line differs in S and
  nothing else. The registers at power-on are random on hardware (U2).
- **Block-transfer reads of the hardware page are not logged** (the core makes none: U7) and
  Mednafen answers `0` for `$0800-$17FF` itself (below).
- **US games** need nothing special: Mednafen detects the card from its contents (Blazing Lazers
  and Bonk's Adventure ran).
- **Backup RAM** at `$1EE000` exists (HuCards ask for the "HUBM" header; Final Soldier does). The
  patch does not log it, so the replay adopts the registers after those 10 reads (it says so).
- **VDC/VCE access costs** are Mednafen's board model, not the CPU's: an access waits for the
  video chips' slot (variable, +9 to +36 units on `STZ abs`, `STA abs`, `LDA abs`, `ST2` to
  `$0000-$07FF`). The core charges the flat one cycle (U18), so those opcodes show as
  cycle differences; no other opcode does.

## What six games say (3.4 million instructions each, 20.4 million in all)

| Game | Register or MPR divergences | Interrupt entry vs core | Interrupts taken at a step the core's poll would not | `CSH`/`CSL` vs core | Cycles equal |
| --- | --- | --- | --- | --- | --- |
| Blazing Lazers | 0 (line 0: S) | +0 x4,764 | 0 | no difference | all but VDC/VCE opcodes |
| Bomberman '94 | 0 | +0 x575 | 0 | no difference | " |
| Bonk's Adventure | 0 | +0 x5,083 | 0 | no difference | " |
| Final Soldier | 0 (10 backup-RAM reads adopted) | +0 x13,953 | 0 | no difference | " |
| Gradius | 0 | +0 x4,710 | 0 | no difference | " |
| R-Type I | 0 | +0 x110 | 0 | no difference | " |

Block transfers were replayed with the core's own A, X, Y (`--no-adopt-block`, 91 transfers, the
RAM clear `tii $2000,$2001,$1FFF` among them): no divergence.

## The votes, per contradiction

These are rows for [undocumented-behavior.md](undocumented-behavior.md); each is emulator tier.

| Entry | Mednafen says | How it was found |
| --- | --- | --- |
| C1 `ST0`-`ST2` | 4 in the CPU, +1 stolen by the memory handler (comment in `huc6280.cpp`): 5 on a board, the core's split | source |
| C3 interrupt entry | **8 cycles** ("Total: 8 cycles" in the code); 29,195 entries in the six games cost what the core charges, bar a handful whose previous instruction was a VDC/VCE access | source, replay (30,000 entries) |
| C4 `$63` | the `default:` case: a 2-cycle one-byte NOP | source |
| C5 `SBC` and T | no: `TPREFIX` is in `ADC AND EOR ORA` only | source |
| C6 `TMA` with several bits | **the highest set bit wins** (the loop overwrites A), like MAME; `TMA #0` leaves A alone (no latch) | source |
| C7 `CSL`/`CSH` | 2 cycles at the old speed and the last cycle at the new one: the core's order, not MAME's | source, replay (no difference) |
| C9 block reads of the hardware page | **`0` for `$0800-$17FF`** (`IORead`: `InBlockMove()` returns 0 for the PSG, timer, port and interrupt-register ranges, not for the VDC/VCE or CD): pcetech's rule and issue 0001's end of range. This corrects the entry's earlier "MAME and Mednafen read the device" | source |
| C12 `TSB`/`TRB` Z | the stored result is zero (`(x \| A) ? 0 : Z`), N and V from the memory byte | source |
| C13 decimal `ADC`/`SBC`, invalid digits | `SBC` (its own digit-wise formula) **agrees with the Rockwell 65C02 corpus in all 4,916 decimal cases** (4,139 with an invalid digit), where the core (Mesen's formula) differs in the invalid ones; `ADC` is **the other way round**: the core agrees with Rockwell in all, Mednafen's adds the adjust differently and differs from both in 375 of the 4,304 invalid cases. The two differ from each other in 9,216 of 131,072 input/carry combinations each, never with valid digits (checked by a transcription of the macros, not a run) | source + corpus |
| C14 block transfers push A, X, Y | **yes** (`LD_BMT`: `PUSH(Y); PUSH(A); PUSH(X)` ... `X = POP()...`): the core's A, X, Y match with no adoption in all 91 transfers | source, replay |
| C15 interrupt after `CLI` | **not taken early**: the six games show 0 steps where the core's poll waits and Mednafen does not (`IFlagSample` is taken in `LastCycle`, before `CLI` changes I) | replay |
| C16 `BRK` with T | pushes T = 0 (`P &= ~T_FLAG` before the pushes), like Mesen and the core, unlike the HDL | source |
| C18 vanished interrupt | the timer is re-checked live (`IRQlow & IQTIMER & IRQMask`) and **dropped** if gone ("else tmpa stays 0"); IRQ1/IRQ2 use the sampled lines: Mesen2's split rule, the core's default | source |
| U8 zero-page pointer wrap | not checked | |

Nothing here changes a default: Mednafen sides with the core on C3, C5, C7, C9, C12, C14, C15, C16
and C18, with MAME on C6, and its decimal `SBC` with the Rockwell chip rather than with the corpus
the core follows (C13: recorded as a lead in [validation.md](validation.md), not a defect).
