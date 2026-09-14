from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
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


def display_name(native_name: str) -> str:
    """Turn an upstream symbol into a compact, stable browser label."""

    words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", native_name)
    words = re.sub(r"(?<=[A-Za-z])(?=[0-9])", " ", words)
    words = words.replace("_", " ")
    return "SC " + " ".join(word.capitalize() for word in words.split())


def _legacy_replacement(label: str) -> str:
    text = label.casefold()
    if "tb-303" in text:
        return "acidOto3091"
    if "physical" in text:
        return "pluck"
    if any(word in text for word in ("bass", "cello", "low dark")):
        return "fmBass"
    if any(word in text for word in ("flute", "piccolo", "recorder")):
        return "waveguideFlute"
    if any(word in text for word in ("violin", "string", "choir", "ensemble")):
        return "prophet5pwmStrings"
    if any(word in text for word in ("organ", "accordion", "calliope", "pipes")):
        return "organTonewheel1"
    if any(word in text for word in ("harpsichord", "clav")):
        return "harpsichord2"
    if any(word in text for word in ("rhodes", "e.piano", "elect. piano", "toy")):
        return "FMRhodes1"
    if "piano" in text:
        return "cheapPiano1"
    if any(word in text for word in ("guitar", "lute", "koto", "pluck", "pizzicato")):
        return "pluck"
    if "steel drum" in text:
        return "steelDrum"
    if "xylophone" in text:
        return "xylophone"
    if any(word in text for word in ("bell", "chime", "celeste", "vibe", "gong", "shimmer")):
        return "glockenspiel"
    if any(word in text for word in ("brass", "trumpet", "fanfare", "horn")):
        return "cs80leadMH"
    if any(word in text for word in ("sweep", "wah", "funky", "rise", "phase")):
        return "midSideSaw"
    if "pad" in text or "ethereal" in text or "sustainer" in text:
        return "feedbackPad2"
    if any(word in text for word in ("clarinet", "bassoon", "reed", "sax")):
        return "defaultB"
    return "defaultB"


def build_legacy_program_map(legacy_catalog: Path) -> dict[str, object]:
    """Create the explicit import sidecar for AMY-era program selections."""

    raw = json.loads(legacy_catalog.read_text(encoding="utf-8"))
    mappings = {
        str(item["key"]): f"sc.sclork.{_legacy_replacement(str(item['label']))}"
        for item in raw["synths"]
    }
    mappings["physical_strings"] = "sc.sclork.pluck"
    mappings["tb303"] = "sc.omni.acid303"
    return {
        "schema_revision": 1,
        "policy": "musical-family replacement; original AMY selection remains in preset data",
        "mappings": dict(sorted(mappings.items())),
    }


def load_legacy_program_map(path: Path) -> dict[str, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_revision") != 1:
        raise ValueError(f"{path} is not a supported program migration map")
    mappings = raw.get("mappings")
    if not isinstance(mappings, dict) or not mappings:
        raise ValueError(f"{path} has no program mappings")
    return {str(key): str(value) for key, value in mappings.items()}


def load_sclork_playback_profile(path: Path) -> tuple[dict[str, float], dict[str, str]]:
    """Load reviewed browser admission and output calibration metadata."""

    source = Path(path)
    raw = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_revision") != 1:
        raise ValueError(f"{source} is not a supported SCLOrk playback profile")
    programs = raw.get("programs")
    excluded = raw.get("excluded")
    if not isinstance(programs, dict) or not isinstance(excluded, dict):
        raise ValueError(f"{source} has incomplete playback metadata")
    gains = {
        str(program_id): float(record["gain"])
        for program_id, record in programs.items()
        if isinstance(record, dict)
    }
    reasons = {
        str(program_id): str(record["reason"])
        for program_id, record in excluded.items()
        if isinstance(record, dict)
    }
    if len(gains) != len(programs) or len(reasons) != len(excluded):
        raise ValueError(f"{source} contains malformed playback records")
    overlap = gains.keys() & reasons.keys()
    if overlap:
        raise ValueError(
            f"{source} both includes and excludes: {', '.join(sorted(overlap))}"
        )
    maximum = raw.get("method", {}).get("max_gain")
    if not isinstance(maximum, (int, float)) or not math.isfinite(float(maximum)):
        raise ValueError(f"{source} has no finite max_gain")
    invalid = [
        program_id
        for program_id, gain in gains.items()
        if not math.isfinite(gain) or gain <= 0 or gain > float(maximum)
    ]
    if invalid:
        raise ValueError(
            f"{source} has invalid playback gain for: {', '.join(sorted(invalid))}"
        )
    return gains, reasons


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
