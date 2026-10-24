# Validation: every oracle, its tier, and the plan

## Oracle tiers

The family's rule (z80-python, sm83-python, 65816-python `docs/validation.md`):
rank an oracle by **where its expected values came from**; a lower tier
detects, the highest tier that covers a claim decides it.

| Tier | Meaning here |
| --- | --- |
| **hardware-captured** | values recorded from a real HuC6280 console and published as data or images: Chris Covell's photographs of his CPU Test on real hardware (`reference/roms/covell-cpu-test/images/`) |
| **hardware-verified** | a statement by an author who says he ran it on a real console, with no re-runnable artefact: Charles MacDonald's pcetech ("I've tested the timer and IRQ1", "Re-tested P startup value") |
| **manufacturer** | Hudson's *Hardware Manual* and *Software Manual* (scans, with OCR errors; known internal contradictions: C2) |
| **research** | community documents and code that state facts without evidence of a run: Shu's `pce_cpu.html`, the PCEAS instruction tables, Dormann's 65C02 test as applied to a different chip |
| **emulator-derived** | values produced by an emulator or hand-written HDL: SingleStepTests `huc6280` and `65x02` (Mesen, Clock Signal-lineage emulators), MAME 0.285, Mednafen/Beetle PCE, ares, Geargrafx, Mesen2, srg320's `HUC6280` VHDL. Detectors only |
| **unknown** | generator not stated. None used |

### What does not exist (searched 2026-10-23)

- **No die-level HuC6280**: no visual6502-style netlist or transistor
  simulation, and no Verilog or VHDL derived from the die. The MiSTer core's
  VHDL is a hand-written re-implementation by srg320 (microcode plus an ALU),
  validated by its authors against real consoles, with no published record.
  GitHub searches for "huc6280 netlist", "huc6280 verilog", "huc6280 vhdl"
  returned the MiSTer repository and nothing derived from the silicon.
