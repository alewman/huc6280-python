# SPDX-License-Identifier: MIT
"""Build the traced Mednafen 1.32.1, which lives outside this repository (emu-tools-gpl2).

    python -I scripts/build_mednafen.py    # runs $EMU_TOOLS_GPL2/tools/mednafen/build.py --machine pce

Since 2026-11-25 (decisions page T3) the build, its pinned tarball and the instruction-trace
patch are all in emu-tools-gpl2's ``tools/mednafen`` (GPL-2.0-only), and the program lands at
``$EMU_TOOLS_GPL2/tools/mednafen/build/pce/bin/mednafen``, where scripts/mednafen_trace.py runs
it. This script only runs that tool's build as a separate program (emu-tools docs/contract.md,
section 5): exit status 3, naming the variable, when ``EMU_TOOLS_GPL2`` is unset. Nothing of
Mednafen is fetched, kept or built in this checkout any more. Needs a C++ compiler, make and
SDL2's development files; no sudo.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import emu_tools


def main() -> int:
    build = emu_tools.require(emu_tools.MEDNAFEN_BUILD)
    done = subprocess.run([sys.executable, "-I", str(build), "--machine", "pce"], check=False)
    return done.returncode


if __name__ == "__main__":
    sys.exit(main())
