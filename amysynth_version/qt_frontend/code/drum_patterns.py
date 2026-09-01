from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from catalog_schema import read_versioned_catalog
from drum_gamma9001 import GAMMA9001_DIRECT_PCM


PPQ = 96
AMY_PPQ = 48
KIT_FAMILIES = ("tiny", "gamma9001", "general_midi")


@dataclass(frozen=True)
class DrumEvent:
    tick: int
    role: str
    velocity: int


@dataclass(frozen=True)
class DrumFill:
    index: int
    fill_id: str
    duration_ticks: int
    allowed_start_beats: tuple[int, ...]
    beat_unit_ticks: int
    events: tuple[DrumEvent, ...]
    continue_roles: frozenset[str]


@dataclass(frozen=True)
class DrumRhythm:
    rhythm_id: str
    meter: str
    period_ticks: int
    period_bars: int
    levels: tuple[tuple[DrumEvent, ...], ...]
    fills: tuple[DrumFill, ...]


@dataclass(frozen=True)
class DrumSound:
    preset: int | None
    note: int
    synth_patch: int | None = None


@dataclass(frozen=True)
class _KitMap:
    activity_profiles: Mapping[str, Mapping[str, DrumSound]]
    activity_rhythm_profile: Mapping[str, str]
    fill_profiles: Mapping[str, Mapping[str, DrumSound]]
    fill_rhythm_profile: Mapping[str, str]


@dataclass(frozen=True)
class DrumPatternCatalog:
    rhythms: Mapping[str, DrumRhythm]
    kits: Mapping[str, _KitMap]

    def rhythm(self, rhythm_id: str) -> DrumRhythm:
        try:
            return self.rhythms[str(rhythm_id)]
        except KeyError as exc:
            raise ValueError(f"unknown drum rhythm {rhythm_id!r}") from exc

    def resolve(
        self,
        kit_family: str,
        rhythm_id: str,
        role: str,
        *,
        fill: bool = False,
    ) -> DrumSound:
        kit_name = str(kit_family)
        try:
            kit = self.kits[kit_name]
        except KeyError as exc:
            raise ValueError(
                f"unknown drum kit {kit_name!r}; expected one of "
                f"{', '.join(KIT_FAMILIES)}"
            ) from exc
        profiles = kit.fill_profiles if fill else kit.activity_profiles
        assignments = (
            kit.fill_rhythm_profile if fill else kit.activity_rhythm_profile
        )
        try:
            profile_name = assignments[str(rhythm_id)]
            return profiles[profile_name][str(role)]
        except KeyError as exc:
            kind = "fill" if fill else "activity"
            raise ValueError(
                f"{kit_name} {kind} mapping cannot resolve "
                f"{rhythm_id!r}/{role!r}"
            ) from exc


def _read(path: Path, schema_name: str) -> Mapping[str, Any]:
    return read_versioned_catalog(path, schema_name)


def _event(raw: Any, *, period_ticks: int, source: str) -> DrumEvent:
    if not isinstance(raw, dict):
        raise ValueError(f"{source} contains a non-object event")
    forbidden = {"preset", "sample", "midi_note", "patch", "note"} & set(raw)
    if forbidden:
        raise ValueError(f"{source} timing event contains kit data: {forbidden}")
    tick = int(raw["tick"])
    velocity = int(raw["velocity"])
    if tick < 0 or tick >= period_ticks or tick % 2:
        raise ValueError(f"{source} has invalid 96-PPQ tick {tick}")
    if not 1 <= velocity <= 127:
        raise ValueError(f"{source} has invalid velocity {velocity}")
    return DrumEvent(tick=tick, role=str(raw["role"]), velocity=velocity)


