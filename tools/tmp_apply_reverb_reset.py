#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "amysynth_version" / "qt_frontend"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one occurrence, found {count}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_regex(path: Path, pattern: str, replacement: str, *, flags: int = 0) -> None:
    text = path.read_text(encoding="utf-8")
    new, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f"{path}: regex did not match exactly once: {pattern[:100]!r}")
    path.write_text(new, encoding="utf-8")


# ---------------------------------------------------------------------------
# Shared hard safety limits. These are deliberately wider than the shipped
# musical defaults, but prevent pathological UI/preset/transport values from
# reaching AMY DSP code.
# ---------------------------------------------------------------------------
control_limits = '''from __future__ import annotations

import math


# Absolute application safety limits. Catalogue entries may narrow these
# ranges, never widen them. Values are in the units shown by the UI.
CONTROL_LIMITS: dict[str, tuple[float, float]] = {
    "filter_hz": (20.0, 10000.0),
    "resonance": (0.51, 12.0),
    "lfo_hz": (0.1, 20.0),
    "vibrato_depth": (0.0, 0.05),
    "filter_lfo_depth": (0.0, 0.5),
    "pulse_width": (0.05, 0.95),
    "pwm_depth": (0.0, 0.45),
    "portamento_ms": (0.0, 1000.0),
    "attack_ms": (0.0, 3000.0),
    "decay_ms": (0.0, 10000.0),
    "sustain": (0.0, 1.0),
    "release_ms": (0.0, 10000.0),
    "algorithm": (1.0, 32.0),
    "feedback": (0.0, 0.5),
}


def hard_range(key: str) -> tuple[float, float] | None:
    return CONTROL_LIMITS.get(str(key))


def bounded_control_range(
    key: str,
    minimum: float,
    maximum: float,
) -> tuple[float, float]:
    low = float(minimum)
    high = float(maximum)
    if not math.isfinite(low) or not math.isfinite(high) or low > high:
        raise ValueError(f"invalid range for {key}: {minimum}..{maximum}")
    hard = hard_range(key)
    if hard is not None:
        low = max(low, hard[0])
        high = min(high, hard[1])
    if low > high:
        raise ValueError(f"empty safe range for {key}: {low}..{high}")
    return low, high


def clamp_control_value(key: str, value: float) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"non-finite value for {key}: {value!r}")
    hard = hard_range(key)
    if hard is None:
        return number
    return max(hard[0], min(hard[1], number))
'''
(FRONTEND / "code" / "control_limits.py").write_text(control_limits, encoding="utf-8")


# ---------------------------------------------------------------------------
# Catalogue: normalize every UI range to the shared hard safety envelope and
# correct the three unsafe >10 kHz application defaults. Raw native_default is
# retained as metadata; if the safe application default differs, SynthState
# sends an explicit override after the factory patch is loaded.
# ---------------------------------------------------------------------------
synth_path = FRONTEND / "instruments" / "synths.json"
synth_data = json.loads(synth_path.read_text(encoding="utf-8"))
limits = {
    "filter_hz": (20.0, 10000.0),
    "resonance": (0.51, 12.0),
    "lfo_hz": (0.1, 20.0),
    "vibrato_depth": (0.0, 0.05),
    "filter_lfo_depth": (0.0, 0.5),
    "pulse_width": (0.05, 0.95),
    "pwm_depth": (0.0, 0.45),
    "portamento_ms": (0.0, 1000.0),
    "attack_ms": (0.0, 3000.0),
    "decay_ms": (0.0, 10000.0),
    "sustain": (0.0, 1.0),
    "release_ms": (0.0, 10000.0),
    "algorithm": (1.0, 32.0),
    "feedback": (0.0, 0.5),
}
filter_defaults = {
    "juno_048": 9000.0,  # Sweep I: retain a very bright setting without Nyquist-edge operation.
    "juno_068": 6000.0,  # Harpsichord 1: P4 stability correction.
    "juno_089": 6000.0,  # Harpsichord 2: same family / same unsafe native extreme.
}
for synth in synth_data["synths"]:
    key = str(synth["key"])
    for control in synth["controls"]:
        ckey = str(control["key"])
        if ckey in limits:
            low, high = limits[ckey]
            control["minimum"] = max(float(control["minimum"]), low)
            control["maximum"] = min(float(control["maximum"]), high)
        if ckey == "filter_hz" and key in filter_defaults:
            control["default"] = filter_defaults[key]
        value = float(control["default"])
        control["default"] = max(float(control["minimum"]), min(float(control["maximum"]), value))

