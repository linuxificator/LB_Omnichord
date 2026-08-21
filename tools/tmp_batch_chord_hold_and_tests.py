#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / 'amysynth_version' / 'qt_frontend'


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding='utf-8')
    if old not in text:
        raise RuntimeError(f'{path}: missing anchor {old[:100]!r}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')

main = F / 'code' / 'main.py'
# Let pressChord update the local hold gate without emitting a standalone
# receiver transaction; chord_state below carries gate+notes atomically.
replace_once(
    main,
    '    def _update_hold_override(self) -> None:\n',
    '    def _update_hold_override(self, *, publish: bool = True) -> None:\n',
)
replace_once(
    main,
    '''        self.rhythmControlsChanged.emit()\n        self._send_rhythm_chord_enabled()\n\n    def _clear_touch_dropout_state(self) -> None:\n''',
    '''        self.rhythmControlsChanged.emit()\n        if publish:\n            self._send_rhythm_chord_enabled()\n\n    def _clear_touch_dropout_state(self) -> None:\n''',
)
replace_once(
    main,
    '''        self._promoted_chords.add(key)\n        self._update_hold_override()\n\n        # Last pressed chord becomes the active chord used by strum/bass.\n''',
    '''        self._promoted_chords.add(key)\n        self._update_hold_override(publish=False)\n\n        # Last pressed chord becomes the active chord used by strum/bass.\n''',
)
replace_once(
    main,
    '''            "rhythm_running": bool(\n                self._rhythm_running\n            ),\n        }\n''',
    '''            "rhythm_running": bool(\n                self._rhythm_running\n            ),\n            "rhythm_chord_enabled": bool(\n                self._rhythm_running\n                and self._effective_chord_activity() > 0\n            ),\n        }\n''',
)

amy = F / 'code' / 'amy_serial.py'
replace_once(
    amy,
    '''        self.chord_notes = [float(x) for x in payload.get("notes", [])]\n        self.bass_notes = [float(x) for x in payload.get("bass_notes", [])]\n\n        if payload.get("play_now") and self.chord_notes:\n''',
    '''        self.chord_notes = [float(x) for x in payload.get("notes", [])]\n        self.bass_notes = [float(x) for x in payload.get("bass_notes", [])]\n        if "rhythm_chord_enabled" in payload:\n            self.rhythm_chord_enabled = bool(\n                payload.get("rhythm_chord_enabled")\n            )\n\n        if payload.get("play_now") and self.chord_notes:\n''',
)

# Bridge timestamp support, allowing the cold-start test to prove K/iv has a
# real block-boundary guard before synth-tier commands hit the PTY.
harness = F / 'tests' / 'integration' / 'harness.py'
replace_once(
    harness,
    '''        self.lines: list[str] = []\n        self.raw_chunks: list[bytes] = []\n''',
    '''        self.lines: list[str] = []\n        self.line_times: list[float] = []\n        self.raw_chunks: list[bytes] = []\n''',
)
replace_once(
    harness,
    '''            self.lines.append(line)\n            self._last_rx = time.monotonic()\n''',
    '''            self.lines.append(line)\n            self.line_times.append(time.monotonic())\n            self._last_rx = self.line_times[-1]\n''',
)
replace_once(
    harness,
    '''    def lines_since(self, start: int) -> list[str]:\n        with self._line_condition:\n            return list(self.lines[start:])\n\n''',
    '''    def lines_since(self, start: int) -> list[str]:\n        with self._line_condition:\n            return list(self.lines[start:])\n\n    def timed_lines(self) -> list[tuple[str, float]]:\n        with self._line_condition:\n            return list(zip(self.lines, self.line_times))\n\n''',
)

serial = F / 'tests' / 'integration' / 'test_serial.py'
text = serial.read_text(encoding='utf-8')
if 'import time\n' not in text:
    text = text.replace('import re\n', 'import re\nimport time\n', 1)
