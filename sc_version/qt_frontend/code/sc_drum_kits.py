from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True, slots=True)
class DrumKit:
    kit_id: str
    label: str
    engine: str
    pad_programs: tuple[tuple[str, str], ...]
    role_defaults: tuple[tuple[str, str], ...]
    gain: float = 1.0

    def pad_for(self, selector: str) -> str:
        requested = str(selector)
        programs = dict(self.pad_programs)
        if requested in programs or "*" in programs:
            return requested
        try:
            return dict(self.role_defaults)[requested]
        except KeyError as exc:
            raise ValueError(
                f"drum kit {self.kit_id!r} has no pad for {requested!r}"
            ) from exc

    def program_for(self, pad_id: str) -> str:
        programs = dict(self.pad_programs)
        if str(pad_id) in programs:
            return programs[str(pad_id)]
        try:
            return programs["*"]
        except KeyError as exc:
            raise ValueError(
                f"drum kit {self.kit_id!r} has no program for pad {pad_id!r}"
            ) from exc

    @property
    def sample_programs(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    program
                    for _pad, program in self.pad_programs
                    if program.startswith("sample.")
                }
            )
        )


def _catalog(name: str) -> dict[str, Any]:
    path = Path(__file__).resolve().parent.parent / "music" / "sc_expansion" / name
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError(f"unsupported SC drum-kit catalogue {name!r}")
    return raw


def _role_defaults(row: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    value = row.get("role_defaults")
    if not isinstance(value, dict) or not value:
        raise ValueError(f"drum kit {row.get('kit_id')!r} has no role defaults")
    return tuple(sorted((str(role), str(pad)) for role, pad in value.items()))


def _load_native_kits() -> tuple[DrumKit, ...]:
    raw = _catalog("sc_native_drumkits_v1.json")
    kits: list[DrumKit] = []
    for row in raw.get("kits", ()):
        if not isinstance(row, dict) or not isinstance(row.get("pads"), dict):
            raise ValueError("SC native drum kit must contain pads")
        pads = row["pads"]
        kits.append(
            DrumKit(
                kit_id=str(row["kit_id"]),
                label=str(row["label"]),
                engine="native",
                pad_programs=tuple(
                    sorted(
                        (str(pad), str(profile["program_id"]))
                        for pad, profile in pads.items()
                        if isinstance(profile, dict)
                    )
                ),
                role_defaults=_role_defaults(row),
                gain=float(row.get("existing_linear_gain", 1.0))
                * (10.0 ** (float(row.get("kit_gain_db", 0.0)) / 20.0)),
            )
        )
    if len(kits) != 5:
        raise ValueError("SC native catalogue must contain five kits")
    return tuple(kits)


def _load_pcm_kits() -> tuple[DrumKit, ...]:
    raw = _catalog("sc_pcm_drumkits_v1.json")
    kits: list[DrumKit] = []
    for row in raw.get("kits", ()):
        if not isinstance(row, dict) or not isinstance(row.get("pads"), dict):
            raise ValueError("SC PCM drum kit must contain pads")
        program = str(row["program_id"])
        kits.append(
            DrumKit(
                kit_id=str(row["kit_id"]),
                label=str(row["label"]),
                engine="sample",
                pad_programs=tuple(
                    sorted((str(pad), program) for pad in row["pads"])
                ),
                role_defaults=_role_defaults(row),
                gain=10.0 ** (float(row.get("kit_gain_db", 0.0)) / 20.0),
            )
        )
    if len(kits) != 9:
        raise ValueError("SC PCM catalogue must contain nine kits")
    return tuple(kits)


_LEGACY_PCM_KIT = DrumKit(
    kit_id="pcm-vsco",
    label="VSCO PCM",
    engine="sample",
    pad_programs=(("*", "sample.vsco.gm-styleperc"),),
    role_defaults=(("*", "*"),),
)

DRUM_KITS = (_LEGACY_PCM_KIT, *_load_native_kits(), *_load_pcm_kits())
if len(DRUM_KITS) != 15 or len({kit.kit_id for kit in DRUM_KITS}) != 15:
    raise ValueError("SC edition requires fifteen unique drum kits")
_BY_ID = MappingProxyType({kit.kit_id: kit for kit in DRUM_KITS})
DEFAULT_DRUM_KIT_ID = _LEGACY_PCM_KIT.kit_id


def kit_by_id(kit_id: str) -> DrumKit:
    try:
        return _BY_ID[str(kit_id)]
    except KeyError as exc:
        raise ValueError(f"unknown SC drum kit {kit_id!r}") from exc


def midi_role(note: int) -> str:
    value = int(note)
    if value in {35, 36, 44}:
        return "low_primary"
    if value in {38, 40}:
        return "backbeat_primary"
    if value == 39:
        return "hand_accent"
    if value in {41, 43, 45}:
        return "tonal_low"
    if value in {47, 48}:
        return "tonal_mid"
    if value == 50:
        return "tonal_high"
    if value in {42, 46, 54, 69, 70, 71}:
        return "timekeeper_open" if value == 46 else "timekeeper_primary"
    if value in {49, 51, 52, 53, 55, 57, 59}:
        return "section_accent"
    if value in {60, 61, 62, 63, 64}:
        return "hand_high" if value in {60, 62, 63} else "hand_low"
    return "electronic_detail"


def resolve_hit(kit_id: str, selector: str) -> tuple[str, str, float]:
    kit = kit_by_id(kit_id)
    requested = str(selector)
    # The expanded catalogue namespaces inherited slots so their identities
    # cannot collide with concrete kit pads.  VSCO's legacy program is keyed
    # by semantic drum role, so remove only that catalogue namespace at this
    # engine adapter boundary.  Direct MIDI roles already arrive unprefixed.
    if kit.kit_id == _LEGACY_PCM_KIT.kit_id and requested.startswith("legacy/"):
        requested = requested.removeprefix("legacy/")
    pad = kit.pad_for(requested)
    profile_id = f"{kit.kit_id}/{pad}" if kit.engine == "native" else pad
    return kit.program_for(pad), profile_id, kit.gain
