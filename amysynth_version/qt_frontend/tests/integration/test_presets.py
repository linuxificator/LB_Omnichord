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


if __name__ == "__main__":
    unittest.main()