def _sound(raw: Any, *, kit_family: str) -> DrumSound:
    if not isinstance(raw, dict):
        raise ValueError(f"{kit_family} contains a non-object role mapping")
    if kit_family == "tiny":
        preset = int(raw["preset"])
        note = int(raw["note"])
        synth_patch = None
        if not 0 <= preset <= 10:
            raise ValueError(f"tiny PCM preset outside 0..10: {preset}")
    elif kit_family == "gamma9001":
        patch = int(raw["patch"])
        midi_note = int(raw["midi_note"])
        if not 384 <= patch <= 390:
            raise ValueError(f"Gamma9001 patch outside 384..390: {patch}")
        try:
            preset, note = GAMMA9001_DIRECT_PCM[(patch, midi_note)]
        except KeyError as exc:
            raise ValueError(
                f"Gamma9001 patch {patch} does not resolve GM note {midi_note}"
            ) from exc
        synth_patch = None
    else:
        # Patch 258 is AMY's engine-side General-MIDI drum-note map. It is
        # loaded once on synth 0; pattern hits then send ordinary AMY notes.
        # No MIDI connection or MIDI event path is involved.
        preset = None
        note = int(raw["midi_note"])
        synth_patch = 258
    if not 0 <= note <= 127:
        raise ValueError(f"{kit_family} drum note outside 0..127: {note}")
    return DrumSound(
        preset=preset,
        note=note,
        synth_patch=synth_patch,
    )


def _load_kit(
    path: Path,
    kit_family: str,
) -> tuple[Mapping[str, Mapping[str, DrumSound]], Mapping[str, str]]:
    raw = _read(path, "drum_kit_v1.schema.json")
    if str(raw.get("kit_family")) != kit_family:
        raise ValueError(f"{path} does not describe kit {kit_family!r}")
    raw_profiles = raw.get("profiles")
    assignments = raw.get("rhythm_profile")
    if not isinstance(raw_profiles, dict) or not isinstance(assignments, dict):
        raise ValueError(f"{path} lacks profiles or rhythm_profile")
    profiles: dict[str, dict[str, DrumSound]] = {}
    for profile_name, profile in raw_profiles.items():
        if not isinstance(profile, dict):
            raise ValueError(f"{path} profile {profile_name!r} is not an object")
        profiles[str(profile_name)] = {
            str(role): _sound(value, kit_family=kit_family)
            for role, value in profile.items()
        }
    immutable_profiles = MappingProxyType(
        {
            key: MappingProxyType(value)
            for key, value in profiles.items()
        }
    )
    return immutable_profiles, MappingProxyType(
        {str(key): str(value) for key, value in assignments.items()}
    )


def _validate_drum_cross_references(catalog: DrumPatternCatalog) -> None:
    global_activity_roles = {
        event.role
        for rhythm in catalog.rhythms.values()
        for level in rhythm.levels
        for event in level
    }
    for rhythm in catalog.rhythms.values():
        active_roles = {event.role for level in rhythm.levels for event in level}
        fill_roles = {event.role for fill in rhythm.fills for event in fill.events}
        for kit_family in KIT_FAMILIES:
            for role in active_roles:
                catalog.resolve(kit_family, rhythm.rhythm_id, role)
            for role in fill_roles:
                catalog.resolve(kit_family, rhythm.rhythm_id, role, fill=True)
        for fill in rhythm.fills:
            # A continuation role absent at the selected level is an
            # intentional no-op; its whitelist is activity-independent.
            if len(fill.events) + len(global_activity_roles - fill.continue_roles) > 64:
                raise ValueError(
                    f"{fill.fill_id} exceeds AMY's 64 events after mutes"
                )


