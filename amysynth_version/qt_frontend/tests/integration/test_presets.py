from __future__ import annotations

import json
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

            protected_attack = changed_control_value(bound_control)
            changed_release = changed_control_value(unbound_control)
            app.action("setChordSynthControl", "attack_ms", protected_attack)
            app.action("setChordSynthControl", "release_ms", changed_release)
            app.action("setChordVolume", 0.91)
            app.action("resetChordSynthToPreset")

            self.assertEqual(
                int(app.query("selectedChordSynthIndex")),
                stored_index,
            )
            self.assertAlmostEqual(float(app.query("chordVolume")), 0.91)
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

            self.assertAlmostEqual(float(app.query("chordVolume")), 0.91)
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
            protected_attack = changed_control_value(bound_control)

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
            app.action("setMidiSynthControl", row, "attack_ms", protected_attack)
            app.action(
                "setMidiSynthControl",
                row,
                "release_ms",
                changed_control_value(unbound_control),
            )
            app.action("setMidiVolume", row, 0.91)
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
            self.assertAlmostEqual(float(app.action("midiVolume", row)), 0.91)

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

            self.assertAlmostEqual(float(app.action("midiVolume", row)), 0.91)
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
            checkpoint = app.bridge.count()

            app.action("selectPreset", 2)
            expected = [f"n{note}l1i3Z" for note in (48, 52, 55)]
            switched = app.bridge.wait_for_lines(
                expected,
                start=checkpoint,
                timeout=3.0,
            )

            self.assertEqual(int(app.query("chordGateState")), 1)
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

            # The original physical button-up must still own the live voice.
            checkpoint = app.bridge.count()
            app.action("releaseChord", 0, 0)
            app.bridge.wait_for_lines(["l0i3Z"], start=checkpoint, timeout=3.0)

    def test_running_rhythm_switch_keeps_tempo_and_clock_running(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)

            # Give two styles distinct remembered tempos while stopped.
            app.action("setRhythmIndex", 0)
            app.action("setRhythmTempo", 100.0)
            app.action("setRhythmIndex", 1)
            app.action("setRhythmTempo", 80.0)
            app.action("setRhythmIndex", 0)
            self.assertAlmostEqual(float(app.query("rhythmTempo")), 100.0)

            app.action("toggleRhythm")
            self.assertTrue(bool(app.query("rhythmRunning")))
            app.bridge.wait_idle(timeout=8.0)
            checkpoint = app.bridge.count()

            app.action("setRhythmIndex", 1)
            app.bridge.wait_idle(timeout=8.0)

            self.assertTrue(bool(app.query("rhythmRunning")))
            self.assertAlmostEqual(float(app.query("rhythmTempo")), 100.0)

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
            for synth in (0, 1, 4):
                self.assertNotIn(
                    f"l0i{synth}Z",
                    switched,
                    f"live style switch explicitly silenced synth {synth}",
                )

            self.assertTrue(
                any(line.startswith("H") and "i0Z" in line for line in switched),
                "live style switch did not replace tagged drum events",
            )

            # Stopped switching still recalls the destination style's own
            # stored tempo; only live switching transfers tempo.
            app.action("toggleRhythm")
            app.action("setRhythmIndex", 2)
            app.action("setRhythmTempo", 73.0)
            app.action("setRhythmIndex", 0)
            self.assertAlmostEqual(float(app.query("rhythmTempo")), 100.0)
            app.action("setRhythmIndex", 2)
            self.assertAlmostEqual(float(app.query("rhythmTempo")), 73.0)

    def test_running_preset_switch_preserves_live_tempo_and_transport(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)

            preset_one_path = app.home / ".omnichord" / "omni_presets" / "p1.json"
            preset_two_path = app.home / ".omnichord" / "omni_presets" / "p2.json"
            preset_one = json.loads(preset_one_path.read_text(encoding="utf-8"))
            preset_two = json.loads(preset_two_path.read_text(encoding="utf-8"))
            rhythm_one = str(preset_one["rhythm"]["selected"])
            rhythm_two = str(preset_two["rhythm"]["selected"])
            preset_one["rhythm"]["settings"][rhythm_one]["tempo"] = 100.0
            preset_two["rhythm"]["settings"][rhythm_two]["tempo"] = 75.0
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
            app.action("toggleRhythm")
            app.action("setRhythmTempo", 107.0)
            app.bridge.wait_idle(timeout=8.0)
            checkpoint = app.bridge.count()

            app.action("selectPreset", 2)
            app.bridge.wait_idle(timeout=8.0)

            self.assertTrue(bool(app.query("rhythmRunning")))
            self.assertAlmostEqual(float(app.query("rhythmTempo")), 107.0)
            self.assertEqual(int(app.query("chordGateState")), 1)
            self.assertEqual(int(app.query("activeRowIndex")), 0)
            self.assertEqual(int(app.query("activeRootSemitone")), 0)
            switched = app.bridge.lines_since(checkpoint)
            self.assertNotIn("zY0Z", switched)
            self.assertNotIn("zY1Z", switched)
            self.assertNotIn("S16384Z", switched)
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


if __name__ == "__main__":
    unittest.main()
