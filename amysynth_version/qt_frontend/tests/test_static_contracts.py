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

    def test_synth_state_has_one_frontend_and_one_receiver_path(self) -> None:
        main_py = (ROOT / "code" / "main.py").read_text(encoding="utf-8")
        amy_py = (ROOT / "code" / "amy_serial.py").read_text(encoding="utf-8")
        state_py = (ROOT / "code" / "synth_state.py").read_text(encoding="utf-8")

        self.assertIn("class SynthState:", state_py)
        self.assertIn("from synth_state import SynthState", main_py)
        self.assertIn("self._runtime(role).load_preset(role_data)", main_py)
        self.assertIn("runtime.set_control(key, value)", main_py)
        self.assertIn("self._runtime(role).transport_payload()", main_py)
        self.assertIn("def _apply_synth_state(", amy_py)
        self.assertIn("self._apply_synth_state(\n            role,", amy_py)
        self.assertIn("resync_chord=True", amy_py)
        self.assertIn('self._sync_synth_params(\n                "chord",', amy_py)

        # These were the old parallel mutation/transport paths. Reintroducing
        # them would make startup/preset/UI behavior capable of diverging again.
        for forbidden in (
            "class SynthRuntime",
            "values_by_synth",
            "collect_synth_parameter_overrides",
            "def _apply_synth_preset(",
            "def _send_synth_name(",
            "def _send_synth_params(",
        ):
            self.assertNotIn(forbidden, main_py, forbidden)


if __name__ == "__main__":
    unittest.main()
