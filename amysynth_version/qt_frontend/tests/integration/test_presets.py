from __future__ import annotations

import json
import unittest

from catalog import control_default, entry_for_index, synth_index
from harness import HeadlessApp


class PresetIntegrationTests(unittest.TestCase):
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
            preset_path = app.home / ".omnichord" / "p1.json"
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

    def test_rhythm_running_is_live_state_not_preset_state(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)
            self.assertFalse(bool(app.query("rhythmRunning")))

            # Storing while the rhythm is running must not persist that state.
            app.action("toggleRhythm")
            self.assertTrue(bool(app.query("rhythmRunning")))
            app.action("storeSelectedPreset")

            preset_path = app.home / ".omnichord" / "p1.json"
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

            preset_one_path = app.home / ".omnichord" / "p1.json"
            preset_two_path = app.home / ".omnichord" / "p2.json"
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
            app.action("toggleRhythm")
            app.action("setRhythmTempo", 107.0)
            app.bridge.wait_idle(timeout=8.0)
            checkpoint = app.bridge.count()

            app.action("selectPreset", 2)
            app.bridge.wait_idle(timeout=8.0)

            self.assertTrue(bool(app.query("rhythmRunning")))
            self.assertAlmostEqual(float(app.query("rhythmTempo")), 107.0)
            switched = app.bridge.lines_since(checkpoint)
            self.assertNotIn("zY0Z", switched)
            self.assertNotIn("zY1Z", switched)
            self.assertNotIn("S16384Z", switched)

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
