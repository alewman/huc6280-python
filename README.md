# huc6280-python

A readable, pure-Python **Hudson Soft HuC6280** CPU core: the 8-bit
processor of the PC Engine, TurboGrafx-16, SuperGrafx and the CD-ROM systems, a
CMOS 6502-family core with a 21-bit memory mapper (eight 8 KB mapping registers),
block transfers, the T flag, a 7.16/1.79 MHz clock switch and a handful of Hudson
instructions. This repository is only the CPU (the boundary, with the on-die
timer, interrupt registers and PSG, is a decision in
[docs/handoff-brief.md](docs/handoff-brief.md)); the console is the board,
`pcengine-python`.

**Status (2026-10-24): the core is built.** `HuC6280(CPUFrame)`: every
cycle one bus callback (`read_byte`, `write_byte`, `idle(address | None)`), the 21-bit
mapper in the core, interrupt lines on the frame's `IRQ_LINE`, one `step()` per block
transfer. It subclasses [6502-python](https://github.com/alewman/6502-python)'s frame (pinned
by commit, never copied) as `65816-python` does. Passing, by rung
([docs/validation.md](docs/validation.md)):

- 0: the opcode map against Hudson's software manual (234 opcodes);
- 1: SingleStepTests `huc6280`, 640,000 of 640,000 cases (emulator tier, masks counted);
- 1b: the Rockwell 65C02 corpus, results only, 2,089,891 cases on 209 shared opcodes;
- 3: directed tests for the hardware-verified and manufacturer-tier quirks;
- 4: MAME 0.285 replay of six games, 21.0 million instructions, no register divergence.

**There is no hardware-captured per-instruction data and no die-level model of this
chip**; the volume judges are emulator tier (detectors). Nothing here was run on a real
console. Tooling at the family bar: `state`, `disasm`, `debug`, `trace`, `console`,
`harness`, and `python -m huc6280 GAME.pce [--trace out.jsonl | --debug]`.

```sh
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest -m "not slow"           # the quick loop
python -I scripts/run_single_step.py               # rung 1, whole (PyPy: minutes)
python -I scripts/run_rockwell.py                  # rung 1b, whole
python -I scripts/mame_trace.py GAME.7z --io --seconds 2 && python -I scripts/mame_replay.py tests/mame_traces/GAME
```

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
| `run_single_step.py`, `run_rockwell.py` | rungs 1 and 1b over every case, a process per chunk |
| `mame_replay.py` | rung 4: replay a MAME trace through the core |

Run anything that reads `reference/` with `python -I`. Traces go in
`tests/mame_traces/` (gitignored); never commit ROMs, traces or fetched files.

## Documents

[docs/README.md](docs/README.md) is the index; [docs/handoff-brief.md](docs/handoff-brief.md)
ends with the open decisions for the owner.

MIT licensed ([LICENSE](LICENSE)).
