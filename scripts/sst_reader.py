"""Read SingleStepTests ``huc6280`` (reference/src/huc6280/v1/XX.json.bin) without converting it.

The binary layout is described by the corpus's own transcode_json.py (read it
for the field order); this module is a reader written for this repository,
yielding plain dictionaries. Emulator-derived data (Mesen): a detector.

Little-endian throughout. A file is ``u32 count`` then ``count`` tests:

    i32 size, 50-byte name, u32 opcode, initial state, final state, cycles

A state is ``i32 size, A X Y S P (5 bytes), u16 PC, 8 MPR bytes, i32 n, n x
(u32 address, u8 value)``. Cycles are ``u32 num_cycles`` (the true count),
``u32 recorded`` (at most 500) and ``recorded`` x ``u32`` packed as
``RD | WR << 1 | dummy << 2 | address << 3 (21 bits) | data << 24``.
"""

from __future__ import annotations

import struct
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "reference" / "src" / "huc6280" / "v1"


def _state(buf: bytes, ptr: int) -> tuple[int, dict]:
    (size,) = struct.unpack_from("<i", buf, ptr)
    ptr += 4
    a, x, y, s, p, pc = struct.unpack_from("<5BH", buf, ptr)
    ptr += 7
    mpr = list(struct.unpack_from("<8B", buf, ptr))
    ptr += 8
    (count,) = struct.unpack_from("<i", buf, ptr)
    ptr += 4
    ram = []
    for _ in range(count):
        address, value = struct.unpack_from("<IB", buf, ptr)
        ptr += 5
        ram.append((address, value))
    return size, {"a": a, "x": x, "y": y, "s": s, "p": p, "pc": pc, "mpr": mpr, "ram": ram}


def tests(path: Path) -> Iterator[dict]:
    """Every test in one ``XX.json.bin`` file."""
    buf = path.read_bytes()
    (count,) = struct.unpack_from("<I", buf, 0)
    ptr = 4
    for _ in range(count):
        (size,) = struct.unpack_from("<i", buf, ptr)
        at = ptr + 4
        name = buf[at : at + 50].decode("ascii", "replace").strip("\0 ")
        at += 50
        (opcode,) = struct.unpack_from("<I", buf, at)
        at += 4
        used, initial = _state(buf, at)
        at += used
        used, final = _state(buf, at)
        at += used
        num_cycles, recorded = struct.unpack_from("<II", buf, at)
        at += 8
        cycles = []
        for word in struct.unpack_from(f"<{recorded}I", buf, at):
            read, write, dummy = word & 1, (word >> 1) & 1, (word >> 2) & 1
            cycles.append((
                (word >> 3) & 0x1FFFFF if read or write else 0,
                (word >> 24) & 0xFF if read or write else 0,
                "r" * read + "w" * write + "d" * dummy,
            ))  # fmt: skip
        yield {
            "name": name, "opcode": opcode, "initial": initial, "final": final,
            "num_cycles": num_cycles, "cycles": cycles,
        }  # fmt: skip
        ptr += size
