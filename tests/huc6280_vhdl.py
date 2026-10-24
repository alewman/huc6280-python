"""Rung 5: srg320's HUC6280_CPU VHDL, run under GHDL on SingleStepTests initial states.

``tests/huc6280_vhdl/tb_huc6280.vhd`` loads each case by running a loader program
(:func:`loader`) after a reset, then logs every bus cycle of the case's instruction. This module
writes the stimulus, runs the testbench (``scripts/build_referees.py huc6280-tb`` builds it),
parses the log, and runs the same case through the core so the two can be compared cycle by
cycle: read or write, address and value.

The HDL is emulator-derived (hand-written, proven on FPGA against games, not traced from a die;
validation.md): a third opinion where Mesen's corpus and the other emulators disagree (C1, C3,
C6, C8), never a judge. It has no "dummy read" or "opcode fetch" pin, so a core's dummy read
and internal cycle are both a read cycle to it; ``MCYCLE`` is logged and examined in the report.
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from huc6280 import HuC6280

ROOT = Path(__file__).resolve().parents[1]
TESTBENCH = ROOT / "reference" / "build" / "huc6280-tb" / "tb_huc6280"
BUILD_HINT = "HuC6280 testbench not built: python -I scripts/build_referees.py huc6280-tb --oss DIR"
LOADER_OFFSETS = (
    0x008,
    0x100,
    0x200,
    0x300,
    0x400,
    0x600,
    0x800,
    0xA00,
    0xC00,
    0x1000,
    0x1400,
    0x1800,
)  # inside logical $E000-$FFFF, after the stub
STACK_PAGE = 0x2100
PLP = 0x28


def physical(mpr: list[int], logical: int) -> int:
    return mpr[logical >> 13] << 13 | logical & 0x1FFF


@dataclass(frozen=True, slots=True)
class Cycle:
    """One bus cycle. ``kind`` is the core's: "r", "w", "d" (a dummy read), "i" (internal);
    the HDL's are "r" and "w" only. ``address`` and ``value`` are None where they mean
    nothing (an internal cycle)."""

    kind: str
    address: int | None
    value: int | None
    mcycle: int | None = None

    @property
    def write(self) -> bool:
        return self.kind == "w"

    def text(self) -> str:
        address = "------" if self.address is None else f"{self.address:06X}"
        value = "--" if self.value is None else f"{self.value:02X}"
        mcycle = "" if self.mcycle is None else f" m{self.mcycle}"
        return f"{self.kind} {address} {value}{mcycle}"


def loader(case: dict, offset: int) -> tuple[dict[int, int], int]:
    """Loader memory (physical address: byte) that leaves the CPU in the case's initial state,
    and the physical address of its final ``JMP``.

    Stub at logical $E000 (MPR7 is 0 after reset, so physical $000000): ``LDA #mpr7; TAM #$80;``
    then ``JMP`` to the main loader, fetched under the new MPR7. The main loader sets MPR0-6, S
    (``TXS``), pushes P so that the final ``PLP`` pulls it (P includes T and D), loads X, Y, A,
    and jumps to the byte before the case's first instruction, where a PLP is overlaid.
    """
    initial = case["initial"]
    mpr = initial["mpr"]
    target = 0xE000 + offset
    base = mpr[7] << 13
    memory = {0: 0xA9, 1: mpr[7], 2: 0x53, 3: 0x80}
    memory[base + 4], memory[base + 5], memory[base + 6] = 0x4C, target & 0xFF, target >> 8
    code = bytearray()
    for index in range(7):
        code += bytes([0xA9, mpr[index], 0x53, 1 << index])  # LDA #mpr, TAM #bit
    code += bytes([0xA2, initial["s"], 0x9A])  # LDX #s, TXS
    code += bytes([0xA9, initial["p"], 0x48])  # LDA #p, PHA: P at stack[s], S = s - 1
    code += bytes([0xA2, initial["x"], 0xA0, initial["y"], 0xA9, initial["a"]])  # LDX, LDY, LDA
    jmp = base + offset + len(code)
    before = (initial["pc"] - 1) & 0xFFFF
    code += bytes([0x4C, before & 0xFF, before >> 8])
    for index, byte in enumerate(code):
        memory[base + offset + index] = byte
    memory[0x1FFE], memory[0x1FFF] = 0x00, 0xE0
    return memory, jmp


def stimulus(case_id: int, case: dict) -> str:
    """Three stimulus lines for one SST case (tb_huc6280.vhd's format)."""
    initial = case["initial"]
    mpr = initial["mpr"]
    plp_cell = physical(mpr, (initial["pc"] - 1) & 0xFFFF)
    stack_cell = physical(mpr, STACK_PAGE | initial["s"])
    for offset in LOADER_OFFSETS:
        memory, jmp = loader(case, offset)
        used = set(memory) - {0x1FFE, 0x1FFF}
        if not {plp_cell, stack_cell} & used:
            break
    else:
        raise ValueError("no loader offset clear of the stack and the byte before the case")
    memory[plp_cell] = PLP
    cycles = case["num_cycles"]
    cap = min(cycles, len(case["cycles"])) + 1  # one more: the next opcode fetch
    ram = initial["ram"]
    head = f"{case_id} {len(memory)} {len(ram)} {jmp} {cap}"
    loader_line = " ".join(f"{a} {v}" for a, v in sorted(memory.items()))
    ram_line = " ".join(f"{a} {v}" for a, v in ram)
    return f"{head}\n{loader_line}\n{ram_line}\n"


def run_testbench(cases: list[dict]) -> list[list[Cycle] | None]:
    """Each case's cycles from HUC6280_CPU (None where the loader failed); one more than the
    case's recorded cycles: the next opcode fetch."""
    with tempfile.TemporaryDirectory() as scratch:
        stim = Path(scratch) / "stimulus.txt"
        out = Path(scratch) / "bus.txt"
        texts, skipped = [], set()
        for number, case in enumerate(cases):
            try:
                texts.append(stimulus(number, case))
            except ValueError:  # no loader address clear of the case's own bytes
                skipped.add(number)
        stim.write_text("".join(texts))
        run = subprocess.run(
            [str(TESTBENCH), f"-gstimulus={stim}", f"-goutput={out}"],
            cwd=scratch, capture_output=True, text=True, check=False,
        )  # fmt: skip
        if run.returncode:
            name = cases[0]["name"] if cases else "?"
            raise RuntimeError(f"tb_huc6280 failed on {name}...: {run.stderr[-600:]}")
        results: list[list[Cycle] | None] = []
        current: list[Cycle] | None = None
        for line in out.read_text().splitlines():
            words = line.split()
            if words[0] == "C":
                current = []
            elif words[0] == "E":
                results.append(current)
            elif words[0] == "X":
                current = None
            elif current is not None:
                address, value = int(words[0]), int(words[1])
                kind = "w" if words[2] == "0" else "r"
                current.append(Cycle(kind, address, value, int(words[3] == "1")))
        # Cases the loader could not be placed for answer None, in their place.
        it = iter(results)
        return [None if number in skipped else next(it) for number in range(len(cases))]


def run_core(case: dict) -> list[Cycle]:
    """The core's cycles for one case (one more than the case's: none, only the case's)."""
    initial = case["initial"]
    memory = dict(initial["ram"])
    seen: list[Cycle] = []

    def read_byte(address: int) -> int:
        value = memory.get(address, 0)
        seen.append(Cycle("r", address, value))
        return value

    def write_byte(address: int, value: int) -> None:
        memory[address] = value
        seen.append(Cycle("w", address, value))

    def idle(address: int | None) -> None:
        seen.append(Cycle("i", None, None) if address is None else Cycle("d", address, None))

    cpu = HuC6280(read_byte, write_byte, idle)
    cpu.block_reads_hardware_page_as_zero = False
    for name in ("a", "x", "y", "s", "p", "pc"):
        setattr(cpu, name, initial[name])
    cpu.mpr[:] = initial["mpr"]
    cpu.step()
    return seen


def run_corpus(case: dict) -> list[Cycle]:
    """SingleStepTests' own cycles for one case."""
    kinds = {"r": "r", "w": "w", "rd": "d", "": "i"}
    return [
        Cycle(kinds[kind], address if kind else None, data if kind in ("r", "w") else None)
        for address, data, kind in case["cycles"]
    ]


CATEGORIES = ("count", "writes", "reads", "idle_count", "pattern")


def _is_access(cycle: Cycle) -> bool:
    """A cycle that puts a read or a write on the bus: for the core and the corpus a read, a
    write or a dummy read (Mesen's model, C8); for the HDL, ``MCYCLE`` high."""
    if cycle.mcycle is not None:
        return cycle.mcycle == 1
    return cycle.kind in ("r", "w", "d")


def pattern(cycles: list[Cycle]) -> str:
    """One letter a cycle: R a read (a dummy read included), W a write, . an internal cycle."""
    return "".join(("W" if c.write else "R") if _is_access(c) else "." for c in cycles)


def _reads(cycles: list[Cycle]) -> list[tuple[int | None, int | None]]:
    """(address, value) of the cycles that read data: the core's and the corpus's real reads,
    the HDL's every read with ``MCYCLE`` high."""
    return [
        (c.address, c.value)
        for c in cycles
        if (c.mcycle == 1 and not c.write) or (c.mcycle is None and c.kind == "r")
    ]


def _subsequence(needle: list, haystack: list) -> bool:
    items = iter(haystack)
    return all(any(item == candidate for candidate in items) for item in needle)


def differences(left: list[Cycle], right: list[Cycle]) -> set[str]:
    """The categories in which two cycle lists differ.

    ``count``: the number of cycles. ``writes``: the (address, value) of the writes, in order.
    ``reads``: the (address, value) of the reads, in order, over the shorter list (the HDL's
    reads include its dummy reads, whose values the core does not have, so those compare by
    address only; see the report).
    ``idle_count``: how many cycles have no data transfer. ``pattern``: the cycle-by-cycle
    sequence of R, W and . (C8, the place of the internal cycles).
    """
    found = set()
    if len(left) != len(right):
        found.add("count")
    if [(c.address, c.value) for c in left if c.write] != [
        (c.address, c.value) for c in right if c.write
    ]:
        found.add("writes")
    hdl_side = left if left and left[0].mcycle is not None else right
    if hdl_side is not left and not (right and right[0].mcycle is not None):
        # No HDL: the core and the corpus must have the same real reads.
        if _reads(left) != _reads(right):
            found.add("reads")
    else:
        # The HDL also reads at its dummy cycles, so the other side's real reads must be a
        # subsequence of the HDL's.
        other = right if hdl_side is left else left
        if not _subsequence(_reads(other), _reads(hdl_side)):
            found.add("reads")
    if sum(not _is_access(c) for c in left) != sum(not _is_access(c) for c in right):
        found.add("idle_count")
    if pattern(left) != pattern(right):
        found.add("pattern")
    return found


def next_fetch_matches(case: dict, hdl: list[Cycle]) -> bool:
    """Whether the HDL's cycle after the case's own is the fetch of the next instruction
    (the final PC, mapped): it took the same number of cycles."""
    recorded = len(case["cycles"])
    final = case["final"]
    if case["num_cycles"] != recorded or len(hdl) <= recorded:
        return True  # a truncated block transfer: no count to check
    return hdl[recorded].address == physical(final["mpr"], final["pc"])


def vote(core: list[Cycle], hdl: list[Cycle], corpus: list[Cycle]) -> dict[str, str]:
    """Who stands alone in each category where the three differ: "HDL alone" (the core and the
    corpus agree), "corpus alone", "core alone", or "all differ"."""
    core_vs_hdl, corpus_vs_hdl = differences(core, hdl), differences(corpus, hdl)
    core_vs_corpus = differences(core, corpus)
    sides = {}
    for category in core_vs_hdl | corpus_vs_hdl | core_vs_corpus:
        if category not in core_vs_corpus:
            sides[category] = "HDL alone"
        elif category not in core_vs_hdl:
            sides[category] = "corpus alone"
        elif category not in corpus_vs_hdl:
            sides[category] = "core alone"
        else:
            sides[category] = "all differ"
    return sides
