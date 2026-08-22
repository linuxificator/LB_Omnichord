from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
