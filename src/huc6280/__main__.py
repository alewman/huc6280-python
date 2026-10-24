"""Run a HuCard in the minimal harness, or step through it: ``python -m huc6280``.

    python -m huc6280 game.pce --max-cycles 1000000
    python -m huc6280 game.pce --trace out.jsonl --max-cycles 100000
    python -m huc6280 game.7z --debug -c "break $E000" -c continue

The host is ``huc6280.harness``: a HuCard (mirrored as Mesen2 mirrors it), work RAM and a stubbed
hardware page; not a PC Engine (that is pcengine-python). A run stops when the program spins on
a jump to itself or after ``--max-cycles`` CPU cycles, and prints why and where. ``--trace``
writes every boundary as a JSON Lines record, bus accesses included (``huc6280.trace``).

``--debug`` (or any ``-c``) opens the command debugger instead (``huc6280.console``); ``-c``
commands run first, then the prompt reads stdin unless ``--batch`` is given. ``help`` lists the
commands. Numbers are decimal; ``0x1234`` or ``$1234`` is hexadecimal. ``.zip`` and ``.7z`` take
the first ``.pce``/``.sgx``/``.bin`` inside.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from huc6280.console import CommandError, HuC6280Debugger, parse_number
from huc6280.debug import HuC6280Session
from huc6280.harness import Harness, load_rom
from huc6280.trace import write_trace


def _number(text: str, name: str) -> int:
    try:
        return parse_number(text, name)
    except CommandError as exc:
        raise SystemExit(f"{name}: {exc}") from exc


def make_session(harness: Harness, **options) -> HuC6280Session:
    """A debug session over the harness's CPU, with logical and physical peeks."""
    cpu = harness.cpu
    return HuC6280Session(
        cpu,
        peek_byte=lambda address: harness.peek(cpu.physical(address)),
        peek_physical=harness.peek,
        **options,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m huc6280",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("rom", type=Path, help=".pce, .sgx, .bin, or a .zip/.7z holding one")
    parser.add_argument("--max-cycles", default="10000000", help="CPU cycles to run at most")
    parser.add_argument("--trace", type=Path, metavar="OUT.jsonl", help="write every boundary")
    parser.add_argument("--debug", action="store_true", help="open the command debugger")
    parser.add_argument(
        "-c", "--command", action="append", default=[], help="a debugger command to run first"
    )
    parser.add_argument("--batch", action="store_true", help="exit after the -c commands")
    args = parser.parse_args(argv)

    harness = Harness(load_rom(args.rom))
    if args.debug or args.command:
        session = make_session(harness, track_accesses=True)
        session.step()  # the reset sequence
        debugger = HuC6280Debugger(session)
        for command in ["registers", "disassemble", *args.command]:
            print(f"{debugger.prompt}{command}")
            try:
                result = debugger.execute(command)
            except CommandError as exc:
                print(f"error: {exc}")
                continue
            for line in result.lines:
                print(line)
            if result.quit:
                return 0
        if not args.batch:
            debugger.interact(sys.stdin, sys.stdout)
        return 0

    max_cycles = _number(args.max_cycles, "--max-cycles")
    if args.trace is None:
        result = harness.run(max_cycles)
    else:
        session = make_session(harness, history_limit=0, track_accesses=True)
        with args.trace.open("w", encoding="utf-8") as out:
            result = harness.run(max_cycles, step=lambda: write_trace((session.step(),), out))
        session.close()
    print(
        f"{result.reason} after {result.cycles:,} cycles at {result.pc:04X} "
        f"({harness.master_clocks:,} master clocks)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
