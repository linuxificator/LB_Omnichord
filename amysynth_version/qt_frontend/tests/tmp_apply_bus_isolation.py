#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, found {count}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def regex_once(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f"{path}: regex match count {count} for {pattern!r}")
    path.write_text(updated, encoding="utf-8")


# ---------------------------------------------------------------------------
# Four independent AMY buses: drums, bass, strum, chords.
# ---------------------------------------------------------------------------
config_path = ROOT / "config" / "amy_config.json"
config = json.loads(config_path.read_text(encoding="utf-8"))
config["buses"] = {
    "drums": 0,
    "bass": 1,
    "strum": 2,
    "chord": 3,
}
config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

amy_path = ROOT / "code" / "amy_serial.py"
regex_once(
    amy_path,
    r'''        buses = config\.get\("buses", \{\}\)\n        self\.bus_id = \{.*?        self\.reverb = \{''',
    '''        buses = config.get("buses", {})
        self.bus_id = {
            "drums": int(buses.get("drums", 0)),
            "bass": int(buses.get("bass", 1)),
            "strum": int(buses.get("strum", 2)),
            "chord": int(buses.get("chord", 3)),
        }
        bus_values = tuple(self.bus_id.values())
        if (
            len(set(bus_values)) != 4
            or any(bus < 0 or bus > 3 for bus in bus_values)
        ):
            raise ValueError(
                "drums, bass, strum and chord must use four distinct AMY buses 0..3"
            )
        self.reverb = {''',
)

regex_once(
    amy_path,
    r'''    def _bus_for_synth\(self, synth: int\) -> int:\n.*?(?=    def _set_reverb\(self, value: Any\) -> None:)''',
    '''    def _bus_for_synth(self, synth: int) -> int:
        if synth == self.synth_id["drums"]:
            return self.bus_id["drums"]
        if synth == self.synth_id["bass"]:
            return self.bus_id["bass"]
        if synth == self.synth_id["strum"]:
            return self.bus_id["strum"]
        if synth in (
            self.synth_id["manual_chord"],
            self.synth_id["rhythm_chord"],
        ):
            return self.bus_id["chord"]
        raise KeyError(f"no AMY bus assigned for synth {synth}")

    def _route_synth_bus(self, synth: int) -> None:
        self._wire(f"i{synth}iy{self._bus_for_synth(synth)}Z")

    def _reverb_command(self, bus: int, *, enabled: bool) -> str:
        level = self.reverb["level"] if enabled else 0.0
        return (
            f"y{int(bus)}h{self._f(level)},"
            f"{self._f(self.reverb['liveness'])},"
            f"{self._f(self.reverb['damping'])}Z"
        )

    def _reverb_enabled_for_bus(self, bus: int) -> bool:
        if int(bus) == self.bus_id["drums"]:
            return bool(self.reverb["drums"])
        return True

    def _apply_reverb_bus(self, bus: int) -> None:
        self._wire(
            self._reverb_command(
                int(bus),
                enabled=self._reverb_enabled_for_bus(int(bus)),
            )
        )

    def _apply_reverb_buses(self) -> None:
        # Every musical role owns its own bus so loading a Juno patch cannot
        # leak the patch's bus-level EQ/chorus/reverb into another role.
        # The user reverb is intentionally shared across the three melodic
        # buses; drums receive the same room only when DRM is enabled.
        for bus in (
            self.bus_id["drums"],
            self.bus_id["bass"],
            self.bus_id["strum"],
            self.bus_id["chord"],
        ):
            self._apply_reverb_bus(bus)

''',
)

regex_once(
    amy_path,
    r'''    def _configure_one_synth\(self, role: str, synth: int\) -> None:\n.*?(?=    def _configure_synth\(self, role: str\) -> None:)''',
    '''    def _configure_one_synth(self, role: str, synth: int) -> None:
        self._bump_synth_generation(synth)
        patch = self._patch(role)
        bus = self._bus_for_synth(synth)
        if synth in self._configured_synths:
            # The synth already owns its dedicated bus. Current AMY preserves
            # that bus across a repatch, so patch-level EQ/chorus remain local.
            self._wire(f"l0i{synth}Z")
            self._wire(f"K{patch}i{synth}Z")
        else:
            voices = self._voice_count_for_synth(synth)
            # Put the bus in the allocation/patch event itself. Many Juno ROM
            # patches contain bus FX; without iy here those startup FX briefly
            # (and persistently) land on default bus 0 before a later route.
            self._wire(f"K{patch}i{synth}iv{voices}iy{bus}Z")
            self._configured_synths.add(synth)

            guard_ms = float(
                self.config.get("performance", {}).get(
                    "synth_alloc_guard_ms", 10.0
                )
            )
            self.writer.delay(max(0.0, guard_ms) / 1000.0)
        self._apply_patch_compatibility(patch, synth)
        self._route_synth_bus(synth)
        self._wire(f"i{synth}iV{self._f(self.volume[role])}Z")
        # A patch may carry its own reverb setting for this bus. The Omnichord
        # reverb controls are the application-level authority, so restore only
        # this role's room after the patch is loaded. Other role buses are not
        # touched.
        self._apply_reverb_bus(bus)

''',
)

