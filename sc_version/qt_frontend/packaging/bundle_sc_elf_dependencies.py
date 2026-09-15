#!/usr/bin/env python3
"""Copy non-platform ELF dependencies into one headless SC runtime prefix."""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path
import re
import shutil
import subprocess


LDD_LINE = re.compile(r"^\s*(?P<name>\S+)\s+=>\s+(?P<path>/\S+)\s+\(")
PLATFORM_LIBRARIES = {
    "ld-linux-aarch64.so.1",
    "ld-linux-x86-64.so.2",
    "libc.so.6",
    "libdl.so.2",
    "libgcc_s.so.1",
    "libjack.so.0",
    "libm.so.6",
    "libpthread.so.0",
    "librt.so.1",
}


def is_elf(path: Path) -> bool:
    try:
        if not path.is_file():
            return False
        with path.open("rb") as stream:
            return stream.read(4) == b"\x7fELF"
    except OSError:
        return False


def dependencies(path: Path) -> tuple[Path, ...]:
    result = subprocess.run(
        ["ldd", str(path)],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ldd failed for {path}: {result.stderr.strip()}")
    if "not found" in result.stdout:
        raise RuntimeError(f"unresolved dependency for {path}: {result.stdout}")
    return tuple(
        Path(match.group("path"))
        for line in result.stdout.splitlines()
        if (match := LDD_LINE.match(line)) is not None
        and match.group("name") not in PLATFORM_LIBRARIES
    )


def bundle(prefix: Path) -> tuple[Path, ...]:
    library_dir = prefix / "lib"
    library_dir.mkdir(parents=True, exist_ok=True)
    roots = [
        prefix / "bin" / "sclang",
        prefix / "bin" / "scsynth",
        prefix / "bin" / "supernova",
    ]
    roots.extend((library_dir / "SuperCollider" / "plugins").glob("*.so"))
    queue = deque(path for path in roots if is_elf(path))
    visited: set[Path] = set()
    copied: list[Path] = []
    while queue:
        binary = queue.popleft().resolve()
        if binary in visited:
            continue
        visited.add(binary)
        for source in dependencies(binary):
            destination = library_dir / source.name
            if not destination.exists():
                shutil.copy2(source, destination, follow_symlinks=True)
                copied.append(destination)
            if is_elf(destination) and destination.resolve() not in visited:
                queue.append(destination)
    return tuple(sorted(copied))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prefix", type=Path)
    args = parser.parse_args()
    copied = bundle(args.prefix.resolve())
    for path in copied:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