insert_marker = '\n\nif __name__ == "__main__":\n'
tests = r'''
    def test_cold_start_guards_synth4_and_zero_reverb_is_not_sent(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=10.0)
            records = app.bridge.timed_lines()
            lines = [line for line, _ in records]

            self.assertNotIn("y0h0Z", lines)
            self.assertNotIn("y1h0Z", lines)

            k4_index = next(
                i for i, line in enumerate(lines)
                if line.startswith("K") and "i4iv" in line
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

            start = app.bridge.count()
            app.action("setPercussionReverb", 0.05)
            app.bridge.wait_for_lines(["y1h0.05Z"], start=start, timeout=5.0)
            start = app.bridge.count()
            app.action("setPercussionReverb", 0.0)
            app.bridge.wait_for_lines(["y1h0.001Z"], start=start, timeout=5.0)
            self.assertEqual(float(app.query("percussionReverb")), 0.0)

    def test_long_manual_chord_hold_keeps_rhythm_transport_and_percussion_alive(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=10.0)
            if not bool(app.query("rhythmRunning")):
                start = app.bridge.count()
                app.action("toggleRhythm")
                app.bridge.wait_for_lines(["zY1Z"], start=start, timeout=8.0)
                app.bridge.wait_idle(timeout=8.0)

            start = app.bridge.count()
            app.action("pressChord", 0, 0)
            app.bridge.wait_for_lines(["zY1Z"], start=start, timeout=8.0)
            app.bridge.wait_idle(timeout=8.0)
            delta = app.bridge.lines_since(start)

            # One rebuild only. It removes automatic chord events but keeps
            # percussion/bass and resumes the same transport.
            self.assertEqual(delta.count("zY0Z"), 1, "manual chord press rebuilt rhythm more than once")
            self.assertTrue(any(line.startswith("H") and "i0Z" in line for line in delta), delta)
            self.assertTrue(bool(app.query("rhythmRunning")))

            time.sleep(1.0)
            self.assertTrue(bool(app.query("rhythmRunning")))

            release_start = app.bridge.count()
            app.action("releaseChord", 0, 0)
            app.bridge.wait_for_lines(["zY1Z"], start=release_start, timeout=8.0)
            app.bridge.wait_idle(timeout=8.0)
            release_delta = app.bridge.lines_since(release_start)
            self.assertEqual(release_delta.count("zY0Z"), 1, "manual chord release rebuilt rhythm more than once")
            self.assertTrue(any(line.startswith("H") and "i0Z" in line for line in release_delta), release_delta)
            self.assertTrue(bool(app.query("rhythmRunning")))
'''
if 'test_long_manual_chord_hold_keeps_rhythm_transport' not in text:
    if insert_marker not in text:
        raise RuntimeError('serial unittest footer marker missing')
    text = text.replace(insert_marker, '\n' + tests + insert_marker, 1)
serial.write_text(text, encoding='utf-8')

native = F / 'tests' / 'integration' / 'test_native_controls.py'
text = native.read_text(encoding='utf-8')
native_test = r'''
    def test_cold_start_defines_all_five_synths_in_real_amy(self) -> None:
        with HeadlessApp(native_amy=True) as app:
            app.bridge.wait_idle(timeout=10.0)
            for synth in range(5):
                commands = app.bridge.synth_commands(synth)
                self.assertTrue(commands, f"native AMY synth {synth} is undefined after cold start")
            app.bridge.checkpoint("cold-start-all-synths", synths=(0, 1, 2, 3, 4))
'''
if 'test_cold_start_defines_all_five_synths' not in text:
    if insert_marker not in text:
        raise RuntimeError('native unittest footer marker missing')
    text = text.replace(insert_marker, '\n' + native_test + insert_marker, 1)
native.write_text(text, encoding='utf-8')

# Static UI regression: no rhythm reset, narrow rail, common RST labels.
static = F / 'tests' / 'test_static_contracts.py'
text = static.read_text(encoding='utf-8')
static_test = r'''
    def test_left_rail_has_no_rhythm_reset_and_uses_common_reset_labels(self) -> None:
        qml = (FRONTEND / "gui" / "Main.qml").read_text(encoding="utf-8")
        self.assertIn("property int leftRailWidth: 64", qml)
        self.assertNotIn("resetRhythmControlsToPreset", qml)
        self.assertNotIn('text: "RHY"', qml)
        self.assertNotIn('text: "BAS"', qml)
        self.assertNotIn('text: "STR"', qml)
        self.assertNotIn('text: "CHD"', qml)
        self.assertNotIn('text: "ROWS"', qml)
        self.assertGreaterEqual(qml.count('text: "RST"'), 4)
'''
if 'test_left_rail_has_no_rhythm_reset' not in text:
    if insert_marker not in text:
        raise RuntimeError('static unittest footer marker missing')
    text = text.replace(insert_marker, '\n' + static_test + insert_marker, 1)
static.write_text(text, encoding='utf-8')

print('Applied atomic chord-hold path and runtime regressions.')
