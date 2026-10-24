"""Rung 2: Klaus Dormann's 65C02 extended opcodes test, relocated, run on the core.

``scripts/dormann_to_ca65.py`` rewrites the source (as65 syntax, GPL-3.0, research tier for this
chip) for ca65 with the HuC6280 settings, and ``ca65``/``ld65`` (cc65 2.19, pinned in
pinned_files.json under ~/.local/opt or on the PATH) make a 64 KB image. The program is
self-checking: it traps (a jump or branch to itself) at the first wrong result, and reaches
``success_address`` when everything passed.

The memory is the 65C02's flat 64 KB through the mapper as rung 1b maps it: MPR0 and MPR1 are
one bank, so the absolute ``$00xx``/``$01xx`` the program uses and the zero page and stack at
``$20xx``/``$21xx`` the core uses are the same bytes; the code is at ``$4000`` and up.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from huc6280 import HuC6280

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "reference" / "build" / "dormann"
CC65 = Path.home() / ".local" / "opt" / "cc65-2.19" / "bin"
BANK = (0x10, 0x10, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17)
SOURCE = ROOT / "reference" / "src" / "dormann" / "65C02_extended_opcodes_test.a65c"


def tool(name: str) -> str:
    local = CC65 / name
    found = str(local) if local.exists() else shutil.which(name)
    if not found:
        raise FileNotFoundError(f"{name} (cc65) not found: see docs/validation.md rung 2")
    return found


def build(directory: Path = BUILD, *, original: bool = False) -> tuple[bytes, dict[str, int]]:
    """Translate, assemble and link the test; return the 64 KB image and its labels."""
    subprocess.run(
        [
            sys.executable, "-I", str(ROOT / "scripts" / "dormann_to_ca65.py"), str(directory),
            *(["--original"] if original else []),
        ],
        check=True, capture_output=True,
    )  # fmt: skip
    subprocess.run(
        [tool("ca65"), "-l", "test.lst", "-o", "test.o", "test.s"],
        cwd=directory, check=True, capture_output=True,
    )  # fmt: skip
    subprocess.run(
        [tool("ld65"), "-C", "test.cfg", "-Ln", "test.lbl", "-o", "test.bin", "test.o"],
        cwd=directory, check=True, capture_output=True,
    )  # fmt: skip
    labels = {}
    for line in (directory / "test.lbl").read_text().splitlines():
        _, address, name = line.split()
        labels[name.lstrip(".")] = int(address, 16)
    return (directory / "test.bin").read_bytes(), labels


@dataclass
class Result:
    reason: str  # "success", "trap" or "limit"
    pc: int  # where it stopped
    instructions: int
    test_case: int  # the program's own test number (the byte at $0202)


def run(image: bytes, labels: dict[str, int], limit: int = 100_000_000) -> Result:
    memory = bytearray(0x200000)
    for page in (0, 2, 3, 4, 5, 6, 7):  # page 1 is page 0 again (MPR1 = MPR0)
        base = BANK[page] << 13
        memory[base : base + 0x2000] = image[page * 0x2000 : (page + 1) * 0x2000]
    cpu = HuC6280(lambda address: memory[address], memory.__setitem__)
    cpu.mpr[:] = BANK
    cpu.pc = labels["start"]
    cpu.s = 0xFF
    cpu.p = 0x04
    step = cpu.step
    done = labels["success_address"]
    instructions = 0
    while instructions < limit:
        before = cpu.pc
        step()
        instructions += 1
        if cpu.pc == before:  # a jump or branch to itself: a trap, or success
            reason = "success" if before == done else "trap"
            return Result(reason, before, instructions, memory[BANK[0] << 13 | 0x202])
    return Result("limit", cpu.pc, instructions, memory[BANK[0] << 13 | 0x202])