# ---------------------------------------------------------------------------
# Wider pink header and permanent UI contracts.
# ---------------------------------------------------------------------------
main_qml = ROOT / "gui" / "Main.qml"
replace_once(
    main_qml,
    '''                ReverbPanel {
                    id: reverbPanel
                    x: 0
                    y: 0
                    width: 360
                    height: parent.height
                    controller: backend
                }
''',
    '''                ReverbPanel {
                    id: reverbPanel
                    x: 0
                    y: 0
                    width: 520
                    height: parent.height
                    controller: backend
                }
''',
)

static_path = ROOT / "tests" / "test_static_contracts.py"
static_text = static_path.read_text(encoding="utf-8")
insert_marker = '\n\nif __name__ == "__main__":\n'
addition = '''
    def test_reverb_header_uses_wide_horizontal_sliders(self) -> None:
        panel = (ROOT / "gui" / "ReverbPanel.qml").read_text(encoding="utf-8")
        main = (ROOT / "gui" / "Main.qml").read_text(encoding="utf-8")
        self.assertEqual(panel.count("LabeledSlider {"), 3)
        self.assertNotIn("VerticalVolume {", panel)
        self.assertGreaterEqual(panel.count("width: 145"), 3)
        self.assertIn("width: 520", main)

    def test_rhythm_transport_canvas_erases_old_symbol(self) -> None:
        qml = (ROOT / "gui" / "RhythmSection.qml").read_text(encoding="utf-8")
        self.assertIn("c.clearRect(0, 0, width, height)", qml)

    def test_each_musical_role_has_a_distinct_amy_bus(self) -> None:
        config = json.loads((ROOT / "config" / "amy_config.json").read_text(encoding="utf-8"))
        self.assertEqual(
            config["buses"],
            {"drums": 0, "bass": 1, "strum": 2, "chord": 3},
        )
        amy_py = (ROOT / "code" / "amy_serial.py").read_text(encoding="utf-8")
        self.assertIn('self.bus_id["strum"]', amy_py)
        self.assertIn('self.bus_id["chord"]', amy_py)
        self.assertIn('f"K{patch}i{synth}iv{voices}iy{bus}Z"', amy_py)
        self.assertIn("self._apply_reverb_bus(bus)", amy_py)
'''
if addition.strip() not in static_text:
    if insert_marker not in static_text:
        raise SystemExit("static-test insertion marker missing")
    static_path.write_text(static_text.replace(insert_marker, "\n" + addition + insert_marker, 1), encoding="utf-8")

# ---------------------------------------------------------------------------
# Serial regression: a strum patch change may touch only synth 2 / bus 2.
# ---------------------------------------------------------------------------
serial_path = ROOT / "tests" / "integration" / "test_serial.py"
serial_text = serial_path.read_text(encoding="utf-8")
serial_marker = '    def test_serial_framing_and_live_chord_patch_order(self) -> None:\n'
serial_test = '''    def test_strum_patch_change_is_bus_isolated_from_chords(self) -> None:
        meow = synth_index("Meow Brass")
        sustainer = synth_index("Sustainer")
        other = synth_index("Orchestral Pad")
        meow_patch = patch_for_index(meow)
        sustainer_patch = patch_for_index(sustainer)
        other_patch = patch_for_index(other)

        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=10.0)
            app.action("setChordSynthIndex", meow)
            app.bridge.wait_for_lines(
                [f"K{meow_patch}i3Z", f"K{meow_patch}i4Z"],
                start=0,
                timeout=8.0,
            )
            app.action("setStrumSynthIndex", sustainer)
            app.bridge.wait_for_lines([f"K{sustainer_patch}i2Z"], start=0, timeout=8.0)
            app.bridge.wait_idle(timeout=8.0)

            start = app.bridge.count()
            app.action("setStrumSynthIndex", other)
            lines = app.bridge.wait_for_lines([f"K{other_patch}i2Z"], start=start, timeout=8.0)
            app.bridge.wait_idle(timeout=8.0)
            lines = app.bridge.lines_since(start)

            self.assertIn("i2iy2Z", lines)
            self.assertTrue(any(line.startswith("y2h") for line in lines), lines)
            self.assertFalse(any("i3" in line or "i4" in line for line in lines), lines)
            self.assertFalse(any(line.startswith("y3") for line in lines), lines)

'''
if serial_test.strip() not in serial_text:
    if serial_marker not in serial_text:
        raise SystemExit("serial insertion marker missing")
    serial_path.write_text(serial_text.replace(serial_marker, serial_test + serial_marker, 1), encoding="utf-8")

