#!/usr/bin/env python3
"""Shared implementation for the portable ESP32-P4 release flashers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys


def _option(name: str, *, modern: bool) -> str:
    separator = "-" if modern else "_"
    return "--" + name.replace("_", separator)


def build_command(
    *,
    package_root: Path,
    profile: str,
    port: str,
    baud: int,
    modern: bool,
) -> tuple[list[str], Path]:
    profile_dir = (package_root / profile).resolve()
    metadata_path = profile_dir / "flasher_args.json"
    if not metadata_path.is_file():
        raise SystemExit(f"firmware metadata is missing: {metadata_path}")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    flash_files = metadata.get("flash_files")
    if not isinstance(flash_files, dict) or not flash_files:
        raise SystemExit(f"invalid flash_files in {metadata_path}")

    operation = "write-flash" if modern else "write_flash"
    command = [
        sys.executable,
        "-m",
        "esptool",
        "--chip",
        "esp32p4",
        "--port",
        port,
        "--baud",
        str(baud),
        operation,
    ]

    settings = metadata.get("flash_settings", {})
    for name in ("flash_mode", "flash_freq", "flash_size"):
        value = settings.get(name)
        if value is not None:
            command.extend((_option(name, modern=modern), str(value)))

    for address, relative_name in sorted(
        flash_files.items(), key=lambda item: int(item[0], 0)
    ):
        relative_path = Path(relative_name)
        image_path = (profile_dir / relative_path).resolve()
        if profile_dir not in image_path.parents or not image_path.is_file():
            raise SystemExit(f"firmware image is missing or unsafe: {relative_name}")
        command.extend((address, relative_path.as_posix()))

    return command, profile_dir


def main(*, modern: bool) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Flash an LB Omnichord ESP32-P4 release image using "
            + ("esptool 5 or newer" if modern else "esptool 4 or older")
        )
    )
    parser.add_argument("profile", choices=("v1", "v3"))
    parser.add_argument("port", help="serial device, for example /dev/ttyACM0")
    parser.add_argument("--baud", type=int, default=921600)
    parser.add_argument(
        "--package-root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate the package and print the command without flashing",
    )
    args = parser.parse_args()

    command, working_directory = build_command(
        package_root=args.package_root,
        profile=args.profile,
        port=args.port,
        baud=args.baud,
        modern=modern,
    )
    print(shlex.join(command))
    if args.dry_run:
        return 0
    return subprocess.run(command, cwd=working_directory, check=False).returncode
