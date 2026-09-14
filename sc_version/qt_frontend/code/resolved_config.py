from __future__ import annotations

import copy
import ipaddress
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, cast

import fastjsonschema  # type: ignore[import-untyped]

from config_migrations import (
    CURRENT_CONFIG_REVISION,
    ConfigMigrationError,
    migrate_config_document,
)


CHORD_VOICE_CAPACITY = 7
CONFIG_SCHEMA_REVISION = CURRENT_CONFIG_REVISION
ConfigSourceKind = Literal["shipped", "user", "external"]
JsonObject = dict[str, Any]
SchemaValidator = Callable[[Any], Any]


@dataclass(frozen=True, slots=True)
class ConfigIssue:
    path: str
    message: str


class ConfigValidationError(ValueError):
    """One or more path-specific configuration problems."""

    def __init__(self, issues: list[ConfigIssue] | tuple[ConfigIssue, ...]) -> None:
        self.issues = tuple(issues)
        details = "\n".join(
            f"- {issue.path}: {issue.message}" for issue in self.issues
        )
        super().__init__(f"invalid AMY configuration:\n{details}")


@dataclass(frozen=True, slots=True)
class TransportConfig:
    serial_port: str
    serial_baud: int
    serial_write_timeout: float


@dataclass(frozen=True, slots=True)
class MidiInputConfig:
    enabled: bool
    configured_profile: str
    profile_source: Literal["runtime-adapter", "explicit-override"]
    device_glob: str
    alsa_raw_globs: tuple[str, ...]
    oss_midi_globs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OscInputConfig:
    enabled: bool
    listen_address: str | None
    listen_port: int | None
    advertise: bool = False
    service_name: str = ""
    configured: bool = True


@dataclass(frozen=True, slots=True)
class VoiceCapacities:
    drums: int
    bass: int
    strum: int
    manual_chord: int
    rhythm_chord: int
    midi_per_synth: int
    midi_drums: int


@dataclass(frozen=True, slots=True)
class RuntimeCapacities:
    max_oscs: int
    max_sequencer_tags: int
    max_sequence_events: int
    max_sequence_executions: int
    max_buses: int
    voices: VoiceCapacities


@dataclass(frozen=True, slots=True)
class SynthBusLayout:
    role_synth_ids: tuple[tuple[str, int], ...]
    midi_synth_ids: tuple[int, ...]
    midi_drum_synth_id: int
    role_buses: tuple[tuple[str, int], ...]
    midi_row_buses: tuple[int, ...]
    midi_drum_bus: int
    sequencer_tag_ranges: tuple[tuple[str, int, int], ...]
    sequencer_sequence_ranges: tuple[tuple[str, int, int], ...]


@dataclass(frozen=True, slots=True)
class DebugConfig:
    log_amy_commands: bool
    amy_command_log: str
    log_logical_events: bool


@dataclass(frozen=True, slots=True)
class SynthDefaults:
    chord: str
    strum: str
    bass: str


@dataclass(frozen=True, slots=True)
class DrumRuntimeConfig:
    kit: str
    velocity_gain: float
    sample_map: tuple[tuple[str, "DrumSampleConfig"], ...]

    def sample(self, name: str) -> DrumSampleConfig | None:
        return next((sample for key, sample in self.sample_map if key == name), None)


@dataclass(frozen=True, slots=True)
class DrumSampleConfig:
    preset: int
    note: int


@dataclass(frozen=True, slots=True)
class RhythmRuntimeConfig:
    chord_gate_beats: float
    bass_gate_beats: float
    max_rhythm_chord_notes: int
    sequencer_reset_guard_ms: float


@dataclass(frozen=True, slots=True)
class PerformanceTimingConfig:
    strum_gate_ms: float
    one_shot_chord_gate_ms: float
    strum_tail_ms: float
    synth_alloc_guard_ms: float


