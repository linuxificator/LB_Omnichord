from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class StaticContractTests(unittest.TestCase):
    def test_codex_startup_reading_routes_existing_design_contracts(self) -> None:
        repository = ROOT.parents[1]
        agents_path = repository / "AGENTS.md"
        design_root = ROOT.parent / "design"
        design_index_path = design_root / "README.md"

        agents = agents_path.read_text(encoding="utf-8")
        design_index = design_index_path.read_text(encoding="utf-8")
        self.assertIn("## Required Codex startup reading", agents)
        self.assertIn("amysynth_version/README.md", agents)
        self.assertIn("amysynth_version/design/README.md", agents)
        self.assertIn("task-routing table", agents)

        required_design_files = (
            "principles.md",
            "architecture.md",
            "behavior.md",
            "testing.md",
            "gui.md",
            "ui_behavior_reference.md",
            "midi.md",
            "midi_control.md",
            "presets.md",
            "sound_balance.md",
            "rhythm_bahavior.md",
            "tuning.md",
            "use_cases.md",
            "amy_interface.md",
            "unclear.md",
        )
        for name in required_design_files:
            self.assertTrue((design_root / name).is_file(), name)
            self.assertIn(name, design_index)

        required_frontend_contracts = (
            ROOT.parent / "README.md",
            ROOT / "docs" / "CONTROL_SAFETY.md",
            ROOT / "docs" / "SEQUENCER_TAGS.md",
            ROOT / "docs" / "WSL_APPIMAGE_TESTING.md",
            ROOT / "tests" / "USE_CASES.md",
            ROOT / "instruments" / "README_defaults.md",
            ROOT.parent / "esp32p4" / "README.md",
            ROOT.parent / "esp32p4" / "CI_FLASH.md",
        )
        for path in required_frontend_contracts:
            self.assertTrue(path.is_file(), str(path))
        self.assertIn("WSL_APPIMAGE_TESTING.md", design_index)

    def test_public_readme_uses_current_amy_and_qt_screenshots(self) -> None:
        repository = ROOT.parents[1]
        public_readme = (repository / "README.md").read_text(encoding="utf-8")
        frontend_readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("https://github.com/linuxificator/amy", public_readme)
        self.assertIn("https://github.com/shorepine/amy", public_readme)
        self.assertIn("`screenshots/`", frontend_readme)
        for name in ("omni.png", "midi.png"):
            relative = f"amysynth_version/qt_frontend/screenshots/{name}"
            self.assertIn(relative, public_readme)
            self.assertTrue((repository / relative).is_file(), relative)

    def test_midi_qml_uses_its_own_bindable_metaobject(self) -> None:
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("PySide6>=6.6", requirements)
        screen = (ROOT / "gui" / "MidiScreen.qml").read_text(encoding="utf-8")
        synth = (ROOT / "gui" / "MidiSynthSection.qml").read_text(
            encoding="utf-8"
        )
        utility = (ROOT / "gui" / "MidiUtilitySection.qml").read_text(
            encoding="utf-8"
        )
        self.assertIn("controller: backend.midiPlayer", screen)
        self.assertIn("root.controller.stateVersion", synth)
        self.assertIn("root.controller.tuningModeIndex", utility)
        self.assertNotIn("root.controller.midiStateVersion", synth)

    def test_local_launcher_validates_but_never_builds_amy(self) -> None:
        launcher = (ROOT / "run_local.sh").read_text(encoding="utf-8")
        self.assertIn("import c_amy", launcher)
        self.assertIn("gamma9001|amy_set_gamma", launcher)
        self.assertNotIn('"$frontend_dir/prepare_local_amy.sh"', launcher)
        self.assertNotIn("pip install", launcher)
        self.assertLess(
            launcher.index("gamma9001|amy_set_gamma"),
            launcher.index("code/local_amy_service.py"),
        )

    def test_midi_cc_bar_clears_omni_button_and_aligns_to_sections(self) -> None:
        qml = (ROOT / "gui" / "MidiScreen.qml").read_text(encoding="utf-8")
        self.assertIn("id: omniButton", qml)
        self.assertIn("+ omniButton.width", qml)
        self.assertIn("+ omniButton.extensionWidth", qml)
        self.assertIn("+ root.hostWindow.controlSpacing", qml)
        self.assertIn("root.hostWindow.volumeX", qml)
        self.assertIn("+ root.hostWindow.volumeWidth", qml)

    def test_every_numeric_control_family_supports_midi_learn(self) -> None:
        parameter = (ROOT / "gui" / "ParameterSlider.qml").read_text(
            encoding="utf-8"
        )
        labeled = (ROOT / "gui" / "LabeledSlider.qml").read_text(
            encoding="utf-8"
        )
        volume = (ROOT / "gui" / "VerticalVolume.qml").read_text(
            encoding="utf-8"
        )
        tuning = (ROOT / "gui" / "TapNumber.qml").read_text(
            encoding="utf-8"
        )
        for component in (parameter, labeled, volume, tuning):
            self.assertIn("activateControlTarget", component)
            self.assertIn("controlTargetTapped", component)
            self.assertIn("midiBound", component)
            self.assertIn('"#35b85a"', component)
            self.assertIn("midiBindingGesture", component)

        self.assertIn("controlTargetMoved", parameter)
        self.assertIn("controlTargetMoved", labeled)
        self.assertIn("if (root.midiBindingGesture)", parameter)
        self.assertIn("if (root.midiBindingGesture)", labeled)

        combined = "\n".join(
            (ROOT / "gui" / name).read_text(encoding="utf-8")
            for name in (
                "Main.qml",
                "MidiSynthSection.qml",
                "SynthSection.qml",
                "ReverbPanel.qml",
                "UtilitySection.qml",
                "MidiUtilitySection.qml",
                "RhythmSection.qml",
            )
        )
        for kind in (
            "synth_control",
            "volume",
            "reverb_level",
            "reverb_liveness",
            "reverb_damping",
            "tuning_reference",
            "rhythm_tempo",
            "bass_voicing",
        ):
            self.assertIn(f'"kind": "{kind}"', combined)

    def test_midi_and_omni_control_led_states_are_rendered(self) -> None:
        midi = (ROOT / "gui" / "MidiScreen.qml").read_text(encoding="utf-8")
        omni = (ROOT / "gui" / "Main.qml").read_text(encoding="utf-8")
        for state in ("learn", "bound", "blue"):
            self.assertIn(f'modelData.state === "{state}"', midi)
        self.assertIn("modelData.evicting", midi)
        self.assertIn("selectControlIndicator", midi)
        self.assertIn("id: omniMidiControlLed", omni)
        self.assertIn("backend.midiPlayer.omniControlLedState", omni)

    def test_omni_control_led_is_centered_in_the_second_row_gap(self) -> None:
        qml = (ROOT / "gui" / "Main.qml").read_text(encoding="utf-8")
        start = qml.index("id: omniMidiControlLed")
        end = qml.index("// Moved left and up", start)
        led = qml[start:end]

        self.assertRegex(
            led,
            r"readonly property real gapLeft:\s*"
            r"window\.contentX\s*\+\s*window\.rowIndent\s*\+\s*"
            r"window\.chordRowContentWidth",
        )
        self.assertRegex(
            led,
            r"readonly property real gapRight:\s*window\.strumX",
        )
        self.assertRegex(
            led,
            r"x:\s*gapLeft\s*\+\s*\(\s*gapRight\s*-\s*gapLeft\s*"
            r"-\s*width\s*\)\s*/\s*2",
        )
        self.assertRegex(
            led,
            r"y:\s*window\.chordRowsY\s*\+\s*window\.rowHeight\s*"
            r"\+\s*window\.rowSpacing\s*\+\s*"
            r"\(window\.rowHeight\s*-\s*height\)\s*/\s*2",
        )

    def test_frontend_tree_contains_no_symlinks(self) -> None:
        generated_roots = {"build", "dist", "test-artifacts"}
        symlinks = [
            str(path.relative_to(ROOT))
            for path in ROOT.rglob("*")
            if path.is_symlink()
            and not generated_roots.intersection(path.relative_to(ROOT).parts)
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
