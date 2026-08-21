#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"anchor not found in {path}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# ---------------------------------------------------------------------------
# Backend stop path: transport stop must be followed by immediate all-off for
# only the accompaniment synths. Manual synth 3 is deliberately not touched.
# ---------------------------------------------------------------------------
amy = ROOT / "code" / "amy_serial.py"
text = amy.read_text(encoding="utf-8")
if "def _silence_accompaniment(" not in text:
    anchor = '''    def _set_rhythm_config(self, payload_text: str) -> None:\n'''
    method = '''    def _silence_accompaniment(self) -> None:\n        """Immediately release every voice owned by the rhythm transport.\n\n        Stopping AMY's sequencer freezes future tagged events.  If transport is\n        stopped between a scheduled note-on and note-off, that note-off can no\n        longer fire.  Explicit all-off messages are therefore part of the stop\n        transaction.  Manual chord synth 3 and strum synth 2 are intentionally\n        excluded because they are controlled by the player's fingers, not by\n        rhythm transport.\n        """\n        for key in ("drums", "bass", "rhythm_chord"):\n            self._wire(f"l0i{self.synth_id[key]}Z")\n\n'''
    if anchor not in text:
        raise SystemExit("_set_rhythm_config anchor missing")
    text = text.replace(anchor, method + anchor, 1)
    amy.write_text(text, encoding="utf-8")

# ---------------------------------------------------------------------------
# Real PTY regression: the frontend action must return normally, publish the
# stopped state, and send explicit all-offs after zY0.
# ---------------------------------------------------------------------------
serial = ROOT / "tests" / "integration" / "test_serial.py"
text = serial.read_text(encoding="utf-8")
if "test_stopping_rhythm_releases_sounding_accompaniment" not in text:
    marker = '''    def test_tag_ranges_are_disjoint_and_lane_updates_do_not_cross(self) -> None:\n'''
    test = '''    def test_stopping_rhythm_releases_sounding_accompaniment(self) -> None:\n        """Stopping mid-pattern must not strand a synth-4 chord or bass note."""\n        with HeadlessApp(native_amy=False) as app:\n            app.bridge.wait_idle(timeout=10.0)\n            app.action("setRhythmChordActivity", 4.0)\n            app.action("setRhythmBassActivity", 4.0)\n            if not bool(app.query("bassRunning")):\n                app.action("toggleBassRunning")\n\n            # Establish an active pitch state and let any one-shot manual chord\n            # release drain before the stop checkpoint.\n            app.action("selectChord", 0, 0)\n            time.sleep(0.75)\n            app.bridge.wait_idle(timeout=8.0)\n\n            if not bool(app.query("rhythmRunning")):\n                start = app.bridge.count()\n                app.action("toggleRhythm")\n                app.bridge.wait_for_lines(["zY1Z"], start=start, timeout=8.0)\n            self.assertTrue(bool(app.query("rhythmRunning")))\n\n            # The regression is the action call itself: the old implementation\n            # raised AttributeError after zY0 because _silence_accompaniment was\n            # missing, so the frontend never emitted rhythmStateChanged.\n            stop_start = app.bridge.count()\n            app.action("toggleRhythm")\n            lines = app.bridge.wait_for_lines(\n                ["zY0Z", "l0i0Z", "l0i1Z", "l0i4Z"],\n                start=stop_start,\n                timeout=8.0,\n            )\n            app.bridge.wait_idle(timeout=8.0)\n            lines = app.bridge.lines_since(stop_start)\n\n            self.assertFalse(bool(app.query("rhythmRunning")))\n            self.assertLess(lines.index("zY0Z"), lines.index("l0i4Z"))\n            self.assertLess(lines.index("zY0Z"), lines.index("l0i1Z"))\n            self.assertNotIn(\n                "l0i3Z",\n                lines,\n                "stopping rhythm must not release a manually held chord",\n            )\n\n'''
    if marker not in text:
        raise SystemExit("serial insertion marker missing")
    serial.write_text(text.replace(marker, test + marker, 1), encoding="utf-8")