- **No hardware-captured per-instruction corpus** and no published
  logic-analyser trace of a real console's CPU pins that can be read per
  cycle. `docs/logs 42.95MHz/` in the MiSTer repository holds seven PNGs; their
  provenance is **not stated** and their header format ("log: Trig @ ...") is
  Quartus SignalTap's, which captures an FPGA design's own signals: treat them
  as the core's, **emulator tier**, until its author says a console produced
  them. `Opcodes timing.png` is nevertheless the one per-cycle picture of
  addressing-mode cycles anywhere (its footnotes: "IO cycle, without memory
  access", "temporary address is set on the address bus, without memory
  access", "modify cycle is set on the address bus, without memory access"),
  which agrees with the corpus's `i` cycles.
- **No CPU-only test ROM.** The community's PC Engine test ROMs found are video
  and CD tests (rgalland's `PCEngine_TestRoms`, 240p Test Suite). The one CPU
  test, Covell's, is a visual raster test that needs a VDC and a VCE, so only a
  board can run it (rung 6). SingleStepTests' README says Mesen "passes timing
  tests other emulators don't" without naming them.
- **No hardware.** The user has none; no step here needs one.

## The oracles

### Hudson Soft HuC6280 Hardware and Software Manuals: manufacturer

- Pins: `reference/docs/huc6280-hardware-manual.pdf` (SHA-256 `40a32e5d...`,
  28 pages), `huc6280-software-manual.pdf` (`51eeda39...`, 110 pages),
  `huc6280-psg-manual.pdf`; fetched from the MiSTer TurboGrafx16 repository at
  commit `827d45f4...`. All rights Hudson's; long circulated.
- HW: registers, MMU (HB-7 to HB-11), interrupts and vectors (HB-12 to HB-17),
  reset (HB-18), ports (HB-19), timer (HB-20 to HB-22), the device address
  table (HB-24), the instruction map (HB-25, partly garbled by OCR). It ends at
  the map: sections 3 and 4 of its own contents (the instruction summary) are
  not in this copy.
- SW: every instruction with addressing modes, machine code, bytes and cycles,
  and flags. `scripts/manual_table.py` reads 111 opcodes: 107 agree with the
  emulators, 3 are OCR errors, 1 is `BRK`'s byte count (C2).
- No per-cycle bus table, no interrupt-entry cycle count, no mention of
  `CSL`/`CSH` in SW's text (they are in HW's map).

### Charles MacDonald, *TurboGrafx-16 Hardware Notes* (pcetech): hardware-verified by the author

- Pin: `reference/docs/pcetech.txt` (SHA-256 `d261a9a3...`), revision history
  09/22/01 to 2002. Copied from the MiSTer repository.
- CPU section 2: block transfers, the I/O-page zero read, TMA/TAM, ST0-2, the
  P state in interrupts, B, `BRK`, `CSL`/`CSH`, power-up state, 65C02 bugs and
  differences, the tested NOP list; 2.1 interrupts, 2.2 timer, 2.3 T flag,
  2.4 clocks; 3 memory map and the I/O buffer.
- The author states for most items that he tested them; none comes with a
  ROM. Where he writes "I think" or "I have not figured out" the entry is
  marked so (C6, U10). This is the highest tier available for CPU behaviour
  the manuals omit.

### Covell's PC-Engine CPU Test: hardware-captured (photographs), board-level

- Pin: `reference/roms/covell-cpu-test/CPU_Test.zip` (SHA-256 `db65a32d...`;
  unpacked: `CPU_Test_10.pce`, 32 KB; `images/`; `source/`, his assembler
  source). No licence stated. Page: `docs/covell-cputest-page.html`.
- Method: each scanline starts with a background change and one instruction is
  looped until the raster beam wraps to the same place on the next line; a
  correct cycle count lines the split up vertically, one extra cycle drifts it.
  Pages for 2-, 3-, 4-, 5-, 6-, 7- and 8-cycle instructions and the block
  transfers ("X-cycle tests"); runs from ROM or RAM.
- Photographs of **real hardware** (a PCE 8M flash card; an SSDS3) next to
  Mednafen and MiSTer. The photos are the hardware-captured tier; **reading
  them is by eye**, and the page says VRAM block-move timing depends on the
  VDC's state at power-up ("a fluke or the mysterious way the PCE operates").
- Needs a VDC and VCE to draw: it judges a **board** at the dot level and
  the CPU only through it. MAME 0.285 runs it (`scripts/mame_trace.py
  reference/roms/covell-cpu-test/CPU_Test_10.pce --no-trace`: 173,610 of
  263,296 pixels lit at 6 s, the first page up with its menu text); I made no
  judgement of its alignment.

### SingleStepTests `huc6280`: emulator-derived (Mesen), the volume detector

- Pin: `SingleStepTests/huc6280` @ `4ce378e04e243437e6f74dfe76c3cb7c70e45bf1`
  (2025-07-06), MIT, 185 MB of binary `v1/XX.json.bin`, `transcode_json.py`
  converts them. `scripts/sst_reader.py` reads the binary directly.
- 256 files (one per opcode, all 256 including the `NOP`s), **2,500 cases each**
  (640,000), measured 2026-10-23. A case: `A X Y S P PC`, `MPR[8]`, sparse RAM
  over a flat 2 MB physical space, final state, and per-cycle
  `[address(21), data, pins]` with pins `r`, `w` or `rd` (a read flagged
  dummy) or empty (an internal cycle: no address, no data); the name seeds
  the generator.
- Provenance: generated by Mesen; its README: "Mesen *may* be the most
  accurate Huc6280 emulator currently... these tests are only as good as
  Mesen", "We're not even 100% sure about dummy reads and writes".
- Limits (measured or stated): up to 500 RAM pairs and 500 recorded cycles
  (**2,499 of 2,500 block-move cases are truncated**; `num_cycles` is exact
  and 17 + 6n held in all 12,500); no interrupts (only `BRK`), no timer or
  VDC; "flat RAM with no MMU other than the usual MPR translation", so no
  hardware-page behaviour; P's B bit is never set (C-notes in
  undocumented-behavior.md U5); initial P includes random T and D.
- Use: rung 1.

