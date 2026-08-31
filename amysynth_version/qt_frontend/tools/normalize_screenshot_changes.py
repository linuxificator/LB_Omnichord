#!/usr/bin/env python3
"""Ignore PNG byte churn when README screenshots are visually unchanged."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

from PySide6.QtGui import QImage


FRONTEND = Path(__file__).resolve().parents[1]
REPOSITORY = FRONTEND.parents[1]
DEFAULT_SCREENSHOTS = (
    FRONTEND / "screenshots" / "omni.png",
    FRONTEND / "screenshots" / "midi.png",
)
MAX_CHANGED_PIXELS = 16
MAX_CHANGED_FRACTION = 0.00001
MAX_CHANNEL_DELTA = 96


class PixelDifference(NamedTuple):
    total_pixels: int
    changed_pixels: int
    max_channel_delta: int


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


def pixel_difference(left: bytes, right: bytes) -> PixelDifference | None:
    try:
        left_pixels = image_pixels(left)
        right_pixels = image_pixels(right)
    except ValueError:
        return None
    if left_pixels[:3] != right_pixels[:3]:
        return None

    left_data = left_pixels[3]
    right_data = right_pixels[3]
    if len(left_data) != len(right_data):
        return None

    changed_pixels = 0
    max_delta = 0
    for offset in range(0, len(left_data), 4):
        channel_delta = max(
            abs(left_data[offset + channel] - right_data[offset + channel])
            for channel in range(4)
        )
        if channel_delta:
            changed_pixels += 1
            max_delta = max(max_delta, channel_delta)

    return PixelDifference(
        total_pixels=len(left_data) // 4,
        changed_pixels=changed_pixels,
        max_channel_delta=max_delta,
    )


def images_match(
    left: bytes,
    right: bytes,
    *,
    max_changed_pixels: int = MAX_CHANGED_PIXELS,
    max_changed_fraction: float = MAX_CHANGED_FRACTION,
    max_channel_delta: int = MAX_CHANNEL_DELTA,
) -> bool:
    if left == right:
        return True

    difference = pixel_difference(left, right)
    if difference is None:
        return False

    allowed_changed_pixels = min(
        max_changed_pixels,
        max(1, int(difference.total_pixels * max_changed_fraction)),
    )
    return (
        difference.changed_pixels <= allowed_changed_pixels
        and difference.max_channel_delta <= max_channel_delta
    )


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
            difference = pixel_difference(baseline, current)
            path.write_bytes(baseline)
            restored += 1
            if difference is None:
                print(f"Restored byte-stable screenshot for {path}")
            else:
                print(
                    "Restored pixel-equivalent screenshot for "
                    f"{path}: changed_pixels={difference.changed_pixels} "
                    f"max_delta={difference.max_channel_delta}"
                )
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
