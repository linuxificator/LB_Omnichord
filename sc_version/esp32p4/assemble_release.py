#!/usr/bin/env python3
"""Assemble both ESP32-P4 ABI profiles into one versioned release ZIP."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re
import zipfile


HELPERS = (
    "release_flash_common.py",
    "flash_esptool_v4.py",
    "flash_esptool_v5.py",
    "RELEASE_FLASHING.md",
)
REQUIRED_PROFILE_FILES = (
    "BUILD_INFO",
    "flasher_args.json",
    "amy_p4_test.bin",
    "bootloader/bootloader.bin",
    "partition_table/partition-table.bin",
)


def assemble(*, release_name: str, v1: Path, v3: Path, output_dir: Path) -> Path:
    if re.fullmatch(r"R[0-9]{8}T[0-9]{6}", release_name) is None:
        raise ValueError(f"invalid release name: {release_name}")

    source_root = Path(__file__).resolve().parent
    profiles = {"v1": v1.resolve(), "v3": v3.resolve()}
    for profile, directory in profiles.items():
        for relative in REQUIRED_PROFILE_FILES:
            if not (directory / relative).is_file():
                raise FileNotFoundError(f"{profile} package is missing {relative}")
    for helper in HELPERS:
        if not (source_root / helper).is_file():
            raise FileNotFoundError(f"release helper is missing: {helper}")

    output_dir.mkdir(parents=True, exist_ok=True)
    release_root = f"LB_Omnichord.{release_name}.ESP32P4"
    archive = output_dir / f"{release_root}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for helper in HELPERS:
            bundle.write(source_root / helper, f"{release_root}/{helper}")
        for profile, directory in profiles.items():
            files = sorted(
                candidate for candidate in directory.rglob("*") if candidate.is_file()
            )
            for path in files:
                relative = path.relative_to(directory)
                bundle.write(path, f"{release_root}/{profile}/{relative.as_posix()}")

    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(archive.suffix + ".sha256").write_text(
        f"{digest}  {archive.name}\n", encoding="utf-8"
    )
    return archive


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-name", required=True)
    parser.add_argument("--v1", required=True, type=Path)
    parser.add_argument("--v3", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    print(
        assemble(
            release_name=args.release_name,
            v1=args.v1,
            v3=args.v3,
            output_dir=args.output_dir,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
