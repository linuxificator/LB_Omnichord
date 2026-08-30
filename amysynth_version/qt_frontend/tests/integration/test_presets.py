from __future__ import annotations

import json
import time
import unittest

from catalog import control_default, entry_for_index, synth_index
from harness import HeadlessApp


def bind_control(
    app: HeadlessApp,
    channel: int,
    controller: int,
    target: dict[str, object],
) -> None:
    app.action("injectMidiControl", channel, controller, 0)
    app.action("injectMidiControl", channel, controller, 1)
    app.action("selectMidiControlIndicator", channel, controller)
    if not app.action("activateMidiControlTarget", target):
        raise AssertionError(f"could not bind MIDI target {target}")


def changed_control_value(control: dict[str, object]) -> float:
    current = float(control["value"])
    minimum = float(control["minimum"])
    maximum = float(control["maximum"])
    return maximum if abs(current - maximum) > 1e-6 else minimum


class PresetIntegrationTests(unittest.TestCase):
    def test_preset_cc_conflict_uses_preset_values_and_visual_handoff(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)
            old_target = {
                "screen": "omni",
                "kind": "volume",
                "role": "chord",
            }
            new_target = {
                "screen": "omni",
                "kind": "volume",
                "role": "strum",
            }
            bind_control(app, 12, 92, old_target)
            app.action("injectMidiControl", 12, 92, 127)
            self.assertAlmostEqual(float(app.query("chordVolume")), 1.0)

            preset_path = app.home / ".omnichord" / "omni_presets" / "p2.json"
            preset = json.loads(preset_path.read_text(encoding="utf-8"))
            preset["volumes"]["chord"] = 0.23
            preset["volumes"]["strum"] = 0.37
            preset["midi_control_bindings"] = [
                {
                    "channel": 12,
                    "controller": 92,
                    "target": new_target,
                }
            ]
            preset_path.write_text(
                json.dumps(preset, indent=2) + "\n",
                encoding="utf-8",
            )

            app.action("selectPreset", 2)
            self.assertAlmostEqual(float(app.query("chordVolume")), 0.23)
            self.assertAlmostEqual(float(app.query("strumVolume")), 0.37)
            self.assertEqual(
                app.action("midiControlTargetVisualState", old_target),
                "preset-displaced",
            )
            self.assertEqual(
                app.action("midiControlTargetVisualState", new_target),
                "preset-incoming",
            )

            # The outgoing target remains protected during the visual handoff.
            app.action("setChordVolume", 0.8)
            self.assertAlmostEqual(float(app.query("chordVolume")), 0.23)

            time.sleep(2.25)
            self.assertEqual(
                app.action("midiControlTargetVisualState", old_target),
                "idle",
            )
            self.assertEqual(
                app.action("midiControlTargetVisualState", new_target),
                "bound",
            )
            app.action("setChordVolume", 0.8)
            app.action("setStrumVolume", 0.8)
            self.assertAlmostEqual(float(app.query("chordVolume")), 0.8)
            self.assertAlmostEqual(float(app.query("strumVolume")), 0.37)

            app.action("injectMidiControl", 12, 92, 0)
            self.assertAlmostEqual(float(app.query("strumVolume")), 0.0)

    def test_coupled_tuning_binding_survives_other_screen_preset(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)
            midi_target = {"screen": "midi", "kind": "tuning_reference"}
            bind_control(app, 10, 90, midi_target)
            app.action("injectMidiControl", 10, 90, 127)
            self.assertEqual(int(app.query("tuningReference")), 466)
            self.assertEqual(int(app.action("midiTuningReference")), 466)

            omni_path = app.home / ".omnichord" / "omni_presets" / "p2.json"
            omni_data = json.loads(omni_path.read_text(encoding="utf-8"))
            omni_data["tuning"]["reference_hz"] = 415
            omni_path.write_text(
                json.dumps(omni_data, indent=2) + "\n",
                encoding="utf-8",
            )
            app.action("selectPreset", 2)
            self.assertEqual(int(app.query("tuningReference")), 466)
            self.assertEqual(int(app.action("midiTuningReference")), 466)

            app.action("moveMidiControlTarget", midi_target)
            omni_target = {"screen": "omni", "kind": "tuning_reference"}
            bind_control(app, 11, 91, omni_target)
            app.action("injectMidiControl", 11, 91, 127)

            midi_path = app.home / ".omnichord" / "midi_presets" / "m2.json"
            midi_data = json.loads(midi_path.read_text(encoding="utf-8"))
            midi_data["tuning"]["reference_hz"] = 415
            midi_path.write_text(
                json.dumps(midi_data, indent=2) + "\n",
                encoding="utf-8",
            )
            app.action("selectMidiPreset", 2)
            self.assertEqual(int(app.query("tuningReference")), 466)
            self.assertEqual(int(app.action("midiTuningReference")), 466)

    def test_midi_control_bindings_are_owned_by_their_screen_presets(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)
            midi_target = {
                "screen": "midi",
                "kind": "volume",
                "row": 0,
            }
            omni_target = {
                "screen": "omni",
                "kind": "volume",
                "role": "chord",
            }

            for channel, controller, target in (
                (1, 20, midi_target),
                (2, 21, omni_target),
            ):
                app.action("injectMidiControl", channel, controller, 0)
                app.action("injectMidiControl", channel, controller, 1)
                app.action(
                    "selectMidiControlIndicator",
                    channel,
                    controller,
                )
                self.assertTrue(
                    app.action("activateMidiControlTarget", target)
                )

            app.action("storeSelectedMidiPreset")
            app.action("storeSelectedPreset")
            midi_data = json.loads(
                (
                    app.home
                    / ".omnichord"
                    / "midi_presets"
                    / "m1.json"
                ).read_text(encoding="utf-8")
            )
            omni_data = json.loads(
                (
                    app.home
                    / ".omnichord"
                    / "omni_presets"
                    / "p1.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(
                midi_data["midi_control_bindings"][0]["controller"],
                20,
            )
            self.assertEqual(
                midi_data["midi_control_bindings"][0]["target"]["screen"],
                "midi",
            )
            self.assertEqual(
                omni_data["midi_control_bindings"][0]["controller"],
                21,
            )
            self.assertEqual(
                omni_data["midi_control_bindings"][0]["target"]["screen"],
                "omni",
            )

            app.action("selectMidiPreset", 2)
            app.action("selectPreset", 2)
            app.action("selectMidiPreset", 1)
            app.action("selectPreset", 1)
            states = {
                (item["channel"], item["controller"]): item["state"]
                for item in app.action("midiControlIndicators")
            }
            self.assertEqual(states[(1, 20)], "bound")
            self.assertEqual(states[(2, 21)], "bound")

    def test_store_persists_all_modified_instruments_sparse(self) -> None:
        labels = [
            "Repeater",
            "Harpsichord 1",
            "Orchestral Pad",
            "Synth Pad",
        ]
        indexes = [synth_index(label) for label in labels]

        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)
            expected: dict[str, float] = {}

            for offset, index in enumerate(indexes, start=1):
                app.action("setChordSynthIndex", index)
                default = control_default(index, "attack_ms")
                value = default + (10.0 * offset)
                app.action("setChordSynthControl", "attack_ms", value)
                key = str(entry_for_index(index)["key"])
                expected[key] = value

            # Switch away and back before storing: the remembered slider value
            # must belong to the instrument rather than to the current panel.
            first_index = indexes[0]
            app.action("setChordSynthIndex", indexes[-1])
            app.action("setChordSynthIndex", first_index)
            controls = list(app.query("chordCommonControls")) + list(
                app.query("chordExtraControls")
            )
            attack = next(c for c in controls if c["key"] == "attack_ms")
            first_key = str(entry_for_index(first_index)["key"])
            self.assertAlmostEqual(
                float(attack["value"]), expected[first_key], places=6
            )

            app.action("storeSelectedPreset")
            preset_path = app.home / ".omnichord" / "omni_presets" / "p1.json"
            data = json.loads(preset_path.read_text(encoding="utf-8"))
            parameters = data["synths"]["chord"]["parameters"]

            for key, value in expected.items():
                self.assertIn(key, parameters)
                self.assertEqual(set(parameters[key]), {"attack_ms"})
                self.assertAlmostEqual(
                    float(parameters[key]["attack_ms"]), value, places=6
                )

            self.assertEqual(
                set(parameters),
                set(expected),
                "preset contains missing or non-modified chord instruments",
            )

    def test_section_rst_restores_stored_synth_selection(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)

            stored = {
                "chord": 7,
                "strum": 8,
                "bass": 9,
            }
            app.action("setChordSynthIndex", stored["chord"])
            app.action("setStrumSynthIndex", stored["strum"])
            app.action("setBassSynthIndex", stored["bass"])
            app.action("storeSelectedPreset")

            app.action("setChordSynthIndex", 10)
            app.action("setStrumSynthIndex", 11)
            app.action("setBassSynthIndex", 12)

            app.action("resetChordSynthToPreset")
            app.action("resetStrumToPreset")
            app.action("resetBassToPreset")
            app.bridge.wait_idle(timeout=8.0)

            self.assertEqual(
                int(app.query("selectedChordSynthIndex")), stored["chord"]
            )
            self.assertEqual(
                int(app.query("selectedStrumSynthIndex")), stored["strum"]
            )
            self.assertEqual(
                int(app.query("selectedBassSynthIndex")), stored["bass"]
            )

    def test_apg_ldr_mode_is_owned_by_omni_preset(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)
            self.assertFalse(bool(app.query("strumLadderMode")))

            app.action("setStrumLadderMode", True)
            app.action("storeSelectedPreset")
            preset_path = app.home / ".omnichord" / "omni_presets" / "p1.json"
            stored = json.loads(preset_path.read_text(encoding="utf-8"))
            self.assertEqual(stored["strum_mode"], "LDR")

            app.action("selectPreset", 2)
            self.assertFalse(bool(app.query("strumLadderMode")))
            app.action("selectPreset", 1)
            self.assertTrue(bool(app.query("strumLadderMode")))

            stored.pop("strum_mode")
            preset_path.write_text(
                json.dumps(stored, indent=2) + "\n",
                encoding="utf-8",
            )
            app.action("selectPreset", 2)
            app.action("selectPreset", 1)
            self.assertFalse(bool(app.query("strumLadderMode")))

    def test_omni_bound_values_survive_rst_and_preset_switch(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)
            stored_index = int(app.query("selectedChordSynthIndex"))
            bound_index = synth_index("Harpsichord 1")
            app.action("setChordSynthIndex", bound_index)
            controls = list(app.query("chordCommonControls")) + list(
                app.query("chordExtraControls")
            )
            bound_control = next(c for c in controls if c["key"] == "attack_ms")
            unbound_control = next(c for c in controls if c["key"] == "release_ms")
            original_unbound = float(unbound_control["value"])
            instrument = str(entry_for_index(bound_index)["key"])

            app.action("setChordSynthIndex", stored_index)
            app.action("storeSelectedPreset")
            app.action("setChordSynthIndex", bound_index)
            bind_control(
                app,
                1,
                70,
                {
                    "screen": "omni",
                    "kind": "synth_control",
                    "role": "chord",
                    "instrument": instrument,
                    "control": "attack_ms",
                },
            )
            bind_control(
                app,
                2,
                71,
                {"screen": "omni", "kind": "volume", "role": "chord"},
            )

            protected_attack = float(bound_control["maximum"])
            changed_release = changed_control_value(unbound_control)
            app.action("injectMidiControl", 1, 70, 127)
            app.action("setChordSynthControl", "release_ms", changed_release)
            app.action("injectMidiControl", 2, 71, 127)
            app.action("resetChordSynthToPreset")

            self.assertEqual(
                int(app.query("selectedChordSynthIndex")),
                stored_index,
            )
            self.assertAlmostEqual(float(app.query("chordVolume")), 1.0)
            app.action("setChordSynthIndex", bound_index)
            reset_controls = list(app.query("chordCommonControls")) + list(
                app.query("chordExtraControls")
            )
            reset_by_key = {str(item["key"]): item for item in reset_controls}
            self.assertAlmostEqual(
                float(reset_by_key["attack_ms"]["value"]),
                protected_attack,
            )
            self.assertAlmostEqual(
                float(reset_by_key["release_ms"]["value"]),
                original_unbound,
            )

            preset_two_path = (
                app.home / ".omnichord" / "omni_presets" / "p2.json"
            )
            preset_two = json.loads(preset_two_path.read_text(encoding="utf-8"))
            preset_two["volumes"]["strum"] = 0.11
            preset_two["midi_control_bindings"] = [
                {
                    "channel": 3,
                    "controller": 72,
                    "target": {
                        "screen": "omni",
                        "kind": "volume",
                        "role": "strum",
                    },
                }
            ]
            preset_two_path.write_text(
                json.dumps(preset_two, indent=2) + "\n",
                encoding="utf-8",
            )
            app.action("setStrumVolume", 0.77)
            app.action("selectPreset", 2)

            self.assertAlmostEqual(float(app.query("chordVolume")), 1.0)
            self.assertAlmostEqual(float(app.query("strumVolume")), 0.77)
            app.action("setChordSynthIndex", bound_index)
            switched_controls = list(app.query("chordCommonControls")) + list(
                app.query("chordExtraControls")
            )
            switched_attack = next(
                item for item in switched_controls if item["key"] == "attack_ms"
            )
            self.assertAlmostEqual(
                float(switched_attack["value"]),
                protected_attack,
            )

    def test_midi_bound_values_survive_rst_and_preset_switch(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)
            row = 0
            selected_index = int(app.action("midiSynthIndex", row))
            instrument = str(entry_for_index(selected_index)["key"])
            controls = list(app.action("midiCommonControls", row)) + list(
                app.action("midiExtraControls", row)
            )
            bound_control = next(c for c in controls if c["key"] == "attack_ms")
            unbound_control = next(c for c in controls if c["key"] == "release_ms")
            original_unbound = float(unbound_control["value"])
            protected_attack = float(bound_control["maximum"])

            bind_control(
                app,
                4,
                73,
                {
                    "screen": "midi",
                    "kind": "synth_control",
                    "row": row,
                    "instrument": instrument,
                    "control": "attack_ms",
                },
            )
            bind_control(
                app,
                5,
                74,
                {"screen": "midi", "kind": "volume", "row": row},
            )
            app.action("injectMidiControl", 4, 73, 127)
            app.action(
                "setMidiSynthControl",
                row,
                "release_ms",
                changed_control_value(unbound_control),
            )
            app.action("injectMidiControl", 5, 74, 127)
            app.action("resetMidiSynthRow", row)

            reset_controls = list(app.action("midiCommonControls", row)) + list(
                app.action("midiExtraControls", row)
            )
            reset_by_key = {str(item["key"]): item for item in reset_controls}
            self.assertAlmostEqual(
                float(reset_by_key["attack_ms"]["value"]),
                protected_attack,
            )
            self.assertAlmostEqual(
                float(reset_by_key["release_ms"]["value"]),
                original_unbound,
            )
            self.assertAlmostEqual(float(app.action("midiVolume", row)), 1.0)

            preset_two_path = (
                app.home / ".omnichord" / "midi_presets" / "m2.json"
            )
            preset_two = json.loads(preset_two_path.read_text(encoding="utf-8"))
            preset_two["rows"][1]["volume"] = 0.12
            preset_two["midi_control_bindings"] = [
                {
                    "channel": 6,
                    "controller": 75,
                    "target": {"screen": "midi", "kind": "volume", "row": 1},
                }
            ]
            preset_two_path.write_text(
                json.dumps(preset_two, indent=2) + "\n",
                encoding="utf-8",
            )
            app.action("setMidiVolume", 1, 0.83)
            app.action("selectMidiPreset", 2)

            self.assertAlmostEqual(float(app.action("midiVolume", row)), 1.0)
            self.assertAlmostEqual(float(app.action("midiVolume", 1)), 0.83)
            app.action("setMidiSynthIndex", row, selected_index)
            switched_controls = list(app.action("midiCommonControls", row)) + list(
                app.action("midiExtraControls", row)
            )
            switched_attack = next(
                item for item in switched_controls if item["key"] == "attack_ms"
            )
            self.assertAlmostEqual(
                float(switched_attack["value"]),
                protected_attack,
            )

    def test_rhythm_running_is_live_state_not_preset_state(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)
            self.assertFalse(bool(app.query("rhythmRunning")))

            # Storing while the rhythm is running must not persist that state.
            app.action("toggleRhythm")
            self.assertTrue(bool(app.query("rhythmRunning")))
            app.action("storeSelectedPreset")

            preset_path = app.home / ".omnichord" / "omni_presets" / "p1.json"
            data = json.loads(preset_path.read_text(encoding="utf-8"))
            self.assertNotIn("rhythm_running", data.get("transport", {}))

            # A legacy preset may still contain rhythm_running=true.  Loading it
            # while stopped must ignore that old field rather than start drums.
            data.setdefault("transport", {})["rhythm_running"] = True
            preset_path.write_text(
                json.dumps(data, indent=2) + "\n",
                encoding="utf-8",
            )
            app.action("toggleRhythm")
            self.assertFalse(bool(app.query("rhythmRunning")))
            app.action("selectPreset", 2)
            app.action("selectPreset", 1)
            self.assertFalse(bool(app.query("rhythmRunning")))

            # Conversely, changing presets while already running must not stop
            # the live transport merely because the destination preset is dry.
            app.action("toggleRhythm")
            self.assertTrue(bool(app.query("rhythmRunning")))
            app.action("selectPreset", 2)
            self.assertTrue(bool(app.query("rhythmRunning")))

    def test_held_chord_survives_preset_switch_with_new_chord_type(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)

            # Factory P1 row 0 is C minor in HARM tuning. P2 changes the same
            # row/root identity to equal-tempered C major.
            app.action("selectPreset", 1)
            app.action("pressChord", 0, 0)
            app.bridge.wait_for_lines(
                ["n48l1i3Z"],
                start=0,
                timeout=3.0,
            )
            # This scenario intentionally exercises a held chord. Qt owns the
            # long-press threshold; this backend test supplies its resulting
            # semantic event directly before switching presets.
            app.action("promoteChordHold", 0, 0)
            self.assertEqual(int(app.query("activeRowIndex")), 0)
            self.assertEqual(int(app.query("activeRootSemitone")), 0)
            checkpoint = app.bridge.count()

            app.action("selectPreset", 2)
            expected = [f"n{note}l1i3Z" for note in (48, 52, 55)]
            switched = app.bridge.wait_for_lines(
                expected,
                start=checkpoint,
                timeout=3.0,
            )

            self.assertEqual(int(app.query("chordGateState")), 2)
            self.assertEqual(int(app.query("activeRowIndex")), 0)
            self.assertEqual(int(app.query("activeRootSemitone")), 0)
            for note in (48, 52, 55):
                self.assertIn(
                    f"n{note}l1i3Z",
                    switched,
                    "preset switch did not continue with the new C-major chord",
                )
            self.assertNotIn("zY0Z", switched)
            self.assertNotIn("S16384Z", switched)
            self.assertNotIn("S20480Z", switched)

            # The original physical button-up must still own the live voice.
            checkpoint = app.bridge.count()
            app.action("releaseChord", 0, 0)
            app.bridge.wait_for_lines(["l0i3Z"], start=checkpoint, timeout=3.0)

    def test_running_rhythm_switch_keeps_live_controls_and_clock_running(
        self,
    ) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)

            # Give three styles distinct remembered controls while stopped.
            app.action("setRhythmIndex", 0)
            app.action("setRhythmTempo", 100.0)
            app.action("setRhythmBusyness", 4.0)
            app.action("setRhythmChordActivity", 3.0)
            app.action("setRhythmBassActivity", 4.0)
            app.action("setRhythmIndex", 1)
            app.action("setRhythmTempo", 80.0)
            app.action("setRhythmBusyness", 1.0)
            app.action("setRhythmChordActivity", 2.0)
            app.action("setRhythmBassActivity", 1.0)
            app.action("setRhythmIndex", 2)
            app.action("setRhythmTempo", 73.0)
            app.action("setRhythmBusyness", 2.0)
            app.action("setRhythmChordActivity", 4.0)
            app.action("setRhythmBassActivity", 3.0)
            app.action("setRhythmIndex", 0)
            self.assertAlmostEqual(float(app.query("rhythmTempo")), 100.0)
            app.action("selectChord", 0, 0)
            app.action("setRowOctave", 0, 2)
            app.action("setBassVoicingShift", -2.0)
            app.action("toggleRhythmFill", 2)
            app.action("setRhythmFillDensity", 5.0)

            app.action("toggleRhythm")
            self.assertTrue(bool(app.query("rhythmRunning")))
            app.bridge.wait_idle(timeout=8.0)
            checkpoint = app.bridge.count()

            app.action("setRhythmIndex", 1)
            app.bridge.wait_idle(timeout=8.0)

            self.assertTrue(bool(app.query("rhythmRunning")))
            self.assertAlmostEqual(float(app.query("rhythmTempo")), 100.0)
            self.assertEqual(int(app.query("rhythmBusyness")), 4)
            self.assertEqual(int(app.query("rhythmChordActivity")), 3)
            self.assertEqual(int(app.query("rhythmBassActivity")), 4)
            self.assertEqual(int(app.query("bassVoicingShift")), -2)
            self.assertEqual(
                list(app.query("rhythmFillEnabled")),
                [False, False, True, False, False],
            )
            self.assertEqual(int(app.query("rhythmFillDensityIndex")), 5)
            self.assertEqual(int(app.action("octaveIndexForRow", 0)), 2)

            switched = app.bridge.lines_since(checkpoint)
            self.assertNotIn(
                "zY0Z",
                switched,
                "live style switch stopped AMY rhythm transport",
            )
            self.assertNotIn(
                "zY1Z",
                switched,
                "live style switch restarted AMY rhythm transport",
            )
            self.assertNotIn(
                "S16384Z",
                switched,
                "live style switch reset the sequencer timebase",
            )
            self.assertNotIn(
                "S20480Z",
                switched,
                "live style switch reset nested sequencer instances",
            )
            for synth in (0, 1, 4):
                self.assertNotIn(
                    f"l0i{synth}Z",
                    switched,
                    f"live style switch explicitly silenced synth {synth}",
                )

            self.assertTrue(
                any(
                    line.startswith("zQE") and "i0Z" in line
                    for line in switched
                ),
                "live style switch did not author nested drum events",
            )
            self.assertTrue(
                any(line.startswith("zQT") for line in switched),
                "live style switch did not quantize new drum role loops",
            )

            # Stopped switching still recalls the destination style's own
            # stored controls; only live switching transfers them.
            app.action("toggleRhythm")
            app.action("setRhythmIndex", 2)
            self.assertAlmostEqual(float(app.query("rhythmTempo")), 73.0)
            self.assertEqual(int(app.query("rhythmBusyness")), 2)
            self.assertEqual(int(app.query("rhythmChordActivity")), 4)
            self.assertEqual(int(app.query("rhythmBassActivity")), 3)

    def test_running_preset_switch_preserves_live_rhythm_controls(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)

            preset_one_path = app.home / ".omnichord" / "omni_presets" / "p1.json"
            preset_two_path = app.home / ".omnichord" / "omni_presets" / "p2.json"
            preset_one = json.loads(preset_one_path.read_text(encoding="utf-8"))
            preset_two = json.loads(preset_two_path.read_text(encoding="utf-8"))
            rhythm_one = str(preset_one["rhythm"]["selected"])
            rhythm_two = str(preset_two["rhythm"]["selected"])
            preset_one["rhythm"]["settings"][rhythm_one]["tempo"] = 100.0
            target_settings = preset_two["rhythm"]["settings"][rhythm_two]
            target_settings.update({
                "tempo": 75.0,
                "percussion_activity": 1,
                "chord_activity": 1,
                "bass_activity": 1,
            })
            preset_two["rhythm"]["bass_voicing_shift"] = 5
            preset_two["rhythm"]["chord_arpeggio_enabled"] = False
            preset_two["rhythm"]["chord_arpeggio_rate"] = 1
            preset_two["rhythm"]["chord_arpeggio_direction"] = "up"
            target_octaves = ("O5", "O1", "O2", "O6")
            for row, octave in zip(preset_two["chord_rows"], target_octaves):
                row["octave"] = octave
            preset_one_path.write_text(
                json.dumps(preset_one), encoding="utf-8"
            )
            preset_two_path.write_text(
                json.dumps(preset_two), encoding="utf-8"
            )

            app.action("selectPreset", 1)
            self.assertAlmostEqual(float(app.query("rhythmTempo")), 100.0)
            app.action("pressChord", 0, 0)
            app.action("releaseChord", 0, 0)
            app.action("toggleChordGate")
            app.action("setRowOctave", 0, 2)
            app.action("setRhythmBusyness", 4.0)
            app.action("setRhythmChordActivity", 3.0)
            app.action("setRhythmBassActivity", 4.0)
            app.action("setBassVoicingShift", -2.0)
            app.action("toggleRhythmFill", 4)
            app.action("setRhythmFillDensity", 6.0)
            app.action("setChordArpeggioRate", 3.0)
            app.action("toggleChordArpeggioDirection")
            app.action("toggleChordArpeggio")
            app.action("toggleRhythm")
            app.action("setRhythmTempo", 107.0)
            app.bridge.wait_idle(timeout=8.0)
            checkpoint = app.bridge.count()

            app.action("selectPreset", 2)
            # The HTTP action completes before the dedicated AMY writer drains
            # a preset's synth setup queue.  wait_idle() alone can therefore
            # observe the old idle period and return before the first new
            # serial line.  Wait for the musical continuation contract first.
            app.bridge.wait_for_line_match(
                lambda line: (
                    line.startswith("H")
                    and "n52" in line
                    and "i4Z" in line
                ),
                "continuing C-major rhythm chord",
                start=checkpoint,
                timeout=3.0,
            )
            app.bridge.wait_idle(timeout=8.0)

            self.assertTrue(bool(app.query("rhythmRunning")))
            self.assertAlmostEqual(float(app.query("rhythmTempo")), 107.0)
            self.assertEqual(int(app.query("rhythmBusyness")), 4)
            self.assertEqual(int(app.query("rhythmChordActivity")), 3)
            self.assertEqual(int(app.query("rhythmBassActivity")), 4)
            self.assertEqual(int(app.query("bassVoicingShift")), -2)
            self.assertEqual(
                list(app.query("rhythmFillEnabled")),
                [False, False, False, False, True],
            )
            self.assertEqual(int(app.query("rhythmFillDensityIndex")), 6)
            self.assertTrue(bool(app.query("chordArpeggioEnabled")))
            self.assertEqual(int(app.query("chordArpeggioRate")), 3)
            self.assertTrue(bool(app.query("chordArpeggioDescending")))
            self.assertEqual(int(app.query("chordGateState")), 1)
            self.assertEqual(int(app.query("activeRowIndex")), 0)
            self.assertEqual(int(app.query("activeRootSemitone")), 0)
            self.assertEqual(int(app.action("octaveIndexForRow", 0)), 2)
            self.assertEqual(int(app.action("octaveIndexForRow", 1)), 0)
            self.assertEqual(int(app.action("octaveIndexForRow", 2)), 1)
            self.assertEqual(int(app.action("octaveIndexForRow", 3)), 5)
            switched = app.bridge.lines_since(checkpoint)
            self.assertNotIn("zY0Z", switched)
            self.assertNotIn("zY1Z", switched)
            self.assertNotIn("S16384Z", switched)
            self.assertNotIn("S20480Z", switched)
            self.assertTrue(
                any(
                    line.startswith("H") and "n52" in line and "i4Z" in line
                    for line in switched
                ),
                "running preset switch did not continue the new C-major chord",
            )

            # STR stores the effective live tempo, not the dormant preset
            # tempo that was deliberately ignored during the live switch.
            app.action("storeSelectedPreset")
            stored = json.loads(preset_two_path.read_text(encoding="utf-8"))
            selected = str(stored["rhythm"]["selected"])
            self.assertAlmostEqual(
                float(stored["rhythm"]["settings"][selected]["tempo"]),
                107.0,
            )
            stored_settings = stored["rhythm"]["settings"][selected]
            self.assertEqual(int(stored_settings["percussion_activity"]), 4)
            self.assertEqual(int(stored_settings["chord_activity"]), 3)
            self.assertEqual(int(stored_settings["bass_activity"]), 4)
            self.assertEqual(stored_settings["fill_order"], [4])
            self.assertEqual(int(stored_settings["fill_density_bars"]), 2)
            self.assertEqual(int(stored["rhythm"]["bass_voicing_shift"]), -2)
            self.assertTrue(bool(stored["rhythm"]["chord_arpeggio_enabled"]))
            self.assertEqual(
                int(stored["rhythm"]["chord_arpeggio_rate"]), 3
            )
            self.assertEqual(
                str(stored["rhythm"]["chord_arpeggio_direction"]), "down"
            )
            self.assertEqual(
                tuple(row["octave"] for row in stored["chord_rows"]),
                ("O3", "O1", "O2", "O6"),
            )

    def test_stopped_preset_switch_loads_all_rhythm_controls(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)
            preset_two_path = app.home / ".omnichord" / "omni_presets" / "p2.json"
            preset_two = json.loads(preset_two_path.read_text(encoding="utf-8"))
            rhythm_two = str(preset_two["rhythm"]["selected"])
            preset_two["rhythm"]["settings"][rhythm_two].update({
                "tempo": 75.0,
                "percussion_activity": 1,
                "chord_activity": 0,
                "bass_activity": 1,
            })
            preset_two["rhythm"]["bass_voicing_shift"] = 5
            preset_two["rhythm"]["chord_arpeggio_enabled"] = True
            preset_two["rhythm"]["chord_arpeggio_rate"] = 4
            preset_two["rhythm"]["chord_arpeggio_direction"] = "down"
            target_octaves = ("O1", "O2", "O5", "O6")
            for row, octave in zip(preset_two["chord_rows"], target_octaves):
                row["octave"] = octave
            preset_two_path.write_text(
                json.dumps(preset_two), encoding="utf-8"
            )

            app.action("selectPreset", 1)
            app.action("pressChord", 0, 0)
            app.action("releaseChord", 0, 0)
            app.action("setRhythmBusyness", 4.0)
            app.action("setRhythmChordActivity", 3.0)
            app.action("setRhythmBassActivity", 4.0)
            app.action("setBassVoicingShift", -2.0)
            self.assertFalse(bool(app.query("rhythmRunning")))

            app.action("selectPreset", 2)
            self.assertAlmostEqual(float(app.query("rhythmTempo")), 75.0)
            self.assertEqual(int(app.query("rhythmBusyness")), 1)
            # Legacy presets could store the former visible zero level. It
            # now migrates to the lowest selectable activity.
            self.assertEqual(int(app.query("rhythmChordActivity")), 1)
            self.assertEqual(int(app.query("rhythmBassActivity")), 1)
            self.assertEqual(int(app.query("bassVoicingShift")), 5)
            self.assertTrue(bool(app.query("chordArpeggioEnabled")))
            self.assertEqual(int(app.query("chordArpeggioRate")), 4)
            self.assertTrue(bool(app.query("chordArpeggioDescending")))
            self.assertEqual(
                tuple(app.action("octaveIndexForRow", row) for row in range(4)),
                (0, 1, 4, 5),
            )

    def test_preset_loads_and_stores_the_riff_selector_fallback(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)
            preset_path = app.home / ".omnichord" / "omni_presets" / "p2.json"
            preset = json.loads(preset_path.read_text(encoding="utf-8"))
            preset["rhythm"]["selected"] = "pop_8"
            preset["rhythm"]["settings"]["pop_8"]["bass_activity"] = 5
            preset["rhythm"]["bass_riff_selector"] = 4
            preset["chord_rows"][0]["chord"] = "major"
            preset_path.write_text(json.dumps(preset), encoding="utf-8")

            app.action("selectPreset", 2)
            app.action("selectChord", 0, 0)
            self.assertTrue(bool(app.query("bassRiffMode")))
            self.assertEqual(int(app.query("bassRiffSelector")), 4)
            self.assertEqual(
                str(app.query("selectedBassRiffId")),
                "riff_0004_pop_8_root_fifth",
            )

            app.action("setBassRiffSelector", 2.0)
            app.action("storeSelectedPreset")
            stored = json.loads(preset_path.read_text(encoding="utf-8"))
            self.assertEqual(int(stored["rhythm"]["bass_riff_selector"]), 2)


if __name__ == "__main__":
    unittest.main()
