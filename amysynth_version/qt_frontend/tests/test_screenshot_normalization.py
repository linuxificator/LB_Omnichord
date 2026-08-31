from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

from PySide6.QtCore import QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QColor, QImage


FRONTEND = Path(__file__).resolve().parents[1]
HELPER_PATH = FRONTEND / "tools" / "normalize_screenshot_changes.py"

spec = importlib.util.spec_from_file_location(
    "normalize_screenshot_changes",
    HELPER_PATH,
)
assert spec is not None
helper = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(helper)


def png_bytes(color: str) -> bytes:
    image = QImage(4, 4, QImage.Format.Format_RGBA8888)
    image.fill(QColor(color))
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "PNG")
    return bytes(data)


class ScreenshotNormalizationTests(unittest.TestCase):
    def test_trailing_png_byte_churn_keeps_the_same_pixels(self) -> None:
        baseline = png_bytes("#123456")

        self.assertNotEqual(baseline, baseline + b"ignored-churn")
        self.assertTrue(helper.images_match(baseline, baseline + b"ignored-churn"))

    def test_real_pixel_changes_do_not_match(self) -> None:
        self.assertFalse(
            helper.images_match(
                png_bytes("#123456"),
                png_bytes("#654321"),
            )
        )


if __name__ == "__main__":
    unittest.main()
