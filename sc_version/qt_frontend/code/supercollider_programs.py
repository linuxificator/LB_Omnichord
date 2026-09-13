from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re


_SYNTHDEF = re.compile(r"SynthDef\(\s*[\\\"']?([A-Za-z0-9_]+)")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT = re.compile(r"//.*?$", re.MULTILINE)
_ARG_BLOCK = re.compile(r"\barg\s+(.*?);", re.DOTALL)
_PIPE_BLOCK = re.compile(r"\{\s*\|(.*?)\|", re.DOTALL)
_IDENTIFIER = re.compile(r"\b([A-Za-z][A-Za-z0-9_]*)\s*(?:=|,|$)")
_SCLORK_SOURCE_COMMIT = "6730c745971aa45c95d9b4cddfb4d5ca342774b3"


@dataclass(frozen=True, slots=True)
class SuperColliderProgram:
    program_id: str
    native_name: str
    category: str
    controls: tuple[str, ...]
    pitch_support: bool
    release_mode: str


def _controls(source: str) -> tuple[str, ...]:
    code = _LINE_COMMENT.sub("", _BLOCK_COMMENT.sub("", source))
    match = _ARG_BLOCK.search(code) or _PIPE_BLOCK.search(code)
    if match is None:
        return ()
    return tuple(dict.fromkeys(_IDENTIFIER.findall(match.group(1))))


def build_sclork_catalog(source_root: Path) -> dict[str, object]:
    """Derive immutable runtime metadata from the pinned SynthDef sources."""

    entries: list[dict[str, object]] = []
    for path in sorted(source_root.rglob("*.scd")):
        source = path.read_text(encoding="utf-8")
        match = _SYNTHDEF.search(source)
        if match is None:
            raise ValueError(f"{path} contains no SynthDef declaration")
        native_name = match.group(1)
        controls = _controls(source)
        entries.append(
            {
                "program_id": f"sc.sclork.{native_name}",
                "native_name": native_name,
                "category": path.parent.name,
                "source_path": path.relative_to(source_root.parent.parent).as_posix(),
                "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "controls": list(controls),
                "pitch_support": "freq" in controls,
                "release_mode": "gated" if "gate" in controls else "natural",
                "routing_adapter_required": not any(
                    control in controls for control in ("out", "outBus", "outbus")
                ),
            }
        )
    names = [str(entry["native_name"]) for entry in entries]
    if len(entries) != 109 or len(names) != len(set(names)):
        raise ValueError(
            f"expected 109 unique SynthDefs, found {len(entries)}/{len(set(names))}"
        )
    return {
        "schema_revision": 1,
        "source_commit": _SCLORK_SOURCE_COMMIT,
        "license": "GPL-3.0-or-later",
        "programs": entries,
    }


def load_supercollider_programs(path: Path) -> tuple[SuperColliderProgram, ...]:
    source = Path(path)
    raw = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_revision") != 1:
        raise ValueError(f"{source} is not a supported SuperCollider catalog")
    programs_raw = raw.get("programs")
    if not isinstance(programs_raw, list):
        raise ValueError(f"{source} has no programs list")
    programs: list[SuperColliderProgram] = []
    for index, item in enumerate(programs_raw):
        if not isinstance(item, dict):
            raise ValueError(f"{source} program {index} is not an object")
        controls = item.get("controls")
        if not isinstance(controls, list) or not all(
            isinstance(value, str) for value in controls
        ):
            raise ValueError(f"{source} program {index} has invalid controls")
        programs.append(
            SuperColliderProgram(
                program_id=str(item["program_id"]),
                native_name=str(item["native_name"]),
                category=str(item["category"]),
                controls=tuple(controls),
                pitch_support=bool(item["pitch_support"]),
                release_mode=str(item["release_mode"]),
            )
        )
    if len(programs) != 109 or len({item.program_id for item in programs}) != 109:
        raise ValueError(f"{source} must contain 109 unique SCLOrk programs")
    return tuple(programs)
