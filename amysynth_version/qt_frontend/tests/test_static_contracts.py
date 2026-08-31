from __future__ import annotations

import ast
import json
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class StaticContractTests(unittest.TestCase):
    def test_esp32_build_uses_the_immutable_omnichord_amy_release(self) -> None:
        repository = ROOT.parents[1]
        workflow = (
            repository / ".github" / "workflows" / "esp32p4-build.yml"
        ).read_text(encoding="utf-8")
        prepare = (ROOT.parent / "esp32p4" / "prepare_amy.sh").read_text(
            encoding="utf-8"
        )
        release_branch = "releases/amy_omnichord_R20260830T220021"
        release_commit = "32f3a68861a68979ceb715cf32e0322e8614365b"

        for contract in (workflow, prepare):
            self.assertIn("https://github.com/linuxificator/amy.git", contract)
            self.assertIn(release_branch, contract)
            self.assertIn(release_commit, contract)
        self.assertNotIn("AMY_REF:-main", prepare)
        self.assertIn("release branch and immutable commit do not match", prepare)

    def test_frontend_code_has_no_amy_library_imports(self) -> None:
        """Only the separately managed local service may load AMY."""
        allowed = {"local_amy_service.py"}
        imported: list[str] = []
        for path in (ROOT / "code").glob("*.py"):
            if path.name in allowed:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.append(node.module)
        forbidden = [name for name in imported if name in {"amy", "c_amy"}]
        self.assertEqual(forbidden, [])

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
            ROOT / "docs" / "WINDOWS_NATIVE.md",
            ROOT / "tests" / "USE_CASES.md",
            ROOT / "instruments" / "README_defaults.md",
            ROOT.parent / "esp32p4" / "README.md",
            ROOT.parent / "esp32p4" / "CI_FLASH.md",
        )
        for path in required_frontend_contracts:
            self.assertTrue(path.is_file(), str(path))
        self.assertIn("WINDOWS_NATIVE.md", design_index)

    def test_public_readme_uses_current_amy_and_qt_screenshots(self) -> None:
        repository = ROOT.parents[1]
        public_readme = (repository / "README.md").read_text(encoding="utf-8")
        frontend_readme = (ROOT / "README.md").read_text(encoding="utf-8")
        capture = (ROOT / "capture_screenshots.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("https://github.com/linuxificator/amy", public_readme)
        self.assertIn("https://github.com/shorepine/amy", public_readme)
        self.assertIn("`screenshots/`", frontend_readme)
        self.assertIn("python capture_screenshots.py", frontend_readme)
        self.assertIn('"QT_QPA_PLATFORM": "offscreen"', capture)
        self.assertIn('"--capture-screenshots-dir"', capture)
        self.assertIn("select.select([master_fd]", capture)
        self.assertIn("os.read(master_fd, 65536)", capture)
        for name in ("omni.png", "midi.png"):
            relative = f"amysynth_version/qt_frontend/screenshots/{name}"
            self.assertIn(relative, public_readme)
            path = repository / relative
            self.assertTrue(path.is_file(), relative)
            png = path.read_bytes()
            self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n", relative)
            width, height = struct.unpack(">II", png[16:24])
            self.assertEqual((width, height), (1920, 850), relative)

        workflow = (
            repository / ".github" / "workflows" / "desktop-release.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("refresh-readme-screenshots:", workflow)
        self.assertIn("needs: [publish-release]", workflow)
        self.assertIn(
            "python amysynth_version/qt_frontend/capture_screenshots.py",
            workflow,
        )

        app_core = (ROOT / "code" / "app_core.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("(2, 7, 104)", app_core)

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
            self.assertIn("controlTargetDoubleTapped", component)
            self.assertIn("controlTargetVisualState", component)
            self.assertIn("midiBound", component)
            self.assertIn('"#35b85a"', component)
            self.assertIn('"#f22b2b"', component)
            self.assertIn('"#3186d7"', component)
            self.assertIn("midiBindingGesture", component)
            self.assertIn('"preset-displaced"', component)
            self.assertIn('"preset-incoming"', component)
            self.assertIn("running: root.midiPresetFeedback", component)
            self.assertEqual(component.count("duration: 110"), 2)
            self.assertIn("const wasBound = root.midiBound", component)
            self.assertIn(
                "return learned || wasBound || root.midiPresetFeedback",
                component,
            )

        self.assertIn("controlTargetMoved", parameter)
        self.assertIn("controlTargetMoved", labeled)
        self.assertIn("if (root.midiBindingGesture)", parameter)
        self.assertIn("if (root.midiBindingGesture)", labeled)
        self.assertIn("root.syncSliderValue()", parameter)
        self.assertIn("slider.value = Qt.binding", labeled)
        self.assertIn("return root.currentValue", labeled)

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
            "master_volume",
            "rhythm_tempo",
            "bass_voicing",
            "bass_riff_selector",
        ):
            self.assertIn(f'"kind": "{kind}"', combined)

    def test_midi_control_states_and_omni_learn_led_are_rendered(self) -> None:
        midi = (ROOT / "gui" / "MidiScreen.qml").read_text(encoding="utf-8")
        omni = (ROOT / "gui" / "Main.qml").read_text(encoding="utf-8")
        rainbow = (ROOT / "gui" / "RainbowModeButton.qml").read_text(
            encoding="utf-8"
        )
        for state in ("learn", "bound", "blue"):
            self.assertIn(f'modelData.state === "{state}"', midi)
        self.assertIn("modelData.evicting", midi)
        self.assertIn("selectControlIndicator", midi)
        self.assertNotIn("id: omniMidiControlLed", omni)
        self.assertIn("backend.midiPlayer.omniControlLedState", omni)
        self.assertIn('=== "learn"', omni)
        self.assertIn("id: midiLearnLed", rainbow)
        self.assertIn("visible: root.midiLearnActive", rainbow)
        self.assertIn("modeLabel.contentWidth", rainbow)
        self.assertIn("width: root.width", rainbow)
        self.assertIn("width: 12", rainbow)
        self.assertIn('color: "#f22b2b"', rainbow)
        self.assertIn("running: root.midiLearnActive", rainbow)

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
        self.assertIn("def _set_rhythm_chord_enabled(", transport_py)
        self.assertIn('self._sync_synth_params(\n                "chord",', transport_py)
        gate_start = transport_py.index("def _set_rhythm_chord_enabled(")
        gate_end = transport_py.index("def _chord_state(", gate_start)
        gate_transition = transport_py[gate_start:gate_end]
        self.assertNotIn("self._wire(", gate_transition)
        self.assertNotIn("_begin_rhythm_chord_drain", transport_py)
        self.assertIn(
            "if not self._set_rhythm_chord_enabled(enabled):",
            transport_py,
        )
        self.assertIn("def _chord_pattern_plan(", transport_py)
        self.assertIn('f"zQT{pattern},0,0"', transport_py)
        self.assertIn('f"zQE{pattern},{gate},0,1"', transport_py)

        # Rhythm is now independent tagged lanes. Reintroducing the previous
        # whole-sequencer rebuild helpers would again make lane-local edits able
        # to interrupt drums/bass/chords together.
        self.assertIn("class _TaggedSequencerLane:", transport_py)
        self.assertNotIn("def retain_only(", transport_py)
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
        self.assertNotIn("enabled: backend.chordGateState !== 0", qml)
        self.assertIn("backend.toggleChordGate()", qml)
        gate_start = qml.index("id: chordGateButton")
        gate_end = qml.index("RainbowModeButton {", gate_start)
        gate = qml[gate_start:gate_end]
        activity_selector = (
            ROOT / "gui" / "ActivitySelector.qml"
        ).read_text(encoding="utf-8")
        self.assertIn("backend.chordGateState === 1", gate)
        for color in (
            '"#fff9dd"',
            '"#4c3b08"',
            '"#c79214"',
            '"#e1ca6a"',
            '"#f3e5a5"',
            '"#96720f"',
        ):
            self.assertIn(color, gate)
            self.assertIn(color, activity_selector)
        self.assertIn("chordGateButton.selectedState ? 2 : 1", gate)
        self.assertIn("backend.rollChordRows(-1)", qml)
        self.assertIn("backend.rollChordRows(1)", qml)

    def test_chord_left_controls_span_two_rows_with_equal_spacing(self) -> None:
        qml = (ROOT / "gui" / "Main.qml").read_text(encoding="utf-8")
        panel_start = qml.index("id: chordControlPanel")
        panel_end = qml.index("PresetResetButton {", panel_start)
        panel = qml[panel_start:panel_end]

        self.assertRegex(
            panel,
            r"height:\s*2 \* window\.rowHeight\s*"
            r"\+ window\.rowSpacing",
        )
        self.assertRegex(
            panel,
            r"readonly property real controlGap:\s*"
            r"\(\s*height\s*- 3 \* 42\s*\) / 4",
        )
        self.assertIn("y: chordControlPanel.controlGap", panel)
        self.assertIn("spacing: chordControlPanel.controlGap", panel)

    def test_rhythm_activity_groups_keep_equal_button_columns(self) -> None:
        qml = (ROOT / "gui" / "RhythmSection.qml").read_text(encoding="utf-8")
        self.assertEqual(qml.count("\n            ActivitySelector {"), 1)
        self.assertEqual(
            qml.count("\n            PercussionActivitySelector {"), 1
        )
        self.assertEqual(qml.count("\n            ChordActivitySelector {"), 1)
        percussion = (
            ROOT / "gui" / "PercussionActivitySelector.qml"
        ).read_text(encoding="utf-8")
        self.assertIn("model: 5", percussion)
        self.assertIn('text: "F" + String(index + 1)', percussion)
        self.assertIn("root.fillToggled(index)", percussion)
        self.assertIn(
            "width: controlsArea.bassActivityWidth",
            qml[qml.index("PercussionActivitySelector {"):],
        )
        self.assertIn('label: "bass activity"', qml)
        self.assertIn('label: "fill density"', qml)
        for label in ('"/32"', '"/16"', '"/8"', '"/1"'):
            self.assertIn(label, qml)
        self.assertNotIn("levels: [0, 1, 2, 3, 4]", qml)
        activity_selector = (
            ROOT / "gui" / "ActivitySelector.qml"
        ).read_text(encoding="utf-8")
        self.assertIn("property var levels: [1, 2, 3, 4]", activity_selector)
        self.assertIn("property var levelLabels: []", activity_selector)
        self.assertIn("height: 29", activity_selector)
        self.assertIn('label: "bass activity"', qml)
        self.assertIn("levels: [1, 2, 3, 4, 5]", qml)
        self.assertIn('levelLabels: ["1", "2", "3", "4", "R"]', qml)
        self.assertIn('"bass voicing"', qml)
        self.assertIn('"riff selector"', qml)
        self.assertIn("? 1 : -6", qml)
        self.assertIn("root.controller.bassRiffSelectorMaximum", qml)
        self.assertIn(": 6", qml)
        self.assertIn("stepValue: 1", qml)
        self.assertIn("root.controller.bassVoicingShift", qml)
        self.assertIn("root.controller.bassRiffSelector", qml)
        self.assertIn(".setBassVoicingShift(value)", qml)
        self.assertIn(".setBassRiffSelector(value)", qml)
        self.assertIn("controlsArea.expandedActivityWidth", qml)
        self.assertIn("5 * activityButtonWidth", qml)
        self.assertIn("2 * bassActivityWidth + 2 * activityGap", qml)
        self.assertEqual(qml.count("x: controlsArea.bassColumnX"), 2)

        chord = (
            ROOT / "gui" / "ChordActivitySelector.qml"
        ).read_text(encoding="utf-8")
        self.assertIn('text: "chord activity"', chord)
        self.assertIn('text: index < 4 ? String(index + 1) : "A"', chord)
        self.assertIn('? "/" + String(index + 1)', chord)
        self.assertIn(': root.directionLabel', chord)
        self.assertIn("model: 5", chord)
        self.assertEqual(chord.count("Button {"), 2)
        self.assertNotIn("MouseArea {", chord)
        self.assertNotIn("Timer {", chord)
        self.assertNotIn("TapHandler {", chord)
        self.assertIn("height: parent.height", qml)
        self.assertIn("width: controlsArea.bassActivityWidth", qml)

    def test_reverb_header_uses_wide_horizontal_sliders(self) -> None:
        panel = (ROOT / "gui" / "ReverbPanel.qml").read_text(encoding="utf-8")
        main = (ROOT / "gui" / "Main.qml").read_text(encoding="utf-8")
        midi_backend = (ROOT / "code" / "midi_player.py").read_text(
            encoding="utf-8"
        )
        omni_backend = (ROOT / "code" / "app_core.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("id: controlsRow", panel)
        self.assertEqual(panel.count("LabeledSlider {"), 3)
        self.assertNotIn("VerticalVolume {", panel)
        self.assertIn("readonly property real controlSliderWidth", panel)
        self.assertEqual(panel.count("width: root.controlSliderWidth"), 3)
        self.assertIn("toValue: 3", panel)
        self.assertIn("MIDI_REVERB_MAX = app_core.REVERB_LEVEL_MAX", midi_backend)
        self.assertIn("REVERB_LEVEL_MAX = 3.0", omni_backend)
        self.assertIn('label: "LEV"', panel)
        self.assertIn('label: "LIVE"', panel)
        self.assertIn('label: "DAMP"', panel)
        self.assertIn("property int reverbPanelWidth: 572", main)

        midi_integration = (
            ROOT / "code" / "midi_integration.py"
        ).read_text(encoding="utf-8")
        self.assertIn("@Property(QObject, constant=True)", midi_integration)

    def test_utility_header_uses_two_aligned_visual_rows(self) -> None:
        main = (ROOT / "gui" / "Main.qml").read_text(encoding="utf-8")
        midi = (ROOT / "gui" / "MidiScreen.qml").read_text(encoding="utf-8")
        utilities = tuple(
            (ROOT / "gui" / name).read_text(encoding="utf-8")
            for name in ("UtilitySection.qml", "MidiUtilitySection.qml")
        )

        self.assertIn("property int presetRowHeight: 64", main)
        self.assertRegex(main, r"property int utilityY:\s*0")
        self.assertRegex(
            main,
            r"property int presetY:\s*utilityY\s*"
            r"\+ sectionHeight\s*\+ sectionGap",
        )
        self.assertRegex(
            main,
            r"property int rhythmY:\s*presetY\s*"
            r"\+ presetRowHeight\s*\+ sectionGap",
        )
        self.assertIn("y: window.presetY", main)
        self.assertIn("width: window.reverbPanelWidth", main)
        self.assertIn("height: window.presetRowHeight", main)
        self.assertIn("y: root.hostWindow.presetY", midi)
        self.assertIn("width: root.hostWindow.reverbPanelWidth", midi)
        self.assertIn("height: root.hostWindow.presetRowHeight", midi)

        for utility in utilities:
            self.assertIn("property int tuningRowHeight", utility)
            self.assertIn("property int presetRowY", utility)
            self.assertIn("property int presetRowHeight", utility)
            store_start = utility.index("id: storeButton")
            preset_start = utility.index("id: presetButtons", store_start)
            store = utility[store_start:preset_start]
            self.assertIn("width: 48", store)
            self.assertIn("height: 48", store)
            self.assertIn('text: "STR"', store)
            self.assertIn('color: "#ffffff"', store)
            self.assertIn('"#6f3599"', store)
            self.assertRegex(store, r"x:\s*8")
            self.assertRegex(
                utility,
                r"x:\s*storeButton\.x\s*"
                r"\+ storeButton\.width\s*\+ 6",
            )

            preset_start = utility.index("id: presetButton\n")
            timer_start = utility.index("Timer {", preset_start)
            preset = utility[preset_start:timer_start]
            for fixed_geometry in (
                "padding: 0",
                "leftInset: 0",
                "rightInset: 0",
                "topInset: 0",
                "bottomInset: 0",
                "scale: 1.0",
                "width: presetButton.width",
                "height: presetButton.height",
                "border.width: 1",
            ):
                self.assertIn(fixed_geometry, preset)
            self.assertNotIn("visible: presetButton.pressed", preset)
            self.assertNotIn("visible: presetButton.selected", preset)
            self.assertRegex(
                preset,
                r"presetButton\.selected\s*\? \"#ffffff\"\s*"
                r": \"#8e6bab\"",
            )

        self.assertIn("anchors.bottom: parent.bottom", main)
        mode_panel_start = main.index("id: strumModePanel")
        mode_panel_end = main.index("ReverbPanel {", mode_panel_start)
        mode_panel = main[mode_panel_start:mode_panel_end]
        self.assertIn("height: window.presetRowHeight", mode_panel)
        self.assertIn("anchors.verticalCenter:", mode_panel)
        self.assertIn("width: 48", mode_panel)
        self.assertIn("height: 48", mode_panel)
        self.assertNotIn("toggleStrumLadderMode", midi)

    def test_brown_master_controls_are_independent_and_right_aligned(self) -> None:
        main = (ROOT / "gui" / "Main.qml").read_text(encoding="utf-8")
        midi = (ROOT / "gui" / "MidiScreen.qml").read_text(encoding="utf-8")
        tap_number = (ROOT / "gui" / "TapNumber.qml").read_text(
            encoding="utf-8"
        )
        utilities = tuple(
            (ROOT / "gui" / name).read_text(encoding="utf-8")
            for name in ("UtilitySection.qml", "MidiUtilitySection.qml")
        )

        self.assertIn("property bool centerButtonEnabled: false", tap_number)
        self.assertIn("signal centerClicked()", tap_number)
        self.assertIn("visible: root.centerButtonEnabled", tap_number)
        self.assertIn("anchors.centerIn: parent", tap_number)
        self.assertIn("root.centerClicked()", tap_number)
        for screen in (main, midi):
            self.assertIn("utilityRightEdge:", screen)
            self.assertIn("reverbPanel.width", screen)
        for screen_name, utility in zip(("omni", "midi"), utilities):
            self.assertIn("property int utilityRightEdge: width", utility)
            self.assertRegex(
                utility,
                r"readonly property int escapeX:\s*"
                r"utilityRightEdge - escapeWidth",
            )
            self.assertRegex(
                utility,
                r"readonly property int masterX:\s*"
                r"panicX - utilityGap - masterWidth",
            )
            self.assertGreaterEqual(utility.count("TapNumber {"), 2)
            self.assertIn('panelColor: "#b58a63"', utility)
            self.assertIn('fillColor: "#704323"', utility)
            self.assertIn('? "UMT" : "MUT"', utility)
            self.assertIn('centerPanelColor:', utility)
            self.assertIn('root.controller.masterMuted ? "#111111" : "#ffffff"', utility)
            self.assertIn(f'"screen": "{screen_name}"', utility)
            self.assertIn('"kind": "master_volume"', utility)
            self.assertIn("setMasterVolume(value / 100)", utility)
            self.assertIn("toggleMasterMuted()", utility)

    def test_midi_title_uses_the_omni_title_geometry(self) -> None:
        main = (ROOT / "gui" / "Main.qml").read_text(encoding="utf-8")
        midi = (ROOT / "gui" / "MidiScreen.qml").read_text(encoding="utf-8")

        self.assertIn("readonly property int omniTitleX", main)
        self.assertIn("readonly property int omniTitleWidth", main)
        self.assertIn("x: window.omniTitleX", main)
        self.assertIn("width: window.omniTitleWidth", main)
        self.assertIn("x: root.hostWindow.omniTitleX", midi)
        self.assertIn("width: root.hostWindow.omniTitleWidth", midi)

    def test_qt_owns_chord_gesture_recognition(self) -> None:
        backend = (ROOT / "code" / "app_core.py").read_text(encoding="utf-8")
        qml = (ROOT / "gui" / "Main.qml").read_text(encoding="utf-8")
        self.assertNotIn("CHORD_QUICK_TAP_MAX_MS", backend)
        self.assertNotIn("_pending_chord_promotions", backend)
        self.assertNotIn("_schedule_chord_hold_promotion", backend)
        self.assertIn("def promoteChordHold(", backend)
        self.assertIn("self._promoted_chords.add(key)", backend)
        press_start = backend.index("def pressChord(")
        promote_start = backend.index("def promoteChordHold(", press_start)
        press = backend[press_start:promote_start]
        self.assertIn("self._send_chord_state(play_now=False)", press)
        self.assertIn("self._set_active_chord(", press)
        promote_end = backend.index("def releaseChord(", promote_start)
        promote = backend[promote_start:promote_end]
        self.assertNotIn("self._set_active_chord(", promote)
        self.assertNotIn("self._send_chord_state(", promote)
        self.assertIn("self._update_hold_override()", promote)
        release_start = backend.index("def releaseChord(")
        release_end = backend.index("def selectChord(", release_start)
        release = backend[release_start:release_end]
        self.assertIn("self._finalize_chord_release(key)", release)
        self.assertNotIn("_schedule_chord_release", backend)
        self.assertNotIn("RELEASE_GRACE", backend)

        chord_start = qml.index(
            "objectName:\n                                        \"chordButton_\""
        )
        chord_end = qml.index(
            "Repeater {\n                                model: octaveNames"
        )
        chord_buttons = qml[chord_start:chord_end]
        self.assertIn("TapHandler {", chord_buttons)
        self.assertIn("gesturePolicy:", chord_buttons)
        self.assertIn("TapHandler.ReleaseWithinBounds", chord_buttons)
        self.assertIn("onPressedChanged:", chord_buttons)
        self.assertIn("onLongPressed:", chord_buttons)
        self.assertIn("backend.pressChord(", chord_buttons)
        self.assertIn("backend.promoteChordHold(", chord_buttons)
        self.assertIn("backend.releaseChord(", chord_buttons)
        self.assertNotIn("MultiPointTouchArea", chord_buttons)

    def test_numeric_controls_delegate_gesture_timing_to_qt(self) -> None:
        numeric = [
            (ROOT / "gui" / name).read_text(encoding="utf-8")
            for name in (
                "TapNumber.qml",
                "VerticalVolume.qml",
                "LabeledSlider.qml",
                "ParameterSlider.qml",
            )
        ]
        combined = "\n".join(numeric)
        for marker in (
            "Date.now()",
            "holdDelayMs",
            "repeatIntervalMs",
            "midiMoveCount",
            "MultiPointTouchArea",
        ):
            self.assertNotIn(marker, combined)
        self.assertIn("autoRepeat: true", numeric[0])
        self.assertIn("autoRepeat: true", numeric[1])
        self.assertIn("onDoubleClicked:", numeric[0])
        self.assertIn("onDoubleClicked:", numeric[1])
        self.assertIn("onDoubleTapped:", numeric[2])
        self.assertIn("onDoubleTapped:", numeric[3])
        self.assertIn("onMoved:", numeric[2])
        self.assertIn("onMoved:", numeric[3])
        midi_state = (ROOT / "code" / "midi_control.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("double_tap_window", midi_state)
        self.assertNotIn("_target_taps", midi_state)
        self.assertIn("def target_double_tapped(", midi_state)

    def test_clickable_visuals_use_qt_quick_buttons(self) -> None:
        rainbow = (ROOT / "gui" / "RainbowModeButton.qml").read_text(
            encoding="utf-8"
        )
        midi = (ROOT / "gui" / "MidiScreen.qml").read_text(encoding="utf-8")
        self.assertTrue(rainbow.lstrip().startswith("import QtQuick"))
        self.assertIn("\nButton {\n", rainbow)
        self.assertNotIn("MouseArea {", rainbow)

        delegate_start = midi.index("delegate: Button {")
        delegate_end = midi.index("MidiStrumPad {", delegate_start)
        indicator = midi[delegate_start:delegate_end]
        self.assertIn("onClicked:", indicator)
        self.assertNotIn("MouseArea {", indicator)

    def test_runtime_ui_does_not_branch_on_operating_system_names(self) -> None:
        runtime_files = [
            *sorted((ROOT / "code").glob("*.py")),
            *sorted((ROOT / "gui").glob("*.qml")),
        ]
        forbidden = (
            "sys.platform",
            "platform.system(",
            "os.name",
            "Qt.platform.os",
        )
        for path in runtime_files:
            source = path.read_text(encoding="utf-8")
            for marker in forbidden:
                self.assertNotIn(marker, source, f"{path}: {marker}")

    def test_apg_ldr_button_uses_backend_preset_state(self) -> None:
        qml = (ROOT / "gui" / "Main.qml").read_text(encoding="utf-8")
        backend = (ROOT / "code" / "app_core.py").read_text(encoding="utf-8")
        self.assertIn(
            "property bool strumLadderMode: backend.strumLadderMode",
            qml,
        )
        self.assertIn("backend.toggleStrumLadderMode()", qml)
        self.assertIn('"strum_mode": "LDR"', backend)
        self.assertIn('data.get("strum_mode", "APG")', backend)

    def test_strum_note_guide_occupies_the_omni_side_gap(self) -> None:
        qml = (ROOT / "gui" / "Main.qml").read_text(encoding="utf-8")
        guide_start = qml.index("id: strumNoteGuide")
        guide_end = qml.index("PresetResetButton {", guide_start)
        guide = qml[guide_start:guide_end]

        self.assertIn("window.volumeX", guide)
        self.assertIn("+ window.volumeWidth", guide)
        self.assertIn("window.strumX", guide)
        self.assertIn("window.strumSynthY", guide)
        self.assertIn("model: backend.strumNoteNames", guide)
        self.assertIn('color: "#dcecf7"', guide)
        self.assertIn("Math.min(34, width - 4)", guide)

    def test_rainbow_mode_button_text_is_large_and_centered(self) -> None:
        qml = (ROOT / "gui" / "RainbowModeButton.qml").read_text(
            encoding="utf-8"
        )
        self.assertIn("font.pixelSize: height * 0.55", qml)
        self.assertNotIn("anchors.horizontalCenterOffset", qml)
        self.assertIn("width: root.width", qml)
        self.assertIn("horizontalAlignment: Text.AlignHCenter", qml)
        self.assertIn("verticalAlignment: Text.AlignVCenter", qml)
        self.assertNotIn("readonly property real labelWidth:", qml)
        self.assertNotIn("MouseArea {", qml)

    def test_hidden_preset_binding_leds_are_wired_to_location_feedback(self) -> None:
        main = (ROOT / "gui" / "Main.qml").read_text(encoding="utf-8")
        midi = (ROOT / "gui" / "MidiScreen.qml").read_text(encoding="utf-8")
        rainbow = (ROOT / "gui" / "RainbowModeButton.qml").read_text(
            encoding="utf-8"
        )
        led = (ROOT / "gui" / "MidiBindingLocationLed.qml").read_text(
            encoding="utf-8"
        )
        utilities = tuple(
            (ROOT / "gui" / name).read_text(encoding="utf-8")
            for name in ("UtilitySection.qml", "MidiUtilitySection.qml")
        )

        self.assertIn("onBindingLocationRequested", led)
        self.assertIn('color: "#31d158"', led)
        self.assertIn("property int targetPreset: 0", led)
        self.assertIn("root.targetPreset <= 0", led)
        self.assertIn("loops: 5", led)
        self.assertEqual(led.count("PauseAnimation { duration: 110 }"), 2)
        for utility, screen in zip(utilities, ("omni", "midi")):
            self.assertIn("MidiBindingLocationLed {", utility)
            self.assertIn("y: 4", utility)
            self.assertIn("width: 7", utility)
            self.assertIn(f'targetScreen: "{screen}"', utility)
            self.assertIn("targetPreset: presetButton.presetNumber", utility)
            self.assertIn("locationEnabled: !presetButton.selected", utility)

        self.assertIn("anchors.verticalCenter: parent.verticalCenter", rainbow)
        self.assertIn("x: 9", rainbow)
        self.assertIn("width: 10", rainbow)
        self.assertNotIn("targetPreset:", rainbow)
        self.assertIn('bindingLocationScreen: "midi"', main)
        self.assertIn('bindingLocationScreen: "omni"', midi)

    def test_rhythm_transport_uses_the_centered_bass_arrow_geometry(self) -> None:
        qml = (ROOT / "gui" / "RhythmSection.qml").read_text(encoding="utf-8")
        self.assertIn("contentItem: Canvas {", qml)
        self.assertIn("c.moveTo(width / 2 - 9, height / 2 - 14)", qml)
        self.assertIn("c.lineTo(width / 2 + 15, height / 2)", qml)
        self.assertIn("c.lineTo(width / 2 - 9, height / 2 + 14)", qml)
        self.assertIn("function onRhythmStateChanged()", qml)
        self.assertIn("rhythmTransportSymbol.requestPaint()", qml)

    def test_midi_owned_tempo_and_tuning_nudges_are_grey_and_disabled(self) -> None:
        main = (ROOT / "gui" / "Main.qml").read_text(encoding="utf-8")
        midi = (ROOT / "gui" / "MidiScreen.qml").read_text(encoding="utf-8")
        button = (ROOT / "gui" / "PresetResetButton.qml").read_text(
            encoding="utf-8"
        )
        compact_button = " ".join(button.split())
        self.assertEqual(main.count("enabled: !window.omniTuningLocked"), 2)
        self.assertEqual(main.count("enabled: !window.rhythmTempoMidiBound"), 2)
        self.assertEqual(midi.count("enabled: !root.tuningMidiLocked"), 2)
        self.assertIn('enabled ? root.textColor : "#686864"', button)
        self.assertIn(
            '? (root.pressed ? Qt.darker(root.panelColor, 1.08) : root.panelColor) : "#bdbdb8"',
            compact_button,
        )
        self.assertIn('enabled ? root.borderColor : "#85857f"', button)

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
        self.assertIn(
            'f"K{patch}i{synth}iv{voices}iy{bus}{flag_fields}Z"',
            transport_py,
        )
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
