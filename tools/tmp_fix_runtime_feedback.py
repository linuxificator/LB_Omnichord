#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "amysynth_version" / "qt_frontend"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"{path}: replacement anchor missing: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# ---------------------------------------------------------------------------
# Cold-start synth allocation: AMY applies K/iv at an audio block boundary.
# Do not send synth-tier commands (bus/level/compatibility/params) immediately
# after first allocation; give the target several blocks to create the synth.
# ---------------------------------------------------------------------------
amy_serial = FRONTEND / "code" / "amy_serial.py"
replace_once(
    amy_serial,
    '''        else:\n            voices = self._voice_count_for_synth(synth)\n            self._wire(f"K{patch}i{synth}iv{voices}Z")\n            self._configured_synths.add(synth)\n        self._apply_patch_compatibility(patch, synth)\n''',
    '''        else:\n            voices = self._voice_count_for_synth(synth)\n            self._wire(f"K{patch}i{synth}iv{voices}Z")\n            self._configured_synths.add(synth)\n\n            # First-time K/iv allocation is executed by AMY on an audio-block\n            # boundary.  Subsequent synth-tier commands (iy/iV/flags/etc.) can\n            # otherwise arrive while the instrument table entry is still NULL,\n            # producing "synth N not defined" warnings on the ESP32-P4.\n            guard_ms = float(\n                self.config.get("performance", {}).get(\n                    "synth_alloc_guard_ms", 10.0\n                )\n            )\n            self.writer.delay(max(0.0, guard_ms) / 1000.0)\n        self._apply_patch_compatibility(patch, synth)\n''',
)

# Exact reverb level 0 is avoided on the P4.  At cold start, zero means do not
# instantiate/touch the effect at all.  When turning an already-active reverb
# off, use a sub-audible nonzero wire value while retaining logical/UI state 0.
replace_once(
    amy_serial,
    '''    def _apply_reverb_buses(self) -> None:\n        self._wire(\n            f"y{self.bus_id['main']}h{self._f(self.reverb['main'])}Z"\n        )\n        self._wire(\n            f"y{self.bus_id['percussion']}h{self._f(self.reverb['percussion'])}Z"\n        )\n\n    def _set_reverb(self, lane: str, value: Any) -> None:\n        level = max(0.0, min(1.0, float(value)))\n        self.reverb[lane] = level\n        bus = self.bus_id[lane]\n        self._wire(f"y{bus}h{self._f(level)}Z")\n''',
    '''    _REVERB_OFF_WIRE_LEVEL = 0.001\n\n    def _apply_reverb_buses(self) -> None:\n        # Do not send h0 on a fresh engine.  On the ESP32-P4 an exact-zero\n        # reverb coefficient can produce low-frequency rumble; untouched AMY\n        # buses are already dry.\n        for lane in ("main", "percussion"):\n            level = self.reverb[lane]\n            if level > 0.0:\n                self._wire(\n                    f"y{self.bus_id[lane]}h{self._f(level)}Z"\n                )\n\n    def _set_reverb(self, lane: str, value: Any) -> None:\n        level = max(0.0, min(1.0, float(value)))\n        previous = self.reverb[lane]\n        if math.isclose(level, previous, rel_tol=0.0, abs_tol=1e-9):\n            return\n        self.reverb[lane] = level\n        bus = self.bus_id[lane]\n        wire_level = (\n            level\n            if level > 0.0\n            else self._REVERB_OFF_WIRE_LEVEL\n        )\n        self._wire(f"y{bus}h{self._f(wire_level)}Z")\n''',
)

# ---------------------------------------------------------------------------
# Manual chord hold must not rebuild rhythm twice. The chord-enable packet is
# sufficient; rhythm config did not change. Receiver rebuilds once, retaining
# percussion and bass lanes while suppressing/restoring automatic chords.
# ---------------------------------------------------------------------------
main_py = FRONTEND / "code" / "main.py"
replace_once(
    main_py,
    '''        self.rhythmControlsChanged.emit()\n        self._send_rhythm_chord_enabled()\n        self._send_rhythm_config()\n\n    def _clear_touch_dropout_state(self) -> None:\n''',
    '''        self.rhythmControlsChanged.emit()\n        self._send_rhythm_chord_enabled()\n\n    def _clear_touch_dropout_state(self) -> None:\n''',
)

# User no longer wants a rhythm reset control; remove its backend method too.
text = main_py.read_text(encoding="utf-8")
start = text.find('    @Slot()\n    def resetRhythmControlsToPreset(self) -> None:\n')
if start >= 0:
    end = text.find('    @Slot()\n    def resetChordRowsToPreset(self) -> None:\n', start)
    if end < 0:
        raise RuntimeError('resetRhythmControlsToPreset end anchor missing')
    text = text[:start] + text[end:]
    main_py.write_text(text, encoding="utf-8")

# ---------------------------------------------------------------------------
# UI: narrow the left rail, remove RHY, and use one common RST label.
# ---------------------------------------------------------------------------
main_qml = FRONTEND / "gui" / "Main.qml"
replace_once(main_qml, '    property int leftRailWidth: 116\n', '    property int leftRailWidth: 64\n')
text = main_qml.read_text(encoding="utf-8")
# Remove the RHY button block, identified by its reset action.
rhy_action = '                onClicked: backend.resetRhythmControlsToPreset()\n'
pos = text.find(rhy_action)
if pos >= 0:
    block_start = text.rfind('            PresetResetButton {\n', 0, pos)
    block_end = text.find('            }\n\n', pos)
    if block_start < 0 or block_end < 0:
        raise RuntimeError('RHY button block boundaries not found')
    text = text[:block_start] + text[block_end + len('            }\n\n'):]
# Center the remaining bass reset in the now-narrow rail.
text = text.replace('                x: 61\n                y: window.bassSynthY',
                    '                x: (window.leftRailWidth - width) / 2\n                y: window.bassSynthY', 1)
# All reset buttons use the same label.
for old in ('text: "BAS"', 'text: "STR"', 'text: "CHD"', 'text: "ROWS"'):
    text = text.replace(old, 'text: "RST"')
# Labels for pink sliders need to live inside the reduced rail. Put compact
# horizontal labels above the percentage panel rather than beside the slider.
text = text.replace('                x: 86\n                y: window.utilityY + 33\n                width: 26\n                text: "ALL\\nREV"',
                    '                x: 2\n                y: window.utilityY + 2\n                width: window.leftRailWidth - 4\n                text: "REV"')
text = text.replace('                x: 86\n                y: window.rhythmY + 33\n                width: 26\n                text: "DRM\\nREV"',
                    '                x: 2\n                y: window.rhythmY + 2\n                width: window.leftRailWidth - 4\n                text: "DRM REV"')
main_qml.write_text(text, encoding="utf-8")

# Configurable allocation guard.
import json
cfg_path = FRONTEND / "config" / "amy_config.json"
cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
cfg.setdefault("performance", {})["synth_alloc_guard_ms"] = 10.0
cfg_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")

print('Applied cold-start, zero-reverb, hold/rhythm, and reset-rail fixes.')
