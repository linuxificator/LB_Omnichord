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
        for name in ("omni.png", "midi.png"):
            helper.validate_screenshot(FRONTEND / "screenshots" / name)

    def test_blank_error_like_screenshot_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="omnichord-screenshot-") as raw:
            path = Path(raw) / "blank.png"
            image = QImage(1920, 850, QImage.Format.Format_RGBA8888)
            image.fill(QColor("#202020"))
            self.assertTrue(image.save(str(path), "PNG"))

            with self.assertRaisesRegex(RuntimeError, "visually sparse"):
                helper.validate_screenshot(path)


if __name__ == "__main__":
    unittest.main()
