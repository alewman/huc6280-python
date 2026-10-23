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
dbg:command('trace cpu.trace,,noloop,{logerror "%X %X %X %X %X %X %X %X %d\n",pc,a,x,y,s,p,mpr0|(mpr1<<8)|(mpr2<<16)|(mpr3<<24),mpr4|(mpr5<<8)|(mpr6<<16)|(mpr7<<24),totalcycles}')
dbg:command("go")
```

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

(Read from the source, not measured; confirm when building rung 4.)

## How MAME scores

Nothing here has been scored: there is no CPU-only test ROM with a verdict
(validation.md), and the one measurement made is that the pinned corpus's
**base cycle table disagrees with MAME's in 26 opcodes** for the reasons in
timing.md (VDC stretch folded in, `BBRi` charged 4 plus a helper, `$63`).

## Use: rung 4, the replay (not yet run)

`scripts/mame_trace.py GAME --io` records the trace and the hardware-page
reads. A harness (docs/validation.md, "The minimal harness") runs the core
from the same reset, answers the core's reads at `$1FE000`-`$1FFFFF` from the
log in order, takes a MAME line's registers as the expectation after each
instruction, and compares the `totalcycles` deltas against the core's cycle
count at the right speed (a delta of 4 per cycle in low speed, 1 in high). The
known, expected differences are the C-items above; anything else is a lead,
to be looked up in [undocumented-behavior.md](undocumented-behavior.md) and
settled by a higher tier. Interrupts: MAME's trace has no line for an entry;
the line after the interrupted instruction is the handler's first, which the
replay recognises by the vector target (`$FFF6`..`$FFFC` reads) and S, as
65816-python's replay does.
