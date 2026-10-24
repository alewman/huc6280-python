# MAME 0.285 as an emulator-derived detector for the HuC6280

MAME's `pce`, `tg16` and `sgx` drivers run real HuCards on the `h6280` device
(`src/devices/cpu/h6280/h6280.cpp`: the core, the MMU, the timer, the interrupt
registers and the speed divider in one class) with the VDC, VCE and PSG around
it. It is **emulator-derived**: use it to find where a core first disagrees on
ordinary code, then settle the disagreement with a higher tier
([validation.md](validation.md)). Its cycle accounting is per instruction (a
constant in each opcode, and helpers for branches and block moves), never per
bus cycle.

Everything on this page was run on 2026-10-23 on this machine, MAME 0.285 at
`/usr/games/mame`. `scripts/mame_trace.py` is the recipe as a script.

## No boot ROM problem

`mame -listroms pce` (and `sgx`) says "No ROMs required": a HuCard runs with
nothing else (the CD-ROM system card is for the CD drivers). That is unlike the
SNES, whose sound CPU needs a boot ROM. Cartridges load with `-cart game.pce`
(`.pce` or `.bin`); a 512-byte copier header is dropped by the script.
**US releases need `tg16`**: Blazing Lazers (USA) and Bonk's Adventure (USA)
under `pce` run to a black screen (2 of 263,296 pixels lit at 10 s) because
the game reads the country bit at `$1000` bit 6 (the code at its reset vector,
`LDA $1000 / AND #$40 / BEQ`, is visible in the trace); under `tg16` they show
their pictures (234,394 and 40,502 pixels lit). Japanese and homebrew games
run under `pce`.

## The recipe

Write `trace.lua` in a fresh working directory:

```lua
local dbg = manager.machine.debugger
dbg.visible_cpu = manager.machine.devices[":maincpu"]
dbg:command('trace cpu.trace,,noloop,{logerror "%X %X %X %X %X %X %d\\n",pc,a,x,y,s,p,totalcycles; logerror "M %X %X %X %X %X %X %X %X\\n",mpr0,mpr1,mpr2,mpr3,mpr4,mpr5,mpr6,mpr7}')
dbg:command("go")
```

(The first version of this recipe packed the eight MPRs into two words with
`mpr0|(mpr1<<8)|(mpr2<<16)|(mpr3<<24)`. **That is wrong beyond MPR1**: the expression gave
`0x4C0F8FF` for MPR0 = $FF, MPR1 = $F8, MPR2 = $13, so the debugger's `<<` or its symbols do
not behave as C; found in rung 4 (2026-10-24) when the replay saw MPR2 = $C0 for a `TAM`
of $13. Two `logerror` calls in one action work and are exact.)

and run, from that directory, with the cartridge copied in as `cart.pce`:

```text
mame pce -cart cart.pce -homepath "$PWD" \
  -video none -sound none -nothrottle -noreadconfig -skip_gameinfo \
  -debug -debugger none -log -seconds_to_run 5 -autoboot_script "$PWD/trace.lua"
```

`error.log` lands in the working directory. Its first lines are a bank of
`[:pce_cd:msm5205]` and `Soft reset` messages (and a UTF-8 byte-order mark);
then one line per instruction, **before it executes**. Verified run: HuZERO
(World) (an unlicensed homebrew) for 1 emulated second under `--io`: **1,511,174
instructions** and 9,928 hardware-page reads in 28.8 s wall; for 3 s with the
watchpoint recipe that does not work (below), 3,982,940 instructions in
75.6 s. The trace slows MAME to about
10 % of real time.

## Facts about the trace

- Device `:maincpu`, `h6280` ("HuC6280"). State symbols (Lua `cpu.state`):
  `GENPC CURPC CURFLAGS PC S P A X Y IM TMR NMI IRQ1 IRQ2 IRQT MPR0 ... MPR7`.
  `pc` is the 16-bit **logical** program counter. There is no T, B or speed
  symbol of its own; they are bits of `p` (T = $20, B = $10) and the speed is
  not visible (infer it from `totalcycles`).
