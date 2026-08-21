#!/usr/bin/env python3
from pathlib import Path

path = Path(__file__).resolve().parent / "integration" / "test_serial.py"
text = path.read_text(encoding="utf-8")
start = text.index("    def test_cold_start_guards_synth4_and_reverb_zero_is_exact(self) -> None:\n")
end = text.index("    def test_long_manual_chord_hold_only_edits_chord_tag_range(self) -> None:\n", start)
replacement = '''    def test_cold_start_guards_synth4_and_reverb_zero_is_exact(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=10.0)
            records = app.bridge.timed_lines()
            lines = [line for line, _ in records]

            # Four isolated buses: drums 0 are dry by default; bass/strum/chord
            # buses also start at user reverb level zero. Liveness/damping are
            # still defined at their neutral midpoint even while level is zero.
            for bus in range(4):
                self.assertIn(f"y{bus}h0,0.5,0.5Z", lines)
            self.assertFalse(any("h0.001" in line for line in lines))

            k4_index = next(
                i for i, line in enumerate(lines)
                if line.startswith("K") and "i4iv" in line and "iy3Z" in line
            )
            next_synth4_index = next(
                i for i in range(k4_index + 1, len(lines))
                if "i4" in lines[i]
            )
            elapsed = records[next_synth4_index][1] - records[k4_index][1]
            self.assertGreaterEqual(
                elapsed,
                0.008,
                f"synth 4 post-allocation command arrived after only {elapsed:.4f}s",
            )

            # User reverb applies to bass/strum/chords, never drums unless DRM
            # is explicitly enabled.
            start = app.bridge.count()
            app.action("setReverbLevel", 0.4)
            app.bridge.wait_for_lines(
                [
                    "y0h0,0.5,0.5Z",
                    "y1h0.4,0.5,0.5Z",
                    "y2h0.4,0.5,0.5Z",
                    "y3h0.4,0.5,0.5Z",
                ],
                start=start,
                timeout=5.0,
            )
            self.assertFalse(bool(app.query("reverbDrumsIncluded")))

            start = app.bridge.count()
            app.action("toggleReverbDrums")
            app.bridge.wait_for_lines(
                ["y0h0.4,0.5,0.5Z"], start=start, timeout=5.0
            )
            self.assertTrue(bool(app.query("reverbDrumsIncluded")))

            # Level zero is exact on every bus, including drums when DRM is on.
            start = app.bridge.count()
            app.action("setReverbLevel", 0.0)
            app.bridge.wait_for_lines(
                [
                    "y0h0,0.5,0.5Z",
                    "y1h0,0.5,0.5Z",
                    "y2h0,0.5,0.5Z",
                    "y3h0,0.5,0.5Z",
                ],
                start=start,
                timeout=5.0,
            )
            self.assertEqual(float(app.query("reverbLevel")), 0.0)

'''
path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
compile(path.read_text(encoding="utf-8"), str(path), "exec")
