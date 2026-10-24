# Documents

Read in this order.

| Document | What it holds |
| --- | --- |
| [start-here.md](start-here.md) | The HuC6280 as a core author needs it: registers and the T flag; the 21-bit MMU and why zero page is at `$2000`; the hardware page; vectors, priority, interrupt entry; the clock and `CSL`/`CSH`; the Hudson instructions; block transfers; what the core owns; the proposed embedding contract |
| [timing.md](timing.md) | The measured agreement (Hudson's manual vs the emulators, 17 + 6n in 12,500 cases); the opcode and base-cycle grids; the bus shape of every addressing mode; the 65C02 comparison; interrupt, reset and speed; the 26 opcodes where four emulators differ |
| [undocumented-behavior.md](undocumented-behavior.md) | U1-U22 quirks and C1-C11 contradictions, each with its tier |
| [validation.md](validation.md) | Every oracle by tier with pins, what does not exist, the rung plan, what no judge decides, the minimal harness |
| [mame-oracle.md](mame-oracle.md) | The verified MAME 0.285 recipe, the working read tap (watchpoints do not), `tg16` for US games, the screen-capture workaround, what MAME does |
| [handoff-brief.md](handoff-brief.md) | The task for the build session: what 6502-python gives and must gain, the core boundary, the bus contract, layout, rungs, tooling, and **Open decisions for Aubrey** |

Build findings (2026-10-24) are in [undocumented-behavior.md](undocumented-behavior.md) (U23, U24, C12-C15) and the rung rows of [validation.md](validation.md).

## Findings made while gathering (2026-10-23)

1. **Nothing in 6502-python needs to change** for this core. The frame's
   subclassing surface is enough; the opcode map and every cycle differ from the
   NMOS and CMOS parts, so a CMOS mode would not be inherited anyway.
2. **There is a volume judge**: SingleStepTests `huc6280` (640,000 cases, per-cycle,
   MPR-aware) from Mesen. It is emulator tier, has no interrupts, timer or
   hardware page, and its author warns that the dummy and internal cycles are a
   guess.
3. **The Hudson manual's per-opcode table agrees with the corpus** wherever the
   scan could be read (107 of 111 opcodes; 3 OCR errors; `BRK`'s byte count is the
   manual's own error).
4. **The 65C02 corpora cannot judge this chip's cycles**: `LDA zp` is 4 cycles
   here and 3 there, `JSR` 7 and 6, `BRK` 8 and 7, and 24 opcodes mean something
   else. They can judge results through a mapped-memory harness (rung 1b).
5. **MAME's debugger watchpoints do not honour a range on this 21-bit space**;
   a Lua read tap does. `video:snapshot()` is black headless; `screen:pixels()`
   has the picture. US HuCards need the `tg16` driver (the games check the
   country bit).
6. **No die-level model, no hardware-captured per-instruction data, no CPU-only
   test ROM exists** (searched). Covell's photographs of his raster CPU test on
   real hardware are the only hardware-captured material, and they need a VDC.
7. **The MiSTer timing captures look like SignalTap of the FPGA core**, not a
   console: provenance is unstated, so they are emulator tier.
