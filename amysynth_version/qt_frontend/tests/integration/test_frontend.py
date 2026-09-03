from __future__ import annotations

import unittest
import time

from harness import HeadlessApp


def bind_control(
    app: HeadlessApp,
    channel: int,
    controller: int,
    target: dict[str, object],
) -> None:
    app.action("injectMidiControl", channel, controller, 0)
    app.action("injectMidiControl", channel, controller, 1)
    states = {
        (item["channel"], item["controller"]): item["state"]
        for item in app.action("midiControlIndicators")
    }
    if states.get((channel, controller)) == "bound":
        # The first click intentionally only unlinks green to blue. Reusing
        # this controller requires a second, separate blue-to-red learn click.
        app.action("clickMidiControlIndicator", channel, controller)
        unlinked = {
            (item["channel"], item["controller"]): item["state"]
            for item in app.action("midiControlIndicators")
        }
        if unlinked.get((channel, controller)) != "blue":
            raise AssertionError("green indicator click did not unlink to blue")
    app.action("clickMidiControlIndicator", channel, controller)
    if not app.action("activateMidiControlTarget", target):
        raise AssertionError(f"could not bind MIDI target {target}")


class FrontendIntegrationTests(unittest.TestCase):
    def test_independent_master_volume_and_mute_are_bus_scoped(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)
            self.assertAlmostEqual(float(app.query("masterVolume")), 1.0)
            self.assertFalse(bool(app.query("masterMuted")))
            self.assertAlmostEqual(float(app.action("midiMasterVolume")), 1.0)
            self.assertFalse(bool(app.action("midiMasterMuted")))

            checkpoint = app.bridge.count()
            app.action("setMasterVolume", 0.42)
            lines = app.bridge.wait_for_lines(
                [f"y{bus}V0.42Z" for bus in range(4)],
                start=checkpoint,
                timeout=3.0,
            )
            self.assertFalse(any(line.startswith("y4V") for line in lines))

            checkpoint = app.bridge.count()
            app.action("toggleMasterMuted")
            app.bridge.wait_for_lines(
                [f"y{bus}V0Z" for bus in range(4)],
                start=checkpoint,
                timeout=3.0,
            )
            self.assertTrue(bool(app.query("masterMuted")))
            app.action("setMasterVolume", 0.73)
            self.assertAlmostEqual(float(app.query("masterVolume")), 0.73)
            checkpoint = app.bridge.count()
            app.action("toggleMasterMuted")
            app.bridge.wait_for_lines(
                [f"y{bus}V0.73Z" for bus in range(4)],
                start=checkpoint,
                timeout=3.0,
            )

            checkpoint = app.bridge.count()
            app.action("setMidiMasterVolume", 0.35)
            lines = app.bridge.wait_for_lines(
                [f"y{bus}V0.35Z" for bus in range(4, 11)],
                start=checkpoint,
                timeout=3.0,
            )
            self.assertFalse(any(line.startswith("y0V") for line in lines))
            app.action("toggleMidiMasterMuted")
            self.assertTrue(bool(app.action("midiMasterMuted")))

            app.action("selectPreset", 2)
            app.action("selectMidiPreset", 2)
            self.assertAlmostEqual(float(app.query("masterVolume")), 0.73)
            self.assertFalse(bool(app.query("masterMuted")))
            self.assertAlmostEqual(float(app.action("midiMasterVolume")), 0.35)
            self.assertTrue(bool(app.action("midiMasterMuted")))

            omni_target = {"screen": "omni", "kind": "master_volume"}
            bind_control(app, 12, 90, omni_target)
            app.action("injectMidiControl", 12, 90, 127)
            self.assertAlmostEqual(float(app.query("masterVolume")), 1.0)
            app.action("setMasterVolume", 0.2)
            self.assertAlmostEqual(float(app.query("masterVolume")), 1.0)
            app.action("toggleMasterMuted")
            self.assertTrue(bool(app.query("masterMuted")))

            midi_target = {"screen": "midi", "kind": "master_volume"}
            bind_control(app, 13, 91, midi_target)
            app.action("injectMidiControl", 13, 91, 127)
            self.assertAlmostEqual(float(app.action("midiMasterVolume")), 1.0)
            app.action("setMidiMasterVolume", 0.2)
            self.assertAlmostEqual(float(app.action("midiMasterVolume")), 1.0)

    def test_bound_numeric_targets_reject_manual_changes(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)

            chord_controls = list(app.query("chordCommonControls")) + list(
                app.query("chordExtraControls")
            )
            chord_control = chord_controls[0]
            chord_target = {
                "screen": "omni",
                "kind": "synth_control",
                "role": "chord",
                "control": str(chord_control["key"]),
            }
            bind_control(app, 1, 80, chord_target)
            app.action("injectMidiControl", 1, 80, 127)
            app.action(
                "setChordSynthControl",
                str(chord_control["key"]),
                float(chord_control["minimum"]),
            )
            current = list(app.query("chordCommonControls")) + list(
                app.query("chordExtraControls")
            )
            protected = next(
                item for item in current
                if item["key"] == chord_control["key"]
            )
            self.assertAlmostEqual(
                float(protected["value"]),
                float(protected["maximum"]),
            )

            volume_target = {
                "screen": "omni",
                "kind": "volume",
                "role": "chord",
            }
            bind_control(app, 2, 81, volume_target)
            app.action("injectMidiControl", 2, 81, 127)
            app.action("setChordVolume", 0.1)
            self.assertAlmostEqual(float(app.query("chordVolume")), 1.0)

            reverb_target = {"screen": "omni", "kind": "reverb_level"}
            bind_control(app, 3, 82, reverb_target)
            app.action("injectMidiControl", 3, 82, 127)
            app.action("setReverbLevel", 0.0)
            self.assertAlmostEqual(float(app.query("reverbLevel")), 3.0)

            voicing_target = {"screen": "omni", "kind": "bass_voicing"}
            bind_control(app, 4, 83, voicing_target)
            app.action("injectMidiControl", 4, 83, 127)
            app.action("setBassVoicingShift", -6.0)
            self.assertEqual(int(app.query("bassVoicingShift")), 6)

            app.action("setRhythmIndex", 0)
            app.action("setRowChordType", 0, 0)
            app.action("selectChord", 0, 0)
            app.action("setRhythmBassActivity", 5.0)
            riff_target = {
                "screen": "omni",
                "kind": "bass_riff_selector",
            }
            bind_control(app, 7, 86, riff_target)
            app.action("injectMidiControl", 7, 86, 127)
            app.action("setBassRiffSelector", 1.0)
            self.assertEqual(int(app.query("bassRiffSelector")), 5)

            tempo_target = {"screen": "omni", "kind": "rhythm_tempo"}
            bind_control(app, 5, 84, tempo_target)
            app.action("injectMidiControl", 5, 84, 64)
            protected_tempo = float(app.query("rhythmTempo"))
            app.action("setRhythmTempo", 40.0)
            app.action("beginTempoNudge", 1)
            time.sleep(0.25)
            app.action("endTempoNudge")
            self.assertAlmostEqual(
                float(app.query("rhythmTempo")),
                protected_tempo,
            )

            tuning_target = {
                "screen": "omni",
                "kind": "tuning_reference",
            }
            bind_control(app, 6, 85, tuning_target)
            app.action("injectMidiControl", 6, 85, 64)
            protected_tuning = int(app.query("tuningReference"))
            app.action("setTuningReference", 415)
            app.action("beginPitchBend", 1)
            time.sleep(0.25)
            app.action("endPitchBend")
            self.assertEqual(
                int(app.query("tuningReference")),
                protected_tuning,
            )

            # Recoupling must take its value from the bound side, even
            # when the user clicks the link on the other screen.  Two
            # independently bound, divergent references cannot be coupled
            # without overwriting one of their MIDI-owned values.
            app.action("setMidiTuningCoupled", False)
            app.action("setMidiTuningReference", 415)
            self.assertTrue(bool(app.action("coupleTuningFromMidi")))
            self.assertEqual(
                int(app.query("tuningReference")),
                protected_tuning,
            )
            app.action("setMidiTuningCoupled", False)
            midi_tuning_target = {
                "screen": "midi",
                "kind": "tuning_reference",
            }
            bind_control(app, 9, 88, midi_tuning_target)
            app.action("injectMidiControl", 9, 88, 127)
            app.action("syncMidiTuningFromOmni")
            self.assertFalse(bool(app.action("coupleTuningFromOmni")))
            self.assertEqual(
                int(app.query("tuningReference")),
                protected_tuning,
            )

            midi_controls = list(app.action("midiCommonControls", 0)) + list(
                app.action("midiExtraControls", 0)
            )
            midi_control = midi_controls[0]
            midi_target = {
                "screen": "midi",
                "kind": "synth_control",
                "row": 0,
                "control": str(midi_control["key"]),
            }
            bind_control(app, 7, 86, midi_target)
            app.action("injectMidiControl", 7, 86, 127)
            app.action(
                "setMidiSynthControl",
                0,
                str(midi_control["key"]),
                float(midi_control["minimum"]),
            )
            midi_current = list(app.action("midiCommonControls", 0)) + list(
                app.action("midiExtraControls", 0)
            )
            midi_protected = next(
                item for item in midi_current
                if item["key"] == midi_control["key"]
            )
            self.assertAlmostEqual(
                float(midi_protected["value"]),
                float(midi_protected["maximum"]),
            )

            midi_volume_target = {
                "screen": "midi",
                "kind": "volume",
                "row": 0,
            }
            bind_control(app, 8, 87, midi_volume_target)
            app.action("injectMidiControl", 8, 87, 127)
            app.action("setMidiVolume", 0, 0.1)
            self.assertAlmostEqual(float(app.action("midiVolume", 0)), 1.0)

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

    def test_chord_gate_only_controls_sequencer_and_strum_stays_live(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)
            self.assertEqual(int(app.query("chordGateState")), 2)
            self.assertEqual(str(app.query("chordGateButtonText")), "CHORD\nOFF")

            # Activity zero is no longer user-selectable. It is reserved as
            # the transient effective value while a manual chord takes over.
            app.action("setRhythmChordActivity", 0.0)
            self.assertEqual(int(app.query("rhythmChordActivity")), 1)
            app.action("setRhythmChordActivity", 3.0)

            # The binary gate can be operated before a chord is known and
            # remains independent of subsequent chord selection.
            app.action("toggleChordGate")
            self.assertEqual(int(app.query("chordGateState")), 1)
            self.assertEqual(str(app.query("chordGateButtonText")), "CHORD\nON")
            app.action("toggleChordGate")
            self.assertEqual(int(app.query("chordGateState")), 2)
            self.assertEqual(str(app.query("chordGateButtonText")), "CHORD\nOFF")

            # A tap starts manual synth 3 and selects the chord for strum and
            # accompaniment, but never enters the temporary hold override.
            app.action("pressChord", 1, 9)
            self.assertEqual(int(app.query("rhythmChordActivity")), 3)
            app.action("releaseChord", 1, 9)
            app.bridge.wait_idle(timeout=3.0)
            self.assertEqual(int(app.query("rhythmChordActivity")), 3)
            self.assertEqual(int(app.query("chordGateState")), 2)
            self.assertEqual(int(app.query("activeRowIndex")), 1)
            self.assertEqual(int(app.query("activeRootSemitone")), 9)

            # Qt reports a long-press separately from pointer-down. The backend
            # consequence is tested explicitly here; the packaged-QML smoke
            # covers Qt's actual gesture recognition.
            app.action("pressChord", 0, 0)
            self.assertEqual(int(app.query("rhythmChordActivity")), 3)
            app.action("promoteChordHold", 0, 0)
            self.assertEqual(int(app.query("rhythmChordActivity")), 0)
            self.assertEqual(int(app.query("activeRowIndex")), 0)
            self.assertEqual(int(app.query("activeRootSemitone")), 0)
            release_start = app.bridge.count()
            app.action("releaseChord", 0, 0)
            self.assertEqual(int(app.query("rhythmChordActivity")), 3)
            app.bridge.wait_for_lines(
                ["l0i3Z"],
                start=release_start,
                timeout=0.3,
            )

            # Keeping the gate off must not erase the remembered identity.
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
            self.assertFalse(
                any(
                    "i3" in line and "n" in line and "l1" in line
                    for line in app.bridge.lines_since(start)
                ),
                "CHORD ON retriggered the remembered manual chord",
            )

            # Even while the same chord button is physically held, CHORD OFF
            # owns only the automatic synth-4 lane. The manual synth-3 voice
            # must remain alive until the matching button release.
            app.action("pressChord", 0, 0)
            app.action("promoteChordHold", 0, 0)
            self.assertEqual(int(app.query("rhythmChordActivity")), 0)
            self.assertEqual(int(app.query("chordGateState")), 1)
            start = app.bridge.count()
            app.action("toggleChordGate")
            app.bridge.wait_idle(timeout=3.0)
            self.assertEqual(int(app.query("chordGateState")), 2)
            self.assertNotIn("l0i3Z", app.bridge.lines_since(start))

            start = app.bridge.count()
            app.action("releaseChord", 0, 0)
            app.bridge.wait_for_lines(["l0i3Z"], start=start, timeout=3.0)

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

    def test_chord_arpeggio_controls_are_independent_and_clamped(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)
            self.assertFalse(bool(app.query("chordArpeggioEnabled")))
            self.assertEqual(int(app.query("chordArpeggioRate")), 1)
            self.assertFalse(bool(app.query("chordArpeggioDescending")))
            self.assertEqual(
                str(app.query("chordArpeggioDirectionLabel")), "U"
            )

            app.action("setChordArpeggioRate", 9.0)
            self.assertEqual(int(app.query("chordArpeggioRate")), 4)
            self.assertFalse(bool(app.query("chordArpeggioEnabled")))

            app.action("toggleChordArpeggioDirection")
            self.assertTrue(bool(app.query("chordArpeggioDescending")))
            self.assertEqual(
                str(app.query("chordArpeggioDirectionLabel")), "D"
            )
            self.assertFalse(bool(app.query("chordArpeggioEnabled")))

            app.action("toggleChordArpeggio")
            self.assertTrue(bool(app.query("chordArpeggioEnabled")))
            self.assertEqual(int(app.query("rhythmChordActivity")), 1)

    def test_riff_selector_tracks_the_playing_riff_across_chord_sets(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)
            app.action("setRhythmIndex", 0)  # pop_8
            app.action("setRowChordType", 0, 1)  # minor
            app.action("selectChord", 0, 0)
            app.action("setRhythmBassActivity", 5.0)

            self.assertTrue(bool(app.query("bassRiffMode")))
            self.assertEqual(int(app.query("bassRiffSelectorMaximum")), 5)
            self.assertEqual(int(app.query("bassRiffSelector")), 1)
            app.action("setBassRiffSelector", 5.0)
            self.assertEqual(
                str(app.query("selectedBassRiffId")),
                "riff_0006_pop_8_minor_triadic",
            )

            # With transport stopped, compatibility alone does not make a riff
            # "currently playing": a changed set falls back to the preset.
            app.action("setRowChordType", 0, 33)  # dominant7_sharp9
            self.assertEqual(int(app.query("bassRiffSelector")), 1)

            app.action("setRowChordType", 0, 1)
            app.action("setBassRiffSelector", 5.0)
            if not bool(app.query("bassRunning")):
                app.action("toggleBassRunning")
            app.action("toggleRhythm")
            app.bridge.wait_idle(timeout=8.0)

            # The same riff is sixth in the new compatible set. While it is
            # playing, identity wins and the slider follows its new position.
            app.action("setRowChordType", 0, 33)
            self.assertEqual(int(app.query("bassRiffSelector")), 6)
            self.assertEqual(
                str(app.query("selectedBassRiffId")),
                "riff_0006_pop_8_minor_triadic",
            )

            # That riff is not major-compatible, so this set change uses the
            # preset/default selector position instead.
            app.action("setRowChordType", 0, 0)
            self.assertEqual(int(app.query("bassRiffSelector")), 1)
            self.assertEqual(
                str(app.query("selectedBassRiffId")),
                "riff_0001_pop_8_root_pedal",
            )

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
            app.action("clickMidiControlIndicator", 1, 74)
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

            app.action("manuallyEditMidiControlTarget", midi_target)
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
            app.action("clickMidiControlIndicator", 2, 75)
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
            app.action("clickMidiControlIndicator", 3, 76)
            self.assertTrue(app.action("activateMidiControlTarget", target))

            checkpoint = app.bridge.count()
            app.action("injectMidiControl", 3, 76, 127)
            expected = [f"y{bus}h3,0.5,0.5Z" for bus in (1, 2, 3)]
            mapped_lines = app.bridge.wait_for_lines(
                expected,
                start=checkpoint,
                timeout=3.0,
            )
            self.assertAlmostEqual(float(app.query("reverbLevel")), 3.0)
            for command in expected:
                self.assertIn(command, mapped_lines)

            app.action("manuallyEditMidiControlTarget", target)
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
            app.action("clickMidiControlIndicator", 4, 77)
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
            synth_lines = app.bridge.wait_for_line_match(
                lambda line: "i5" in line and "n" in line and "l" in line,
                "MIDI synth-5 preview note",
                start=start,
                timeout=3.0,
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
            drum_lines = app.bridge.wait_for_line_match(
                lambda line: line.startswith("p") and "i11Z" in line,
                "Drum Kit 0 synth-11 sample hit",
                start=start,
                timeout=3.0,
            )
            self.assertFalse(
                any("drum_kit_0" in line for line in drum_lines),
                "MIDI-only drum label leaked into AMY wire protocol",
            )
            app.action("midiPreviewEnd")


if __name__ == "__main__":
    unittest.main()
