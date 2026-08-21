from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class StaticContractTests(unittest.TestCase):
    def test_frontend_tree_contains_no_symlinks(self) -> None:
        symlinks = [
            str(path.relative_to(ROOT))
            for path in ROOT.rglob("*")
            if path.is_symlink()
        ]
        self.assertEqual(symlinks, [], f"unexpected symlinks: {symlinks}")

    def test_tuba_watermark_is_canonical_gui_asset(self) -> None:
        qml = (ROOT / "gui" / "InstrumentWatermarks.qml").read_text(
            encoding="utf-8"
        )
        png = ROOT / "gui" / "tuba_watermark.png"
        self.assertTrue(png.is_file())
        self.assertIn('source: "tuba_watermark.png"', qml)

    def test_parameter_slider_always_formats_numeric_value(self) -> None:
        qml = (ROOT / "gui" / "ParameterSlider.qml").read_text(
            encoding="utf-8"
        )
        self.assertIn("Number(slider.value).toFixed", qml)
        self.assertIn("from: Number(root.control.minimum)", qml)
        self.assertIn("to: Number(root.control.maximum)", qml)

    def test_catalogue_uses_physical_ranges_and_clean_labels(self) -> None:
        data = json.loads(
            (ROOT / "instruments" / "synths.json").read_text(
                encoding="utf-8"
            )
        )
        synths = data["synths"]
        self.assertEqual(len(synths), 123)
        for synth in synths:
            label = str(synth["label"])
            self.assertFalse(label.upper().endswith(" PATCH"), label)
            self.assertFalse(label.startswith("Juno "), label)
            self.assertFalse(label.startswith("DX7 "), label)
            for control in synth["controls"]:
                minimum = float(control["minimum"])
                maximum = float(control["maximum"])
                default = float(control["default"])
                self.assertGreaterEqual(minimum, 0.0, (synth["key"], control["key"]))
                self.assertLessEqual(minimum, default)
                self.assertLessEqual(default, maximum)
                if control["key"] == "sustain":
                    self.assertEqual(minimum, 0.0)
                    self.assertEqual(maximum, 1.0)


if __name__ == "__main__":
    unittest.main()
