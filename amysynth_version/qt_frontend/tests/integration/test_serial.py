from __future__ import annotations

import unittest

from catalog import control_default, patch_for_index, synth_index
from harness import HeadlessApp


def wire_float(value: float) -> str:
    return f"{float(value):.9g}"


class SerialIntegrationTests(unittest.TestCase):
    def test_preset7_rhythm_start_reasserts_chord_state_before_schedule(self) -> None:
        """Reproduce the clean-home P7 startup failure reported on hardware."""
        chorus_index = synth_index("Chorus Vibes")
        chorus_patch = patch_for_index(chorus_index)
        cutoff = control_default(chorus_index, "filter_hz")
        cutoff4 = f"v0F{wire_float(cutoff)}i4Z"

        # HeadlessApp uses a fresh temporary HOME, equivalent to removing
        # ~/.omnichord before startup.
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)

            # 1. Select factory preset 7 and play a manual chord while rhythm
            # is stopped. P7 selects Chorus Vibes for the chord role.
            app.action("selectPreset", 7)
            app.bridge.wait_idle(timeout=8.0)
            self.assertEqual(app.query("selectedPreset"), 7)
            self.assertEqual(app.query("selectedChordSynthIndex"), chorus_index)

            app.action("pressChord", 0, 0)
            app.action("releaseChord", 0, 0)
            app.bridge.wait_idle(timeout=8.0)

            # 2/3. Starting rhythm must explicitly converge rhythm synth 4 from
            # the exact same stored state before any automatic chord is queued.
            start = app.bridge.count()
            if not bool(app.query("rhythmRunning")):
                app.action("toggleRhythm")
            app.bridge.wait_for_lines(["zY1Z", cutoff4], start=start, timeout=8.0)
            app.bridge.wait_idle(timeout=8.0)
            lines = app.bridge.lines_since(start)

            reset = lines.index("S4096Z")
            cutoff_index = lines.index(cutoff4)
            first_chord_schedule = next(
                index
                for index, line in enumerate(lines)
                if line.startswith("H") and "i4Z" in line
            )
            self.assertLess(reset, cutoff_index)
            self.assertLess(cutoff_index, first_chord_schedule)

            # Starting the rhythm must not reload the instrument; it only
            # reasserts the complete current parameter state on synth 4.
            self.assertNotIn(f"K{chorus_patch}i4Z", lines)

            # 4. A UI cutoff edit follows exactly the same complete-state path.
            # The AMY-side diff must update both manual synth 3 and rhythm synth
            # 4 without repatching or resending unrelated state.
            edited_cutoff = min(18000.0, cutoff + 250.0)
            edited3 = f"v0F{wire_float(edited_cutoff)}i3Z"
            edited4 = f"v0F{wire_float(edited_cutoff)}i4Z"
            edit_start = app.bridge.count()
            app.action("setChordSynthControl", "filter_hz", edited_cutoff)
            edit_lines = app.bridge.wait_for_lines(
                [edited3, edited4],
                start=edit_start,
                timeout=8.0,
            )
            self.assertNotIn(f"K{chorus_patch}i3Z", edit_lines)
            self.assertNotIn(f"K{chorus_patch}i4Z", edit_lines)

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
            app.bridge.wait_for_lines(
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
