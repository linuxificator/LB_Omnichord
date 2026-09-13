from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SampleProgram:
    program_id: str
    display_name: str
    articulations: tuple[str, ...]
    default_articulation: str


def load_vsco_programs(path: Path) -> tuple[SampleProgram, ...]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_revision") != 1:
        raise ValueError(f"{path} is not a supported sample manifest")
    bank = raw.get("bank")
    programs = raw.get("programs")
    if not isinstance(bank, dict) or bank.get("id") != "vsco-2-ce":
        raise ValueError(f"{path} is not the VSCO manifest")
    if not isinstance(programs, list) or len(programs) != 75:
        raise ValueError(f"{path} must describe all 75 VSCO source mappings")
    result = tuple(
        SampleProgram(
            program_id=str(item["id"]),
            display_name=str(item["display_name"]),
            articulations=tuple(str(value) for value in item["articulations"]),
            default_articulation=str(item["default_articulation"]),
        )
        for item in programs
    )
    if len({item.program_id for item in result}) != len(result):
        raise ValueError(f"{path} has duplicate sample program IDs")
    return result