### SingleStepTests `65x02` (`rockwell65c02`, `wdc65c02`, `synertek65c02`): emulator-derived, a semantic subset only

- Pin: `SingleStepTests/65x02` @ `2f6980a2...` (2025-05-10), MIT, **sparse:
  only the README files are checked out** (each CMOS set is 256 files and
  about 1.0 GB; the local corpora in `6502-python/tests/6502_test_vectors`
  hold `6502` and `nes6502` only, measured 2026-10-23). Widen the sparse list
  to `/rockwell65c02/` for rung 1b.
- 10,000 cases per opcode, per-cycle `[address, value, "read"|"write"]`. The
  Rockwell set is the 65C02 with the bit instructions and no `WAI`/`STP`: the
  closest to the HuC6280. Ten files were fetched to the scratchpad on
  2026-10-23 to measure timing.md's comparison table.
- It cannot judge cycles or bus shapes (the HuC6280 spends an extra cycle on
  almost every memory access), nor any opcode whose meaning differs (24 Hudson-only
  opcodes, timing.md, plus the multi-byte `NOP`s). It can judge **results**: A X Y S
  P PC and the bytes written, for the opcodes the chips share, if the memory
  is mapped as rung 1b says.

### Klaus Dormann's 65C02 extended opcodes test: research for this chip

- Pin: `Klaus2m5/6502_65C02_functional_tests` @ `7954e2db...`, sparse
  (`65C02_extended_opcodes_test.a65c`, its `.bin`, `as65_142.zip`,
  `readme.txt`, `license.txt`), GPL-3.0.
- A self-checking program for a 65C02 that traps on the first wrong result;
  its configuration (`zero_page = $a`, `data_segment = $200`, `code_segment =
  $400`, `wdc_op`, `rkwl_wdc_op`) is in the source. **It cannot run unmodified**:
  the code occupies `$0400` to about `$3500`, across the logical `$2000` where
  this chip's zero page lives, it tests 65C02 NOPs and decimal-mode V, and its
  vectors are the 65C02's. Rung 2 relocates it; `as65` is a 32-bit ELF that does
  **not run on this machine** (no `ld-linux.so.2`, checked 2026-10-23), so the
  relocation needs a ca65 port of the source (6502-python uses amb5l's for the
  decimal test, `tests/dormann/6502_decimal_test.bin`) or a 32-bit loader.
  Unproven: nobody has run it on a HuC6280 or its emulators in what was found.

### MAME 0.285 `h6280`: emulator-derived, a trace detector

- `/usr/games/mame`, version `0.285 (unknown)`; its source pinned at
  `mamedev/mame` @ `f379cd06...` (the `mame0285` tag): `src/devices/cpu/h6280/`,
  `src/mame/nec/pce.cpp`.
- The `pce`, `tg16` and `sgx` drivers run HuCards headless, need **no BIOS**,
  and give a per-instruction trace through the debugger. See
  [mame-oracle.md](mame-oracle.md) for the recipe, the facts, and the traps.
- Instruction-level cycle accounting (a constant per opcode, `h6280_cycles(N)`,
  and helpers for branches and block moves), not per bus cycle; an interrupt
  entry is 7 cycles (C3). Its history in the source header (Wilbert Pol, Charles
  MacDonald, Rob Bohms) records which behaviours were fixed against which game.
  Never a referee for timing below the instruction.

### Mednafen / Beetle PCE, ares, Geargrafx, Mesen2: emulator-derived

- Pins: `libretro/beetle-pce-libretro` @ `b96c11e0...` (Mednafen's accurate
  `huc6280.cpp`), `libretro/beetle-pce-fast-libretro` @ `4eee99c4...`,
  `ares-emulator/ares` @ `c76aaffa...`, `drhelius/Geargrafx` @ `57c257dd...`,
  `SourMesen/Mesen2` @ `b9fa69dd...` (sparse, GPL or ISC; read, never copied).
- Covell's page calls Mednafen's CPU emulation "very accurate" (and says its
  VBlank starts late); the corpus README calls Mesen possibly the most
  accurate. Both are opinions checked against hardware by eye, not by data.
  Mesen generated the corpus. Every cross-emulator
  comparison in timing.md and undocumented-behavior.md is among these.