synth_data["schema_version"] = max(6, int(synth_data.get("schema_version", 1)))
synth_data.setdefault("source", {})["slider_defaults"] = (
    "Native AMY values remain metadata; application defaults and all UI/preset/transport values "
    "are bounded by shared DSP safety limits. Frequency controls use Hz and logarithmic travel."
)
synth_path.write_text(json.dumps(synth_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Defaults/config: effects default to dry, route drums to bus 1 and melodic
# synths to bus 0, and lower known unsafe factory-patch compatibility values.
# ---------------------------------------------------------------------------
defaults_path = FRONTEND / "config" / "defaults.json"
defaults = json.loads(defaults_path.read_text(encoding="utf-8"))
defaults["effects"] = {"main_reverb": 0.0, "percussion_reverb": 0.0}
defaults_path.write_text(json.dumps(defaults, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

amy_cfg_path = FRONTEND / "config" / "amy_config.json"
amy_cfg = json.loads(amy_cfg_path.read_text(encoding="utf-8"))
amy_cfg["buses"] = {"main": 0, "percussion": 1}
compat = amy_cfg.setdefault("patch_compatibility", {})
compat["68"]["reason"] = (
    "Factory patch requests an extreme filter state; constrain the P4 filter to a stable bright range."
)
compat["68"]["juno_filter_hz"] = 6000.0
compat["68"]["juno_resonance"] = 4.0
compat["89"] = {
    "label": "Juno B26 Harpsichord 2",
    "reason": "Factory filter base is at the unsafe top edge; keep the P4 filter in a stable bright range.",
    "juno_filter_hz": 6000.0,
}
compat["48"] = {
    "label": "Juno A71 Sweep I",
    "reason": "Factory filter base is at the previous 18 kHz UI limit; constrain it below the DSP safety ceiling.",
    "juno_filter_hz": 9000.0,
}
amy_cfg_path.write_text(json.dumps(amy_cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# SynthState: one shared clamping function and an OO reset operation that keeps
# the selected synth while restoring only that synth's preset/default values.
# ---------------------------------------------------------------------------
synth_state = FRONTEND / "code" / "synth_state.py"
replace_once(
    synth_state,
    "import math\nfrom typing import Any, Sequence\n",
    "import math\nfrom typing import Any, Sequence\n\nfrom control_limits import clamp_control_value\n",
)
replace_once(
    synth_state,
    '''        clamped = max(\n            float(control.minimum),\n            min(float(control.maximum), float(value)),\n        )\n''',
    '''        clamped = clamp_control_value(control.key, float(value))\n        clamped = max(\n            float(control.minimum),\n            min(float(control.maximum), clamped),\n        )\n''',
)
replace_once(
    synth_state,
    '''                    stored = float(stored_values[control.key])\n                    # Legacy presets used negative values as "patch/default".\n                    if stored < 0.0 and float(control.default) >= 0.0:\n                        continue\n                    values[control.key] = max(\n                        float(control.minimum),\n                        min(float(control.maximum), stored),\n                    )\n''',
    '''                    stored = float(stored_values[control.key])\n                    # Legacy presets used negative values as "patch/default".\n                    if stored < 0.0 and float(control.default) >= 0.0:\n                        continue\n                    try:\n                        stored = clamp_control_value(control.key, stored)\n                    except ValueError:\n                        continue\n                    values[control.key] = max(\n                        float(control.minimum),\n                        min(float(control.maximum), stored),\n                    )\n''',
)
insert_before = '''    def control_model(self, group: str) -> list[dict[str, Any]]:\n'''
reset_method = '''    def reset_selected_from_preset(self, data: dict[str, Any]) -> bool:\n        """Restore the current instrument without changing instrument selection.\n\n        Sparse preset parameters are keyed by instrument. Missing values mean\n        application catalogue defaults. This is the exact reset semantics used\n        by the per-section UI reset buttons.\n        """\n        definition = self.selected_definition\n        new_values = {\n            str(control.key): float(control.default)\n            for control in definition.controls\n        }\n        all_parameters = data.get("parameters", {}) if isinstance(data, dict) else {}\n        stored_values = (\n            all_parameters.get(definition.key, {})\n            if isinstance(all_parameters, dict)\n            else {}\n        )\n        if isinstance(stored_values, dict):\n            for control in definition.controls:\n                if control.key not in stored_values:\n                    continue\n                stored = float(stored_values[control.key])\n                if stored < 0.0 and float(control.default) >= 0.0:\n                    continue\n                try:\n                    stored = clamp_control_value(control.key, stored)\n                except ValueError:\n                    continue\n                new_values[control.key] = max(\n                    float(control.minimum),\n                    min(float(control.maximum), stored),\n                )\n\n        old_values = self.selected_values\n        changed = any(\n            not math.isclose(\n                float(old_values.get(key, value)),\n                float(value),\n                rel_tol=0.0,\n                abs_tol=1e-9,\n            )\n            for key, value in new_values.items()\n        )\n        if changed:\n            self._values_by_synth[self._selected_index] = new_values\n        return changed\n\n'''
replace_once(synth_state, insert_before, reset_method + insert_before)


# ---------------------------------------------------------------------------
# main.py catalogue safety + effects/preset reset state.
# ---------------------------------------------------------------------------
main_py = FRONTEND / "code" / "main.py"
replace_once(
    main_py,
    "from amy_serial import AmySerialClient, load_amy_config\nfrom synth_state import SynthState\n",
    "from amy_serial import AmySerialClient, load_amy_config\nfrom control_limits import bounded_control_range, clamp_control_value\nfrom synth_state import SynthState\n",
)
old_catalog = '''        controls = tuple(\n            SynthControl(\n                key=str(control["key"]),\n                label=str(control["label"]),\n                group=str(control["group"]),\n                default=float(control["default"]),\n                native_default=(\n                    None\n                    if control.get("native_default") is None\n                    else float(control["native_default"])\n                ),\n                minimum=float(control["minimum"]),\n                maximum=float(control["maximum"]),\n                step=float(control["step"]),\n                decimals=int(control["decimals"]),\n                unit=str(control.get("unit", "")),\n                scale=str(control.get("scale", "linear")),\n            )\n            for control in raw_synth["controls"]\n        )\n'''
new_catalog = '''        controls_list: list[SynthControl] = []\n        for control in raw_synth["controls"]:\n            key = str(control["key"])\n            minimum, maximum = bounded_control_range(\n                key,\n                float(control["minimum"]),\n                float(control["maximum"]),\n            )\n            default = clamp_control_value(key, float(control["default"]))\n            default = max(minimum, min(maximum, default))\n            controls_list.append(\n                SynthControl(\n                    key=key,\n                    label=str(control["label"]),\n                    group=str(control["group"]),\n                    default=default,\n                    native_default=(\n                        None\n                        if control.get("native_default") is None\n                        else float(control["native_default"])\n                    ),\n                    minimum=minimum,\n                    maximum=maximum,\n                    step=float(control["step"]),\n                    decimals=int(control["decimals"]),\n                    unit=str(control.get("unit", "")),\n                    scale=str(control.get("scale", "linear")),\n                )\n            )\n        controls = tuple(controls_list)\n'''
replace_once(main_py, old_catalog, new_catalog)

replace_once(
    main_py,
    '''    percussionVolumeChanged = Signal()\n    bassRunningChanged = Signal()\n''',
    '''    percussionVolumeChanged = Signal()\n    mainReverbChanged = Signal()\n    percussionReverbChanged = Signal()\n    bassRunningChanged = Signal()\n''',
)
replace_once(
    main_py,
    '''        percussion_amp_address: str,\n        chord_synth_address: str,\n''',
    '''        percussion_amp_address: str,\n        main_reverb_address: str,\n        percussion_reverb_address: str,\n        chord_synth_address: str,\n''',
)
replace_once(
    main_py,
    '''        self._percussion_amp_address = percussion_amp_address\n        self._chord_synth_address = chord_synth_address\n''',
    '''        self._percussion_amp_address = percussion_amp_address\n        self._main_reverb_address = main_reverb_address\n        self._percussion_reverb_address = percussion_reverb_address\n        self._chord_synth_address = chord_synth_address\n''',
)
replace_once(
    main_py,
    '''        self._selected_preset = 1\n        self._tuning_mode_index = (\n''',
    '''        self._defaults = copy.deepcopy(defaults)\n        self._preset_reference_data: dict[str, Any] = {}\n        self._selected_preset = 1\n        self._tuning_mode_index = (\n''',
)
replace_once(
    main_py,
    '''        self._percussion_volume = float(\n            volumes["percussion"]\n        )\n        self._bass_running = bool(\n''',
    '''        self._percussion_volume = float(\n            volumes["percussion"]\n        )\n        effects = defaults.get("effects", {})\n        self._main_reverb = max(\n            0.0, min(1.0, float(effects.get("main_reverb", 0.0)))\n        )\n        self._percussion_reverb = max(\n            0.0, min(1.0, float(effects.get("percussion_reverb", 0.0)))\n        )\n        self._bass_running = bool(\n''',
)
replace_once(
    main_py,
    '''    @Property(float, notify=percussionVolumeChanged)\n    def percussionVolume(self) -> float:\n        return self._percussion_volume\n\n''',
    '''    @Property(float, notify=percussionVolumeChanged)\n    def percussionVolume(self) -> float:\n        return self._percussion_volume\n\n    @Property(float, notify=mainReverbChanged)\n    def mainReverb(self) -> float:\n        return self._main_reverb\n\n    @Property(float, notify=percussionReverbChanged)\n    def percussionReverb(self) -> float:\n        return self._percussion_reverb\n\n''',
)
replace_once(
    main_py,
    '''    def _emit_synth_change(\n''',
    '''    @Slot(float)\n    def setMainReverb(self, value: float) -> None:\n        clamped = max(0.0, min(1.0, float(value)))\n        if abs(clamped - self._main_reverb) < 0.0001:\n            return\n        self._main_reverb = clamped\n        self.mainReverbChanged.emit()\n        self._client.send_message(self._main_reverb_address, clamped)\n\n    @Slot(float)\n    def setPercussionReverb(self, value: float) -> None:\n        clamped = max(0.0, min(1.0, float(value)))\n        if abs(clamped - self._percussion_reverb) < 0.0001:\n            return\n        self._percussion_reverb = clamped\n        self.percussionReverbChanged.emit()\n        self._client.send_message(self._percussion_reverb_address, clamped)\n\n    def _emit_synth_change(\n''',
)

# Snapshot becomes a local object so optional dry effects can be omitted.
replace_once(main_py, "        return {\n            \"version\": 1,\n", "        snapshot: dict[str, Any] = {\n            \"version\": 1,\n")
replace_once(
    main_py,
    '''            "tuning": {\n                "mode": TUNING_MODE_NAMES[\n                    self._tuning_mode_index\n                ],\n                "reference_hz": (\n                    self._tuning_reference\n                ),\n            },\n        }\n\n    def _ensure_preset_storage''',
    '''            "tuning": {\n                "mode": TUNING_MODE_NAMES[\n                    self._tuning_mode_index\n                ],\n                "reference_hz": (\n                    self._tuning_reference\n                ),\n            },\n        }\n        effects: dict[str, float] = {}\n        if abs(self._main_reverb) > 1e-9:\n            effects["main_reverb"] = self._main_reverb\n        if abs(self._percussion_reverb) > 1e-9:\n            effects["percussion_reverb"] = self._percussion_reverb\n        if effects:\n            snapshot["effects"] = effects\n        return snapshot\n\n    def _ensure_preset_storage''',
)

# Keep the selected preset's file as the immutable reset baseline until Store.
replace_once(
    main_py,
    '''            self._apply_preset_data(data)\n            self._selected_preset = (\n                preset_number\n            )\n''',
    '''            self._apply_preset_data(data)\n            self._preset_reference_data = copy.deepcopy(data)\n            self._selected_preset = (\n                preset_number\n            )\n''',
)
# selectPreset has a second occurrence after the startup one.
replace_once(
    main_py,
    '''        self._selected_preset = preset_number\n        self._write_last_preset()\n\n        self._emit_full_preset_state()\n''',
    '''        self._selected_preset = preset_number\n        self._preset_reference_data = copy.deepcopy(data)\n        self._write_last_preset()\n\n        self._emit_full_preset_state()\n''',
)
replace_once(
    main_py,
    '''    def storeSelectedPreset(self) -> None:\n        self._write_json_atomic(\n            self._preset_path(\n                self._selected_preset\n            ),\n            self._preset_snapshot(),\n        )\n        self._write_last_preset()\n''',
    '''    def storeSelectedPreset(self) -> None:\n        snapshot = self._preset_snapshot()\n        self._write_json_atomic(\n            self._preset_path(\n                self._selected_preset\n            ),\n            snapshot,\n        )\n        self._preset_reference_data = copy.deepcopy(snapshot)\n        self._write_last_preset()\n''',
)

# Preset effects always fall back to dry, never to the previously selected preset.
replace_once(
    main_py,
    '''        transport = data.get(\n            "transport",\n            {},\n        )\n''',
    '''        effects = data.get("effects", {})\n        if not isinstance(effects, dict):\n            effects = {}\n        default_effects = self._defaults.get("effects", {})\n        self._main_reverb = max(\n            0.0,\n            min(\n                1.0,\n                float(effects.get("main_reverb", default_effects.get("main_reverb", 0.0))),\n            ),\n        )\n        self._percussion_reverb = max(\n            0.0,\n            min(\n                1.0,\n                float(\n                    effects.get(\n                        "percussion_reverb",\n                        default_effects.get("percussion_reverb", 0.0),\n                    )\n                ),\n            ),\n        )\n\n        transport = data.get(\n            "transport",\n            {},\n        )\n''',
)
replace_once(
    main_py,
    '''        self.percussionVolumeChanged.emit()\n        self.bassRunningChanged.emit()\n''',
    '''        self.percussionVolumeChanged.emit()\n        self.mainReverbChanged.emit()\n        self.percussionReverbChanged.emit()\n        self.bassRunningChanged.emit()\n''',
)

# Reset helpers/slots, inserted before panic.
reset_slots = '''    def _preset_role_data(self, role: SynthRole) -> dict[str, Any]:\n        synths = self._preset_reference_data.get("synths", {})\n        if not isinstance(synths, dict):\n            return {}\n        value = synths.get(role, {})\n        return value if isinstance(value, dict) else {}\n\n    def _preset_volume_for_role(self, role: SynthRole) -> float:\n        volumes = self._preset_reference_data.get("volumes", {})\n        if not isinstance(volumes, dict):\n            volumes = {}\n        default = float(self._defaults["volumes"][role])\n        return max(0.0, min(1.0, float(volumes.get(role, default))))\n\n    def _reset_synth_role_to_preset(self, role: SynthRole) -> None:\n        runtime = self._runtime(role)\n        runtime.reset_selected_from_preset(self._preset_role_data(role))\n        volume = self._preset_volume_for_role(role)\n        if role == "chord":\n            self._chord_volume = volume\n            self.chordVolumeChanged.emit()\n            amp_address = self._chord_amp_address\n        elif role == "strum":\n            self._strum_volume = volume\n            self.strumVolumeChanged.emit()\n            amp_address = self._strum_amp_address\n        else:\n            self._bass_volume = volume\n            self.bassVolumeChanged.emit()\n            amp_address = self._bass_amp_address\n        self._emit_synth_change(role, selection_changed=False)\n        self._send_synth_state(role)\n        self._client.send_message(amp_address, volume)\n\n    @Slot()\n    def resetBassToPreset(self) -> None:\n        # Deliberately does not touch bass synth selection or bass on/off.\n        self._reset_synth_role_to_preset("bass")\n\n    @Slot()\n    def resetStrumToPreset(self) -> None:\n        self._reset_synth_role_to_preset("strum")\n\n    @Slot()\n    def resetChordSynthToPreset(self) -> None:\n        self._reset_synth_role_to_preset("chord")\n\n    @Slot()\n    def resetRhythmControlsToPreset(self) -> None:\n        index = self._rhythm.selected_index\n        rhythm = self._rhythms[index]\n        rhythm_data = self._preset_reference_data.get("rhythm", {})\n        if not isinstance(rhythm_data, dict):\n            rhythm_data = {}\n        settings = rhythm_data.get("settings", {})\n        if not isinstance(settings, dict):\n            settings = {}\n        stored = settings.get(rhythm.key, {})\n        if not isinstance(stored, dict):\n            stored = {}\n        self._rhythm.tempo_by_rhythm[index] = max(\n            40.0, min(200.0, float(stored.get("tempo", rhythm.tempo_default)))\n        )\n        self._rhythm.busyness_by_rhythm[index] = max(\n            1,\n            min(\n                4,\n                int(\n                    stored.get(\n                        "percussion_activity",\n                        source_activity_to_ui(rhythm.default_busyness),\n                    )\n                ),\n            ),\n        )\n        self._rhythm.chord_activity_by_rhythm[index] = max(\n            0,\n            min(\n                4,\n                int(\n                    stored.get(\n                        "chord_activity",\n                        source_activity_to_ui(rhythm.default_chord_activity),\n                    )\n                ),\n            ),\n        )\n        self._rhythm.bass_activity_by_rhythm[index] = max(\n            1,\n            min(\n                4,\n                int(\n                    stored.get(\n                        "bass_activity",\n                        source_activity_to_ui(rhythm.default_bass_activity),\n                    )\n                ),\n            ),\n        )\n        self.rhythmControlsChanged.emit()\n        self._send_rhythm_chord_enabled()\n        self._send_rhythm_config()\n\n    @Slot()\n    def resetChordRowsToPreset(self) -> None:\n        rows = self._preset_reference_data.get("chord_rows", [])\n        defaults = self._defaults["chord_rows"]\n        if not isinstance(rows, list) or len(rows) != ROW_COUNT:\n            rows = defaults\n        suffix_to_index = {chord.suffix: i for i, chord in enumerate(self._chords)}\n        octave_to_index = {name: i for i, name in enumerate(OCTAVE_NAMES)}\n        for row_index in range(ROW_COUNT):\n            stored = rows[row_index] if isinstance(rows[row_index], dict) else {}\n            fallback = defaults[row_index]\n            chord_key = str(stored.get("chord", fallback["chord"]))\n            octave_key = str(stored.get("octave", fallback["octave"]))\n            chord_index = suffix_to_index.get(\n                chord_key, suffix_to_index[str(fallback["chord"])]\n            )\n            octave_index = octave_to_index.get(\n                octave_key, octave_to_index[str(fallback["octave"])]\n            )\n            self._row_chord_indexes[row_index] = chord_index\n            self._row_octave_indexes[row_index] = octave_index\n            inversion_count = len(self._chords[chord_index].inversions)\n            self._row_inversion_indexes[row_index] = (\n                int(stored.get("inversion", fallback.get("inversion", 0)))\n                % inversion_count\n            )\n        self._strum_last_index = None\n        self._emit_state_changed()\n        for row_index in range(ROW_COUNT):\n            self._refresh_row_chord_notes(row_index)\n\n'''
replace_once(main_py, "    @Slot()\n    def panic(self) -> None:\n", reset_slots + "    @Slot()\n    def panic(self) -> None:\n")

# Initial state must explicitly restore the two buses' effect levels.
replace_once(
    main_py,
    '''        self._client.send_message(\n            self._percussion_amp_address,\n            self._percussion_volume,\n        )\n\n        self._send_synth_state("chord")\n''',
    '''        self._client.send_message(\n            self._percussion_amp_address,\n            self._percussion_volume,\n        )\n        self._client.send_message(\n            self._main_reverb_address,\n            self._main_reverb,\n        )\n        self._client.send_message(\n            self._percussion_reverb_address,\n            self._percussion_reverb,\n        )\n\n        self._send_synth_state("chord")\n''',
)

# CLI/logical address wiring.
replace_once(
    main_py,
    '''    parser.add_argument(\n        "--percussion-amp-address",\n        default="/rhythm/amp",\n    )\n''',
    '''    parser.add_argument(\n        "--percussion-amp-address",\n        default="/rhythm/amp",\n    )\n    parser.add_argument(\n        "--main-reverb-address",\n        default="/effects/main/reverb",\n    )\n    parser.add_argument(\n        "--percussion-reverb-address",\n        default="/effects/percussion/reverb",\n    )\n''',
)
replace_once(
    main_py,
    '''        "percussion_amp": args.percussion_amp_address,\n        "chord_synth": args.chord_synth_address,\n''',
    '''        "percussion_amp": args.percussion_amp_address,\n        "main_reverb": args.main_reverb_address,\n        "percussion_reverb": args.percussion_reverb_address,\n        "chord_synth": args.chord_synth_address,\n''',
)
replace_once(
    main_py,
    '''        percussion_amp_address=args.percussion_amp_address,\n        chord_synth_address=args.chord_synth_address,\n''',
    '''        percussion_amp_address=args.percussion_amp_address,\n        main_reverb_address=args.main_reverb_address,\n        percussion_reverb_address=args.percussion_reverb_address,\n        chord_synth_address=args.chord_synth_address,\n''',
)


# ---------------------------------------------------------------------------
# AmySerialClient: defensive parameter clamping, bus routing and per-bus reverb.
# ---------------------------------------------------------------------------
amy_serial = FRONTEND / "code" / "amy_serial.py"
replace_once(
    amy_serial,
    "import serial\n\n\nAMY_PPQ",
    "import serial\n\nfrom control_limits import clamp_control_value\n\n\nAMY_PPQ",
)
replace_once(
    amy_serial,
    ''' 'default_synths': {'chord': 'juno_004', 'strum': 'juno_028', 'bass': 'dx7_143'},\n 'drums': {''',
    ''' 'default_synths': {'chord': 'juno_004', 'strum': 'juno_028', 'bass': 'dx7_143'},\n 'buses': {'main': 0, 'percussion': 1},\n 'drums': {''',
)
replace_once(
    amy_serial,
    '''                                'juno_filter_hz': 16000.0,\n                                'juno_resonance': 4.0},\n                         '74': {''',
    '''                                'juno_filter_hz': 6000.0,\n                                'juno_resonance': 4.0},\n                         '89': {'label': 'Juno B26 Harpsichord 2',\n                                'reason': 'Factory filter base is at the unsafe top edge; keep the P4 filter stable.',\n                                'juno_filter_hz': 6000.0},\n                         '48': {'label': 'Juno A71 Sweep I',\n                                'reason': 'Factory filter base is at the previous 18 kHz UI limit; keep below safety ceiling.',\n                                'juno_filter_hz': 9000.0},\n                         '74': {''',
)
replace_once(
    amy_serial,
    '''        self.volume = {\n            "chord": 0.5,\n            "strum": 0.5,\n            "bass": 0.5,\n            "drums": 0.5,\n        }\n\n        self.chord_notes''',
    '''        self.volume = {\n            "chord": 0.5,\n            "strum": 0.5,\n            "bass": 0.5,\n            "drums": 0.5,\n        }\n        buses = config.get("buses", {})\n        self.bus_id = {\n            "main": int(buses.get("main", 0)),\n            "percussion": int(buses.get("percussion", 1)),\n        }\n        self.reverb = {"main": 0.0, "percussion": 0.0}\n\n        self.chord_notes''',
)
# Compatibility clamps.
replace_once(
    amy_serial,
    '''        if "juno_filter_hz" in raw:\n            out.append(f"v0F{self._f(float(raw['juno_filter_hz']))}i{synth}Z")\n        if "juno_resonance" in raw:\n            out.append(f"v0R{self._f(float(raw['juno_resonance']))}i{synth}Z")\n''',
    '''        if "juno_filter_hz" in raw:\n            value = clamp_control_value("filter_hz", float(raw["juno_filter_hz"]))\n            out.append(f"v0F{self._f(value)}i{synth}Z")\n        if "juno_resonance" in raw:\n            value = clamp_control_value("resonance", float(raw["juno_resonance"]))\n            out.append(f"v0R{self._f(value)}i{synth}Z")\n''',
)
# Bus helpers before configure_one_synth.
replace_once(
    amy_serial,
    '''    def _configure_one_synth(self, role: str, synth: int) -> None:\n''',
    '''    def _bus_for_synth(self, synth: int) -> int:\n        return (\n            self.bus_id["percussion"]\n            if synth == self.synth_id["drums"]\n            else self.bus_id["main"]\n        )\n\n    def _route_synth_bus(self, synth: int) -> None:\n        self._wire(f"i{synth}iy{self._bus_for_synth(synth)}Z")\n\n    def _apply_reverb_buses(self) -> None:\n        self._wire(\n            f"y{self.bus_id['main']}h{self._f(self.reverb['main'])}Z"\n        )\n        self._wire(\n            f"y{self.bus_id['percussion']}h{self._f(self.reverb['percussion'])}Z"\n        )\n\n    def _set_reverb(self, lane: str, value: Any) -> None:\n        level = max(0.0, min(1.0, float(value)))\n        self.reverb[lane] = level\n        bus = self.bus_id[lane]\n        self._wire(f"y{bus}h{self._f(level)}Z")\n\n    def _configure_one_synth(self, role: str, synth: int) -> None:\n''',
)
replace_once(
    amy_serial,
    '''        self._apply_patch_compatibility(patch, synth)\n        self._wire(f"i{synth}iV{self._f(self.volume[role])}Z")\n''',
    '''        self._apply_patch_compatibility(patch, synth)\n        self._route_synth_bus(synth)\n        self._wire(f"i{synth}iV{self._f(self.volume[role])}Z")\n''',
)
replace_once(
    amy_serial,
    '''        self._wire(f"v0w7i{drums}Z")\n        self._wire(f"i{drums}iV{self._f(self.volume['drums'])}Z")\n        self._configured_synths.add(drums)\n\n        self._configure_synth("bass")\n        self._configure_synth("strum")\n        self._configure_synth("chord")\n''',
    '''        self._wire(f"v0w7i{drums}Z")\n        self._route_synth_bus(drums)\n        self._wire(f"i{drums}iV{self._f(self.volume['drums'])}Z")\n        self._configured_synths.add(drums)\n\n        self._configure_synth("bass")\n        self._configure_synth("strum")\n        self._configure_synth("chord")\n        self._apply_reverb_buses()\n''',
)
# Clamp all incoming sparse state before it is stored/diffed.
replace_once(
    amy_serial,
    '''            try:\n                result[str(values[index])] = float(values[index + 1])\n            except (TypeError, ValueError):\n                pass\n''',
    '''            try:\n                key = str(values[index])\n                result[key] = clamp_control_value(key, float(values[index + 1]))\n            except (TypeError, ValueError):\n                pass\n''',
)
# Replace old local hard clamps with already-centralized clamped values where relevant.
replace_once(amy_serial, "                cutoff = max(20.0, min(18000.0, cutoff))\n", "                cutoff = clamp_control_value(\"filter_hz\", cutoff)\n")
replace_once(amy_serial, "                resonance = max(0.51, min(12.0, resonance))\n", "                resonance = clamp_control_value(\"resonance\", resonance)\n")
replace_once(amy_serial, "                    f\"v1f{self._f(max(0.01, min(20.0, lfo_hz)))}i{synth}Z\"\n", "                    f\"v1f{self._f(clamp_control_value('lfo_hz', lfo_hz))}i{synth}Z\"\n")
# There are two identical lfo clamp snippets; replace second if still present.
text = amy_serial.read_text(encoding="utf-8")
text = text.replace("f\"v1f{self._f(max(0.01, min(20.0, lfo_hz)))}i{synth}Z\"", "f\"v1f{self._f(clamp_control_value('lfo_hz', lfo_hz))}i{synth}Z\"")
text = text.replace("depth = max(0.0, min(4.0, vcf_lfo))", "depth = clamp_control_value(\"filter_lfo_depth\", vcf_lfo)")
amy_serial.write_text(text, encoding="utf-8")
# Logical reverb dispatch.
replace_once(
    amy_serial,
    '''        elif address == a["percussion_amp"]:\n            self._set_volume("drums", value)\n        elif address == a["chord_synth"]:\n''',
    '''        elif address == a["percussion_amp"]:\n            self._set_volume("drums", value)\n        elif address == a["main_reverb"]:\n            self._set_reverb("main", value)\n        elif address == a["percussion_reverb"]:\n            self._set_reverb("percussion", value)\n        elif address == a["chord_synth"]:\n''',
)


# ---------------------------------------------------------------------------
# Headless integration app gets the same new logical addresses.
# ---------------------------------------------------------------------------
headless = FRONTEND / "tests" / "integration" / "headless_app.py"
replace_once(
    headless,
    '''        "percussion_amp": args.percussion_amp_address,\n        "chord_synth": args.chord_synth_address,\n''',
    '''        "percussion_amp": args.percussion_amp_address,\n        "main_reverb": args.main_reverb_address,\n        "percussion_reverb": args.percussion_reverb_address,\n        "chord_synth": args.chord_synth_address,\n''',
)
replace_once(
    headless,
    '''        percussion_amp_address=args.percussion_amp_address,\n        chord_synth_address=args.chord_synth_address,\n''',
    '''        percussion_amp_address=args.percussion_amp_address,\n        main_reverb_address=args.main_reverb_address,\n        percussion_reverb_address=args.percussion_reverb_address,\n        chord_synth_address=args.chord_synth_address,\n''',
)


# ---------------------------------------------------------------------------
# UI: a new left rail. The two reverb controls share one connected pastel-pink
# panel. Section reset buttons use a reusable round component.
# ---------------------------------------------------------------------------
reset_qml = '''import QtQuick\nimport QtQuick.Controls\n\nButton {\n    id: root\n\n    property color panelColor: "#d7d7d2"\n    property color borderColor: "#85857f"\n    property color textColor: "#343432"\n\n    width: 52\n    height: 52\n\n    font.pixelSize: 11\n    font.bold: true\n\n    contentItem: Text {\n        text: root.text\n        color: root.textColor\n        font: root.font\n        horizontalAlignment: Text.AlignHCenter\n        verticalAlignment: Text.AlignVCenter\n    }\n\n    background: Rectangle {\n        radius: width / 2\n        color: root.pressed ? Qt.darker(root.panelColor, 1.08) : root.panelColor\n        border.color: root.borderColor\n        border.width: 2\n    }\n}\n'''
(FRONTEND / "gui" / "PresetResetButton.qml").write_text(reset_qml, encoding="utf-8")

main_qml = FRONTEND / "gui" / "Main.qml"
replace_once(
    main_qml,
    '''    property int controlSpacing: 6\n\n    property int chordRowContentWidth:\n''',
    '''    property int controlSpacing: 6\n    property int leftRailWidth: 116\n    property int leftSliderWidth: 52\n    property int contentX: leftRailWidth\n\n    property int chordRowContentWidth:\n''',
)
replace_once(
    main_qml,
    '''    property int maximumChordRowWidth:\n        rowIndent * 3\n        + chordRowContentWidth\n''',
    '''    property int maximumChordRowWidth:\n        contentX\n        + rowIndent * 3\n        + chordRowContentWidth\n''',
)
replace_once(
    main_qml,
    '''    property int volumeX:\n        chordRowContentWidth\n        + volumeGap\n''',
    '''    property int volumeX:\n        contentX\n        + chordRowContentWidth\n        + volumeGap\n''',
)
# Utility shifts right and keeps original width.
replace_once(
    main_qml,
    '''            UtilitySection {\n                x: 0\n''',
    '''            UtilitySection {\n                x: window.contentX\n''',
)
replace_once(
    main_qml,
    '''                width:\n                    window.volumeX\n                    + window.volumeWidth\n''',
    '''                width:\n                    window.volumeX\n                    + window.volumeWidth\n                    - window.contentX\n''',
)
# Rhythm yellow starts at old content edge; bass/strum/chord bars extend left.
replace_once(main_qml, "                x: 0\n                y: window.rhythmY\n", "                x: window.contentX\n                y: window.rhythmY\n")
replace_once(
    main_qml,
    '''                width:\n                    window.volumeX\n                    + window.volumeWidth\n                height: window.sectionHeight\n                radius: 12\n                color: "#fbf0bd"\n''',
    '''                width:\n                    window.volumeX\n                    + window.volumeWidth\n                    - window.contentX\n                height: window.sectionHeight\n                radius: 12\n                color: "#fbf0bd"\n''',
)
# Move actual sections right.
replace_once(main_qml, "            RhythmSection {\n                x: 0\n", "            RhythmSection {\n                x: window.contentX\n")
for section_id in ("bassSynthSection", "strumSynthSection", "chordSynthSection"):
    replace_once(main_qml, f'''            SynthSection {{\n                id: {section_id}\n\n                x: 0\n''', f'''            SynthSection {{\n                id: {section_id}\n\n                x: window.contentX\n''')
# Their widths are the old content width, not including the new rail.
text = main_qml.read_text(encoding="utf-8")
text = text.replace("                width:\n                    window.chordRowContentWidth\n", "                width:\n                    window.chordRowContentWidth\n", 4)
main_qml.write_text(text, encoding="utf-8")
# Chord rows shift right.
replace_once(main_qml, "                x: 0\n                y: window.chordRowsY\n", "                x: window.contentX\n                y: window.chordRowsY\n")

# Pink connected panel + two reverb controls before UtilitySection.
pink_block = '''            Rectangle {\n                x: 0\n                y: window.utilityY\n                width: window.leftRailWidth\n                height:\n                    window.sectionHeight * 2\n                    + window.sectionGap\n                radius: 12\n                color: "#f7dce6"\n                border.color: "#c98da5"\n                border.width: 1\n            }\n\n            VerticalVolume {\n                x: (window.leftRailWidth - window.leftSliderWidth) / 2\n                y: window.utilityY\n                width: window.leftSliderWidth\n                height: window.sectionHeight\n                currentValue: backend.mainReverb\n                panelColor: "#f2c8d8"\n                panelBorderColor: "#bd839b"\n                fillColor: "#d87fa5"\n                textColor: "#5c2840"\n                onEdited: (value) => backend.setMainReverb(value)\n            }\n\n            VerticalVolume {\n                x: (window.leftRailWidth - window.leftSliderWidth) / 2\n                y: window.rhythmY\n                width: window.leftSliderWidth\n                height: window.sectionHeight\n                currentValue: backend.percussionReverb\n                panelColor: "#f2c8d8"\n                panelBorderColor: "#bd839b"\n                fillColor: "#d87fa5"\n                textColor: "#5c2840"\n                onEdited: (value) => backend.setPercussionReverb(value)\n            }\n\n'''
replace_once(main_qml, "            UtilitySection {\n", pink_block + "            UtilitySection {\n")

# Reset buttons. Bass row gets rhythm + bass side by side; strum/chord one each.
buttons = '''            PresetResetButton {\n                x: 5\n                y: window.bassSynthY + (window.sectionHeight - height) / 2\n                width: 50\n                height: 50\n                text: "RHY"\n                panelColor: "#ecece8"\n                borderColor: "#8c8c86"\n                onClicked: backend.resetRhythmControlsToPreset()\n            }\n\n            PresetResetButton {\n                x: 61\n                y: window.bassSynthY + (window.sectionHeight - height) / 2\n                width: 50\n                height: 50\n                text: "BAS"\n                panelColor: "#d0d0cc"\n                borderColor: "#7b7b76"\n                onClicked: backend.resetBassToPreset()\n            }\n\n            PresetResetButton {\n                x: (window.leftRailWidth - width) / 2\n                y: window.strumSynthY + (window.sectionHeight - height) / 2\n                text: "STR"\n                panelColor: "#b9def3"\n                borderColor: "#589bc6"\n                textColor: "#12344d"\n                onClicked: backend.resetStrumToPreset()\n            }\n\n            PresetResetButton {\n                x: (window.leftRailWidth - width) / 2\n                y: window.chordSynthY + (window.sectionHeight - height) / 2\n                text: "CHD"\n                panelColor: "#c7ddc5"\n                borderColor: "#649068"\n                textColor: "#1d4023"\n                onClicked: backend.resetChordSynthToPreset()\n            }\n\n'''
replace_once(main_qml, "            RhythmSection {\n", buttons + "            RhythmSection {\n")

# Upper chord row left extension/reset button, leaving rows 1..3 unchanged.
row_extension = '''                        Rectangle {\n                            visible: rowItem.rowIndex === 0\n                            x: -window.contentX\n                            y: 0\n                            width: window.contentX + window.wheelWidth\n                            height: window.rowHeight\n                            radius: 10\n                            color: window.chordPanelColor\n                            border.color: window.chordPanelBorderColor\n                            border.width: 1\n                        }\n\n                        PresetResetButton {\n                            visible: rowItem.rowIndex === 0\n                            x: -window.contentX + (window.contentX - width) / 2\n                            y: (window.rowHeight - height) / 2\n                            text: "ROWS"\n                            panelColor: "#e5d9b2"\n                            borderColor: "#9f9165"\n                            textColor: "#4a4022"\n                            onClicked: backend.resetChordRowsToPreset()\n                        }\n\n'''
replace_once(main_qml, "                        Button {\n                            id: offButton\n", row_extension + "                        Button {\n                            id: offButton\n")


print("Applied control safety, reverb buses, preset resets, and left-rail UI.")