@dataclass(frozen=True, slots=True)
class ConfigProvenance:
    source_path: Path
    source_kind: ConfigSourceKind
    shipped_baseline_path: Path | None
    user_override_paths: tuple[str, ...]
    platform_derived_paths: tuple[str, ...]
    runtime_override_paths: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ResolvedAmyConfig:
    revision: int
    transport: TransportConfig
    midi_input: MidiInputConfig
    osc_input: OscInputConfig
    capacities: RuntimeCapacities
    layout: SynthBusLayout
    debug: DebugConfig
    synth_defaults: SynthDefaults
    drums: DrumRuntimeConfig
    rhythm: RhythmRuntimeConfig
    performance: PerformanceTimingConfig
    synth_patches: tuple[tuple[str, int], ...]
    instrument_levels: tuple[tuple[str, float], ...]
    role_levels: tuple[tuple[str, float], ...]
    provenance: ConfigProvenance
    _compatibility_json: str = field(repr=False, compare=False)
    _synth_programs_json: str = field(repr=False, compare=False)
    _patch_compatibility_json: str = field(repr=False, compare=False)

    def compatibility_dict(self) -> JsonObject:
        """Return an isolated mutable view for transitional legacy consumers."""

        value = json.loads(self._compatibility_json)
        if not isinstance(value, dict):
            raise RuntimeError("resolved configuration compatibility view is invalid")
        return cast(JsonObject, value)

    def synth_program(self, key: str) -> JsonObject | None:
        programs = json.loads(self._synth_programs_json)
        raw = programs.get(key)
        return cast(JsonObject, raw) if isinstance(raw, dict) else None

    def synth_program_keys(self) -> tuple[str, ...]:
        programs = json.loads(self._synth_programs_json)
        return tuple(sorted(str(key) for key in programs))

    def patch_compatibility(self, patch: int) -> JsonObject | None:
        entries = json.loads(self._patch_compatibility_json)
        raw = entries.get(str(patch))
        return cast(JsonObject, raw) if isinstance(raw, dict) else None

    def instrument_level(self, key: str) -> float:
        return next(
            (level for name, level in self.instrument_levels if name == key),
            1.0,
        )

    def role_level(self, role: str) -> float:
        return next(
            (level for name, level in self.role_levels if name == role),
            1.0,
        )


def _json_path(parts: list[object] | tuple[object, ...]) -> str:
    path = "$"
    for part in parts:
        if part == "data" and path == "$":
            continue
        if isinstance(part, int):
            path += f"[{part}]"
        elif re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(part)):
            path += f".{part}"
        else:
            escaped = str(part).replace("\\", "\\\\").replace("'", "\\'")
            path += f"['{escaped}']"
    return path


def _schema_candidates(source_path: Path, revision: int) -> tuple[Path, ...]:
    name = f"amy_config_v{revision}.schema.json"
    module_dir = Path(__file__).resolve().parent
    return (
        source_path.parent / "schema" / name,
        module_dir / "config" / "schema" / name,
        module_dir.parent / "config" / "schema" / name,
    )


def _schema_path(source_path: Path, revision: int) -> Path:
    for candidate in _schema_candidates(source_path, revision):
        if candidate.is_file():
            return candidate
    searched = ", ".join(str(path) for path in _schema_candidates(source_path, revision))
    raise RuntimeError(
        f"configuration schema revision {revision} is not packaged; searched {searched}"
    )


@lru_cache(maxsize=8)
def _compiled_schema(schema_path: Path) -> SchemaValidator:
    with schema_path.open("r", encoding="utf-8") as handle:
        schema = json.load(handle)
    return cast(SchemaValidator, fastjsonschema.compile(schema))


