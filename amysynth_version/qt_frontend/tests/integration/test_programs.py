from __future__ import annotations

import re
import time
import unittest

from catalog import synths
from harness import HeadlessApp


class ProgramIntegrationTests(unittest.TestCase):
    def test_physical_strings_configures_karplus_strong_without_fake_patch(self) -> None:
        physical_index = len(synths())
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

    def test_gated_strum_wraps_selected_timbre_and_can_be_disabled(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=10.0)
            self.assertFalse(bool(app.query("strumGateEnabled")))

            app.action("selectChord", 0, 0)
            app.bridge.wait_idle(timeout=8.0)
            app.action("setStrumGateAttack", 0.05)
            app.action("setStrumGateSustain", 0.10)
            app.action("toggleStrumGate")
            self.assertTrue(bool(app.query("strumGateEnabled")))

            start = app.bridge.count()
            app.action("strumTap", 0.5)
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                lines = app.bridge.lines_since(start)
                if (
                    "i2iV0Z" in lines
                    and any(re.match(r"^n[-+0-9.]+l1i2Z$", line) for line in lines)
                    and any(line.startswith("i2iV") and line != "i2iV0Z" for line in lines)
                ):
                    break
                time.sleep(0.01)
            else:
                self.fail("gated strum did not emit gate envelope and note-on")

            app.action("toggleStrumGate")
            self.assertFalse(bool(app.query("strumGateEnabled")))
            app.bridge.wait_idle(timeout=5.0)
            normal_start = app.bridge.count()
            app.action("strumTap", 0.55)
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                normal = app.bridge.lines_since(normal_start)
                if any(re.match(r"^n[-+0-9.]+l1i2Z$", line) for line in normal):
                    break
                time.sleep(0.01)
            else:
                self.fail("ordinary strum emitted no note-on after disabling GTD")
            self.assertNotIn("i2iV0Z", normal)


if __name__ == "__main__":
    unittest.main()
