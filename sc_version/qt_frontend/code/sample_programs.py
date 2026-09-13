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
    source_program_id: str
    selected_articulation: str


ARTICULATION_ID_SEPARATOR = ".art."


def articulation_program_id(program_id: str, articulation: str) -> str:
    return f"{program_id}{ARTICULATION_ID_SEPARATOR}{articulation}"


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
    result: list[SampleProgram] = []
    for item in programs:
        source_program_id = str(item["id"])
        display_name = str(item["display_name"])
        articulations = tuple(str(value) for value in item["articulations"])
        default_articulation = str(item["default_articulation"])
        if not articulations or default_articulation not in articulations:
            raise ValueError(
                f"{path} program {source_program_id} has no valid default articulation"
            )
        result.append(
            SampleProgram(
                program_id=source_program_id,
                display_name=display_name,
                articulations=articulations,
                default_articulation=default_articulation,
                source_program_id=source_program_id,
                selected_articulation=default_articulation,
            )
        )
        result.extend(
            SampleProgram(
                program_id=articulation_program_id(source_program_id, articulation),
                display_name=f"{display_name} — {articulation.replace('-', ' ')}",
                articulations=articulations,
                default_articulation=default_articulation,
                source_program_id=source_program_id,
                selected_articulation=articulation,
            )
            for articulation in articulations
            if articulation != default_articulation
        )
    result_tuple = tuple(result)
    if len({item.program_id for item in result_tuple}) != len(result_tuple):
        raise ValueError(f"{path} has duplicate sample program IDs")
    return result_tuple
