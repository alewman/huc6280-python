# Handoff: build `huc6280-python`, the PC Engine's CPU core

## Context you are inheriting

The family's shape is **chips are cores, boards compose cores**. Each core is
certified on its own against its oracles and pinned by the boards that use it.
This core's first user is `pcengine-python` (`/data/emu/pcengine-python`,
prepared in parallel; do not edit it). The SuperGrafx and the CD-ROM
systems are the same CPU. A board that finds a corner of this core raises it
**on the core** (an issue or a PR here; re-certification is fine), never as a
workaround in the board.

Models for the code and the tooling:

- `6502-python` (`/data/emu/6502-python`, public): **its frame is this core's
  base class** (decided below). Every CPU cycle is one bus callback, in chip
  order; interrupts polled at the end of the second-to-last cycle.
  `src/sixfiveohtwo/frame.py` is the whole base class (347 lines).
- `65816-python` (`/data/emu/65816-python`): the model for everything else. It
  subclasses the frame, has an `idle` callback and its own state, tooling,
  harness, and a Phase 0 identical in shape to this one. Read its
  `docs/handoff-brief.md` and `src/w65c816/cpu.py` before writing code.
- `z80-python`: the readability contract (one instruction family per module, one
  mnemonic per handler docstring, the hardware reason as a comment on the line
  that encodes it), the tooling bar, `docs/` layout, oracle tiers.
- `m6800-python`, `sm83-python`: the rung ladder and the scripts that drive MAME.

The user's rules that bind this work:

- **Oracle tiers**: hardware-captured > hardware-verified > manufacturer >
  research > emulator-derived (validation.md); a low-tier oracle is a detector,
  never a judge; state the tier of every claim.
- **Python floor 3.11** (the newest PyPy supports): `requires-python = ">=3.11"`,
  ruff `target-version = "py311"`, CPython and PyPy both green.
- **Reference cores are correct, not fast.** A `-fast` fork is later work.
- **Modern over compat**: callables, dataclasses, no shims; no external users.
- **No dangerous-looking shell one-liners** in scripts or docs (no `rm -rf`,
  `sed -i`, `ln -sfn`); keep CI minimal (PyPy only, main + PRs, cancel in
  progress) if and when a GitHub repository exists. This repository is **local
  git only** until the user says otherwise.
- **Never copy a chip file between repositories**; extract on the second
  consumer.
- **The user has no hardware.** No rung needs a console, a capture rig or a
  flash cartridge; published captures, emulators and die models only.
- Run any Python that reads `reference/` with `-I`.

### Read, in this order, before writing code

1. `README.md`.
2. `docs/start-here.md`: registers, the MMU, the zero page at `$2000`, vectors,
   the clock, block transfers, what the core does not own.
3. `docs/timing.md`: the measured agreement, the opcode and cycle grids, the
   bus shapes, the disagreements.
4. `docs/undocumented-behavior.md`: U1-U22, C1-C11.
5. `docs/validation.md`: every oracle with tier and pin, the rung plan, what no
   judge decides.
6. `docs/mame-oracle.md`.
7. `/data/emu/6502-python/docs/start-here.md`, `docs/api-stability.md`, all of
   `src/sixfiveohtwo/frame.py`; `/data/emu/65816-python/src/w65c816/` (cpu.py,
   `_core.py`, `harness.py`) as the worked example of a frame subclass.

