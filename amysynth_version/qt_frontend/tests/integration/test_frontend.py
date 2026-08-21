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


if __name__ == "__main__":
    unittest.main()
