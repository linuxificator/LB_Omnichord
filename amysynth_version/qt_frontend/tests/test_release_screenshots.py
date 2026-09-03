from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

from PySide6.QtGui import QColor, QImage


FRONTEND = Path(__file__).resolve().parents[1]
HELPER_PATH = FRONTEND / "tools" / "update_release_screenshots.py"

spec = importlib.util.spec_from_file_location(
    "update_release_screenshots",
    HELPER_PATH,
)
assert spec is not None
helper = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(helper)


class ReleaseScreenshotTests(unittest.TestCase):
    def test_current_readme_screenshots_pass_the_release_sanity_check(self) -> None:
        for name in (
            "omni.png",
            "midi.png",
            "osc-omni.png",
            "osc-midi.png",
        ):
            helper.validate_screenshot(FRONTEND / "screenshots" / name)

    def test_blank_error_like_screenshot_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="omnichord-screenshot-") as raw:
            path = Path(raw) / "blank.png"
            image = QImage(1920, 850, QImage.Format.Format_RGBA8888)
            image.fill(QColor("#202020"))
            self.assertTrue(image.save(str(path), "PNG"))

            with self.assertRaisesRegex(RuntimeError, "visually sparse"):
                helper.validate_screenshot(path)

    def test_retention_keeps_three_latest_tagged_images_per_screen(self) -> None:
        with tempfile.TemporaryDirectory(prefix="omnichord-screenshots-") as raw:
            directory = Path(raw)
            tags = (
                "R20260828T010101",
                "R20260829T010101",
                "R20260830T010101",
                "R20260831T010101",
            )
            for screen in ("omni", "midi"):
                for tag in tags:
                    (directory / f"{screen}-{tag}.png").write_bytes(tag.encode())
                (directory / f"{screen}.png").write_bytes(b"capture")
            unrelated = directory / "notes.png"
            unrelated.write_bytes(b"unrelated")

            removed = helper.prune_release_screenshots(directory)

            self.assertEqual(len(removed), 2)
            self.assertFalse(
                (directory / f"omni-{tags[0]}.png").exists()
            )
            self.assertFalse(
                (directory / f"midi-{tags[0]}.png").exists()
            )
            for screen in ("omni", "midi"):
                self.assertTrue((directory / f"{screen}.png").exists())
                for tag in tags[1:]:
                    self.assertTrue((directory / f"{screen}-{tag}.png").exists())
            self.assertTrue(unrelated.exists())


if __name__ == "__main__":
    unittest.main()
