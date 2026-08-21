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
        self.assertIn("formattedValue", qml)
        self.assertIn("Math.log", qml)
        self.assertIn("Math.exp", qml)
        self.assertIn("midiNoteName", qml)

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
        self.assertIn('self._sync_synth_params(\n                    "chord",', amy_py)

        # Rhythm is now independent tagged lanes. Reintroducing the previous
        # whole-sequencer rebuild helpers would again make lane-local edits able
        # to interrupt drums/bass/chords together.
        self.assertIn("class _TaggedSequencerLane:", amy_py)
        self.assertIn("def _replace_lane(", amy_py)
        self.assertIn('self._replace_lane("bass")', amy_py)
        self.assertIn('self._replace_lane("chords")', amy_py)
        self.assertNotIn("def _prepare_rhythm_rebuild(", amy_py)
        self.assertNotIn("def _rebuild_rhythm(", amy_py)

        # These were the old parallel synth mutation/transport paths.
        for forbidden in (
            "class SynthRuntime",
            "values_by_synth",
            "collect_synth_parameter_overrides",
            "def _apply_synth_preset(",
            "def _send_synth_name(",
            "def _send_synth_params(",
        ):
            self.assertNotIn(forbidden, main_py, forbidden)

    def test_left_rail_has_no_rhythm_reset_and_uses_common_reset_labels(self) -> None:
        qml = (ROOT / "gui" / "Main.qml").read_text(encoding="utf-8")
        self.assertIn("property int leftRailWidth: 64", qml)
        self.assertNotIn("resetRhythmControlsToPreset", qml)
        self.assertNotIn('text: "RHY"', qml)
        self.assertNotIn('text: "BAS"', qml)
        self.assertNotIn('text: "STR"', qml)
        self.assertNotIn('text: "CHD"', qml)
        self.assertNotIn('text: "ROWS"', qml)
        self.assertGreaterEqual(qml.count('text: "RST"'), 4)

    def test_reverb_header_uses_wide_horizontal_sliders(self) -> None:
        panel = (ROOT / "gui" / "ReverbPanel.qml").read_text(encoding="utf-8")
        main = (ROOT / "gui" / "Main.qml").read_text(encoding="utf-8")
        self.assertIn("id: controlsRow", panel)
        self.assertEqual(panel.count("LabeledSlider {"), 3)
        self.assertNotIn("VerticalVolume {", panel)
        self.assertGreaterEqual(panel.count("width: 145"), 3)
        self.assertIn('label: "LEV"', panel)
        self.assertIn('label: "LIVE"', panel)
        self.assertIn('label: "DAMP"', panel)
        self.assertIn("width: 520", main)

    def test_rhythm_transport_icon_is_bound_directly_to_backend_state(self) -> None:
        qml = (ROOT / "gui" / "RhythmSection.qml").read_text(encoding="utf-8")
        self.assertIn('text: root.controller.rhythmRunning ? "■" : "▶"', qml)
        self.assertNotIn("Canvas {", qml)

    def test_each_musical_role_has_a_distinct_amy_bus(self) -> None:
        config = json.loads((ROOT / "config" / "amy_config.json").read_text(encoding="utf-8"))
        self.assertEqual(
            config["buses"],
            {"drums": 0, "bass": 1, "strum": 2, "chord": 3},
        )
        amy_py = (ROOT / "code" / "amy_serial.py").read_text(encoding="utf-8")
        self.assertIn('self.bus_id["strum"]', amy_py)
        self.assertIn('self.bus_id["chord"]', amy_py)
        self.assertIn('f"K{patch}i{synth}iv{voices}iy{bus}Z"', amy_py)
        self.assertIn("self._apply_reverb_bus(bus)", amy_py)

    def test_silent_factory_juno_patches_get_explicit_excitation(self) -> None:
        config = json.loads(
            (ROOT / "config" / "amy_config.json").read_text(encoding="utf-8")
        )
        compatibility = config["patch_compatibility"]
        for patch in ("57", "109"):
            self.assertGreater(
                float(compatibility[patch]["juno_noise_amp"]),
                0.0,
                patch,
            )
        self.assertEqual(
            compatibility["109"]["label"],
            "Juno B66 Toy Rhodes",
        )


if __name__ == "__main__":
    unittest.main()
