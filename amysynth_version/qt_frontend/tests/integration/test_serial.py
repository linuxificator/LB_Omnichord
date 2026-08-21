from __future__ import annotations

import unittest

from catalog import patch_for_index, synth_index
from harness import HeadlessApp


class SerialIntegrationTests(unittest.TestCase):
    def test_serial_framing_and_live_chord_patch_order(self) -> None:
        brass_index = synth_index("Brass Ensemble")
        other_index = synth_index("Orchestral Pad")
        brass_patch = patch_for_index(brass_index)
        other_patch = patch_for_index(other_index)

        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)

            # Real pyserial writes must be one complete AMY message per LF line.
            for line in app.bridge.lines_since(0):
                self.assertTrue(line.endswith("Z"), line)
                self.assertNotIn("\n", line)
                self.assertNotIn("\r", line)

            app.action("setChordSynthIndex", brass_index)
            app.bridge.wait_for_lines(
                [f"K{brass_patch}i3Z", f"K{brass_patch}i4Z"],
                start=0,
            )

            # Run actual rhythm chords before changing the sound.
            app.action("setRhythmChordActivity", 3.0)
            if not bool(app.query("rhythmRunning")):
                app.action("toggleRhythm")
            app.action("pressChord", 0, 0)
            app.action("releaseChord", 0, 0)
            app.bridge.wait_idle(timeout=8.0)

            switch_start = app.bridge.count()
            app.action("setChordSynthIndex", other_index)
            lines = app.bridge.wait_for_lines(
                [f"K{other_patch}i3Z", f"K{other_patch}i4Z", "S4096Z"],
                start=switch_start,
                timeout=8.0,
            )
            app.bridge.wait_idle(timeout=8.0)
            lines = app.bridge.lines_since(switch_start)

            stop = lines.index("zY0Z")
            reset = lines.index("S4096Z")
            k3 = lines.index(f"K{other_patch}i3Z")
            k4 = lines.index(f"K{other_patch}i4Z")
            first_schedule = next(
                index for index, line in enumerate(lines) if line.startswith("H")
            )
            self.assertLess(stop, reset)
            self.assertLess(reset, k3)
            self.assertLess(k3, k4)
            self.assertLess(k4, first_schedule)

            # A live rhythm refresh must define chord events against the
            # dedicated rhythm chord synth 4, never manual synth 3.
            scheduled = [line for line in lines if line.startswith("H")]
            self.assertTrue(scheduled, "no sequencer events sent after switch")
            self.assertTrue(
                any("i4Z" in line for line in scheduled),
                "refreshed rhythm contains no synth-4 chord events",
            )

            # Once the new instrument switch begins, the old Brass patch may
            # not be reloaded into either chord synth by a stale host command.
            self.assertNotIn(f"K{brass_patch}i3Z", lines)
            self.assertNotIn(f"K{brass_patch}i4Z", lines)


if __name__ == "__main__":
    unittest.main()
