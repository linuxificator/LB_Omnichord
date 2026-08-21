from __future__ import annotations

import unittest

from catalog import control_default, patch_for_index, synth_index
from harness import HeadlessApp


def wire_float(value: float) -> str:
    return f"{float(value):.9g}"


class SerialIntegrationTests(unittest.TestCase):
    def test_preset7_rhythm_start_preserves_native_filter_until_user_override(self) -> None:
        """Fresh P7 must leave Chorus Vibes' complete native VCF model intact."""
        chorus_index = synth_index("Chorus Vibes")
        chorus_patch = patch_for_index(chorus_index)
        cutoff = control_default(chorus_index, "filter_hz")
        native_cutoff4 = f"v0F{wire_float(cutoff)}i4Z"

        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)
            app.action("selectPreset", 7)
            app.bridge.wait_idle(timeout=8.0)
            self.assertEqual(app.query("selectedPreset"), 7)
            self.assertEqual(app.query("selectedChordSynthIndex"), chorus_index)

            # The factory K66 command already installs F27.365 together with
            # note/envelope tracking. The host must not rewrite that native
            # base coefficient merely because it is visible in the UI.
            select_lines = app.bridge.lines_since(0)
            self.assertNotIn(native_cutoff4, select_lines)

            app.action("pressChord", 0, 0)
            app.action("releaseChord", 0, 0)
            app.bridge.wait_idle(timeout=8.0)

            start = app.bridge.count()
            if not bool(app.query("rhythmRunning")):
                app.action("toggleRhythm")
            app.bridge.wait_for_lines(["zY1Z"], start=start, timeout=8.0)
            app.bridge.wait_idle(timeout=8.0)
            lines = app.bridge.lines_since(start)
            self.assertNotIn(native_cutoff4, lines)
            self.assertNotIn(f"K{chorus_patch}i4Z", lines)
            self.assertTrue(
                any(line.startswith("H") and "i4Z" in line for line in lines),
                "no rhythm-chord events were scheduled",
            )

            # A real UI edit becomes an explicit engine override and is sent to
            # both manual and rhythm chord synths.
            edited_cutoff = max(500.0, cutoff + 250.0)
            edited3 = f"v0F{wire_float(edited_cutoff)}i3Z"
            edited4 = f"v0F{wire_float(edited_cutoff)}i4Z"
            edit_start = app.bridge.count()
            app.action("setChordSynthControl", "filter_hz", edited_cutoff)
            edit_lines = app.bridge.wait_for_lines(
                [edited3, edited4], start=edit_start, timeout=8.0
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
