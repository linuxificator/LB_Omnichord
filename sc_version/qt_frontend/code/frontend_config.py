from __future__ import annotations

import ipaddress
import json
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, cast

import fastjsonschema  # type: ignore[import-untyped]


CURRENT_FRONTEND_CONFIG_REVISION = 1
ConfigSourceKind = Literal["shipped", "user", "external"]
JsonObject = dict[str, Any]
SchemaValidator = Callable[[Any], Any]


@dataclass(frozen=True, slots=True)
class ConfigIssue:
    path: str
    message: str


class FrontendConfigError(ValueError):
    def __init__(self, issues: list[ConfigIssue] | tuple[ConfigIssue, ...]) -> None:
        self.issues = tuple(issues)
        details = "\n".join(f"- {issue.path}: {issue.message}" for issue in self.issues)
        super().__init__(f"invalid frontend configuration:\n{details}")


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
class ProgramDefaults:
    chord: str
    strum: str
    bass: str


@dataclass(frozen=True, slots=True)
class RhythmConfig:
    chord_gate_beats: float
    bass_gate_beats: float
    max_chord_notes: int


@dataclass(frozen=True, slots=True)
class PerformanceConfig:
    strum_tail_ms: float


@dataclass(frozen=True, slots=True)
class LogicalBusLayout:
    role_buses: tuple[tuple[str, int], ...]
    midi_row_buses: tuple[int, ...]
    midi_drum_bus: int


@dataclass(frozen=True, slots=True)
class FrontendConfig:
    revision: int
    midi_input: MidiInputConfig
    osc_input: OscInputConfig
    program_defaults: ProgramDefaults
    midi_voices_per_row: int
    rhythm: RhythmConfig
    performance: PerformanceConfig
    layout: LogicalBusLayout
    source_path: Path
    source_kind: ConfigSourceKind


def _json_path(parts: list[object]) -> str:
    path = "$"
    for part in parts:
        if part == "data" and path == "$":
            continue
        if isinstance(part, int):
            path += f"[{part}]"
        elif str(part).replace("_", "").isalnum():
            path += f".{part}"
        else:
            escaped = str(part).replace("\\", "\\\\").replace("'", "\\'")
            path += f"['{escaped}']"
    return path