- A debugger expression can be at most 14 values in `logerror` (the family's
  trap); this recipe uses 9 by packing the eight MPRs into two 32-bit words,
  MPR0 (or MPR4) in the low byte: `F8FF` after `TAM #$01` then `TAM #$02`
  means MPR0 = $FF and MPR1 = $F8.
- **`totalcycles` counts 7.16 MHz cycles**, i.e. the master clock divided by 3
  (`m_clocks_per_cycle`: 4 in low speed, 1 in high speed; `h6280_cycles(n)`
  subtracts `n * m_clocks_per_cycle`), plus the 1 charged for an access to the
  VDC or VCE. The first lines of HuZERO: `SEI` at `$E000` is 8 (2 cycles at
  4), `CSH` 12 (3 cycles at 4: the old speed is charged), `CLD` 2 at the new
  speed. The timer counts these too (`m_timer_value -= cyc * clocks_per_cycle`).
- Registers at reset (HuZERO's first trace line): `A = X = Y = 0`, `S = $FF`,
  `P = $14` (I and B), all eight MPRs 0 (`device_reset` zeroes A, X, Y and the
  MPRs; the console leaves A X Y S and MPR0-6 random, U2).
- **Debugger watchpoints do not work for the hardware page.** `wpset
  1FE000,2000,r,1,{...; g}` fires for every program-space read (its address
  starts at `$0`, the instruction stream itself: 1,825,429 hits in 3 s) and a
  write watchpoint on RAM (`wpset 1F0000,2000,w,...`) never fires, so the
  range is ignored on this 21-bit space (also the condition `wpaddr>=1FE000`
  matched nothing). **`install_read_tap` works**: `spaces["program"]:
  install_read_tap(0x1FE000, 0x1FFFFF, "io", function(offset, data, mask) ...
  end)` receives the physical address and the value. `machine:logerror(text)`
  writes it into `error.log`, prefixed `[luaengine] `; the tap runs after the
  trace line of the instruction making the read, so the order is right.
  Keep the tap in a global.
- `--io` logs `[luaengine] R 1FF803 2` style lines: **physical** addresses
  (`$1FE000` VDC, `$1FE400` VCE, `$1FEC00` timer, `$1FF000` port, `$1FF400`
  interrupt registers, `$1FF800` CD-ROM). HuZERO makes 9,928 of them in
  one emulated second: joypad `$1FF000`, the VDC, and CD-interface probes at
  `$1FF803`.
- **`video:snapshot()` writes an all-black PNG** for these drivers under
  `-video none` (and under `-video soft -window` with no display), while
  `screen:pixels()` holds the picture. `scripts/mame_trace.py` therefore
  writes the raw frame (`B G R A`, 1088 x 242) and converts it to
  `snap/frame.png` itself and prints how many pixels are not black.
- Screen: 1088 x 242 at **59.826 Hz** (`screen.refresh`).
- State can be set from Lua (`cpu.state["PC"].value = ...` reads back), but
  `dbg:command("step")` from a frame notifier did not advance the CPU in the
  one attempt made, so a per-instruction MAME fuzzer (set state, step one
  instruction, read state) is **untried**, not impossible.
- Other devices: `:pce_cd` (the CD-ROM interface, present with no disc),
  the HuC6270 VDC, the HuC6260 VCE, the PSG inside the `h6280` device.
- `-seconds_to_run` and the frame-notifier exit give the same stop; the script
  stops at a frame so snapshots line up.

## What MAME does with the HuC6280 (read from `h6280.cpp`; emulator-derived)

| Behaviour | MAME | Compare |
| --- | --- | --- |
| interrupt order | timer, IRQ1, IRQ2, after NMI, only if I = 0 and the disable register allows | agrees with HW HB-13 |
| interrupt entry | `h6280_cycles(7)`, pushes PCH PCL P (B cleared, T as it stands), `P = (P & ~D) \| I`: T is not cleared explicitly | 8 elsewhere (C3) |
| interrupt taken | after the next instruction (a one-instruction pipeline: `m_irq_pending`) | the frame's rule |
| `TMA` several bits | highest bit wins | Mesen ORs (C6) |
| block transfer | atomic loop, `h6280_cycles(6*len + 17)`; reads the device through `program_read8` | C9: pcetech says reads of `$0800`-`$13FF` return 0 |
| `CSL`/`CSH` | `m_clocks_per_cycle = 4 / 1` after the instruction's 3 cycles | C7 |
| VDC/VCE access | +1 cycle in `program_read8`/`program_write8` | U18 |
| `$63` | 4 cycles | 2 elsewhere (C4) |
| `SBC` with T | honoured | C5 |
| timer | `m_timer_load = ((data & 127) + 1) * 1024 * m_timer_scale`; reload only on a 0 to 1 control write; interrupt when the counter reaches 0 at an instruction boundary | U16 |
| timer register read | `(m_timer_value >> 10) & 0x7F` with bit 7 from the I/O buffer | HW HB-21's "read twice" caution is not modelled |

(Read from the source, not measured; rung 4 confirmed the interrupt entry, the poll and `CSL`/`CSH` rows below.)

## How MAME scores

Nothing here has been scored: there is no CPU-only test ROM with a verdict
(validation.md), and the one measurement made is that the pinned corpus's
**base cycle table disagrees with MAME's in 26 opcodes** for the reasons in
timing.md (VDC stretch folded in, `BBRi` charged 4 plus a helper, `$63`).

## Rung 4: the replay (run 2026-10-24)

`scripts/mame_trace.py GAME --io --seconds 2 [--driver tg16]` records the trace, the
hardware-page reads and the backup-RAM reads (`$1EE000-$1EFFFF`: MAME's `pce` driver always
carries a CD-ROM unit's BRAM, and Final Soldier reads its "HUBM" header). `tests/mame_replay.py`
runs the core in the minimal harness from the same reset, answers those reads from the log in
order, and after every instruction compares PC, A, X, Y, S, P (without B) and MPR0-7 with MAME's
next line and the cycle count with MAME's `totalcycles` delta (`scripts/mame_replay.py DIR`).

| Game (driver) | Instructions | Register divergences | Cycles equal |
| --- | --- | --- | --- |
| Blazing Lazers (tg16) | 3,843,616 | 0 | 3,838,160 of 3,838,161 |
| Bomberman '94 (pce) | 3,335,648 | 0 | 3,335,082 of 3,335,083 |
| Bonk's Adventure (tg16) | 3,495,812 | 0 | 3,490,540 of 3,490,541 |
| Final Soldier (pce) | 3,400,730 | 0 | 3,386,775 of 3,386,778 |
| Gradius (pce) | 3,458,889 | 0 | 3,454,098 of 3,454,099 |
| R-Type I (pce) | 3,479,285 | 0 | 3,479,170 of 3,479,171 |

21.0 million instructions, 0 register or mapper divergences, with these differences, all
explained and counted (the report prints them):

- **Interrupt entry (C3).** 30,000-odd entries (IRQ1 and the timer); the replay steps the entry
  when MAME's next line is at a vector's target with three more bytes on the stack. MAME charges
  7 cycles, the core 8: every entry differs by exactly that one cycle.
- **`CSH`/`CSL` (C7).** 3 of 21 million instructions: MAME bills the old speed for all three
  cycles, the core switches before the last (+3 units at 7.16 MHz when going to high speed, -3
  coming back).
- **Interrupts taken a step earlier than the core's poll (U21).** After `CLI` MAME takes a
  pending interrupt at once (about 600 times: 543 of them in Blazing Lazers); Mesen, Mednafen and the core let one more instruction run. The replay forces the entry
  and counts it. Which is right is *undecidable here* (HW HB-12 says "sampled in the last bus
  cycle"; whether `CLI`'s I counts there is what is unknown).
- **Block transfers (C14).** MAME's transfers neither push nor pop A, X, Y; the core's (like
  Mesen's and Mednafen's, HW HB-6) do, so `tii $2000,$2001,$1FFF` (the RAM clear every game
  starts with) leaves A = 0 where MAME leaves it. The replay adopts MAME's A, X, Y after a
  block transfer (91 times).
- **Nothing else.** No unlogged hardware-page read, no logged read left unread, no cycle
  difference in any other opcode: the VDC/VCE stretch, the taken-branch cost, `BBR`/`BBS`,
  decimal `ADC` and the T-flag forms all agree with MAME's tables. (The CD-ROM and the timer
  were MAME's, not the core's: the replay answers from the log.)
