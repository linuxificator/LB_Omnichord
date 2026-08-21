from __future__ import annotations

import re
import time
import unittest

from catalog import patch_for_index, synth_index
from harness import HeadlessApp


def normalized_timbre(commands: list[str]) -> list[str]:
    # Manual and rhythm chords intentionally use different voice-pool sizes
    # (7 and 4). get_synth_commands() omits the synth number, so normalize only
    # that allocation field and compare every per-voice timbre command exactly.
    return [re.sub(r"iv\d+", "iv#", command, count=1) for command in commands]


class NativeRhythmTests(unittest.TestCase):
    def test_running_rhythm_tracks_live_chord_instrument_switch(self) -> None:
        brass_index = synth_index("Brass Ensemble")
        other_index = synth_index("Orchestral Pad")
        brass_patch = patch_for_index(brass_index)
        other_patch = patch_for_index(other_index)
        self.assertNotEqual(brass_patch, other_patch)

        with HeadlessApp(native_amy=True) as app:
            app.bridge.wait_idle(timeout=10.0)

            # Reduce unrelated accompaniment so diagnostics describe the chord
            # path as clearly as possible.
            if bool(app.query("bassRunning")):
                app.action("toggleBassRunning")
            app.action("setPercussionVolume", 0.0)
            app.action("setRhythmChordActivity", 3.0)

            app.action("setChordSynthIndex", brass_index)
            app.bridge.wait_for_lines(
                [f"K{brass_patch}i3Z", f"K{brass_patch}i4Z"],
                start=0,
                timeout=8.0,
            )
            app.bridge.wait_idle(timeout=8.0)

            if not bool(app.query("rhythmRunning")):
                app.action("toggleRhythm")
            app.action("pressChord", 0, 0)
            app.action("releaseChord", 0, 0)
            time.sleep(0.35)
            app.bridge.wait_idle(timeout=8.0)

            brass3 = app.bridge.synth_commands(3)
            brass4 = app.bridge.synth_commands(4)
            self.assertEqual(
                normalized_timbre(brass3),
                normalized_timbre(brass4),
                "manual/rhythm synths do not match with Brass Ensemble",
            )
            app.bridge.checkpoint("brass-running")

            switch_start = app.bridge.count()
            app.action("setChordSynthIndex", other_index)
            app.bridge.wait_for_lines(
                [f"K{other_patch}i3Z", f"K{other_patch}i4Z"],
                start=switch_start,
                timeout=8.0,
            )
            app.bridge.wait_idle(timeout=8.0)

            other3 = app.bridge.synth_commands(3)
            other4 = app.bridge.synth_commands(4)
            self.assertEqual(
                normalized_timbre(other3),
                normalized_timbre(other4),
                "native AMY rhythm synth 4 did not follow the selected chord instrument",
            )
            self.assertNotEqual(
                normalized_timbre(brass4),
                normalized_timbre(other4),
                "native rhythm synth still has the Brass Ensemble timbre after switch",
            )

            # Exercise another chord after the switch, then allow real AMY's
            # sequencer to run. The rhythm synth must remain on the new timbre.
            app.action("pressChord", 1, 9)
            app.action("releaseChord", 1, 9)
            time.sleep(0.6)
            app.bridge.wait_idle(timeout=8.0)

            final4 = app.bridge.synth_commands(4)
            self.assertEqual(
                normalized_timbre(other4),
                normalized_timbre(final4),
                "rhythm playback reverted synth 4 after the instrument switch",
            )

            switched_lines = app.bridge.lines_since(switch_start)
            scheduled_chords = [
                line
                for line in switched_lines
                if line.startswith("H") and "i4Z" in line
            ]
            self.assertTrue(
                scheduled_chords,
                "no post-switch sequencer chord events target rhythm synth 4",
            )
            self.assertNotIn(f"K{brass_patch}i4Z", switched_lines)
            app.bridge.checkpoint("after-live-instrument-switch")


if __name__ == "__main__":
    unittest.main()