def _validate_structure(data: JsonObject, source_path: Path) -> int:
    revision = data.get("config_revision")
    if not isinstance(revision, int) or isinstance(revision, bool):
        raise ConfigValidationError(
            [ConfigIssue("$.config_revision", "must be an integer")]
        )
    if revision != CONFIG_SCHEMA_REVISION:
        raise ConfigValidationError(
            [
                ConfigIssue(
                    "$.config_revision",
                    f"unsupported revision {revision}; expected {CONFIG_SCHEMA_REVISION}",
                )
            ]
        )
    validator = _compiled_schema(_schema_path(source_path, revision))
    try:
        validator(data)
    except fastjsonschema.JsonSchemaException as exc:
        raw_path = cast(list[object], getattr(exc, "path", []))
        message = str(getattr(exc, "message", exc))
        rule = str(getattr(exc, "rule", ""))
        definition = getattr(exc, "definition", None)
        value = getattr(exc, "value", None)
        issues: list[ConfigIssue] = []
        if rule == "additionalProperties" and isinstance(value, dict):
            properties = (
                definition.get("properties", {})
                if isinstance(definition, dict)
                else {}
            )
            if isinstance(properties, dict):
                for key in sorted(set(value).difference(properties)):
                    issues.append(
                        ConfigIssue(
                            _json_path([*raw_path, key]),
                            "unknown property",
                        )
                    )
        elif rule == "required" and isinstance(value, dict):
            required = (
                definition.get("required", [])
                if isinstance(definition, dict)
                else []
            )
            if isinstance(required, list):
                for key in required:
                    if key not in value:
                        issues.append(
                            ConfigIssue(
                                _json_path([*raw_path, key]),
                                "required property is missing",
                            )
                        )
        if not issues:
            issues.append(ConfigIssue(_json_path(raw_path), message))
        raise ConfigValidationError(issues) from exc
    return revision


def _role_items(section: Mapping[str, Any]) -> tuple[tuple[str, int], ...]:
    roles = ("drums", "bass", "strum", "manual_chord", "rhythm_chord")
    return tuple((role, int(section[role])) for role in roles)


