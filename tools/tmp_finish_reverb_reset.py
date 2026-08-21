#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "amysynth_version" / "qt_frontend"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"{path}: replacement anchor missing: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# ---------------------------------------------------------------------------
# Preset loading: reset the entire presettable model to application defaults,
# then overlay sparse JSON. This makes "missing means default" one rule rather
# than many unrelated fallbacks.
# ---------------------------------------------------------------------------
main_py = FRONTEND / "code" / "main.py"
reset_method = '''    def _reset_presettable_state_to_defaults(self) -> None:\n        """Restore every presettable field to application/catalogue defaults."""\n        suffix_to_index = {\n            chord.suffix: index\n            for index, chord in enumerate(self._chords)\n        }\n        octave_to_index = {\n            name: index\n            for index, name in enumerate(OCTAVE_NAMES)\n        }\n        row_defaults = self._defaults["chord_rows"]\n        self._row_chord_indexes = [\n            suffix_to_index[str(row["chord"])]\n            for row in row_defaults\n        ]\n        self._row_octave_indexes = [\n            octave_to_index[str(row["octave"])]\n            for row in row_defaults\n        ]\n        self._row_inversion_indexes = []\n        for row_index, row in enumerate(row_defaults):\n            chord_index = self._row_chord_indexes[row_index]\n            inversion_count = len(self._chords[chord_index].inversions)\n            self._row_inversion_indexes.append(\n                int(row.get("inversion", 0)) % inversion_count\n            )\n\n        for role in ("chord", "strum", "bass"):\n            self._runtime(role).reset_to_defaults()\n\n        volumes = self._defaults["volumes"]\n        self._chord_volume = max(0.0, min(1.0, float(volumes["chord"])))\n        self._strum_volume = max(0.0, min(1.0, float(volumes["strum"])))\n        self._bass_volume = max(0.0, min(1.0, float(volumes["bass"])))\n        self._percussion_volume = max(\n            0.0, min(1.0, float(volumes["percussion"]))\n        )\n\n        effects = self._defaults.get("effects", {})\n        self._main_reverb = max(\n            0.0, min(1.0, float(effects.get("main_reverb", 0.0)))\n        )\n        self._percussion_reverb = max(\n            0.0, min(1.0, float(effects.get("percussion_reverb", 0.0)))\n        )\n\n        transport = self._defaults["transport"]\n        self._rhythm_running = bool(transport["rhythm_running"])\n        self._bass_running = bool(transport["bass_running"])\n\n        rhythm_key_to_index = {\n            rhythm.key: index\n            for index, rhythm in enumerate(self._rhythms)\n        }\n        default_rhythm_key = str(self._defaults["rhythm"]["selected"])\n        self._rhythm.selected_index = rhythm_key_to_index[default_rhythm_key]\n        self._rhythm.tempo_by_rhythm = [\n            rhythm.tempo_default for rhythm in self._rhythms\n        ]\n        self._rhythm.busyness_by_rhythm = [\n            source_activity_to_ui(rhythm.default_busyness)\n            for rhythm in self._rhythms\n        ]\n        self._rhythm.chord_activity_by_rhythm = [\n            source_activity_to_ui(rhythm.default_chord_activity)\n            for rhythm in self._rhythms\n        ]\n        self._rhythm.bass_activity_by_rhythm = [\n            source_activity_to_ui(rhythm.default_bass_activity)\n            for rhythm in self._rhythms\n        ]\n\n        tuning = self._defaults.get("tuning", {})\n        mode = str(tuning.get("mode", "EQ"))\n        self._tuning_mode_index = (\n            TUNING_MODE_NAMES.index(mode)\n            if mode in TUNING_MODE_NAMES\n            else DEFAULT_TUNING_MODE_INDEX\n        )\n        self._tuning_reference = max(\n            415,\n            min(466, int(tuning.get("reference_hz", DEFAULT_TUNING_REFERENCE))),\n        )\n\n'''
replace_once(
    main_py,
    "    def _apply_preset_data(\n",
    reset_method + "    def _apply_preset_data(\n",
)
replace_once(
    main_py,
    '''    def _apply_preset_data(\n        self,\n        data: dict[str, Any],\n    ) -> None:\n        suffix_to_index = {\n''',
    '''    def _apply_preset_data(\n        self,\n        data: dict[str, Any],\n    ) -> None:\n        self._reset_presettable_state_to_defaults()\n\n        suffix_to_index = {\n''',
)

# ---------------------------------------------------------------------------
# Defensive AMY-side safety: every sparse parameter read by command generation
# goes through the same hard safety table, even in tests/internal callers.
# Also validate the two effect buses are distinct and are within default AMY's
# four-bus range.
# ---------------------------------------------------------------------------
amy_serial = FRONTEND / "code" / "amy_serial.py"
replace_once(
    amy_serial,
    '''        self.bus_id = {\n            "main": int(buses.get("main", 0)),\n            "percussion": int(buses.get("percussion", 1)),\n        }\n        self.reverb = {"main": 0.0, "percussion": 0.0}\n''',
    '''        self.bus_id = {\n            "main": int(buses.get("main", 0)),\n            "percussion": int(buses.get("percussion", 1)),\n        }\n        if (\n            self.bus_id["main"] == self.bus_id["percussion"]\n            or any(bus < 0 or bus > 3 for bus in self.bus_id.values())\n        ):\n            raise ValueError(\n                "main and percussion buses must be distinct AMY buses 0..3"\n            )\n        self.reverb = {"main": 0.0, "percussion": 0.0}\n''',
)
replace_once(
    amy_serial,
    '''            value = params.get(name)\n            if value is None or value < 0:\n                return None\n            return float(value)\n''',
    '''            value = params.get(name)\n            if value is None or value < 0:\n                return None\n            return clamp_control_value(name, float(value))\n''',
)
replace_once(
    amy_serial,
    '''                    value = params.get(name)\n                    if value is None or value < 0:\n                        return None\n                    return float(value)\n''',
    '''                    value = params.get(name)\n                    if value is None or value < 0:\n                        return None\n                    return clamp_control_value(name, float(value))\n''',
)

# ---------------------------------------------------------------------------
# Small UI polish: identify the two otherwise unlabeled pink sliders and avoid
# giving shifted chord-row delegates an unnecessary extra left-rail width.
# ---------------------------------------------------------------------------
main_qml = FRONTEND / "gui" / "Main.qml"
labels = '''            Text {\n                x: 86\n                y: window.utilityY + 33\n                width: 26\n                text: "ALL\\nREV"\n                color: "#6b3048"\n                font.pixelSize: 9\n                font.bold: true\n                horizontalAlignment: Text.AlignHCenter\n            }\n\n            Text {\n                x: 86\n                y: window.rhythmY + 33\n                width: 26\n                text: "DRM\\nREV"\n                color: "#6b3048"\n                font.pixelSize: 9\n                font.bold: true\n                horizontalAlignment: Text.AlignHCenter\n            }\n\n'''
replace_once(
    main_qml,
    "            UtilitySection {\n",
    labels + "            UtilitySection {\n",
)
replace_once(
    main_qml,
    '''                        width:\n                            window.maximumChordRowWidth\n                        height: window.rowHeight\n''',
    '''                        width:\n                            window.maximumChordRowWidth\n                            - window.contentX\n                        height: window.rowHeight\n''',
)

print("Finished preset-default semantics, AMY safety validation and UI labels.")
