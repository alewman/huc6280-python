# huc6280-python

A readable, pure-Python **Hudson Soft HuC6280** CPU core, planned: the 8-bit
processor of the PC Engine, TurboGrafx-16, SuperGrafx and the CD-ROM systems, a
CMOS 6502-family core with a 21-bit memory mapper (eight 8 KB mapping registers),
block transfers, the T flag, a 7.16/1.79 MHz clock switch and a handful of Hudson
instructions. This repository is only the CPU (the boundary, with the on-die
timer, interrupt registers and PSG, is a decision in
[docs/handoff-brief.md](docs/handoff-brief.md)); the console is the board,
[pcengine-python](../pcengine-python).

**Status (2026-10-23): Phase 0 only.** No core code exists. What exists is the
research, the pinned oracles, the measured agreement between sources and the
handoff brief for the session that builds it:

- every oracle with its tier and a rung plan, honest about what no judge can
  decide ([docs/validation.md](docs/validation.md));
- the opcode map, bytes and cycles, the bus shapes of every addressing mode and
  the 26 opcodes where four emulators disagree ([docs/timing.md](docs/timing.md));
- 22 quirks and 11 contradictions, each with its tier
  ([docs/undocumented-behavior.md](docs/undocumented-behavior.md));
- a verified headless MAME 0.285 recipe for PC Engine, TurboGrafx-16 and
  SuperGrafx ([docs/mame-oracle.md](docs/mame-oracle.md)).

It will build on [6502-python](https://github.com/alewman/6502-python)'s frame
(`CPUFrame`) and tooling hooks, subclassed through their documented surface, as
[65816-python](../65816-python) does; a pinned dependency, never copied files.
**There is no hardware-captured per-instruction data and no die-level model of
this chip**; the volume judge is SingleStepTests `huc6280`, which Mesen
generated (emulator tier, a detector). Nothing here was run on a real console.

## What is fetched

Nothing third-party is committed. `scripts/fetch_references.py` rebuilds
`reference/` from `scripts/pinned_files.json` (Hudson's hardware, software and
PSG manuals, MacDonald's pcetech and SuperGrafx notes, Shu's CPU page,
Covell's CPU Test and its page, a 750 MB GHDL bundle and Mednafen's source,
all by SHA-256) and `scripts/pinned_repos.json` (11 repositories at full
commit SHAs, sparse where large): SingleStepTests `huc6280` and `65x02`, MAME
0.285's source, Mesen2, Mednafen's Beetle ports, ares, Geargrafx, the MiSTer
TurboGrafx16 VHDL with its timing captures, the HuC assembler, and Dormann's
65C02 test.

```sh
python -I scripts/fetch_references.py --no-tools   # everything but the two tool pins (~200 MB)
python -I scripts/fetch_references.py --verify     # check what is present
python -I scripts/build_referees.py huc6280-vhdl --oss /path/to/oss-cad-suite
```

They need `git`, `curl`, `pdftotext` (poppler) for `manual_table.py`, and `7z` for
games kept as `.7z`. No sudo.

## Scripts

| Script | What |
| --- | --- |
| `fetch_references.py` | fetch and verify the pinned files and repositories |
| `build_referees.py` | analyse srg320's HUC6280 VHDL with GHDL |
| `sst_reader.py` | read SingleStepTests huc6280's binary files |
| `survey_sst.py` | cycle counts and bus shapes per opcode in the corpus |
| `compare_cycles.py` | four emulators' base cycle tables side by side |
| `opcode_map.py` | the opcode grid with modes, bytes and cycles |
| `manual_table.py` | bytes and cycles read out of Hudson's software manual, compared |
| `mame_trace.py` | the MAME per-instruction trace and hardware-page read log, and a screen capture |

Run anything that reads `reference/` with `python -I`. Traces go in
`tests/mame_traces/` (gitignored); never commit ROMs, traces or fetched files.

## Documents

[docs/README.md](docs/README.md) is the index; [docs/handoff-brief.md](docs/handoff-brief.md)
ends with the open decisions for the owner.

MIT licensed ([LICENSE](LICENSE)).