def _domain_issues(data: JsonObject) -> list[ConfigIssue]:
    issues: list[ConfigIssue] = []
    osc_input = data.get("osc_input")
    if isinstance(osc_input, dict) and "listen_address" in osc_input:
        try:
            ipaddress.IPv4Address(str(osc_input["listen_address"]))
        except ipaddress.AddressValueError:
            issues.append(
                ConfigIssue(
                    "$.osc_input.listen_address",
                    "must be a numeric IPv4 address",
                )
            )
    if isinstance(osc_input, dict) and "service_name" in osc_input:
        service_name = str(osc_input["service_name"])
        encoded_name = service_name.encode("utf-8")
        if service_name != service_name.strip():
            issues.append(
                ConfigIssue(
                    "$.osc_input.service_name",
                    "must not start or end with whitespace",
                )
            )
        if len(encoded_name) > 63:
            issues.append(
                ConfigIssue(
                    "$.osc_input.service_name",
                    "must be at most 63 UTF-8 bytes for DNS-SD",
                )
            )
        if any(
            ord(character) < 32 or ord(character) == 127
            for character in service_name
        ):
            issues.append(
                ConfigIssue(
                    "$.osc_input.service_name",
                    "must not contain control characters",
                )
            )
    synth_ids = cast(dict[str, Any], data["synth_ids"])
    role_synths = _role_items(synth_ids)
    if len({value for _role, value in role_synths}) != len(role_synths):
        issues.append(
            ConfigIssue("$.synth_ids", "role synth IDs must be unique")
        )

    voices = cast(dict[str, Any], data["voices"])
    for role in ("manual_chord", "rhythm_chord"):
        if int(voices[role]) < CHORD_VOICE_CAPACITY:
            issues.append(
                ConfigIssue(
                    f"$.voices.{role}",
                    f"voices.{role} must be at least {CHORD_VOICE_CAPACITY}; "
                    "the chord catalogue and sequenced arpeggios contain up to "
                    f"{CHORD_VOICE_CAPACITY} distinct notes",
                )
            )

    midi = cast(dict[str, Any], data["midi_player"])
    midi_synths = tuple(int(value) for value in cast(list[Any], midi["synth_ids"]))
    midi_drum_synth = int(midi["drum_synth_id"])
    all_synths = tuple(value for _role, value in role_synths) + midi_synths + (
        midi_drum_synth,
    )
    if len(set(midi_synths)) != len(midi_synths):
        issues.append(
            ConfigIssue("$.midi_player.synth_ids", "MIDI row synth IDs must be unique")
        )
    if len(set(all_synths)) != len(all_synths):
        issues.append(
            ConfigIssue(
                "$.midi_player",
                "OMNI roles, MIDI rows and MIDI drums must own distinct synth IDs",
            )
        )

    buses = cast(dict[str, Any], data["buses"])
    role_bus_names = ("drums", "bass", "strum", "chord")
    role_buses = tuple(int(buses[name]) for name in role_bus_names)
    midi_buses = tuple(int(value) for value in cast(list[Any], buses["midi_rows"]))
    midi_drum_bus = int(buses["midi_drums"])
    all_buses = role_buses + midi_buses + (midi_drum_bus,)
    if len(set(all_buses)) != len(all_buses):
        issues.append(
            ConfigIssue("$.buses", "every OMNI/MIDI owner must have a distinct bus")
        )
    max_buses = int(data["amy_max_buses"])
    if all_buses and max(all_buses) >= max_buses:
        issues.append(
            ConfigIssue(
                "$.amy_max_buses",
                f"must exceed highest configured bus index {max(all_buses)}",
            )
        )

    rhythm = cast(dict[str, Any], data["rhythm"])
    max_tags = int(data["amy_max_sequencer_tags"])
    ranges = cast(dict[str, Any], rhythm["tag_ranges"])
    occupied: set[int] = set()
    for name in ("drums", "bass", "chords"):
        item = cast(dict[str, Any], ranges[name])
        start = int(item["start"])
        count = int(item["count"])
        current = set(range(start, start + count))
        if start + count > max_tags:
            issues.append(
                ConfigIssue(
                    f"$.rhythm.tag_ranges.{name}",
                    f"range ends at {start + count}, beyond max_sequencer_tags {max_tags}",
                )
            )
        if current.intersection(occupied):
            issues.append(
                ConfigIssue(
                    f"$.rhythm.tag_ranges.{name}",
                    "must not overlap another sequencer tag range",
                )
            )
        occupied.update(current)

    sequence_ranges = cast(dict[str, Any], rhythm["sequence_ranges"])
    expected_start: int | None = None
    for name in ("fills", "chords", "drum_bases"):
        item = cast(dict[str, Any], sequence_ranges[name])
        start = int(item["start"])
        count = int(item["count"])
        if expected_start is not None and start != expected_start:
            issues.append(
                ConfigIssue(
                    f"$.rhythm.sequence_ranges.{name}.start",
                    f"must be {expected_start} so sequence ranges are contiguous",
                )
            )
        current = set(range(start, start + count))
        if start + count > max_tags:
            issues.append(
                ConfigIssue(
                    f"$.rhythm.sequence_ranges.{name}",
                    f"range ends at {start + count}, beyond amy_max_sequencer_tags {max_tags}",
                )
            )
        overlap = current.intersection(occupied)
        if overlap:
            issues.append(
                ConfigIssue(
                    f"$.rhythm.sequence_ranges.{name}",
                    f"shares sequencer tag {min(overlap)} with another range",
                )
            )
        occupied.update(current)
        expected_start = start + count
    if expected_start != max_tags:
        issues.append(
            ConfigIssue(
                "$.amy_max_sequencer_tags",
                "must equal the end of the addressable rhythm sequence ranges",
            )
        )

    if int(data["amy_max_sequence_events"]) < 64:
        issues.append(
            ConfigIssue(
                "$.amy_max_sequence_events",
                "must be at least 64 for the largest authored sequence",
            )
        )
    if int(data["amy_max_sequence_executions"]) < 34:
        issues.append(
            ConfigIssue(
                "$.amy_max_sequence_executions",
                "must be at least 34 for the characterized worst-case rhythm",
            )
        )

    programs = cast(dict[str, Any], data["synth_programs"])
    patches = _legacy_patch_map(data)
    valid_programs = set(programs).union(patches)
    defaults = cast(dict[str, Any], data["default_synths"])
    for role in ("chord", "strum", "bass"):
        selected = str(defaults[role])
        if selected not in valid_programs:
            issues.append(
                ConfigIssue(
                    f"$.default_synths.{role}",
                    f"unknown synth program {selected!r}",
                )
            )
    return issues