- Mednafen proper (the program, not the libretro port) is pinned as
  `mednafen-1.32.1.tar.xz` (tool, 3.5 MB, SHA-256 `de7eb94a...`). It has no
  headless instruction trace; a second referee would need a patch to
  `huc6280.cpp` that prints PC, registers and the cycle count per instruction
  (about ten lines) and a build of the 1.32.1 tree (SDL2 development files are
  installed). **Not built in Phase 0.**

### srg320's `HUC6280` VHDL (MiSTer TurboGrafx16): emulator-derived, a per-cycle third opinion

- Pin: `MiSTer-devel/TurboGrafx16_MiSTer` @ `827d45f4...` (2026-07-09), GPL-2.0+,
  sparse (`/rtl/HUC6280/`, `/rtl/pce_top.vhd`, `/docs/logs 42.95MHz/`).
- `HUC6280_CPU` (ports `A_OUT[20:0]`, `DI`, `DO`, `WE_N`, `RDY`, `NMI_N`,
  `IRQ1_N`, `IRQ2_N`, `IRQT_N`, `MCYCLE`) has the MMU inside; the PSG
  (`psg.vhd`) is separate. **It analyses cleanly with GHDL 7.0.0-dev**
  (`scripts/build_referees.py huc6280-vhdl --oss <bundle>`, six units, run
  2026-10-23 with the bundle 65816-python unpacked, read only). No testbench
  yet; rung 5.
- Hand-written (microcode in `HUC6280_MC.vhd`, 568 KB), not die-traced.

## Rung plan

The ladder mirrors 65816-python's. Each rung says its judge and its tier.

