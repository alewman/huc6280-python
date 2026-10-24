#!/usr/bin/env python3
"""Build the referee material from what scripts/fetch_references.py fetched.

Everything lands under reference/build/ (gitignored); nothing needs sudo. Each
step is skipped when its output already exists.

- ``oss``: unpack the oss-cad-suite bundle into reference/build/oss-cad-suite
  (GHDL 7.0.0-dev). The bundle is a 750 MB ``tool`` pin; fetch it with
  ``scripts/fetch_references.py`` (without ``--no-tools``) first, or point
  ``--oss`` at a bundle already unpacked elsewhere (read only).
- ``huc6280-vhdl``: analyse srg320's HuC6280 VHDL (reference/src/
  TurboGrafx16_MiSTer/rtl/HUC6280) with GHDL into reference/build/huc6280-vhdl,
  in dependency order. ``HUC6280_CPU`` has the MMU inside (``A_OUT`` is 21
  bits), the T flag, block transfers, and three interrupt inputs; ``psg.vhd``
  and the top-level wrapper ``HUC6280.vhd`` are not analysed (the PSG is the
  board's). Hand-written HDL, not die-traced: emulator tier. This step only proves it analyses.
- ``huc6280-tb``: analyse the same units with tests/huc6280_vhdl/tb_huc6280.vhd (GHDL's LLVM
  back end, -O2) and elaborate the rung 5 testbench executable into reference/build/huc6280-tb.

    python -I scripts/build_referees.py                  # all steps
    python -I scripts/build_referees.py huc6280-vhdl --oss /path/to/oss-cad-suite
    python -I scripts/build_referees.py huc6280-tb --oss /path/to/oss-cad-suite   # the rung 5 testbench
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "reference" / "build"
SRC = ROOT / "reference" / "src"
RTL = SRC / "TurboGrafx16_MiSTer" / "rtl" / "HUC6280"
# The order the units depend on each other (HUC6280.qip lists them differently).
UNITS = ("HUC6280_PKG", "AddSubBCD", "HUC6280_ALU", "HUC6280_AG", "HUC6280_MC", "HUC6280_CPU")


def oss_dir(given: Path | None) -> Path:
    return given if given else BUILD / "oss-cad-suite"


def step_oss(given: Path | None) -> None:
    target = oss_dir(given)
    if (target / "bin" / "ghdl").exists():
        return
    archive = BUILD / "oss-cad-suite-linux-x64-20261005.tgz"
    with tarfile.open(archive) as bundle:
        bundle.extractall(BUILD, filter="tar")


def step_vhdl(given: Path | None) -> None:
    work = BUILD / "huc6280-vhdl"
    if (work / "work-obj08.cf").exists():
        return
    step_oss(given)
    work.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PATH"] = f"{oss_dir(given) / 'bin'}:{env['PATH']}"
    for unit in UNITS:
        subprocess.run(
            ["ghdl", "-a", "--std=08", "-fsynopsys", str(RTL / f"{unit}.vhd")],
            cwd=work, env=env, check=True,
        )  # fmt: skip
    print(f"analysed {len(UNITS)} units into {work}")


def step_vhdl_tb(given: Path | None) -> None:
    work = BUILD / "huc6280-tb"
    bench = ROOT / "tests" / "huc6280_vhdl" / "tb_huc6280.vhd"
    executable = work / "tb_huc6280"
    if executable.exists() and executable.stat().st_mtime > bench.stat().st_mtime:
        return
    step_oss(given)
    work.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PATH"] = f"{oss_dir(given) / 'bin'}:{env['PATH']}"
    sources = [RTL / f"{unit}.vhd" for unit in UNITS] + [bench]
    for source in sources:
        subprocess.run(
            ["ghdl", "-a", "--std=08", "-fsynopsys", "-O2", str(source)],
            cwd=work, env=env, check=True,
        )  # fmt: skip
    subprocess.run(
        ["ghdl", "-e", "--std=08", "-fsynopsys", "tb_huc6280"], cwd=work, env=env, check=True
    )
    print(f"built {executable}")


STEPS = {"oss": step_oss, "huc6280-vhdl": step_vhdl, "huc6280-tb": step_vhdl_tb}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("steps", nargs="*", metavar="STEP", help=f"any of {', '.join(STEPS)}")
    parser.add_argument("--oss", type=Path, help="an unpacked oss-cad-suite to use (read only)")
    args = parser.parse_args()
    unknown = set(args.steps) - set(STEPS)
    if unknown:
        parser.error(f"unknown step(s): {', '.join(sorted(unknown))}")
    for name in args.steps or STEPS:
        STEPS[name](args.oss)
    return 0


if __name__ == "__main__":
    sys.exit(main())
