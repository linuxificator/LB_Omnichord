from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ChordRowPreset:
    chord_index: int
    octave_index: int
    inversion_index: int


@dataclass(frozen=True, slots=True)
class EffectsPreset:
    level: float
    liveness: float
    damping: float
    drums: bool


@dataclass(frozen=True, slots=True)
class RhythmSettingPreset:
    tempo: float
    percussion_activity: int
    chord_activity: int
    bass_activity: int
    fill_order: tuple[int, ...]
    fill_density_index: int


@dataclass(frozen=True, slots=True)
class OmniPresetPlan:
    strum_ladder_mode: bool
    chord_rows: tuple[ChordRowPreset, ...]
    volumes: tuple[float, float, float, float]
    effects: EffectsPreset
    bass_running: bool
    selected_rhythm_index: int
    rhythm_settings: tuple[RhythmSettingPreset, ...]
    tuning_mode_index: int
    tuning_reference_hz: float


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, dict) else {}


def _clamp(value: Any, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def compile_omni_preset_plan(
    data: Mapping[str, Any],
    *,
    chord_suffixes: Sequence[str],
    chord_inversion_counts: Sequence[int],
    octave_names: Sequence[str],
    default_rows: Sequence[ChordRowPreset],
    default_volumes: tuple[float, float, float, float],
    default_effects: EffectsPreset,
    default_bass_running: bool,
    rhythm_keys: Sequence[str],
    default_selected_rhythm_index: int,
    default_rhythm_settings: Sequence[RhythmSettingPreset],
    fill_density_bars: Sequence[int],
    tuning_modes: Sequence[str],
    default_tuning_mode_index: int,
    default_tuning_reference_hz: float,
    reverb_level_max: float,
) -> OmniPresetPlan:
    """Normalize an OMNI preset without mutating application/QObject state."""

    suffix_to_index = {str(value): index for index, value in enumerate(chord_suffixes)}
    octave_to_index = {str(value): index for index, value in enumerate(octave_names)}
    rows = list(default_rows)
    raw_rows = data.get("chord_rows", [])
    if isinstance(raw_rows, list) and len(raw_rows) == len(rows):
        for index, raw in enumerate(raw_rows):
            if not isinstance(raw, dict):
                continue
            row_fallback = rows[index]
            chord_index = suffix_to_index.get(
                str(raw.get("chord", chord_suffixes[row_fallback.chord_index])),
                row_fallback.chord_index,
            )
            octave_index = octave_to_index.get(
                str(raw.get("octave", octave_names[row_fallback.octave_index])),
                row_fallback.octave_index,
            )
            inversion_count = max(1, int(chord_inversion_counts[chord_index]))
            rows[index] = ChordRowPreset(
                chord_index,
                octave_index,
                int(raw.get("inversion", 0)) % inversion_count,
            )

    raw_volumes = _mapping(data.get("volumes", {}))
    volume_names = ("chord", "strum", "bass", "percussion")
    volumes = tuple(
        _clamp(raw_volumes.get(name, default_volumes[index]), 0.0, 1.0)
        for index, name in enumerate(volume_names)
    )

    raw_effects = _mapping(data.get("effects", {}))
    legacy_main = raw_effects.get("main_reverb", default_effects.level)
    legacy_drums = raw_effects.get("percussion_reverb", 0.0)
    effects = EffectsPreset(
        _clamp(raw_effects.get("reverb_level", legacy_main), 0.0, reverb_level_max),
        _clamp(raw_effects.get("reverb_liveness", default_effects.liveness), 0.0, 1.0),
        _clamp(raw_effects.get("reverb_damping", default_effects.damping), 0.0, 1.0),
        bool(raw_effects.get("reverb_drums", float(legacy_drums) > 0.0)),
    )

    transport = _mapping(data.get("transport", {}))
    bass_running = bool(transport.get("bass_running", default_bass_running))

    rhythm = _mapping(data.get("rhythm", {}))
    rhythm_key_to_index = {str(key): index for index, key in enumerate(rhythm_keys)}
    selected_rhythm_index = rhythm_key_to_index.get(
        str(rhythm.get("selected", rhythm_keys[default_selected_rhythm_index])),
        default_selected_rhythm_index,
    )
    settings = _mapping(rhythm.get("settings", {}))
    rhythm_plans: list[RhythmSettingPreset] = []
    for index, key in enumerate(rhythm_keys):
        rhythm_fallback = default_rhythm_settings[index]
        stored = _mapping(settings.get(key, {}))
        raw_order = stored.get("fill_order", rhythm_fallback.fill_order)
        order = rhythm_fallback.fill_order
        if isinstance(raw_order, (list, tuple)):
            order = tuple(
                dict.fromkeys(
                    fill_index
                    for fill_index in (int(value) for value in raw_order)
                    if 0 <= fill_index < 5
                )
            )
        raw_density = int(
            stored.get(
                "fill_density_bars",
                fill_density_bars[rhythm_fallback.fill_density_index],
            )
        )
        if raw_density in fill_density_bars:
            density_index = fill_density_bars.index(raw_density)
        elif raw_density > max(fill_density_bars):
            # Presets written before the useful fill range was narrowed could
            # contain /16 or /32. Preserve their intent as the longest now
            # supported interval rather than falling back to an unrelated
            # per-rhythm value.
            density_index = fill_density_bars.index(max(fill_density_bars))
        else:
            density_index = rhythm_fallback.fill_density_index
        rhythm_plans.append(
            RhythmSettingPreset(
                tempo=_clamp(stored.get("tempo", rhythm_fallback.tempo), 40.0, 200.0),
                percussion_activity=int(
                    _clamp(
                        stored.get(
                            "percussion_activity",
                            rhythm_fallback.percussion_activity,
                        ),
                        1,
                        5,
                    )
                ),
                chord_activity=int(
                    _clamp(
                        stored.get("chord_activity", rhythm_fallback.chord_activity),
                        1,
                        4,
                    )
                ),
                bass_activity=int(
                    _clamp(
                        stored.get("bass_activity", rhythm_fallback.bass_activity),
                        1,
                        5,
                    )
                ),
                fill_order=order,
                fill_density_index=density_index,
            )
        )

    tuning = _mapping(data.get("tuning", {}))
    mode = str(tuning.get("mode", tuning_modes[default_tuning_mode_index]))
    tuning_mode_index = (
        tuning_modes.index(mode) if mode in tuning_modes else default_tuning_mode_index
    )
    tuning_reference_hz = float(
        max(
            415,
            min(
                466,
                int(tuning.get("reference_hz", default_tuning_reference_hz)),
            ),
        )
    )
    return OmniPresetPlan(
        str(data.get("strum_mode", "APG")).upper() == "LDR",
        tuple(rows),
        (volumes[0], volumes[1], volumes[2], volumes[3]),
        effects,
        bass_running,
        selected_rhythm_index,
        tuple(rhythm_plans),
        tuning_mode_index,
        tuning_reference_hz,
    )