def load_drum_pattern_catalog(directory: Path) -> DrumPatternCatalog:
    directory = Path(directory)
    activity = _read(
        directory / "drum_activity_timing.json",
        "drum_activity_v1.schema.json",
    )
    fills_raw = _read(
        directory / "drum_fills_timing.json",
        "drum_fills_v2.schema.json",
    )
    continuation = _read(
        directory / "drum_fill_continuation_roles.json",
        "drum_continuation_v1.schema.json",
    )
    if int(activity.get("design_contract", {}).get("ppq", 0)) != PPQ:
        raise ValueError("drum activity catalogue must use 96 PPQ")

    fill_items = fills_raw.get("fills")
    continuation_items = continuation.get("fills")
    if not isinstance(fill_items, list) or not isinstance(continuation_items, list):
        raise ValueError("fill timing and continuation catalogues require fills")
    continue_by_id = {
        str(item["fill_id"]): frozenset(
            str(role) for role in item["continue_roles"]
        )
        for item in continuation_items
    }
    if len(continue_by_id) != len(continuation_items):
        raise ValueError("duplicate fill id in continuation catalogue")

    fills_by_index: dict[int, DrumFill] = {}
    for item in fill_items:
        timing = item["timing"]
        fill_id = str(item["fill_id"])
        duration = int(timing["duration_ticks"])
        if int(timing["ppq"]) != PPQ or duration <= 0 or duration % 2:
            raise ValueError(f"{fill_id} has invalid duration/PPQ")
        denominator = int(str(item["meter"]).split("/", 1)[1])
        beat_unit_ticks = PPQ * 4 // denominator
        allowed_starts = tuple(
            int(value) for value in item["allowed_start_beats"]
        )
        numerator = int(str(item["meter"]).split("/", 1)[0])
        if (
            duration % beat_unit_ticks
            or not allowed_starts
            or allowed_starts != tuple(sorted(set(allowed_starts)))
            or any(value < 1 or value > numerator for value in allowed_starts)
            or any(
                (value - 1) * beat_unit_ticks + duration
                > numerator * beat_unit_ticks
                for value in allowed_starts
            )
        ):
            raise ValueError(
                f"{fill_id} must occupy whole beats inside its meter"
            )
        fill = DrumFill(
            index=int(item["index"]),
            fill_id=fill_id,
            duration_ticks=duration,
            allowed_start_beats=allowed_starts,
            beat_unit_ticks=beat_unit_ticks,
            events=tuple(
                _event(raw, period_ticks=duration, source=fill_id)
                for raw in timing["events"]
            ),
            continue_roles=continue_by_id[fill_id],
        )
        if fill.index in fills_by_index:
            raise ValueError(f"duplicate fill index {fill.index}")
        fills_by_index[fill.index] = fill
    if set(continue_by_id) != {
        fill.fill_id for fill in fills_by_index.values()
    }:
        raise ValueError("fill timing and continuation coverage differ")

    index_raw = fills_raw.get("rhythm_fill_index")
    if not isinstance(index_raw, dict):
        raise ValueError("fill catalogue lacks rhythm_fill_index")
    rhythms: dict[str, DrumRhythm] = {}
    for item in activity.get("rhythms", []):
        rhythm_id = str(item["id"])
        period_ticks = int(item["period_ticks"])
        period_bars = int(item["period_bars"])
        if (
            period_ticks <= 0
            or period_ticks % 2
            or period_bars <= 0
            or period_ticks % period_bars
        ):
            raise ValueError(f"{rhythm_id} has invalid period")
        levels = tuple(
            tuple(
                _event(
                    raw,
                    period_ticks=period_ticks,
                    source=f"{rhythm_id} level {level['level']}",
                )
                for raw in level["events"]
            )
            for level in item["levels"]
        )
        if len(levels) != 5:
            raise ValueError(
                f"{rhythm_id} must have five complete activity levels"
            )
        fill_indexes = index_raw.get(rhythm_id)
        if not isinstance(fill_indexes, list) or len(fill_indexes) != 5:
            raise ValueError(f"{rhythm_id} must have five fills")
        rhythms[rhythm_id] = DrumRhythm(
            rhythm_id=rhythm_id,
            meter=str(item["meter"]),
            period_ticks=period_ticks,
            period_bars=period_bars,
            levels=levels,
            fills=tuple(
                fills_by_index[int(index)] for index in fill_indexes
            ),
        )

    kits: dict[str, _KitMap] = {}
    for kit_family in KIT_FAMILIES:
        activity_profiles, activity_assignments = _load_kit(
            directory / f"drum_activity_instruments_{kit_family}.json",
            kit_family,
        )
        fill_profiles, fill_assignments = _load_kit(
            directory / f"drum_fills_instruments_{kit_family}.json",
            kit_family,
        )
        kits[kit_family] = _KitMap(
            activity_profiles=activity_profiles,
            activity_rhythm_profile=activity_assignments,
            fill_profiles=fill_profiles,
            fill_rhythm_profile=fill_assignments,
        )

    catalog = DrumPatternCatalog(
        rhythms=MappingProxyType(rhythms),
        kits=MappingProxyType(kits),
    )
    _validate_drum_cross_references(catalog)
    return catalog
