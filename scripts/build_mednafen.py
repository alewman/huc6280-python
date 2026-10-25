"""Build Mednafen 1.32.1 (the pinned source) with the instruction-trace patch, headless-ready.

    python -I scripts/build_mednafen.py            # fetch, verify, patch, configure, build
    python -I scripts/mednafen_trace.py GAME.pce   # run it (see docs/mednafen-oracle.md)

Everything lands under reference/build/ (gitignored): the tarball (SHA-256 from
scripts/pinned_files.json), the unpacked tree, the binary. The patch is
``tools/mednafen-trace.patch`` (committed); the source tree and binary never are. Needs a C++
compiler, make and SDL2's development files (found on this machine); no sudo.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "reference" / "build"
TARBALL = BUILD / "mednafen-1.32.1.tar.xz"
TREE = BUILD / "mednafen-src"
PATCH = ROOT / "tools" / "mednafen-trace.patch"
BINARY = BUILD / "mednafen-bin" / "bin" / "mednafen"


def fetch() -> None:
    pin = next(
        e for e in json.loads((ROOT / "scripts" / "pinned_files.json").read_text())
        if e["path"].endswith("mednafen-1.32.1.tar.xz")
    )  # fmt: skip
    if not TARBALL.exists():
        BUILD.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(pin["url"], headers={"User-Agent": "huc6280-python"})
        TARBALL.write_bytes(urllib.request.urlopen(request).read())
    digest = hashlib.sha256(TARBALL.read_bytes()).hexdigest()
    if digest != pin["sha256"]:
        raise SystemExit(f"{TARBALL}: SHA-256 {digest} is not the pinned {pin['sha256']}")


def unpack() -> None:
    if TREE.exists():
        return
    with tarfile.open(TARBALL) as archive:
        archive.extractall(BUILD, filter="data")
    (BUILD / "mednafen").rename(TREE)


def patch() -> None:
    marker = TREE / ".trace-patched"
    if marker.exists():
        return
    subprocess.run(["patch", "-p1", "-i", str(PATCH)], cwd=TREE, check=True)
    marker.write_text("patched\n")


def build() -> None:
    if BINARY.exists() and BINARY.stat().st_mtime > PATCH.stat().st_mtime:
        return
    prefix = BINARY.parent.parent
    env = dict(os.environ)
    subprocess.run(
        ["./configure", f"--prefix={prefix}", "--enable-pce", "--disable-pce-fast",
         "--disable-apple2", "--disable-gb", "--disable-gba", "--disable-lynx", "--disable-md",
         "--disable-nes", "--disable-ngp", "--disable-pcfx", "--disable-psx", "--disable-sasplay",
         "--disable-sms", "--disable-snes", "--disable-snes-faust", "--disable-ss",
         "--disable-ssfplay", "--disable-vb", "--disable-wswan", "--disable-nls",
         "--disable-alsa", "--disable-jack", "--disable-debugger", "--without-libflac"],
        cwd=TREE, check=True, env=env,
    )  # fmt: skip
    subprocess.run(["make", f"-j{os.cpu_count() or 4}"], cwd=TREE, check=True, env=env)
    subprocess.run(["make", "install"], cwd=TREE, check=True, env=env)


def main() -> int:
    fetch()
    unpack()
    patch()
    build()
    print(f"built {BINARY}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
