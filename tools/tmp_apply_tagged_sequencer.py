#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "amysynth_version" / "qt_frontend"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"{path}: expected one occurrence, found {count}: {old[:120]!r}"
        )
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


amy = F / "code" / "amy_serial.py"

# A repeating event's tick must be inside 0..period-1. In particular a gate
# note-off near the end of a bar can otherwise be scheduled beyond period and
# never fire in AMY's offset == tick comparison.
replace_once(
    amy,
    '''        for index, (tick, period, body) in enumerate(events):\n            tag = self.start + index\n            body = str(body)\n            if body.endswith("Z"):\n                body = body[:-1]\n            commands.append(\n                f"H{max(0, int(tick))},{max(1, int(period))},{tag}{body}Z"\n            )\n''',
    '''        for index, (tick, period, body) in enumerate(events):\n            tag = self.start + index\n            period_value = max(1, int(period))\n            tick_value = max(0, int(tick)) % period_value\n            body = str(body)\n            if body.endswith("Z"):\n                body = body[:-1]\n            commands.append(\n                f"H{tick_value},{period_value},{tag}{body}Z"\n            )\n''',
)

# A targeted edit must never invalidate a full Start/style transaction halfway
# through. It simply queues after it. A newer full transaction can still cancel
# an older full transaction, and a full transaction invalidates queued per-lane
# work before installing its authoritative complete state.
replace_once(
    amy,
    '''    def _invalidate_full_rhythm_transaction(self) -> None:\n        self.writer.new_low_generation("rhythm-full")\n\n    def _replace_lane(self, lane_name: str) -> None:\n        self._invalidate_full_rhythm_transaction()\n        lane = self._sequencer_lanes[lane_name]\n''',
    '''    def _replace_lane(self, lane_name: str) -> None:\n        lane = self._sequencer_lanes[lane_name]\n''',
)

# Same-style rhythm changes do not need a pseudo-atomic full transaction. Queue
# the three independent lane replacements; if a Start transaction is still
# draining, these edits naturally follow it and converge the requested state.
replace_once(
    amy,
    '''        else:\n            self._replace_all_lanes(resume_transport=False)\n\n    def _start_rhythm(self) -> None:\n''',
    '''        else:\n            for lane_name in ("drums", "bass", "chords"):\n                self._replace_lane(lane_name)\n\n    def _start_rhythm(self) -> None:\n''',
)

# ---------------------------------------------------------------------------
# Unit fixtures: instrument changes no longer own/rebuild the sequencer.
# ---------------------------------------------------------------------------
unit = F / "tests" / "test_instrument_defaults.py"
replace_once(
    unit,
    '''        client.rhythm_running = False\n        return client\n''',
    '''        client.rhythm_running = False\n        client._wire = lambda command: None\n        return client\n''',
)

replace_once(
    unit,
    '''    def test_live_chord_instrument_transaction_preserves_phase(self) -> None:\n        client = self.bare_client()\n        client.patch_map = {"juno_050": 50}\n        client.rhythm_running = True\n\n        calls: list[tuple[str, object]] = []\n\n        def prepare(*, reset_phase: bool):\n            calls.append(("prepare", reset_phase))\n            return 17, {"tempo": 108.0}\n\n        client._prepare_rhythm_rebuild = prepare\n        client._configure_synth = lambda role: calls.append(("configure", role))\n        client.writer = SimpleNamespace(\n            delay=lambda seconds: calls.append(("delay", seconds))\n        )\n        client._rhythm_guard_seconds = lambda: 0.01\n        client._install_rhythm_schedule = (\n            lambda generation, config: calls.append(("install", generation))\n        )\n\n        AmySerialClient._set_synth_state(\n            client,\n            "chord",\n            {\n                "name": "juno_050",\n                "params": ["resonance", 7.5],\n            },\n        )\n\n        self.assertEqual(\n            calls,\n            [\n                ("prepare", False),\n                ("configure", "chord"),\n                ("delay", 0.01),\n                ("install", 17),\n            ],\n        )\n''',
    '''    def test_live_chord_instrument_change_does_not_rebuild_sequencer(self) -> None:\n        client = self.bare_client()\n        client.patch_map = {"juno_050": 50}\n        client.rhythm_running = True\n\n        calls: list[tuple[str, object]] = []\n        client._wire = lambda command: calls.append(("wire", command))\n        client._configure_synth = lambda role: calls.append(("configure", role))\n\n        AmySerialClient._set_synth_state(\n            client,\n            "chord",\n            {\n                "name": "juno_050",\n                "params": ["resonance", 7.5],\n            },\n        )\n\n        self.assertEqual(\n            calls,\n            [("wire", "l0i4Z"), ("configure", "chord")],\n        )\n        self.assertFalse(\n            any(\n                command in {"zY0Z", "zY1Z", "S4096Z"}\n                for kind, command in calls\n                if kind == "wire"\n            )\n        )\n''',
)

replace_once(
    unit,
    '''    def test_stopped_rhythm_is_not_rebuilt_on_chord_instrument_change(self) -> None:\n        client = self.bare_client()\n        client.patch_map = {"juno_050": 50}\n        calls: list[tuple[str, object]] = []\n        client._configure_synth = lambda role: calls.append(("configure", role))\n\n        AmySerialClient._set_synth_state(\n            client,\n            "chord",\n            {"name": "juno_050", "params": ["resonance", 7.5]},\n        )\n\n        self.assertEqual(calls, [("configure", "chord")])\n''',
    '''    def test_stopped_rhythm_is_not_rebuilt_on_chord_instrument_change(self) -> None:\n        client = self.bare_client()\n        client.patch_map = {"juno_050": 50}\n        calls: list[tuple[str, object]] = []\n        client._wire = lambda command: calls.append(("wire", command))\n        client._configure_synth = lambda role: calls.append(("configure", role))\n\n        AmySerialClient._set_synth_state(\n            client,\n            "chord",\n            {"name": "juno_050", "params": ["resonance", 7.5]},\n        )\n\n        self.assertEqual(\n            calls,\n            [("wire", "l0i4Z"), ("configure", "chord")],\n        )\n''',
)

