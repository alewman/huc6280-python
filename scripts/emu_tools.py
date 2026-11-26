# SPDX-License-Identifier: MIT
"""Find a family tool at its documented path (emu-tools docs/contract.md, section 5).

One variable per tool repository (Aubrey, 2026-11-24): ``EMU_TOOLS`` (MIT emu-tools),
``EMU_TOOLS_GPL`` (emu-tools-gpl) and ``EMU_TOOLS_GPL2`` (emu-tools-gpl2, GPL-2.0-only). Each
tool sits at a fixed path under its repository, listed in that repository's
``tools/README.md``. The tools are separate programs or files applied to a fetched upstream;
nothing here imports them.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

#: Mednafen 1.32.1 with the instruction-trace patch (GPL-2.0-only, so in emu-tools-gpl2): its
#: build script and the program it builds (since 2026-11-25; the patch alone until then).
MEDNAFEN_BUILD = ("EMU_TOOLS_GPL2", "tools/mednafen/build.py")
MEDNAFEN_PCE = ("EMU_TOOLS_GPL2", "tools/mednafen/build/pce/bin/mednafen")
#: The testbenches for srg320's HUC6280 VHDL (not regrouped yet).
TB_HUC6280 = ("EMU_TOOLS_GPL", "tools/huc6280-python/huc6280_vhdl/tb_huc6280.vhd")
TB_VANISH = ("EMU_TOOLS_GPL", "tools/huc6280-python/huc6280_vhdl/tb_vanish.vhd")
#: The C16 and C18 probe's Mesen2 driver (a shim over mesen2-runner), run by hand.
VANISH_PROBE = ("EMU_TOOLS_GPL", "tools/huc6280-python/vanish_probe.py")


def find(tool: tuple[str, str]) -> Path | None:
    """The tool's path, or None when its variable is unset or the file is absent."""
    var, rel = tool
    root = os.environ.get(var)
    if not root:
        return None
    path = Path(root) / rel
    return path if path.exists() else None


def require(tool: tuple[str, str]) -> Path:
    """The tool's path; exit status 3 (a missing input, as the contract says) without it."""
    path = find(tool)
    if path is None:
        print(why_missing(tool), file=sys.stderr)
        sys.exit(3)
    return path


def why_missing(tool: tuple[str, str]) -> str:
    """The message (and test skip reason) naming the variable and the path expected."""
    return f"${tool[0]}/{tool[1]} not found: set {tool[0]} (emu-tools docs/contract.md, section 5)"
