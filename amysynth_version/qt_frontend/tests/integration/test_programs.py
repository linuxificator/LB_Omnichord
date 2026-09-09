from __future__ import annotations

import re
import unittest

from catalog import synths
from harness import HeadlessApp


class ProgramIntegrationTests(unittest.TestCase):
    def test_physical_strings_configures_karplus_strong_without_fake_patch(self) -> None:
        physical_index = len(synths())  # appended after the JSON ROM catalogue
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=10.0)
            start = app.bridge.count()
            app.action("setStrumSynthIndex", physical_index)
            app.bridge.wait_for_lines(
                ["i2iv2in1iy2Z", "v0w6b0.985i2Z"],
                start=start,
                timeout=8.0,
            )
            app.bridge.wait_idle(timeout=8.0)

            controls = app.query("strumExtraControls")
            self.assertEqual(len(controls), 1, controls)
            self.assertEqual(controls[0]["key"], "ks_feedback")
            self.assertEqual(controls[0]["label"], "DECAY")
            self.assertGreaterEqual(float(controls[0]["minimum"]), 0.90)
            self.assertGreater(float(controls[0]["maximum"]), 0.99)

            lines = app.bridge.lines_since(start)
            self.assertFalse(
                any(line.startswith("K") and "i2" in line for line in lines),
                lines,
            )

            edit = app.bridge.count()
            app.action("setStrumSynthControl", "ks_feedback", 0.99)
            app.bridge.wait_for_lines(["v0b0.99i2Z"], start=edit, timeout=5.0)
            edit_lines = app.bridge.lines_since(edit)
            self.assertFalse(any(line.startswith("K") for line in edit_lines))

            app.action("selectChord", 0, 0)
            high_note = app.bridge.count()
            app.action("strumTap", 0.0)
            app.bridge.wait_for_lines(["i2iV4.2Z"], start=high_note, timeout=5.0)

    def test_physical_chord_keeps_warning_policy_on_automatic_synth_only(self) -> None:
        physical_index = len(synths())
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=10.0)
            start = app.bridge.count()
            app.action("setChordSynthIndex", physical_index)
            app.bridge.wait_for_lines(
                [
                    "i3iv7in1iy3Z",
                    "i4iv7in1iy3if8Z",
                ],
                start=start,
                timeout=8.0,
            )
            app.bridge.wait_idle(timeout=8.0)

            lines = app.bridge.lines_since(start)
            self.assertFalse(
                any("i3" in line and "if8" in line for line in lines)
            )

    def test_tb303_is_available_to_every_role_with_bass_only_articulation(self) -> None:
        tb303_index = len(synths()) + 1  # physical strings is appended first
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=10.0)

            start = app.bridge.count()
            app.action("setBassSynthIndex", tb303_index)
            app.bridge.wait_for_lines(
                [
                    "i1iv1in1iy1Z",
                    "v0G4A2,1,0,1,20,0i1Z",
                    "v0w2i1Z",
                    "v0F400,,,,2i1Z",
                    "v0R1.2i1Z",
                    "v0B0,1,250,0,20,0i1Z",
                ],
                start=start,
                timeout=8.0,
            )
            controls = list(app.query("bassCommonControls")) + list(
                app.query("bassExtraControls")
            )
            self.assertEqual(len(controls), 7)
            self.assertEqual(
                {str(control["key"]) for control in controls},
                {
                    "waveform",
                    "filter_hz",
                    "resonance",
                    "filter_env_octaves",
                    "filter_decay_ms",
                    "accent_amount",
                    "portamento_ms",
                },
            )

            if not bool(app.query("bassRunning")):
                app.action("toggleBassRunning")
            app.action("selectChord", 0, 0)
            app.action("setRhythmBassActivity", 2.0)
            rhythm_start = app.bridge.count()
            app.action("toggleRhythm")
            app.bridge.wait_for_line_match(
                lambda line: re.match(r"^H\d+,\d+,56a", line) is not None,
                "TB-303-articulated bass event",
                start=rhythm_start,
                timeout=8.0,
            )

            ordinary_start = app.bridge.count()
            app.action("setBassSynthIndex", 0)
            app.bridge.wait_for_lines(["HR56Z"], start=ordinary_start, timeout=8.0)
            ordinary_lines = app.bridge.wait_for_line_match(
                lambda line: re.match(r"^H\d+,\d+,56n", line) is not None,
                "ordinary bass event after leaving TB-303",
                start=ordinary_start,
                timeout=8.0,
            )
            last_reset = max(
                index
                for index, line in enumerate(ordinary_lines)
                if line == "HR56Z"
            )
            self.assertFalse(
                any(
                    re.match(r"^H\d+,\d+,56a", line)
                    for line in ordinary_lines[last_reset + 1 :]
                )
            )

            chord_start = app.bridge.count()
            app.action("setChordSynthIndex", tb303_index)
            app.bridge.wait_for_lines(
                ["i3iv7in1iy3Z", "i4iv7in1iy3if8Z"],
                start=chord_start,
                timeout=8.0,
            )

            names = list(app.query("midiSynthNames"))
            self.assertEqual(names[tb303_index], "TB-303")
            midi_start = app.bridge.count()
            app.action("setMidiSynthIndex", 0, tb303_index)
            app.bridge.wait_for_lines(
                ["i5iv4in1iy4Z", "v0G4A2,1,0,1,20,0i5Z"],
                start=midi_start,
                timeout=8.0,
            )


if __name__ == "__main__":
    unittest.main()
