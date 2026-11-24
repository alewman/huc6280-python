<!-- SPDX-License-Identifier: MIT -->
# Mednafen 1.32.1 as an emulator-derived referee (rung 4b)

Mednafen (GPL-2.0) is, with Mesen, one of the two PC Engine emulators the community calls
accurate (Covell's page). It is **emulator tier**: a third vote where MAME and Mesen2 disagree, never
a judge ([validation.md](validation.md)). It is **run as a closed box and its source is not read**
(docs/restart.md); the only thing committed is the tracing patch, a GPL-2.0-or-later tool file.
The replays were run on 2026-10-24, the directed cards on 2026-11-19.

## The recipe

```text
python -I scripts/build_mednafen.py                     # fetch (SHA-256 checked), patch, configure, build: ~2 minutes
python -I scripts/mednafen_trace.py GAME.7z --count 3400000
python -I scripts/mame_replay.py tests/mednafen_traces/GAME [--no-adopt-block]
```

- `scripts/build_mednafen.py` downloads the pinned `mednafen-1.32.1.tar.xz` into `reference/build/`
  (gitignored), applies **`mednafen-trace.patch`** (about 30 changed lines; committed here until
  2026-11-21, now a GPL-2.0-only tool outside this repository, at
  `$EMU_TOOLS_GPL2/tools/mednafen/patches/mednafen-trace.patch`: set `EMU_TOOLS_GPL2`) and builds a PC Engine-only binary
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

- **Mednafen's own cycle count is not a running total** (it restarts every frame), so the patch
  keeps its own running count, in master clocks (a cycle is 3 high, 12 low), and prints it divided
  by 3, MAME's 7.16 MHz units.
- **Reset leaves S = 0** (MAME and the core: $FF); the first replay line differs in S and
  nothing else. The registers at power-on are random on hardware (U2).
- **Block-transfer reads of the hardware page are not logged** (the core makes none: U7); a
  directed card shows Mednafen answers `0` there (C9 below).
- **US games** need nothing special: Mednafen detects the card from its contents (Blazing Lazers
  and Bonk's Adventure ran).
- **Backup RAM** at `$1EE000` exists (HuCards ask for the "HUBM" header; Final Soldier does). The
  patch does not log it, so the replay adopts the registers after those 10 reads (it says so).
- **VDC/VCE access costs** differ from the core's: the traces show a variable wait (+9 to +36
  units on `STZ abs`, `STA abs`, `LDA abs`, `ST2` to `$0000-$07FF`), a board matter. The core
  charges the flat one cycle (U18), so those opcodes show as cycle differences; no other opcode
  does.

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

## The votes, per contradiction (closed box)

These are rows for [undocumented-behavior.md](undocumented-behavior.md); each is emulator tier and
each was **observed from outside**: the six replays above, or a directed HuCard traced on
2026-11-19 (`scripts/decimal_tables.py`, `validation/vanish_probe.py`, and a card of single
instructions whose results are the next trace line's registers). The earlier version of this table
also cited Mednafen's source; those rows are withdrawn and, where they were not re-established
here, say so.

| Entry | Mednafen does | How it was observed |
| --- | --- | --- |
| C1 `ST0`-`ST2` | not re-established (the traces include the board's VDC wait) | |
| C3 interrupt entry | 29,195 entries in the six games cost what the core charges (8 cycles), bar a handful whose previous instruction was a VDC/VCE access | replay |
| C4 `$63` | a one-byte, 2-cycle NOP | directed card |
| C5 `SBC` and T | T ignored: `SET; SBC #$01` changes A, not M(X) | directed card |
| C6 `TMA` with several bits | **the highest set bit's register** (`TMA #$0C` with MPR2 = $81, MPR3 = $42 gives $42), like MAME; the corpus records the OR | directed card |
| C7 `CSL`/`CSH` | the last cycle at the new speed: `CSH` from low costs 4 + 4 + 1 units, `CSL` from high 1 + 1 + 4 | directed card, replay (no difference) |
| C9 block reads of the hardware page | **0**: `TII` from the I/O port stores 0 where a plain read gives $BF; pcetech's rule | directed card |
| C12 `TSB`/`TRB` Z | the stored result is zero (`TSB` of $0F with A = $F0 clears Z; `TRB` of $0F with A = $0F sets it) | directed card |
| C13 decimal `ADC`/`SBC`, invalid digits | the full table of 262,144 operations, the core's default since 2026-11-10 (issue 0004). Against the Rockwell 65C02 corpus's decimal cases, its `SBC` agrees in all and Mesen's differs in 3,164; for `ADC` Mesen's agrees in all and Mednafen's differs in 3,195 | directed card, corpus |
| C14 block transfers push A, X, Y | the core's A, X, Y match with no adoption in all 91 transfers | replay |
| C15 interrupt after `CLI` | **not taken early**: the six games show 0 steps where the core's poll waits and Mednafen does not | replay |
| C16 T on an interrupt entry | cleared for the handler: a timer taken between `SET` and its target runs the handler's `ORA #$0F` on A | directed card |
| C18 vanished interrupt | a timer acknowledged in the last cycle is **dropped**; a VDC interrupt acknowledged by a status read in the last cycle is **taken**: the core's default | directed cards |
| U8 zero-page pointer wrap | not checked | |

One default changed on Mednafen's vote: C13 (issue 0004). Otherwise Mednafen sides with the core on
C3, C4, C5, C7, C9, C12, C14, C15, C16 and C18, and with MAME on C6.