| Rung | What | Judge, tier | State |
| --- | --- | --- | --- |
| 0 | Opcode map, bytes and cycles; every handler cites its manual page | Hudson's software manual, manufacturer; cross-checks `scripts/opcode_map.py`, `compare_cycles.py`, `manual_table.py` | **PASSED** (2026-10-24): `tests/manual.py` transcribes the manual's pages for all 234 defined opcodes (232 from SW, `CSL`/`CSH` from HW HB-25); `tests/test_tables.py` checks mnemonic, mode, bytes and base cycles of `_dispatch.OPCODES` against it, the 22 undefined opcodes against U3, and every row the OCR reads cleanly against the transcription |
| 1 | SingleStepTests huc6280, all 640,000 cases: A X Y S P(B masked) PC, MPR, RAM, every recorded cycle's address, data and kind | SST, emulator; masks for the C-items: C1 `ST0-2` (4 not 5), C2 BRK bytes, C4 `$63`, truncated blocks compared for the first 500 cycles plus `num_cycles` | **PASSED** (2026-10-24): **640,000 of 640,000** cases compared, 0 failing, on CPython 3.14 and PyPy 3.11 (`tests/single_step.py`, `scripts/run_single_step.py`). Masks, each counted: ST0-ST2's write cycle is an internal cycle in the corpus (7,500 cases, C1); TSB/TRB Z (1,492 cases where the two rules differ, C12); TMA #$00 returns a latch the corpus does not initialise (13); block transfers: 12,481 of 12,500 are truncated (500 cycles, 500 RAM pairs), 11,177 read bytes the case does not list (those bytes and what they feed are not compared), 5,031 overwrite their own opcode, operand or stack bytes (those cells are tainted the same way) and **16 still disagree on the final A, X, Y or a listed RAM cell with every recorded cycle, `num_cycles`, PC, P and S agreeing; cause not found** (see tests/single_step.py) |
| 1b | Rockwell 65C02 corpus, semantic only: the ~150 opcodes with the same meaning, final registers and written bytes, with MPR0 and MPR1 mapped to the same RAM (so absolute `$00xx` and zero page `$20xx` meet), P bit 5 cleared in, forced in the comparison, D = 1 cases compared without V, `BRK` and the vector opcodes excluded; every exclusion counted | SST 65x02, emulator | **PASSED** (2026-10-24): `rockwell65c02` fetched in full (550 MB, pin 2f6980a). 209 shared opcodes x 10,000 = **2,089,891 cases pass, 0 fail** (CPython and PyPy; `tests/rockwell.py`, `scripts/run_rockwell.py`). Not run: 470,000 cases of the 46 opcodes the chips do not share (the Hudson-only opcodes, the 65C02's multi-byte NOPs and the other undefined slots) and `BRK` (own vector); 109 excluded because two listed addresses alias through MPR0 = MPR1. Masks, counted: `BIT #imm` N,V (10,000, U19); `TSB`/`TRB` N,V,Z (40,000, U19/C12); decimal `ADC`/`SBC` V (89,721, U14); `PHP`'s pushed bit 5 (10,000); **decimal `SBC` with an invalid BCD digit: A, N, Z, C not compared (38,004, C13)** |
| 2 | Dormann's 65C02 extended opcodes test relocated so code starts at `$4000`, page-zero data at logical `$2000`, vectors at `$FFF6`..`$FFFE` | the program's own traps, research (self-checking) | untried; needs a ca65 build (above) |
| 3 | Directed tests, one per U-item whose tier is hw-verified or manufacturer: MPR reset, `TAM`/`TMA` mask and `$00` rules, `ST0-2` physical address, T-flag lifetimes (SET, PHP, interrupt, PLP, RTI), B in pushed P, block-transfer push order and alternation, `JMP (abs)` at `$xxFF`, the reads-zero rule, decimal V | the sources named in each U-row; expected values written from the statement, not from an emulator | to write |
| 4 | **MAME replay of real games** in a board-less harness: the core runs the ROM from the same reset, hardware-page reads are answered from MAME's log in order, registers and MPRs compared after every instruction; interrupts recognised by the vector target. Games in `/data/emu/share/roms-retrobat/pcengine/` (179 `.7z` HuCards, homebrew and translations: R-Type, Bomberman '94, Blazing Lazers, Bonk's Adventure and others); US releases need `--driver tg16` | MAME 0.285, emulator: a **detector**; each first divergence is looked up in undocumented-behavior.md and settled by the highest tier that covers it | recipe verified (mame-oracle.md); harness to write |
| 5 | srg320's VHDL under GHDL: SST initial states in, per-cycle address and kind compared; a third opinion on C1-C3, C8 | the VHDL, emulator | analyses; testbench to write (same method as 65816-python's `tb_p65c816`) |
| 6 | Through `pcengine-python`: Covell's CPU Test against his photographs, the timer, the VDC stretch, IRQ1 and TIQ timing, `CSH`/`CSL`, block-transfer-to-VRAM | Covell's photographs (hardware-captured, by eye), games | the board's work; failures come back here as issues |

### What no judge decides (do not pretend)

These stay parameters of the core, set to the majority emulator behaviour and
named in the docs, until a published capture or a die model settles them:
the cost and timing of an actual speed change (U10, C7), the interrupt entry's
7 or 8 cycles (C3), the position of every internal cycle and the address of
every dummy read (C8), `TMA` with several bits (C6), the zero-page pointer wrap
(U8), the order of a pending interrupt and the next fetch after a block
transfer (U6), the timer-versus-VDC sampling difference (C10). Rung 5's
VHDL and rung 6's photographs can narrow some; neither is a judge for all.

## The minimal harness (rungs 1-4)

`huc6280.harness` (to write, like `w65c816.harness`): a flat 2 MB physical
`bytearray` (RAM at `$1F0000`-`$1F7FFF` mirrored in pages `$F8`-`$FB`, HuCard
ROM at `$000000` and mirrored up, `$FF` for the unused pages), MPR7 = 0 at
reset, a `read_byte`/`write_byte`/`idle` triple, the hardware page answered by
a stub (constants for rung 1; the MAME log for rung 4), and a loader for `.pce`
files (a 512-byte copier header dropped when the size is 512 mod 8,192) from
`.zip`, `.7z` and raw. The same `load_rom` rule is in `scripts/mame_trace.py`.
