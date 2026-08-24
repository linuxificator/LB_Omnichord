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
        entry_py = (ROOT / "code" / "main.py").read_text(encoding="utf-8")
        core_py = (ROOT / "code" / "app_core.py").read_text(encoding="utf-8")
        perf_py = (ROOT / "code" / "performance_backend.py").read_text(
            encoding="utf-8"
        )
        public_amy_py = (ROOT / "code" / "amy_serial.py").read_text(
            encoding="utf-8"
        )
        transport_py = (ROOT / "code" / "amy_transport.py").read_text(
            encoding="utf-8"
        )
        state_py = (ROOT / "code" / "synth_state.py").read_text(encoding="utf-8")

        self.assertIn("class SynthState:", state_py)
        self.assertIn("from synth_state import SynthState", core_py)
        self.assertIn("self._runtime(role).load_preset(role_data)", core_py)
        self.assertIn("runtime.set_control(key, value)", core_py)
        self.assertIn("self._runtime(role).transport_payload()", core_py)
        self.assertIn("from midi_integration import InstrumentBackend", entry_py)
        self.assertIn("class InstrumentBackend(app_core.InstrumentBackend):", perf_py)

        # The public transport facade owns configuration/program selection; the
        # stable protocol implementation remains independently inspectable.
        self.assertIn("from config_loader import load_amy_config", public_amy_py)
        self.assertNotIn("DEFAULT_CONFIG: dict", public_amy_py)
        self.assertIn("ProgramAmySerialClient as AmySerialClient", public_amy_py)
        self.assertIn("def _apply_synth_state(", transport_py)
        self.assertIn("self._apply_synth_state(\n            role,", transport_py)
        self.assertIn('self._sync_synth_params(\n                    "chord",', transport_py)

        # Rhythm is now independent tagged lanes. Reintroducing the previous
        # whole-sequencer rebuild helpers would again make lane-local edits able
        # to interrupt drums/bass/chords together.
        self.assertIn("class _TaggedSequencerLane:", transport_py)
        self.assertIn("def _replace_lane(", transport_py)
        self.assertIn('self._replace_lane("bass")', transport_py)
        self.assertIn('self._replace_lane("chords")', transport_py)
        self.assertNotIn("def _prepare_rhythm_rebuild(", transport_py)
        self.assertNotIn("def _rebuild_rhythm(", transport_py)

        for forbidden in (
            "class SynthRuntime",
            "values_by_synth",
            "collect_synth_parameter_overrides",
            "def _apply_synth_preset(",
            "def _send_synth_name(",
            "def _send_synth_params(",
        ):
            self.assertNotIn(forbidden, core_py, forbidden)

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

    def test_chord_gate_and_grouped_row_roll_controls_are_present(self) -> None:
        qml = (ROOT / "gui" / "Main.qml").read_text(encoding="utf-8")
        self.assertIn("text: backend.chordGateButtonText", qml)
        self.assertIn("enabled: backend.chordGateState !== 0", qml)
        self.assertIn("backend.toggleChordGate()", qml)
        self.assertIn("backend.rollChordRows(-1)", qml)
        self.assertIn("backend.rollChordRows(1)", qml)

    def test_bass_activity_has_adjacent_voicing_slider(self) -> None:
        qml = (ROOT / "gui" / "RhythmSection.qml").read_text(encoding="utf-8")
        self.assertIn('label: "bass activity"', qml)
        self.assertIn('label: "bass voicing"', qml)
        self.assertIn("fromValue: -6", qml)
        self.assertIn("toValue: 6", qml)
        self.assertIn("stepValue: 1", qml)
        self.assertIn("root.controller.bassVoicingShift", qml)
        self.assertIn(".setBassVoicingShift(value)", qml)

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

        midi_integration = (
            ROOT / "code" / "midi_integration.py"
        ).read_text(encoding="utf-8")
        self.assertIn("@Property(QObject, constant=True)", midi_integration)

    def test_rainbow_mode_button_text_is_large_and_centered(self) -> None:
        qml = (ROOT / "gui" / "RainbowModeButton.qml").read_text(
            encoding="utf-8"
        )
        self.assertIn("font.pixelSize: height * 0.55", qml)
        self.assertIn(
            "anchors.horizontalCenterOffset: root.extensionWidth / 2",
            qml,
        )
        self.assertIn("horizontalAlignment: Text.AlignHCenter", qml)
        self.assertIn("verticalAlignment: Text.AlignVCenter", qml)

    def test_rhythm_transport_icon_is_bound_directly_to_backend_state(self) -> None:
        qml = (ROOT / "gui" / "RhythmSection.qml").read_text(encoding="utf-8")
        self.assertIn('text: root.controller.rhythmRunning ? "■" : "▶"', qml)
        self.assertNotIn("Canvas {", qml)

    def test_each_musical_role_has_a_distinct_amy_bus(self) -> None:
        config = json.loads((ROOT / "config" / "amy_config.json").read_text(encoding="utf-8"))
        self.assertEqual(
            config["buses"],
            {
                "drums": 0,
                "bass": 1,
                "strum": 2,
                "chord": 3,
                "midi_rows": [4, 5, 6, 7, 8, 9],
                "midi_drums": 10,
            },
        )
        self.assertGreaterEqual(config["amy_max_buses"], 11)
        transport_py = (ROOT / "code" / "amy_transport.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('self.bus_id["strum"]', transport_py)
        self.assertIn('self.bus_id["chord"]', transport_py)
        self.assertIn('f"K{patch}i{synth}iv{voices}iy{bus}Z"', transport_py)
        self.assertIn("self._apply_reverb_bus(bus)", transport_py)

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
