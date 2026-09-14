from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class DrumKit:
    kit_id: str
    label: str
    program_id: str
    role_defaults: tuple[tuple[str, str], ...]
    gain: float = 1.0

    def pad_for(self, role: str) -> str:
        try:
            return dict(self.role_defaults)[str(role)]
        except KeyError as exc:
            raise ValueError(
                f"drum kit {self.kit_id!r} has no pad for role {role!r}"
            ) from exc


def _load_kits() -> tuple[DrumKit, ...]:
    path = (
        Path(__file__).resolve().parent.parent
        / "music"
        / "sc_expansion"
        / "sc_pcm_drumkits_v1.json"
    )
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("unsupported SC PCM drum-kit catalogue")
    kits: list[DrumKit] = []
    for row in raw.get("kits", ()):
        if not isinstance(row, dict):
            raise ValueError("SC PCM drum kit must be an object")
        role_defaults = row.get("role_defaults")
        if not isinstance(role_defaults, dict) or not role_defaults:
            raise ValueError(f"drum kit {row.get('kit_id')!r} has no role defaults")
        kits.append(
            DrumKit(
                kit_id=str(row["kit_id"]),
                label=str(row["label"]),
                program_id=str(row["program_id"]),
                role_defaults=tuple(
                    sorted(
                        (str(role), str(pad))
                        for role, pad in role_defaults.items()
                    )
                ),
                gain=10.0 ** (float(row.get("kit_gain_db", 0.0)) / 20.0),
            )
        )
    if len(kits) != 9 or len({kit.kit_id for kit in kits}) != len(kits):
        raise ValueError("SC PCM catalogue must contain nine unique kits")
    return tuple(kits)


DRUM_KITS = _load_kits()
_BY_ID = MappingProxyType({kit.kit_id: kit for kit in DRUM_KITS})
DEFAULT_DRUM_KIT_ID = DRUM_KITS[0].kit_id


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


def resolve_hit(kit_id: str, role: str) -> tuple[str, str, float]:
    kit = kit_by_id(kit_id)
    return kit.program_id, kit.pad_for(str(role)), kit.gain
