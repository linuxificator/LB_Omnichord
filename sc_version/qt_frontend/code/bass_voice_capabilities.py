from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class BassVoiceCapability:
    program_id: str
    lifetime: str
    tie_supported: bool
    legato_supported: bool
    glide_supported: bool
    glide_control: str | None
    accent_path: str

    def supports(self, link: str) -> bool:
        if self.lifetime != "gated":
            return False
        if link == "tie":
            return self.tie_supported
        if link == "legato_glide":
            return self.legato_supported and self.glide_supported
        return False


def _load() -> MappingProxyType[str, BassVoiceCapability]:
    path = (
        Path(__file__).resolve().parent.parent
        / "music"
        / "sc_expansion"
        / "bass_voice_capabilities_v1.json"
    )
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("unsupported bass voice capability catalogue")
    result: dict[str, BassVoiceCapability] = {}
    for row in raw.get("voices", ()):
        capability = BassVoiceCapability(
            program_id=str(row["program_id"]),
            lifetime=str(row["lifetime"]),
            tie_supported=bool(row["tie_supported"]),
            legato_supported=bool(row["legato_supported"]),
            glide_supported=bool(row["glide_supported"]),
            glide_control=(
                None if row.get("glide_control") is None else str(row["glide_control"])
            ),
            accent_path=str(row["accent_path"]),
        )
        if capability.program_id in result:
            raise ValueError(f"duplicate bass capability {capability.program_id!r}")
        result[capability.program_id] = capability
    return MappingProxyType(result)


CAPABILITIES = _load()
DETACHED = BassVoiceCapability(
    program_id="*",
    lifetime="unknown",
    tie_supported=False,
    legato_supported=False,
    glide_supported=False,
    glide_control=None,
    accent_path="attack_velocity",
)


def capability_for(program_id: str) -> BassVoiceCapability:
    return CAPABILITIES.get(str(program_id), DETACHED)