Then `python -I scripts/fetch_references.py --no-tools` (11 repositories and
9 files, 200 MB including the SingleStepTests corpus; the two `tool` pins are the
750 MB GHDL bundle and Mednafen's source), and `python -I scripts/survey_sst.py`,
`compare_cycles.py`, `opcode_map.py`, `manual_table.py` to see the data run.

## What 6502-python must gain

**Decided here: subclass the frame, as 65816-python does; do not subclass
`MOS6502` or add a CMOS mode first.** The evidence, measured against the frame
and the NMOS handlers as they are on `origin/main` @ `9dc34bd` (PRs #7
dma-stall and #8 CPUFrame merged; local `main` in `/data/emu/6502-python` is
behind it) and `tooling-hooks` @ `2146eba` (PR #9, open):

### What the frame gives (read from `frame.py`, `tests/test_frame.py`)

- the two bus callables and their replaceable setters; `_read`/`_write` and the
  `_confirm()` wrappers that tell whether a request changed before the last
  cycle;
- `step()`'s skeleton: reset, a halted CPU, the interrupt this boundary takes,
  one instruction, the deferred poll, with the hooks `_accept_reset`,
  `_halted`, `_boundary_interrupt`, `_enter_interrupt(kind)`, `_execute`;
- the request API (`request_maskable_interrupt`, `request_non_maskable_interrupt`,
  `request_reset` and their clears and `*_pending`), the poll rules (requests as
  they stood at the end of the second-to-last cycle; `CLI`/`SEI`/`PLP` act one
  instruction late through `_polled_i`; `BRK`, entries and reset do not poll), and
  the poll fields of a snapshot;
- room for a part's own request bits, for the part's own `kind` in
  `_enter_interrupt`, a `p` whose bit 2 is the interrupt-disable flag
  (**true for the HuC6280**), and `note_stall()` for a read a host stretches
  (the VDC/VCE wait is such a stretch: whether it should call it is a question for
  the board, since HW HB-12 samples interrupts in the last bus cycle);
- with PR #9: `StepRecord`, `DebugSession`, `read_trace` and `CommandDebugger` as
  subclassing surfaces, including `address_mask` and part-specific access kinds
  (an access kind starts with `r`/`w` for a read/write, or any other letter for a
  cycle that is neither: use `dummy` and `idle`).

That covers the HuC6280's needs without a change, because:

- **the opcode map is different**: 24 Hudson-only opcodes (`SXY` `SAX` `SAY` `CLA`
  `CLX` `CLY` `ST0-2` `TMA` `TAM` `CSL` `CSH` `SET` `BSR` four `TST`s and five block
  transfers) sit where the 65C02 has `NOP`s, and the `NOP` set is another, and **the cycles are different in every memory
  mode** (timing.md: `LDA zp` 4 not 3, `JSR` 7 not 6, `(zp),Y` 7 not 5, no index
  or branch page penalties, `BRK` 8);
- **the addresses are different**: a 16-bit logical address becomes 21-bit
  physical in the core; zero page and stack are at `$2000`/`$2100`; the NMOS
  `_ea_*` helpers (page zero wrap, dummy reads of the unindexed address) do none
  of this;
- **no NMOS behaviour carries over** (the 65816 brief's list applies, with
  these differences): no dummy write in read-modify-write (the corpus shows a
  read, an internal cycle, a write), no interrupt hijacking, no JAM, no
  undocumented opcodes (every one is a `NOP`), no decimal quirks (U14), no
  `JMP ($xxFF)` bug (U9), no branch-specific poll points (a taken branch costs
  2 and has no page penalty; unknown whether it polls differently, C8).

### What a CMOS layer would add (and why this core is not it)

A `W65C02` (or `W65SC02`) class on `MOS6502` would add, for the Atari Lynx, the
Apple IIc and similar boards: its own opcode table (the 105 undocumented NMOS
opcodes replaced by documented or `NOP` entries of various lengths and
cycles), `BRA`, `STZ`, `TSB`, `TRB`, `PHX`/`PHY`/`PLX`/`PLY`, `INC A`/`DEC A`,
`BIT` immediate/`zp,X`/`abs,X`, `(zp)`, `JMP (abs,X)`, the fixed `JMP (abs)`
(6 cycles), a dummy read instead of a dummy write in read-modify-write, `BRK`
clearing D, valid N and Z and an extra cycle in decimal mode, and for the
Rockwell/WDC variants `RMB`/`SMB`/`BBR`/`BBS` (and `WAI`/`STP` on the WDC part).
The HuC6280 shares the *semantics* of that list and **none of its cycles or bus
cycles**, so it cannot inherit those handlers; it can only share pure helpers.
The pure ALU functions exist (`sixfiveohtwo._alu.add`/`subtract`,
`w65c816._alu.add`/`subtract`) but are flavour-specific: NMOS decimal takes its
flags from the binary sum, the 65C816's takes N, Z, C from the decimal result
and V from a partial sum, the HuC6280's takes N, Z, C from the decimal result
and **leaves V** (U14). A third flavour is a third function, not a shared one.
So **write `huc6280._alu` here** (about 80 lines), citing its own sources.

### The PRs, in order (small, none blocks the build)

0. **None required to start.** Pin `6502-python` by commit, as 65816-python does
   (`pyproject.toml` `dependencies`): `@2146eba3b3da4d2cc6c8fa3994f100bcb5abf039`
   (PR #9's head, which has the frame and the tooling hooks) until #9 merges and
   a release contains it; then the release.
1. **(optional) Extra request bits in the snapshot.** `CPUFrame._poll_fields` and
   `_restore_poll` capture `IRQ_LINE` and `NMI_LATCH` only; the 65816's ABORT bit
   is captured by that core itself, outside the polled snapshot. If the build
   uses extra request bits for IRQ1/IRQ2/TIQ (the alternative below), a class
   attribute naming the subclass's bits would let the frame capture and restore
   them with the rest. Not needed for the recommended design (below), which
   keeps the single `IRQ_LINE`.
2. **(optional, not on this path) A CMOS class in 6502-python for the Lynx.**
   The Rockwell/WDC/Synertek corpora are the judges
   (`SingleStepTests/65x02`: `wdc65c02`, `rockwell65c02`, `synertek65c02`, 256 files
   x 10,000 cases, about 1.0 GB each, **not in any local checkout**: 6502-python's
   `tests/6502_test_vectors` has `6502` and `nes6502` only). This core's rung 1b
   would reuse the Rockwell set without that PR.
3. **(later, when a second chip needs it) Public pure helpers.** Do not extract
   the ALU functions yet; the three flavours differ. Revisit when a fourth part
   (the Lynx's 65SC02, the 65CE02) arrives.

### The interrupt design (recommended; uses the frame unchanged)

Keep the frame's `IRQ_LINE` as "an enabled maskable source is asserted" and
`NMI_LATCH` as NMI. The core exposes `set_irq_lines(irq1, irq2, tiq)` and a
plain `irq_disable` attribute (bits 0-2: IRQ2, IRQ1, TIQ, 1 = disabled, the
`$1402` layout; the board's register forwards its writes), computes
`pending = lines & ~irq_disable`, and calls `request_maskable_interrupt` or
`clear_maskable_interrupt` when `pending` changes. `_enter_interrupt(IRQ_LINE)`
picks the vector at entry from the lines in priority order (TIQ `$FFFA`, IRQ1
`$FFF8`, IRQ2 `$FFF6`), as Mednafen and MAME do. NMI is `$FFFC` and is never
connected on a console (pcetech). `BRK` is its own instruction (vector `$FFF6`,
B = 1).

## The core boundary

**Decision for Aubrey**, recommendation first (the rule: CPUs always own a core;
a non-CPU chip used by one machine family stays in the board unless other
emulators could use it).

| Piece | Recommended owner | Why |
| --- | --- | --- |
| CPU, instruction set, T flag, `SET`, block transfers, `CSL`/`CSH` state | core | it is the CPU |
| **MMU** (MPR0-7, `TAM`/`TMA`, 21-bit address, zero page and stack at `$2000`/`$2100`, `ST0-2` bypass) | **core** | it changes what the CPU does (zero page, stack, `TMA #0`'s last-value latch, `ST0` skipping the mapper); every emulator (MAME, Mesen, Mednafen, ares, Geargrafx) and the MiSTer VHDL (`A_OUT[20:0]`) puts it in the CPU model; the core emits physical addresses and a flat host can ignore it |
| interrupt lines, priority, vectors, the `irq_disable` gate | core | the vector choice and the I-flag timing are CPU behaviour (above) |
| the block-transfer zero-read rule (U7) | core | the CPU, not the device, returns 0 |
| **timer**, the `$1402`/`$1403` registers' bus behaviour, the I/O buffer, port K and port O | **board** | on the die but outside the CPU; used by one family; the RP2A03 precedent (its APU, DMA and ports are the host's) and the chip-extraction rule agree. The core's contract is the three line inputs and `irq_disable` |
| **PSG** | **board** | six channels of sound; a different chip's job; extract only if a second emulator wants it (a `huc6280-psg-python` later) |
| VDC/VCE one-cycle stretch | board | it decodes the address; the board charges master clocks inside its callback |
| VDC, VCE, CD-ROM, joypads | board | |

Alternative: ship the timer, the two interrupt registers and the I/O buffer as
a `huc6280.onchip` module in this repository (tested by this core's rungs, used
by the board, no import from the CPU class). It costs nothing now and would
spare `pcengine-python` writing them, but it makes this repository own a
non-CPU chip's behaviour on one family's behalf. Recommendation stands: board.

## The bus contract (required)

```python
cpu = HuC6280(read_byte, write_byte, idle)
#   read_byte(address) -> int      a cycle with a data read; 21-bit physical address
#   write_byte(address, value)     a cycle with a data write
#   idle(address)                  a cycle with no data transfer; address is the
#                                  dummy-read address (PC + 1) or None for an internal cycle
cycles = cpu.step()    # CPU cycles consumed == number of callbacks made
```

- Inside any callback, `cpu.high_speed` (bool) says the current speed, and
  `cpu.kind` is `"read"`, `"write"`, `"dummy"` or `"idle"` (the tooling hook's
  access kinds).
- The board advances its devices **inside** the callbacks by 3 or 12 master
  clocks (by `cpu.high_speed`) plus its own VDC/VCE stretch, never by adding
  `step()`'s return on top (the 65816 contract).
- `step()` runs one instruction or one interrupt entry; a **block transfer is
  one instruction** (`TII` and friends do not refetch; the interrupt waits, U6),
  at most 393,233 callbacks.
- `high_speed` changes at `CSL`/`CSH` (C7: for the instruction's last cycle).
- Interrupt API: 6502-python's, plus `set_irq_lines(irq1, irq2, tiq)` and the
  `irq_disable` attribute.
- Dummy reads go to `idle(address)`, not `read_byte`: nothing on the console
  reacts to a read of `PC + 1`, and the corpus marks them dummy. If the board
  ever needs them as reads, that is a flag on the core, raised as an issue.
- Plain integers in the hot path, no generators, so a `huc6280-rust` and `-fast`
  forks can transcribe it.

## Proposed layout (the build session may refine)

`src/huc6280/`: `cpu.py` (`HuC6280(CPUFrame)`, the step, the interrupt entry, the
reset), `_core.py` (registers, flags, the MMU translate, the cycle helpers
`_read`/`_write`/`_idle`, the zero-page and stack helpers), `_dispatch.py` (the
256-entry table: handler, mode, base cycles from `opcode_map.py`'s grid),
`_alu.py`, `_loads.py`, `_shifts.py`, `_control.py` (branches, stack, `BSR`,
`BRK`, `RTI`), `_bits.py` (`RMB`/`SMB`/`BBR`/`BBS`/`TSB`/`TRB`), `_hudson.py` (`SXY` `SAX`
`SAY` `CLA` `CLX` `CLY` `ST0-2` `TST` `TMA` `TAM` `CSL` `CSH` `SET`), `_block.py`,
`state.py`, `disasm.py`, `debug.py`, `trace.py`, `console.py`, `harness.py`,
`__main__.py`, `py.typed`.

- **One instruction family per module, one mnemonic per handler docstring, the
  manual page or source tier as a comment on the line that encodes each fact**
  (`# U7: pcetech 2.0, hw-verified`).
- **T**: stored in `p` bit 5; `_execute` reads and clears it at the fetch (so a
  handler sees `t_was_set`), `SET` sets it after, `PLP`/`RTI` can set it from the
  stack; the four ALU handlers check `t_was_set` (U4). `p`'s bit 4 reads as 1
  when pushed by `PHP`/`BRK`; keep it clear in storage, as the corpus does.
- **Reset** (`_accept_reset`): MPR7 = 0, the others as the host's `power_on_mpr`
  (default zero, documented as random on hardware, U2), I set, D and T clear,
  low speed, vector from physical `$001FFE` through MPR7.

## Your task

Build the core to the rung ladder in `docs/validation.md`, one rung per
commit, in this order: 0 (the grid and the manual tables), 1 (SingleStepTests
`huc6280`, all 640,000 cases, masks counted), 1b (Rockwell 65C02, semantic),
3 (directed U-tests), then 4 (the MAME replay), 2 (Dormann, relocated) and 5
(the VHDL testbench) as time allows. Keep `docs/` current; every deviation from a source gets
a U or C entry with its tier.

### Tooling at the family bar

`state.py` (`CPUState` with `a x y s pc p mpr[8] high_speed`, the poll fields),
`disasm.py` (the 24 Hudson opcodes, operand lengths, checked against MAME's
6280dasm in `error.log` order), `debug.py` (breakpoints on logical PC and on the
21-bit address, watchpoints on physical addresses), `trace.py` (JSONL, the family
schema with `kind` = read, write, dummy, idle), `console.py`, and `python -m
huc6280 GAME.pce [--max-cycles N] [--trace out.jsonl]` running a HuCard in the
harness. Use 6502-python's tooling hooks (PR #9), not parallel modules.

## Decided by the user

Nothing yet: this Phase 0 is new. The section below lists what it needs.

## Open decisions for Aubrey

Each with the recommendation. Items 1 and 2 are the ones that block the first
line of code.

1. **Names.** Distribution `huc6280-python`, import package `huc6280`, class
   `HuC6280` (one class for the HuC6280 and HuC6280A; the CD-ROM and
   SuperGrafx systems use it unchanged). Alternatives: `hudson6280` (avoids the
   digits-first problem the 65816 had: not an issue here, a name may start with
   `h`); `HuC6280A` for the class (the revision most consoles shipped with;
   nothing found distinguishes the CPUs); `pce-cpu` (rejected: not the part's
   name, the family names chips by part).
2. **The core boundary** (above): MMU, interrupt lines, vector choice and the
   block-transfer zero-read rule in the core; timer, `$1402`/`$1403`, I/O buffer,
   ports and PSG in the board. Alternative: a `huc6280.onchip` module here for
   the timer and interrupt registers. **Recommend: board**, with the line API.
3. **Frame subclass, no CMOS prerequisite.** `HuC6280(CPUFrame)`, `huc6280._alu`
   written here, pin 6502-python by commit (PR #9's head). PRs 1-3 above are
   optional and none blocks. **Recommend: yes**, and leave the Lynx's 65C02 mode
   to its own plan.
4. **Bus contract**: `idle(address | None)` for internal cycles and dummy reads,
   `read_byte`/`write_byte` physical 21-bit, `cpu.high_speed` and `cpu.kind`
   readable in callbacks, one `step()` per block transfer. **Recommend: as
   written**; the alternative is dummy reads as flagged `read_byte` calls
   (Mesen's model), which costs a branch per implied instruction for a side effect
   nothing has.
5. **How to settle what no judge can** (validation.md "What no judge decides").
   Defaults, each labelled emulator-derived in the code and docs: interrupt entry
   8 cycles (C3), `TMA` with several bits ORs (C6), a speed change takes effect for
   the instruction's last cycle and costs 3 (C7), zero-page pointers wrap in the
   zero page (U8), block reads of `$0800`-`$13FF` return 0 (C9, hw-verified),
   `SBC` ignores T (C5), `$63` is a 2-cycle `NOP` (C4). **Recommend: adopt these**,
   keep each as a named class attribute so a board or a later capture can change
   it.
6. **Check out the Rockwell 65C02 corpus (1.0 GB, sparse `/rockwell65c02/`) for
   rung 1b.** **Recommend: yes**, in `reference/` (gitignored), after rung 1
   passes; it is the only volume judge for the semantics of the 65C02
   instructions on this chip, and the Lynx plan will want the same files.
7. **Build Mednafen 1.32.1 with a trace patch as the second referee** (pinned,
   not built: about ten lines in `huc6280.cpp`, a build with SDL2). **Recommend:
   yes, after the MAME replay is working**; Mednafen is the other emulator
   Covell's page vouches for, and where MAME and Mesen disagree it would break the
   tie as a vote (still emulator tier).
8. **Public or local.** 65816-python stayed local until rung 1 passed and then
   went public; the five chip cores flipped public for free CI. **Recommend:
   local until rung 1 passes, then public (a CPU core, MIT, no third-party files
   committed)**; the pins in `scripts/` fetch everything else.
9. **Rust and `-fast` forks.** Not now; `pcengine-python` is the first user and
   only needs correct. Revisit with the board's speed measurements, as the Mega
   Drive's were.
10. **Covell's CPU Test as the board's acceptance judge.** The photographs are the
    only hardware-captured material found, and they need a VDC and VCE. **Recommend:
    `pcengine-python` adopts it as a rung-6 milestone and reports line-up
    differences by instruction page back to this core as issues**; do not treat
    a passing run as certification of anything below the instruction.
