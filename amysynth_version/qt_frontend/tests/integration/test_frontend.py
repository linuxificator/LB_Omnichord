from __future__ import annotations

import unittest

from harness import HeadlessApp


class FrontendIntegrationTests(unittest.TestCase):
    def test_startup_and_representative_chord_actions(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)
            startup = app.bridge.lines_since(0)

            self.assertIn("zY0Z", startup)
            self.assertIn("S12288Z", startup)
            self.assertTrue(any("i0iv4in1Z" in line for line in startup))
            for synth in (1, 2, 3, 4):
                self.assertTrue(
                    any(f"i{synth}" in line and "K" in line for line in startup),
                    f"startup did not configure synth {synth}",
                )

            # Current factory P1 selects HARM tuning. Row 0 is C minor/O3.
            start = app.bridge.count()
            app.action("pressChord", 0, 0)
            app.bridge.wait_for_lines(
                [
                    "l0i3Z",
                    "n48l1i3Z",
                    "n51.1564129l1i3Z",
                    "n55.01955l1i3Z",
                ],
                start=start,
            )
            app.action("releaseChord", 0, 0)

            # A second chord catches accidental hard-coded first-row behavior.
            start = app.bridge.count()
            app.action("pressChord", 1, 9)
            app.bridge.wait_for_lines(
                [
                    "l0i3Z",
                    "n57l1i3Z",
                    "n60.1564129l1i3Z",
                    "n64.01955l1i3Z",
                    "n66.6882591l1i3Z",
                ],
                start=start,
            )
            app.action("releaseChord", 1, 9)

    def test_chord_gate_remembers_last_chord_and_strum_stays_live(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)
            self.assertEqual(int(app.query("chordGateState")), 0)

            app.action("pressChord", 0, 0)
            app.action("releaseChord", 0, 0)
            app.bridge.wait_idle(timeout=3.0)
            self.assertEqual(int(app.query("chordGateState")), 1)
            self.assertEqual(int(app.query("activeRowIndex")), 0)
            self.assertEqual(int(app.query("activeRootSemitone")), 0)

            app.action("toggleChordGate")
            app.bridge.wait_idle(timeout=3.0)
            self.assertEqual(int(app.query("chordGateState")), 2)
            # Gating the chord must not erase the remembered chord identity.
            self.assertEqual(int(app.query("activeRowIndex")), 0)
            self.assertEqual(int(app.query("activeRootSemitone")), 0)

            start = app.bridge.count()
            app.action("strumTap", 0.5)
            app.bridge.wait_idle(timeout=3.0)
            self.assertTrue(
                any(
                    "i2" in line and "n" in line and "l" in line
                    for line in app.bridge.lines_since(start)
                ),
                "strum emitted no synth-2 note while chord gate was off",
            )

            start = app.bridge.count()
            app.action("toggleChordGate")
            app.bridge.wait_idle(timeout=3.0)
            self.assertEqual(int(app.query("chordGateState")), 1)
            self.assertTrue(
                any(
                    "i3" in line and "n" in line and "l1" in line
                    for line in app.bridge.lines_since(start)
                ),
                "CHORD ON did not retrigger the remembered manual chord",
            )

    def test_bass_voicing_property_is_centered_and_stepwise(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)
            self.assertEqual(int(app.query("bassVoicingShift")), 0)
            app.action("setBassVoicingShift", -1.0)
            self.assertEqual(int(app.query("bassVoicingShift")), -1)
            app.action("setBassVoicingShift", 1.0)
            self.assertEqual(int(app.query("bassVoicingShift")), 1)
            app.action("setBassVoicingShift", 99.0)
            self.assertEqual(int(app.query("bassVoicingShift")), 6)

    def test_sustain_frontend_range_and_numeric_value(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)
            controls = list(app.query("chordCommonControls")) + list(
                app.query("chordExtraControls")
            )
            sustain = next(
                control for control in controls if control["key"] == "sustain"
            )
            self.assertEqual(float(sustain["minimum"]), 0.0)
            self.assertEqual(float(sustain["maximum"]), 1.0)
            self.assertGreaterEqual(float(sustain["value"]), 0.0)
            self.assertLessEqual(float(sustain["value"]), 1.0)

    def test_reverb_level_reaches_three_and_is_clamped_there(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)
            start = app.bridge.count()

            app.action("setReverbLevel", 3.0)
            app.bridge.wait_idle(timeout=3.0)

            self.assertAlmostEqual(float(app.query("reverbLevel")), 3.0)
            lines = app.bridge.lines_since(start)
            for bus in (1, 2, 3):
                self.assertIn(
                    f"y{bus}h3,0.5,0.5Z",
                    lines,
                    f"reverb level 3.0 did not reach AMY bus {bus}",
                )

            app.action("setReverbLevel", 9.0)
            self.assertAlmostEqual(float(app.query("reverbLevel")), 3.0)

    def test_midi_rows_use_real_catalog_controls_and_channels_one_to_six(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)

            self.assertEqual(
                [int(app.action("midiChannel", row)) for row in range(6)],
                [1, 2, 3, 4, 5, 6],
            )

            names = list(app.query("midiSynthNames"))
            self.assertGreater(len(names), 1)
            self.assertEqual(names[-1], "Drum Kit 0")

            controls = list(app.action("midiExtraControls", 0)) + list(
                app.action("midiCommonControls", 0)
            )
            keys = {str(control["key"]) for control in controls}
            self.assertIn("filter_hz", keys)
            self.assertIn("attack_ms", keys)
            self.assertNotIn("brightness", keys)

            app.action("setMidiSynthIndex", 0, len(names) - 1)
            self.assertEqual(list(app.action("midiExtraControls", 0)), [])
            self.assertEqual(list(app.action("midiCommonControls", 0)), [])

    def test_midi_control_learn_routes_hidden_midi_and_omni_instruments(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)

            midi_index = int(app.action("midiSynthIndex", 0))
            midi_controls = list(app.action("midiExtraControls", 0)) + list(
                app.action("midiCommonControls", 0)
            )
            midi_control = midi_controls[0]
            midi_target = {
                "screen": "midi",
                "kind": "synth_control",
                "row": 0,
                "control": midi_control["key"],
            }
            app.action("injectMidiControl", 1, 74, 0)
            app.action("injectMidiControl", 1, 74, 1)
            app.action("selectMidiControlIndicator", 1, 74)
            self.assertTrue(app.action("activateMidiControlTarget", midi_target))

            other_midi = 1 if midi_index != 1 else 2
            app.action("setMidiSynthIndex", 0, other_midi)
            self.assertNotEqual(int(app.action("midiSynthIndex", 0)), midi_index)
            app.action("injectMidiControl", 1, 74, 127)
            app.bridge.wait_idle(timeout=3.0)
            self.assertEqual(int(app.action("midiSynthIndex", 0)), midi_index)
            restored = list(app.action("midiExtraControls", 0)) + list(
                app.action("midiCommonControls", 0)
            )
            mapped = next(
                item for item in restored if item["key"] == midi_control["key"]
            )
            self.assertAlmostEqual(
                float(mapped["value"]),
                float(mapped["maximum"]),
            )

            app.action("tapMidiControlTarget", midi_target)
            states = {
                (item["channel"], item["controller"]): item["state"]
                for item in app.action("midiControlIndicators")
            }
            self.assertEqual(states[(1, 74)], "bound")
            app.action("tapMidiControlTarget", midi_target)
            states = {
                (item["channel"], item["controller"]): item["state"]
                for item in app.action("midiControlIndicators")
            }
            self.assertEqual(states[(1, 74)], "blue")

            omni_index = int(app.query("selectedChordSynthIndex"))
            omni_controls = list(app.query("chordExtraControls")) + list(
                app.query("chordCommonControls")
            )
            omni_control = omni_controls[0]
            omni_target = {
                "screen": "omni",
                "kind": "synth_control",
                "role": "chord",
                "control": omni_control["key"],
            }
            app.action("injectMidiControl", 2, 75, 0)
            app.action("injectMidiControl", 2, 75, 1)
            app.action("selectMidiControlIndicator", 2, 75)
            self.assertTrue(app.action("activateMidiControlTarget", omni_target))

            other_omni = 1 if omni_index != 1 else 2
            app.action("setChordSynthIndex", other_omni)
            self.assertNotEqual(int(app.query("selectedChordSynthIndex")), omni_index)
            app.action("injectMidiControl", 2, 75, 127)
            app.bridge.wait_idle(timeout=3.0)
            self.assertEqual(int(app.query("selectedChordSynthIndex")), omni_index)
            restored_omni = list(app.query("chordExtraControls")) + list(
                app.query("chordCommonControls")
            )
            mapped_omni = next(
                item
                for item in restored_omni
                if item["key"] == omni_control["key"]
            )
            self.assertAlmostEqual(
                float(mapped_omni["value"]),
                float(mapped_omni["maximum"]),
            )

    def test_midi_control_updates_omni_reverb_and_blue_returns_idle(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)
            target = {"screen": "omni", "kind": "reverb_level"}

            app.action("injectMidiControl", 3, 76, 0)
            app.action("injectMidiControl", 3, 76, 1)
            app.action("selectMidiControlIndicator", 3, 76)
            self.assertTrue(app.action("activateMidiControlTarget", target))

            checkpoint = app.bridge.count()
            app.action("injectMidiControl", 3, 76, 127)
            app.bridge.wait_idle(timeout=3.0)
            self.assertAlmostEqual(float(app.query("reverbLevel")), 3.0)
            mapped_lines = app.bridge.lines_since(checkpoint)
            for bus in (1, 2, 3):
                self.assertIn(f"y{bus}h3,0.5,0.5Z", mapped_lines)

            app.action("moveMidiControlTarget", target)
            states = {
                (item["channel"], item["controller"]): item["state"]
                for item in app.action("midiControlIndicators")
            }
            self.assertEqual(states[(3, 76)], "blue")

            app.action("injectMidiControl", 3, 76, 64)
            states = {
                (item["channel"], item["controller"]): item["state"]
                for item in app.action("midiControlIndicators")
            }
            self.assertEqual(states[(3, 76)], "idle")
            self.assertAlmostEqual(float(app.query("reverbLevel")), 3.0)

    def test_midi_control_maps_midi_reverb_to_three(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)
            target = {"screen": "midi", "kind": "reverb_level"}
            app.action("injectMidiControl", 4, 77, 0)
            app.action("injectMidiControl", 4, 77, 1)
            app.action("selectMidiControlIndicator", 4, 77)
            self.assertTrue(app.action("activateMidiControlTarget", target))

            checkpoint = app.bridge.count()
            app.action("injectMidiControl", 4, 77, 127)
            expected = [f"y{bus}h3,0.58,0.52Z" for bus in range(4, 10)]
            lines = app.bridge.wait_for_lines(
                expected,
                start=checkpoint,
                timeout=3.0,
            )
            for command in expected:
                self.assertIn(command, lines)

    def test_midi_presets_select_and_configure_their_rows(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)

            first_index = int(app.action("midiSynthIndex", 0))
            start = app.bridge.count()
            app.action("selectMidiPreset", 2)
            app.bridge.wait_idle(timeout=3.0)

            self.assertEqual(int(app.query("selectedMidiPreset")), 2)
            self.assertNotEqual(
                int(app.action("midiSynthIndex", 0)),
                first_index,
            )
            self.assertTrue(
                any(
                    "i5" in line and "K" in line
                    for line in app.bridge.lines_since(start)
                ),
                "MIDI preset selection did not configure its first row",
            )

    def test_midi_strum_previews_synth_and_drumkit_without_changing_omni_catalog(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)
            names = list(app.query("midiSynthNames"))

            # With no selected Omnichord chord yet, MIDI preview falls back to
            # C major and still emits a normal MIDI synth-5 strum note.
            self.assertEqual(int(app.query("activeRowIndex")), -1)
            start = app.bridge.count()
            app.action("midiPreviewStart", 0, 0.5, True)
            app.bridge.wait_idle(timeout=3.0)
            synth_lines = app.bridge.lines_since(start)
            self.assertTrue(
                any("i5" in line and "n" in line and "l" in line for line in synth_lines),
                "MIDI synth preview emitted no synth-5 note",
            )
            app.action("midiPreviewEnd")
            app.action("finishMidiPreview")
            app.bridge.wait_idle(timeout=3.0)

            # Drum Kit 0 is MIDI-only and previews through MIDI drum synth 11;
            # selecting it must not attempt to configure synth 5 with a
            # fake ROM patch/program.
            app.action("setMidiSynthIndex", 0, len(names) - 1)
            start = app.bridge.count()
            app.action("midiPreviewStart", 0, 0.5, True)
            app.bridge.wait_idle(timeout=3.0)
            drum_lines = app.bridge.lines_since(start)
            self.assertTrue(
                any(line.startswith("p") and "i11Z" in line for line in drum_lines),
                "Drum Kit 0 preview emitted no synth-11 sample hit",
            )
            self.assertFalse(
                any("drum_kit_0" in line for line in drum_lines),
                "MIDI-only drum label leaked into AMY wire protocol",
            )
            app.action("midiPreviewEnd")


if __name__ == "__main__":
    unittest.main()
