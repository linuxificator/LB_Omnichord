#!/usr/bin/env python3
"""Promote captured UI screenshots to release-tagged README assets."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path

from PySide6.QtGui import QImage


FRONTEND = Path(__file__).resolve().parents[1]
REPOSITORY = FRONTEND.parents[1]
SCREENSHOT_DIR = FRONTEND / "screenshots"
EXPECTED_SIZE = (1920, 850)
MIN_SAMPLED_COLORS = 128
SCREENS = {
    "omni": "LB Omnichord OMNI performance screen",
    "midi": "LB Omnichord MIDI performance screen",
}
RETAIN_RELEASES = 3


def relative(path: Path) -> str:
    return path.resolve().relative_to(REPOSITORY).as_posix()


def committed_bytes(path: Path) -> bytes | None:
    completed = subprocess.run(
        ["git", "-C", str(REPOSITORY), "show", f"HEAD:{relative(path)}"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout


def restore_committed_file(path: Path) -> None:
    baseline = committed_bytes(path)
    if baseline is not None:
        path.write_bytes(baseline)


def validate_screenshot(path: Path) -> None:
    image = QImage(str(path))
    if image.isNull():
        raise RuntimeError(f"{path} is not a readable PNG screenshot")
    size = (image.width(), image.height())
    if size != EXPECTED_SIZE:
        raise RuntimeError(
            f"{path} has size {size}, expected {EXPECTED_SIZE}"
        )

    sampled_colors: set[int] = set()
    for y in range(0, image.height(), 17):
        for x in range(0, image.width(), 19):
            sampled_colors.add(image.pixelColor(x, y).rgba())
    if len(sampled_colors) < MIN_SAMPLED_COLORS:
        raise RuntimeError(
            f"{path} looks too visually sparse to be the real UI "
            f"({len(sampled_colors)} sampled colors)"
        )


def update_readme(release_tag: str, targets: dict[str, Path]) -> None:
    readme = REPOSITORY / "README.md"
    text = readme.read_text(encoding="utf-8")
    for screen, alt_text in SCREENS.items():
        target = f"./{relative(targets[screen])}"
        pattern = re.compile(
            rf"!\[{re.escape(alt_text)}\]"
            r"\(\./amysynth_version/qt_frontend/screenshots/[^)]+\.png\)"
        )
        replacement = f"![{alt_text}]({target})"
        text, count = pattern.subn(replacement, text)
        if count != 1:
            raise RuntimeError(
                f"README.md should contain exactly one {screen} screenshot"
            )
    readme.write_text(text, encoding="utf-8")


def prune_release_screenshots(
    directory: Path = SCREENSHOT_DIR,
    *,
    retain: int = RETAIN_RELEASES,
) -> tuple[Path, ...]:
    if retain < 1:
        raise ValueError("at least one release screenshot must be retained")
    removed: list[Path] = []
    for screen in SCREENS:
        pattern = re.compile(rf"^{re.escape(screen)}-R[0-9]{{8}}T[0-9]{{6}}\.png$")
        releases = sorted(
            path for path in directory.iterdir() if pattern.fullmatch(path.name)
        )
        for obsolete in releases[:-retain]:
            obsolete.unlink()
            removed.append(obsolete)
    return tuple(removed)


def promote_screenshots(release_tag: str) -> None:
    if not re.fullmatch(r"R[0-9]{8}T[0-9]{6}", release_tag):
        raise RuntimeError(
            f"release tag {release_tag!r} must look like RYYYYMMDDTHHMMSS"
        )

    targets: dict[str, Path] = {}
    for screen in SCREENS:
        captured = SCREENSHOT_DIR / f"{screen}.png"
        validate_screenshot(captured)
        target = SCREENSHOT_DIR / f"{screen}-{release_tag}.png"
        shutil.copyfile(captured, target)
        validate_screenshot(target)
        targets[screen] = target
        restore_committed_file(captured)

    update_readme(release_tag, targets)
    prune_release_screenshots()


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--release-tag",
        required=True,
        help="Release tag to include in the README screenshot filenames.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    promote_screenshots(args.release_tag)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