def _legacy_patch_map(data: Mapping[str, Any]) -> dict[str, int]:
    result = {
        **{f"juno_{patch:03d}": patch for patch in range(128)},
        **{f"dx7_{patch:03d}": patch for patch in range(128, 256)},
    }
    configured = data.get("synth_patches")
    if isinstance(configured, dict):
        result.update({str(key): int(value) for key, value in configured.items()})
    return result


def _shipped_config_path(source_path: Path) -> Path | None:
    module_dir = Path(__file__).resolve().parent
    candidates = (
        module_dir / "config" / "amy_config.json",
        module_dir.parent / "config" / "amy_config.json",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return source_path.resolve() if source_path.is_file() else None


def _changed_paths(base: Any, current: Any, prefix: str = "$") -> list[str]:
    if isinstance(base, dict) and isinstance(current, dict):
        result: list[str] = []
        for key in sorted(set(base).union(current)):
            child = f"{prefix}.{key}"
            if key not in base or key not in current:
                result.append(child)
            else:
                result.extend(_changed_paths(base[key], current[key], child))
        return result
    if base != current:
        return [prefix]
    return []


def _infer_source_kind(source_path: Path, shipped_path: Path | None) -> ConfigSourceKind:
    resolved = source_path.resolve()
    if shipped_path is not None and resolved == shipped_path:
        return "shipped"
    if source_path.parent.name == "config" and source_path.parent.parent.name == ".omnichord":
        return "user"
    return "external"


def _provenance(
    source_path: Path,
    data: JsonObject,
    source_kind: ConfigSourceKind | None,
) -> ConfigProvenance:
    shipped_path = _shipped_config_path(source_path)
    changed: list[str] = []
    if shipped_path is not None and source_path.resolve() != shipped_path:
        try:
            shipped = json.loads(shipped_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            shipped = None
        if isinstance(shipped, dict):
            changed = _changed_paths(shipped, data)
    midi = cast(dict[str, Any], data["midi_input"])
    configured_profile = str(midi["tech_profile"]).strip().casefold()
    return ConfigProvenance(
        source_path=source_path.resolve(),
        source_kind=source_kind or _infer_source_kind(source_path, shipped_path),
        shipped_baseline_path=shipped_path,
        user_override_paths=tuple(changed),
        platform_derived_paths=("$.midi_input.tech_profile",)
        if configured_profile in ("", "auto")
        else (),
    )


def _to_resolved(
    data: JsonObject,
    revision: int,
    provenance: ConfigProvenance,
) -> ResolvedAmyConfig:
    serial = cast(dict[str, Any], data["serial"])
    midi_input = cast(dict[str, Any], data["midi_input"])
    osc_input = cast(dict[str, Any] | None, data.get("osc_input"))
    configured_profile = str(midi_input["tech_profile"]).strip().casefold()
    voices = cast(dict[str, Any], data["voices"])
    midi_player = cast(dict[str, Any], data["midi_player"])
    synth_ids = cast(dict[str, Any], data["synth_ids"])
    buses = cast(dict[str, Any], data["buses"])
    rhythm = cast(dict[str, Any], data["rhythm"])
    tag_ranges = cast(dict[str, Any], rhythm["tag_ranges"])
    sequence_ranges = cast(dict[str, Any], rhythm["sequence_ranges"])
    debug = cast(dict[str, Any], data["debug"])
    defaults = cast(dict[str, Any], data["default_synths"])
    drums = cast(dict[str, Any], data["drums"])
    performance = cast(dict[str, Any], data["performance"])
    sample_map = cast(dict[str, Any], drums["sample_map"])
    instrument_levels = cast(dict[str, Any], data["instrument_levels"])
    role_levels = cast(dict[str, Any], data["role_levels"])
    synth_programs = cast(dict[str, Any], data["synth_programs"])
    patch_compatibility = cast(dict[str, Any], data["patch_compatibility"])

    compatibility = copy.deepcopy(data)
    compatibility["synth_patches"] = _legacy_patch_map(data)
    return ResolvedAmyConfig(
        revision=revision,
        transport=TransportConfig(
            serial_port=str(serial["port"]),
            serial_baud=int(serial["baud"]),
            serial_write_timeout=float(serial["write_timeout"]),
        ),
        midi_input=MidiInputConfig(
            enabled=bool(midi_input["enabled"]),
            configured_profile=configured_profile,
            profile_source="runtime-adapter"
            if configured_profile in ("", "auto")
            else "explicit-override",
            device_glob=str(midi_input["device_glob"]),
            alsa_raw_globs=tuple(str(value) for value in midi_input["alsa_raw_globs"]),
            oss_midi_globs=tuple(str(value) for value in midi_input["oss_midi_globs"]),
        ),
        osc_input=OscInputConfig(
            enabled=bool(osc_input["enabled"]) if osc_input else False,
            listen_address=(
                str(osc_input["listen_address"])
                if osc_input and "listen_address" in osc_input
                else None
            ),
            listen_port=(
                int(osc_input["listen_port"])
                if osc_input and "listen_port" in osc_input
                else None
            ),
            advertise=bool(osc_input["advertise"]) if osc_input else False,
            service_name=str(osc_input["service_name"]) if osc_input else "",
            configured=bool(
                osc_input
                and "listen_address" in osc_input
                and "listen_port" in osc_input
            ),
        ),
        capacities=RuntimeCapacities(
            max_oscs=int(data["amy_max_oscs"]),
            max_sequencer_tags=int(data["amy_max_sequencer_tags"]),
            max_sequence_events=int(data["amy_max_sequence_events"]),
            max_sequence_executions=int(data["amy_max_sequence_executions"]),
            max_buses=int(data["amy_max_buses"]),
            voices=VoiceCapacities(
                drums=int(voices["drums"]),
                bass=int(voices["bass"]),
                strum=int(voices["strum"]),
                manual_chord=int(voices["manual_chord"]),
                rhythm_chord=int(voices["rhythm_chord"]),
                midi_per_synth=int(midi_player["voices_per_synth"]),
                midi_drums=int(midi_player["drum_voices"]),
            ),
        ),
        layout=SynthBusLayout(
            role_synth_ids=_role_items(synth_ids),
            midi_synth_ids=tuple(int(value) for value in midi_player["synth_ids"]),
            midi_drum_synth_id=int(midi_player["drum_synth_id"]),
            role_buses=tuple(
                (name, int(buses[name])) for name in ("drums", "bass", "strum", "chord")
            ),
            midi_row_buses=tuple(int(value) for value in buses["midi_rows"]),
            midi_drum_bus=int(buses["midi_drums"]),
            sequencer_tag_ranges=tuple(
                (
                    name,
                    int(cast(dict[str, Any], tag_ranges[name])["start"]),
                    int(cast(dict[str, Any], tag_ranges[name])["count"]),
                )
                for name in ("drums", "bass", "chords")
            ),
            sequencer_sequence_ranges=tuple(
                (
                    name,
                    int(cast(dict[str, Any], sequence_ranges[name])["start"]),
                    int(cast(dict[str, Any], sequence_ranges[name])["count"]),
                )
                for name in ("fills", "chords", "drum_bases")
            ),
        ),
        debug=DebugConfig(
            log_amy_commands=bool(debug["log_amy_commands"]),
            amy_command_log=str(debug["amy_command_log"]),
            log_logical_events=bool(debug["log_logical_events"]),
        ),
        synth_defaults=SynthDefaults(
            chord=str(defaults["chord"]),
            strum=str(defaults["strum"]),
            bass=str(defaults["bass"]),
        ),
        drums=DrumRuntimeConfig(
            kit=str(drums["kit"]),
            velocity_gain=float(drums["velocity_gain"]),
            sample_map=tuple(
                (
                    str(name),
                    DrumSampleConfig(
                        preset=int(cast(dict[str, Any], sample)["preset"]),
                        note=int(cast(dict[str, Any], sample)["note"]),
                    ),
                )
                for name, sample in sorted(sample_map.items())
            ),
        ),
        rhythm=RhythmRuntimeConfig(
            chord_gate_beats=float(rhythm["chord_gate_beats"]),
            bass_gate_beats=float(rhythm["bass_gate_beats"]),
            max_rhythm_chord_notes=int(rhythm["max_rhythm_chord_notes"]),
            sequencer_reset_guard_ms=float(rhythm["sequencer_reset_guard_ms"]),
        ),
        performance=PerformanceTimingConfig(
            strum_gate_ms=float(performance["strum_gate_ms"]),
            one_shot_chord_gate_ms=float(
                performance["one_shot_chord_gate_ms"]
            ),
            strum_tail_ms=float(performance["strum_tail_ms"]),
            synth_alloc_guard_ms=float(performance["synth_alloc_guard_ms"]),
        ),
        synth_patches=tuple(sorted(_legacy_patch_map(data).items())),
        instrument_levels=tuple(
            (str(name), float(level))
            for name, level in sorted(instrument_levels.items())
        ),
        role_levels=tuple(
            (str(name), float(level))
            for name, level in sorted(role_levels.items())
        ),
        provenance=provenance,
        _compatibility_json=json.dumps(
            compatibility,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        _synth_programs_json=json.dumps(
            synth_programs,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        _patch_compatibility_json=json.dumps(
            patch_compatibility,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    )


def load_resolved_amy_config(
    path: Path,
    *,
    source_kind: ConfigSourceKind | None = None,
) -> ResolvedAmyConfig:
    source_path = Path(path).expanduser()
    if not source_path.is_file():
        raise FileNotFoundError(
            f"AMY configuration file not found: {source_path}. "
            "The frontend no longer falls back to an embedded configuration."
        )
    try:
        with source_path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ConfigValidationError(
            [
                ConfigIssue(
                    "$",
                    f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}",
                )
            ]
        ) from exc
    return resolve_amy_config_data(
        loaded,
        source_path=source_path,
        source_kind=source_kind,
    )


def resolve_amy_config_data(
    loaded: object,
    *,
    source_path: Path,
    source_kind: ConfigSourceKind | None = None,
) -> ResolvedAmyConfig:
    """Migrate, validate and freeze one already-decoded config document."""

    if not isinstance(loaded, dict):
        raise ConfigValidationError(
            [ConfigIssue("$", "must contain a JSON object")]
        )
    try:
        migration = migrate_config_document(cast(JsonObject, loaded))
    except ConfigMigrationError as exc:
        raise ConfigValidationError([ConfigIssue(exc.path, exc.detail)]) from exc
    data = migration.data
    revision = _validate_structure(data, source_path)
    issues = _domain_issues(data)
    if issues:
        raise ConfigValidationError(issues)
    provenance = _provenance(source_path, data, source_kind)
    return _to_resolved(data, revision, provenance)


def apply_transport_overrides(
    resolved: ResolvedAmyConfig,
    *,
    serial_port: str | None = None,
    serial_baud: int | None = None,
) -> ResolvedAmyConfig:
    """Return a resolved config with explicit CLI transport provenance."""

    if serial_port is None and serial_baud is None:
        return resolved
    compatibility = resolved.compatibility_dict()
    serial = cast(dict[str, Any], compatibility["serial"])
    paths = list(resolved.provenance.runtime_override_paths)
    transport = resolved.transport
    if serial_port is not None:
        serial["port"] = serial_port
        transport = replace(transport, serial_port=serial_port)
        paths.append("$.serial.port")
    if serial_baud is not None:
        if serial_baud < 1200:
            raise ConfigValidationError(
                [ConfigIssue("$.serial.baud", "CLI override must be at least 1200")]
            )
        serial["baud"] = serial_baud
        transport = replace(transport, serial_baud=serial_baud)
        paths.append("$.serial.baud")
    provenance = replace(
        resolved.provenance,
        runtime_override_paths=tuple(dict.fromkeys(paths)),
    )
    return replace(
        resolved,
        transport=transport,
        provenance=provenance,
        _compatibility_json=json.dumps(
            compatibility,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    )