# ---------------------------------------------------------------------------
# Static UI contracts: transport glyph is declarative, and the current pink
# panel must fit its three 145 px sliders plus DRM inside the 520 px panel.
# ---------------------------------------------------------------------------
static = ROOT / "tests" / "test_static_contracts.py"
text = static.read_text(encoding="utf-8")
start_name = "    def test_reverb_controls_are_side_by_side_touch_targets(self) -> None:\n"
next_name = "    def test_reverb_header_uses_wide_horizontal_sliders(self) -> None:\n"
if start_name in text:
    start = text.index(start_name)
    end = text.index(next_name, start)
    text = text[:start] + text[end:]

old_transport = '''    def test_rhythm_transport_canvas_erases_old_symbol(self) -> None:\n        qml = (ROOT / "gui" / "RhythmSection.qml").read_text(encoding="utf-8")\n        self.assertIn("c.clearRect(0, 0, width, height)", qml)\n'''
new_transport = '''    def test_rhythm_transport_icon_is_bound_directly_to_backend_state(self) -> None:\n        qml = (ROOT / "gui" / "RhythmSection.qml").read_text(encoding="utf-8")\n        self.assertIn('text: root.controller.rhythmRunning ? "■" : "▶"', qml)\n        self.assertNotIn("Canvas {", qml)\n'''
if old_transport in text:
    text = text.replace(old_transport, new_transport, 1)
elif "test_rhythm_transport_icon_is_bound_directly_to_backend_state" not in text:
    raise SystemExit("transport static-test anchor missing")

old_panel = '''        self.assertGreaterEqual(panel.count("width: 145"), 3)\n        self.assertIn("width: 520", main)\n'''
new_panel = '''        self.assertGreaterEqual(panel.count("width: 145"), 3)\n        self.assertIn("anchors.margins: 4", panel)\n        self.assertIn("spacing: 6", panel)\n        self.assertIn("width: 50", panel)\n        self.assertIn("width: 520", main)\n'''
if old_panel in text:
    text = text.replace(old_panel, new_panel, 1)
static.write_text(text, encoding="utf-8")

# ---------------------------------------------------------------------------
# Regression catalogue.
# ---------------------------------------------------------------------------
use = ROOT / "tests" / "USE_CASES.md"
text = use.read_text(encoding="utf-8")
if "RHYTHM-05 — stopping transport releases sounding accompaniment" not in text:
    marker = "### TUNING — all note-producing paths follow the selected tuning\n"
    addition = '''**RHYTHM-05 — stopping transport releases sounding accompaniment**\n\n- `zY0` stops future sequencer execution, so a note-off scheduled later in the pattern cannot be relied upon after Stop.\n- Every rhythm Stop must therefore immediately send all-off to percussion synth 0, bass synth 1 and automatic-chord synth 4.\n- Manual chord synth 3 and strum synth 2 are not rhythm-owned and must remain untouched.\n- The frontend Stop action must complete normally and emit the changed `rhythmRunning` state so the Play/Stop control follows the backend.\n\n**Failure history:** stopping while an automatic chord was sounding froze transport before its tagged note-off fired, leaving a hanging chord. The same stop path called a missing `_silence_accompaniment()` method after sending `zY0`, raising `AttributeError`; as a result the actual transport stopped but `rhythmStateChanged` was never emitted and the button remained visually stuck on STOP.\n\n'''
    if marker not in text:
        raise SystemExit("USE_CASES tuning marker missing")
    use.write_text(text.replace(marker, addition + marker, 1), encoding="utf-8")

# Basic local syntax validation before CI invokes py_compile as well.
compile(amy.read_text(encoding="utf-8"), str(amy), "exec")
compile(serial.read_text(encoding="utf-8"), str(serial), "exec")
compile(static.read_text(encoding="utf-8"), str(static), "exec")
