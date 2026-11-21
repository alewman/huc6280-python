"""Rung 2: Dormann's 65C02 extended opcodes test, relocated, passes on the core.

The program is the research-tier judge (self-checking; written for the 65C02, not this chip). Three
facts are tested: the translation to ca65 reproduces Dormann's published binary byte for byte with
his own settings (so the relocation changes nothing else); the relocated program, with the changes
scripts/dormann_to_ca65.py documents, runs to its success trap on the core; and the same program
does trap when the core is made wrong in an opcode it tests. Skipped without cc65 or the source.
"""

import shutil
from pathlib import Path

import dormann
import pytest

PUBLISHED = (
    dormann.ROOT / "reference" / "src" / "dormann" / "bin_files" / "65C02_extended_opcodes_test.bin"
)

pytestmark = pytest.mark.skipif(
    not dormann.SOURCE.is_file() or not ((dormann.CC65 / "ca65").exists() or shutil.which("ca65")),
    reason="Dormann's source or cc65 missing: python -I scripts/fetch_references.py",
)


def test_translation_reproduces_the_published_binary(tmp_path: Path) -> None:
    image, _labels = dormann.build(tmp_path, original=True)
    published = PUBLISHED.read_bytes()
    assert len(image) == len(published) == 0x10000
    # Where the published image holds a zero the link leaves the fill ($FF) in bytes the source
    # reserves with ds but never writes; every byte of code and data is identical.
    different = [i for i in range(0x10000) if image[i] != published[i]]
    assert all(image[i] == 0xFF and published[i] == 0 for i in different)
    assert len(different) < 300


@pytest.fixture(scope="module")
def relocated() -> tuple[bytes, dict[str, int]]:
    return dormann.build()


@pytest.mark.slow
def test_relocated_test_reaches_its_success_trap(relocated: tuple[bytes, dict[str, int]]) -> None:
    image, labels = relocated
    result = dormann.run(image, labels)
    assert result.reason == "success", result
    assert result.instructions > 20_000_000


def test_a_wrong_incrementer_is_caught(relocated: tuple[bytes, dict[str, int]]) -> None:
    from huc6280._shifts import ShiftMixin

    original = ShiftMixin._inc
    ShiftMixin._inc = lambda self, value: self._set_nz((value + 2) & 0xFF)
    try:
        result = dormann.run(*relocated, limit=200_000)
    finally:
        ShiftMixin._inc = original
    assert result.reason == "trap"