def _schema_path(source_path: Path) -> Path:
    name = "frontend_v1.schema.json"
    candidates = (
        source_path.parent / "schema" / name,
        Path(__file__).resolve().parent.parent / "config" / "schema" / name,
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RuntimeError(
        "frontend configuration schema is not packaged; searched "
        + ", ".join(str(path) for path in candidates)
    )


@lru_cache(maxsize=2)
def _compiled_schema(path: Path) -> SchemaValidator:
    return cast(
        SchemaValidator,
        fastjsonschema.compile(json.loads(path.read_text(encoding="utf-8"))),
    )


def _validate_schema(data: JsonObject, source_path: Path) -> None:
    revision = data.get("config_revision")
    if revision != CURRENT_FRONTEND_CONFIG_REVISION:
        raise FrontendConfigError(
            [
                ConfigIssue(
                    "$.config_revision",
                    f"unsupported revision {revision!r}; expected "
                    f"{CURRENT_FRONTEND_CONFIG_REVISION}",
                )
            ]
        )
    try:
        _compiled_schema(_schema_path(source_path))(data)
    except fastjsonschema.JsonSchemaException as exc:
        raw_path = cast(list[object], getattr(exc, "path", []))
        rule = str(getattr(exc, "rule", ""))
        definition = getattr(exc, "definition", None)
        value = getattr(exc, "value", None)
        issues: list[ConfigIssue] = []
        if rule == "additionalProperties" and isinstance(value, dict):
            properties = definition.get("properties", {}) if isinstance(definition, dict) else {}
            for key in sorted(set(value).difference(properties)):
                issues.append(ConfigIssue(_json_path([*raw_path, key]), "unknown property"))
        elif rule == "required" and isinstance(value, dict):
            required = definition.get("required", []) if isinstance(definition, dict) else []
            for key in required:
                if key not in value:
                    issues.append(ConfigIssue(_json_path([*raw_path, key]), "required property is missing"))
        if not issues:
            issues.append(ConfigIssue(_json_path(raw_path), str(getattr(exc, "message", exc))))
        raise FrontendConfigError(issues) from exc


def _source_kind(path: Path) -> ConfigSourceKind:
    if path.parent.name == "config" and path.parent.parent.name == ".omnichord":
        return "user"
    shipped = Path(__file__).resolve().parent.parent / "config" / "frontend.json"
    return "shipped" if path.resolve() == shipped.resolve() else "external"


def resolve_frontend_config(
    loaded: object,
    *,
    source_path: Path,
    source_kind: ConfigSourceKind | None = None,
) -> FrontendConfig:
    if not isinstance(loaded, dict):
        raise FrontendConfigError([ConfigIssue("$", "must contain a JSON object")])
    data = cast(JsonObject, loaded)
    _validate_schema(data, source_path)

    midi_input = cast(dict[str, Any], data["midi_input"])
    profile = str(midi_input["tech_profile"]).strip().casefold()
    osc_input = cast(dict[str, Any], data["osc_input"])
    issues: list[ConfigIssue] = []
    listen_address = osc_input.get("listen_address")
    listen_port = osc_input.get("listen_port")
    if (listen_address is None) != (listen_port is None):
        missing = "listen_port" if listen_port is None else "listen_address"
        issues.append(
            ConfigIssue(
                f"$.osc_input.{missing}",
                "must be configured together with the OSC listen address/port",
            )
        )
    elif listen_address is not None:
        try:
            ipaddress.IPv4Address(str(listen_address))
        except ipaddress.AddressValueError:
            issues.append(
                ConfigIssue(
                    "$.osc_input.listen_address",
                    "must be a numeric IPv4 address",
                )
            )
    service_name = str(osc_input["service_name"])
    if service_name != service_name.strip() or any(ord(char) < 32 or ord(char) == 127 for char in service_name):
        issues.append(ConfigIssue("$.osc_input.service_name", "must not contain surrounding whitespace or control characters"))

    buses = cast(dict[str, Any], data["logical_buses"])
    role_buses = tuple((name, int(buses[name])) for name in ("drums", "bass", "strum", "chord"))
    midi_buses = tuple(int(value) for value in cast(list[Any], buses["midi_rows"]))
    drum_bus = int(buses["midi_drums"])
    all_buses = tuple(value for _name, value in role_buses) + midi_buses + (drum_bus,)
    if len(set(all_buses)) != len(all_buses):
        issues.append(ConfigIssue("$.logical_buses", "every OMNI/MIDI owner must have a distinct bus"))
    if issues:
        raise FrontendConfigError(issues)

    defaults = cast(dict[str, Any], data["default_programs"])
    midi = cast(dict[str, Any], data["midi"])
    rhythm = cast(dict[str, Any], data["rhythm"])
    performance = cast(dict[str, Any], data["performance"])
    return FrontendConfig(
        revision=CURRENT_FRONTEND_CONFIG_REVISION,
        midi_input=MidiInputConfig(
            enabled=bool(midi_input["enabled"]),
            configured_profile=profile,
            profile_source="runtime-adapter" if profile in ("", "auto") else "explicit-override",
            device_glob=str(midi_input["device_glob"]),
            alsa_raw_globs=tuple(str(value) for value in midi_input["alsa_raw_globs"]),
            oss_midi_globs=tuple(str(value) for value in midi_input["oss_midi_globs"]),
        ),
        osc_input=OscInputConfig(
            enabled=bool(osc_input["enabled"]),
            listen_address=(
                str(listen_address) if listen_address is not None else None
            ),
            listen_port=int(listen_port) if listen_port is not None else None,
            advertise=bool(osc_input["advertise"]),
            service_name=service_name,
            configured=listen_address is not None and listen_port is not None,
        ),
        program_defaults=ProgramDefaults(
            chord=str(defaults["chord"]),
            strum=str(defaults["strum"]),
            bass=str(defaults["bass"]),
        ),
        midi_voices_per_row=int(midi["voices_per_row"]),
        rhythm=RhythmConfig(
            chord_gate_beats=float(rhythm["chord_gate_beats"]),
            bass_gate_beats=float(rhythm["bass_gate_beats"]),
            max_chord_notes=int(rhythm["max_chord_notes"]),
        ),
        performance=PerformanceConfig(strum_tail_ms=float(performance["strum_tail_ms"])),
        layout=LogicalBusLayout(role_buses, midi_buses, drum_bus),
        source_path=source_path.resolve(),
        source_kind=source_kind or _source_kind(source_path),
    )


def load_frontend_config(
    path: Path,
    *,
    source_kind: ConfigSourceKind | None = None,
) -> FrontendConfig:
    source_path = Path(path).expanduser()
    if not source_path.is_file():
        raise FileNotFoundError(f"frontend configuration file not found: {source_path}")
    try:
        loaded = json.loads(source_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FrontendConfigError(
            [ConfigIssue("$", f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}")]
        ) from exc
    return resolve_frontend_config(loaded, source_path=source_path, source_kind=source_kind)