# Startup K/iv expectations must accept the explicit bus field now included in
# the first allocation event.
serial_text = serial_path.read_text(encoding="utf-8")
serial_text = serial_text.replace(
    'if line.startswith("K") and "i4iv" in line',
    'if line.startswith("K") and "i4iv" in line and "iy3Z" in line',
)
serial_path.write_text(serial_text, encoding="utf-8")

# ---------------------------------------------------------------------------
# Native AMY regression: chord synth and chord-bus FX are invariant when only
# the strum patch changes.
# ---------------------------------------------------------------------------
native_path = ROOT / "tests" / "integration" / "test_native_controls.py"
native_text = native_path.read_text(encoding="utf-8")
native_marker = '\n\nif __name__ == "__main__":\n'
native_test = '''
    def test_strum_patch_change_cannot_change_chord_synth_or_bus(self) -> None:
        meow = synth_index("Meow Brass")
        sustainer = synth_index("Sustainer")
        other = synth_index("Orchestral Pad")

        def bus_line(state: str, bus: int) -> str:
            prefix = f"y{bus}"
            matches = [line for line in state.splitlines() if line.startswith(prefix)]
            self.assertEqual(len(matches), 1, state)
            return matches[0]

        with HeadlessApp(native_amy=True) as app:
            app.bridge.wait_idle(timeout=10.0)
            app.action("setChordSynthIndex", meow)
            app.action("setStrumSynthIndex", sustainer)
            app.bridge.wait_idle(timeout=8.0)

            before3 = app.bridge.synth_commands(3)
            before4 = app.bridge.synth_commands(4)
            before_bus3 = bus_line(app.bridge.dump_state("before-strum-switch"), 3)

            start = app.bridge.count()
            app.action("setStrumSynthIndex", other)
            app.bridge.wait_for_lines(
                [f"K{patch_for_index(other)}i2Z"], start=start, timeout=8.0
            )
            app.bridge.wait_idle(timeout=8.0)

            after3 = app.bridge.synth_commands(3)
            after4 = app.bridge.synth_commands(4)
            after_bus3 = bus_line(app.bridge.dump_state("after-strum-switch"), 3)

            self.assertEqual(before3, after3, "strum patch switch changed manual chord synth")
            self.assertEqual(before4, after4, "strum patch switch changed rhythm chord synth")
            self.assertEqual(before_bus3, after_bus3, "strum patch switch changed chord bus FX")
            app.bridge.checkpoint("strum-isolated-from-chord", synths=(2, 3, 4))
'''
if native_test.strip() not in native_text:
    if native_marker not in native_text:
        raise SystemExit("native insertion marker missing")
    native_path.write_text(native_text.replace(native_marker, "\n" + native_test + native_marker, 1), encoding="utf-8")

# Documentation note.
doc_path = ROOT / "docs" / "SEQUENCER_TAGS.md"
if doc_path.exists():
    text = doc_path.read_text(encoding="utf-8")
    note = '''\n## Synth and bus isolation\n\nSequencer tags isolate scheduled events; AMY synths isolate voice/oscillator ownership. Audio effects require one more boundary because Juno patches can contain bus-level EQ/chorus/reverb. The frontend therefore uses four AMY buses: drums 0, bass 1, strum 2, and both chord synths 3/4 on chord bus 3. A strum patch change can consequently alter only bus 2; it cannot change the sound of an already-playing chord on bus 3.\n'''
    if "## Synth and bus isolation" not in text:
        doc_path.write_text(text.rstrip() + "\n" + note, encoding="utf-8")

# Compile all edited Python sources now so the workflow fails before committing
# a malformed transformation.
for path in (amy_path, static_path, serial_path, native_path):
    compile(path.read_text(encoding="utf-8"), str(path), "exec")
