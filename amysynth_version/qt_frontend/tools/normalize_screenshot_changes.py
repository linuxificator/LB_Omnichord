#!/usr/bin/env python3
"""Ignore PNG byte churn when README screenshots are visually unchanged."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from PySide6.QtGui import QImage


FRONTEND = Path(__file__).resolve().parents[1]
REPOSITORY = FRONTEND.parents[1]
DEFAULT_SCREENSHOTS = (
    FRONTEND / "screenshots" / "omni.png",
    FRONTEND / "screenshots" / "midi.png",
)


def image_pixels(image_bytes: bytes) -> tuple[int, int, int, bytes]:
    image = QImage()
    if not image.loadFromData(image_bytes, "PNG"):
        raise ValueError("not a readable PNG image")
    image = image.convertToFormat(QImage.Format.Format_RGBA8888)
    return (
        image.width(),
        image.height(),
        image.bytesPerLine(),
        image.constBits().tobytes(),
    )


def images_match(left: bytes, right: bytes) -> bool:
    try:
        return image_pixels(left) == image_pixels(right)
    except ValueError:
        return False


def committed_bytes(path: Path) -> bytes | None:
    relative = path.resolve().relative_to(REPOSITORY).as_posix()
    completed = subprocess.run(
        ["git", "-C", str(REPOSITORY), "show", f"HEAD:{relative}"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout


def normalize(paths: tuple[Path, ...]) -> int:
    restored = 0
    for path in paths:
        path = path.expanduser().resolve()
        baseline = committed_bytes(path)
        if baseline is None:
            continue
        current = path.read_bytes()
        if current != baseline and images_match(baseline, current):
            path.write_bytes(baseline)
            restored += 1
            print(f"Restored byte-stable screenshot for {path}")
    return restored


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "screenshots",
        nargs="*",
        type=Path,
        default=DEFAULT_SCREENSHOTS,
        help="Screenshot paths to normalize.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    normalize(tuple(args.screenshots))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