# ---------------------------------------------------------------------------
# Serial tests: populate accompaniment lanes before testing their removal.
# ---------------------------------------------------------------------------
serial = F / "tests" / "integration" / "test_serial.py"

setup_anchor = '''            if not bool(app.query("rhythmRunning")):\n                start = app.bridge.count()\n                app.action("toggleRhythm")\n                app.bridge.wait_for_lines(["zY1Z"], start=start, timeout=8.0)\n                app.bridge.wait_idle(timeout=8.0)\n\n            start = app.bridge.count()\n            app.action("pressChord", 0, 0)\n'''
setup_replacement = '''            if not bool(app.query("rhythmRunning")):\n                start = app.bridge.count()\n                app.action("toggleRhythm")\n                app.bridge.wait_for_lines(["zY1Z"], start=start, timeout=8.0)\n                app.bridge.wait_idle(timeout=8.0)\n\n            # First establish real bass/chord tagged patterns. The cancellation\n            # assertion below is meaningful only for tags that were installed.\n            seed = app.bridge.count()\n            app.action("selectChord", 0, 0)\n            deadline = time.monotonic() + 8.0\n            while time.monotonic() < deadline:\n                seeded = app.bridge.lines_since(seed)\n                if (\n                    any(line.startswith("H") and "i1Z" in line for line in seeded)\n                    and any(line.startswith("H") and "i4Z" in line for line in seeded)\n                ):\n                    break\n                time.sleep(0.01)\n            else:\n                self.fail("failed to seed bass and rhythm-chord tag ranges")\n            time.sleep(0.75)  # allow one-shot chord release timer to drain\n            app.bridge.wait_idle(timeout=8.0)\n\n            start = app.bridge.count()\n            app.action("pressChord", 0, 0)\n'''
replace_once(serial, setup_anchor, setup_replacement)

# The tag-range test has a separate, structurally identical start block; seed
# its lanes before toggling bass as well.
range_anchor = '''            if not bool(app.query("rhythmRunning")):\n                start = app.bridge.count()\n                app.action("toggleRhythm")\n                app.bridge.wait_for_lines(["zY1Z"], start=start, timeout=8.0)\n                app.bridge.wait_idle(timeout=8.0)\n\n            if bool(app.query("bassRunning")):\n'''
range_replacement = '''            if not bool(app.query("rhythmRunning")):\n                start = app.bridge.count()\n                app.action("toggleRhythm")\n                app.bridge.wait_for_lines(["zY1Z"], start=start, timeout=8.0)\n                app.bridge.wait_idle(timeout=8.0)\n\n            seed = app.bridge.count()\n            app.action("selectChord", 0, 0)\n            deadline = time.monotonic() + 8.0\n            while time.monotonic() < deadline:\n                seeded = app.bridge.lines_since(seed)\n                if (\n                    any(line.startswith("H") and "i1Z" in line for line in seeded)\n                    and any(line.startswith("H") and "i4Z" in line for line in seeded)\n                ):\n                    break\n                time.sleep(0.01)\n            else:\n                self.fail("failed to seed tag ranges before isolation test")\n            time.sleep(0.75)\n            app.bridge.wait_idle(timeout=8.0)\n\n            if bool(app.query("bassRunning")):\n'''
replace_once(serial, range_anchor, range_replacement)

# A held chord changes bass pitch because it becomes the active chord. The
# important invariant is that no DRUM tag is touched; bass is allowed to update.
replace_once(
    serial,
    '''            self.assertTrue(all(112 <= tag < 252 for tag in cancel_tags), cancel_tags)\n''',
    '''            self.assertTrue(all(112 <= tag < 252 for tag in cancel_tags), cancel_tags)\n            self.assertFalse(\n                any(\n                    line.startswith("H0,0,")\n                    and int(line.split(",", 2)[2][:-1]) < 56\n                    for line in delta\n                ),\n                delta,\n            )\n''',
)

# Update stale comments in the regression contract: there is no full rebuild
# for ordinary chord-lane changes anymore.
use = F / "tests" / "USE_CASES.md"
text = use.read_text(encoding="utf-8")
text = text.replace(
    "- Instrument configuration and rhythm scheduling must have one explicit ordering contract.\n- Tests must inspect both serial command order and native AMY synth state after a live switch.\n",
    "- Chord patch changes update synths 3/4 directly; existing tagged synth-4 events remain installed and use the new patch on their next firing.\n- A timbre-only switch must not stop transport or reset/rebuild unrelated sequencer lanes. Tests inspect both serial commands and native AMY synth state.\n",
)
text = text.replace(
    "- Starting rhythm from stopped state must clear stale sequencer events, cross the configured AMY reset guard, reapply the current logical chord parameters specifically to rhythm synth 4, then install automatic chord events and resume transport.\n- This reapplication uses the same stored chord state; it must not invent defaults, derive values independently, or reload the patch.\n",
    "- Starting rhythm from stopped state installs the authoritative tagged drum/bass/chord ranges and resumes transport only after those definitions are queued ahead of `zY1`.\n- Starting rhythm must not require `RESET_SEQUENCER`; tagged replacement itself removes stale lane entries.\n",
)
use.write_text(text, encoding="utf-8")

for path in (amy, unit, serial):
    compile(path.read_text(encoding="utf-8"), str(path), "exec")
