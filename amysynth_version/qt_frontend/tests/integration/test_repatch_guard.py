from __future__ import annotations

import unittest

from catalog import patch_for_index, synth_index
from harness import HeadlessApp


class RepatchSettlingRegressionTests(unittest.TestCase):
    def test_live_chord_repatches_are_serialized(self) -> None:
        """Synth 4 must not start its ROM repatch in synth 3's settling window.

        The original startup-bass failure appeared when several expensive ROM
        repatches were queued essentially back-to-back.  Chord patch changes are
        a compact reproducer because one UI action repatches both the manual
        chord synth (3) and rhythm chord synth (4).
        """
        target_index = synth_index("Orchestral Pad")
        target_patch = patch_for_index(target_index)

        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=10.0)
            start = app.bridge.count()

            app.action("setChordSynthIndex", target_index)
            app.bridge.wait_for_lines(
                [f"K{target_patch}i3Z", f"K{target_patch}i4Z"],
                start=start,
                timeout=8.0,
            )
            app.bridge.wait_idle(timeout=8.0)

            records = app.bridge.timed_lines()[start:]
            lines = [line for line, _ in records]
            k3 = lines.index(f"K{target_patch}i3Z")
            k4 = lines.index(f"K{target_patch}i4Z")
            elapsed = records[k4][1] - records[k3][1]

            self.assertGreaterEqual(
                elapsed,
                0.008,
                "live chord ROM repatches were queued only "
                f"{elapsed:.4f}s apart; the settling guard regressed",
            )

            # The guard belongs between complete transactions.  These are the
            # normal synth-3 compatibility/routing commands and must still be
            # emitted before synth 4 begins its patch load.
            between = lines[k3 + 1 : k4]
            self.assertIn("i3iy3Z", between)
            self.assertTrue(any(line.startswith("y3h") for line in between))


if __name__ == "__main__":
    unittest.main()
