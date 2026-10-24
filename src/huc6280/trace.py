"""Deterministic boundary traces of the HuC6280: write, read and compare them.

6502-python's trace functions (its docs/trace-schema.md, version 1) with this core's record
type: one JSON object per boundary, with ``kind`` one of :class:`~huc6280.debug.BoundaryKind`'s
values, ``before`` and ``after`` :class:`~huc6280.state.CPUState`'s fields, ``instruction.address``
the 16-bit logical PC, and ``accesses`` ``[kind, address, value]`` with the kinds of
:mod:`huc6280.debug` (``"r"``, ``"w"``, ``"d"``, ``"i"``) and 21-bit physical addresses, one per
cycle. A trace written here is read back equal, and two cores' traces are compared with
:func:`first_trace_divergence`.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TextIO

from sixfiveohtwo.trace import (
    TRACE_SCHEMA_VERSION,
    TraceDifference,
    TraceDivergence,
    compare_step_records,
    first_session_divergence,
    first_trace_divergence,
    iter_session_steps,
    iter_trace_divergences,
    step_record_to_dict,
    write_trace,
)
from sixfiveohtwo.trace import read_trace as _read_trace
from sixfiveohtwo.trace import step_record_from_dict as _step_record_from_dict

from huc6280.debug import HuC6280Record


def step_record_from_dict(value: object) -> HuC6280Record:
    """Reconstruct one strictly validated HuC6280 record."""
    return _step_record_from_dict(value, record_type=HuC6280Record)


def read_trace(stream: TextIO) -> Iterator[HuC6280Record]:
    """Yield strictly validated HuC6280 records lazily from a JSON Lines stream."""
    return _read_trace(stream, record_type=HuC6280Record)


__all__ = [
    "TRACE_SCHEMA_VERSION",
    "TraceDifference",
    "TraceDivergence",
    "compare_step_records",
    "first_session_divergence",
    "first_trace_divergence",
    "iter_session_steps",
    "iter_trace_divergences",
    "read_trace",
    "step_record_from_dict",
    "step_record_to_dict",
    "write_trace",
]
