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


def png_bytes(
    color: str,
    *,
    size: tuple[int, int] = (4, 4),
    changed: tuple[tuple[int, int, str], ...] = (),
) -> bytes:
    image = QImage(size[0], size[1], QImage.Format.Format_RGBA8888)
    image.fill(QColor(color))
    for x, y, pixel_color in changed:
        image.setPixelColor(x, y, QColor(pixel_color))
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

    def test_sparse_capture_jitter_matches_within_tolerance(self) -> None:
        baseline = png_bytes("#123456", size=(100, 100))
        current = png_bytes(
            "#123456",
            size=(100, 100),
            changed=(
                (20, 40, "#123457"),
                (20, 41, "#123457"),
                (20, 42, "#123457"),
                (20, 43, "#123457"),
            ),
        )

        self.assertTrue(
            helper.images_match(
                baseline,
                current,
                max_changed_pixels=16,
                max_changed_fraction=1.0,
                max_channel_delta=96,
            )
        )


if __name__ == "__main__":
    unittest.main()
