from __future__ import annotations

import array
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import struct
import sys
from typing import Any

import soundfile  # type: ignore[import-untyped]


COMPILER_VERSION = 5
VSCO_SOURCE_PIN = "6dd651d55dde97fd4028699be9d4481f26917891"
_HEADER = re.compile(r"<([A-Za-z]+)>")
_OPCODE = re.compile(r"(?<!\S)([A-Za-z][A-Za-z0-9_]*)=")
_NOTE = re.compile(r"^([a-gA-G])([#b]?)(-?[0-9]+)$")
_DEFINE = re.compile(r"^\s*#define\s+(\$[A-Za-z0-9_]+)\s+(.+?)\s*$")
_INCLUDE = re.compile(r'#include\s+"([^"]+)"')
_MACRO = re.compile(r"\$[A-Za-z0-9_]+")
_AUDIT_LOCATION_LIMIT = 16
_KNOWN_OPCODES = {
    "ampeg_attack",
    "ampeg_dynamic",
    "ampeg_release",
    "default_path",
    "group_label",
    "hikey",
    "hirand",
    "hivel",
    "key",
    "lokey",
    "lorand",
    "lovel",
    "pitch_keycenter",
    "sample",
    "seq_length",
    "seq_position",
    "sw_default",
    "sw_hikey",
    "sw_label",
    "sw_last",
    "sw_lokey",
    "tune",
    "trigger",
    "volume",
}
_OPCODE_CLASSIFICATION = {
    "default_path": "compile-time-metadata",
    "group_label": "implemented-runtime",
    "sw_label": "compile-time-metadata",
    **{
        opcode: "implemented-runtime"
        for opcode in _KNOWN_OPCODES - {"default_path", "group_label", "sw_label"}
    },
}


@dataclass(frozen=True, slots=True)
class _SourceRegion:
    source: Path
    line: int
    values: dict[str, str]


@dataclass(frozen=True, slots=True)
class _ExpandedLine:
    source: Path
    line: int
    text: str


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _number(value: str | None, default: float) -> float:
    if value is None:
        return default
    return float(value)


def _midi_note(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        match = _NOTE.fullmatch(value.strip())
        if match is None:
            raise ValueError(f"invalid SFZ note {value!r}") from None
        pitch_class = {
            "c": 0,
            "d": 2,
            "e": 4,
            "f": 5,
            "g": 7,
            "a": 9,
            "b": 11,
        }[match.group(1).casefold()]
        accidental = {"": 0, "#": 1, "b": -1}[match.group(2)]
        return (int(match.group(3)) + 1) * 12 + pitch_class + accidental


def _opcodes(line: str) -> tuple[tuple[str, str], ...]:
    source = line.split("//", 1)[0].strip()
    matches = tuple(_OPCODE.finditer(source))
    return tuple(
        (
            match.group(1),
            source[match.end() : matches[index + 1].start()].strip()
            if index + 1 < len(matches)
            else source[match.end() :].strip(),
        )
        for index, match in enumerate(matches)
    )


def _replace_macros(
    text: str,
    macros: dict[str, str],
    *,
    source: Path,
    line: int,
) -> str:
    result = text
    for _ in range(32):
        names = set(_MACRO.findall(result))
        if not names:
            return result
        missing = sorted(name for name in names if name not in macros)
        if missing:
            raise ValueError(
                f"{source}:{line}: undefined SFZ macro {missing[0]}"
            )
        replaced = _MACRO.sub(lambda match: macros[match.group(0)], result)
        if replaced == result:
            break
        result = replaced
    raise ValueError(f"{source}:{line}: recursive SFZ macro expansion")


def preprocess_sfz(path: Path, *, root: Path | None = None) -> tuple[_ExpandedLine, ...]:
    """Expand standard SFZ defines/includes while retaining source locations."""

    source_root = (root or path.parent).resolve()
    macros: dict[str, str] = {}
    active: list[Path] = []

    def resolve_include(current: Path, value: str, line: int) -> Path:
        portable = PurePosixPath(value.replace("\\", "/"))
        candidates = (
            current.parent.joinpath(*portable.parts).resolve(),
            source_root.joinpath(*portable.parts).resolve(),
        )
        for candidate in candidates:
            try:
                candidate.relative_to(source_root)
            except ValueError:
                continue
            if candidate.is_file():
                return candidate
        raise ValueError(f"{current}:{line}: missing or unsafe include {value!r}")

    def expand_file(current: Path) -> list[_ExpandedLine]:
        resolved = current.resolve()
        try:
            resolved.relative_to(source_root)
        except ValueError:
            raise ValueError(f"SFZ source escapes bank root: {resolved}") from None
        if resolved in active:
            cycle = " -> ".join(str(item) for item in (*active, resolved))
            raise ValueError(f"SFZ include cycle: {cycle}")
        active.append(resolved)
        output: list[_ExpandedLine] = []
        try:
            lines = resolved.read_text(encoding="utf-8-sig").splitlines()
            for line_number, raw_line in enumerate(lines, start=1):
                line = raw_line.split("//", 1)[0]
                definition = _DEFINE.fullmatch(line)
                if definition is not None:
                    macros[definition.group(1)] = _replace_macros(
                        definition.group(2),
                        macros,
                        source=resolved,
                        line=line_number,
                    )
                    continue
                pending = line
                while include := _INCLUDE.search(pending):
                    prefix = pending[: include.start()]
                    include_name = _replace_macros(
                        include.group(1),
                        macros,
                        source=resolved,
                        line=line_number,
                    )
                    included = expand_file(
                        resolve_include(resolved, include_name, line_number)
                    )
                    if included:
                        expanded_prefix = _replace_macros(
                            prefix,
                            macros,
                            source=resolved,
                            line=line_number,
                        )
                        if expanded_prefix.strip():
                            output.append(
                                _ExpandedLine(resolved, line_number, expanded_prefix)
                            )
                        output.extend(included)
                    else:
                        pending = prefix + pending[include.end() :]
                        continue
                    pending = pending[include.end() :]
                expanded = _replace_macros(
                    pending,
                    macros,
                    source=resolved,
                    line=line_number,
                )
                if expanded.strip():
                    output.append(_ExpandedLine(resolved, line_number, expanded))
        finally:
            active.pop()
        return output

    return tuple(expand_file(path))


def parse_sfz(path: Path, *, root: Path | None = None) -> tuple[_SourceRegion, ...]:
    """Resolve control/global/master/group inheritance into complete regions."""

    scopes: dict[str, dict[str, str]] = {
        "control": {},
        "global": {},
        "master": {},
        "group": {},
    }
    current = "global"
    regions: list[_SourceRegion] = []
    region_values: dict[str, str] | None = None
    region_line = 0
    region_source = path

    def finish_region() -> None:
        nonlocal region_values
        if region_values is not None:
            regions.append(_SourceRegion(region_source, region_line, region_values))
            region_values = None

    for expanded in preprocess_sfz(path, root=root):
        line_number = expanded.line
        source_path = expanded.source
        line = expanded.text.strip()
        if not line:
            continue
        header = _HEADER.search(line)
        if header is not None:
            finish_region()
            current = header.group(1).casefold()
            if current not in (*scopes, "region"):
                raise ValueError(f"{source_path}:{line_number}: unsupported <{current}>")
            if current in ("master", "group"):
                scopes[current] = {}
            if current == "region":
                region_line = line_number
                region_source = source_path
                region_values = {
                    **scopes["control"],
                    **scopes["global"],
                    **scopes["master"],
                    **scopes["group"],
                }
            line = line[header.end() :].strip()
        for key, value in _opcodes(line):
            if key not in _KNOWN_OPCODES:
                raise ValueError(f"{source_path}:{line_number}: unsupported opcode {key}")
            if not value:
                raise ValueError(f"{source_path}:{line_number}: empty opcode {key}")
            if current == "region":
                if region_values is None:
                    raise AssertionError("region scope is not initialized")
                region_values[key] = value
            else:
                scopes[current][key] = value
    finish_region()
    if not regions:
        raise ValueError(f"{path} contains no regions")
    return tuple(regions)


def audit_sfz_opcodes(
    paths: tuple[Path, ...],
    *,
    root: Path,
) -> dict[str, Any]:
    """Inventory the complete preprocessed opcode surface without accepting it."""

    source_root = root.resolve()
    occurrences: dict[str, list[dict[str, Any]]] = {}
    for path in sorted(path.resolve() for path in paths):
        for expanded in preprocess_sfz(path, root=source_root):
            line = expanded.text.strip()
            header = _HEADER.search(line)
            if header is not None:
                line = line[header.end() :].strip()
            for opcode, _value in _opcodes(line):
                try:
                    source_file = expanded.source.relative_to(source_root).as_posix()
                except ValueError:
                    raise ValueError(
                        f"opcode source escapes bank root: {expanded.source}"
                    ) from None
                occurrences.setdefault(opcode, []).append(
                    {"source_file": source_file, "line": expanded.line}
                )

    records = [
        {
            "opcode": opcode,
            "classification": _OPCODE_CLASSIFICATION.get(
                opcode, "unsupported-error"
            ),
            "occurrence_count": len(locations),
            "locations": locations[:_AUDIT_LOCATION_LIMIT],
            "locations_truncated": len(locations) > _AUDIT_LOCATION_LIMIT,
        }
        for opcode, locations in sorted(occurrences.items())
    ]
    unsupported = [
        record["opcode"]
        for record in records
        if record["classification"] == "unsupported-error"
    ]
    return {
        "schema_revision": 1,
        "compiler_version": COMPILER_VERSION,
        "mapping_count": len(paths),
        "complete": not unsupported,
        "unsupported_opcodes": unsupported,
        "opcodes": records,
    }


def _relative_sample(root: Path, region: _SourceRegion) -> Path:
    sample = region.values.get("sample")
    if sample is None:
        raise ValueError(f"{region.source}:{region.line}: region has no sample")
    default_path = region.values.get("default_path", "")
    portable = PurePosixPath(
        (default_path + sample).replace("\\", "/").lstrip("/")
    )
    resolved = root.joinpath(*portable.parts).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        raise ValueError(
            f"{region.source}:{region.line}: sample escapes bank root"
        ) from None
    if not resolved.is_file():
        raise ValueError(
            f"{region.source}:{region.line}: missing sample {portable.as_posix()}"
        )
    return resolved


def _decoded_pcm_digest(source: soundfile.SoundFile) -> str:
    """Hash decoded PCM in one architecture-independent representation."""

    digest = hashlib.sha256()
    while chunk := source.buffer_read(65536, dtype="int32"):
        if sys.byteorder == "big":
            values = array.array("i")
            values.frombytes(chunk)
            values.byteswap()
            chunk = values.tobytes()
        digest.update(chunk)
    return digest.hexdigest()


def _original_bit_depth(subtype: str, path: Path) -> int:
    match = re.fullmatch(r"PCM_[SU]?(\d+)", subtype)
    if match is None:
        raise ValueError(f"{path}: unsupported sample encoding {subtype}")
    return int(match.group(1))


def _audio_record(root: Path, path: Path, *, bank_id: str = "vsco") -> dict[str, Any]:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    try:
        with soundfile.SoundFile(path) as source:
            channels = source.channels
            sample_rate = source.samplerate
            frames = source.frames
            bit_depth = _original_bit_depth(source.subtype, path)
            pcm_digest = _decoded_pcm_digest(source)
    except soundfile.SoundFileRuntimeError as exc:
        raise ValueError(f"{path}: unsupported or invalid audio file: {exc}") from exc
    embedded_root_key, embedded_loops = (
        _wav_sampler_metadata(path, frames)
        if path.suffix.casefold() == ".wav"
        else (None, [])
    )
    relative = path.relative_to(root).as_posix()
    record: dict[str, Any] = {
        "id": f"{_slug(bank_id)}-file-"
        + hashlib.sha256(relative.encode()).hexdigest()[:16],
        "relative_path": relative,
        "sha256": digest.hexdigest(),
        "pcm_sha256": pcm_digest,
        "pcm_hash_encoding": "signed-int32-left-aligned-little-endian",
        "frames": frames,
        "sample_rate": sample_rate,
        "channels": channels,
        "original_bit_depth": bit_depth,
        "decoded_bytes": frames * channels * 4,
    }
    if embedded_root_key is not None:
        record["embedded_root_key"] = embedded_root_key
    if embedded_loops:
        record["embedded_loops"] = embedded_loops
    return record


def _wav_sampler_metadata(
    path: Path,
    frame_count: int,
) -> tuple[int | None, list[dict[str, int | str]]]:
    """Read standard RIFF `smpl` metadata without trusting it as playback policy."""

    with path.open("rb") as source:
        header = source.read(12)
        if len(header) != 12 or header[:4] not in (b"RIFF", b"RIFX"):
            return None, []
        byte_order = "<" if header[:4] == b"RIFF" else ">"
        while chunk_header := source.read(8):
            if len(chunk_header) != 8:
                raise ValueError(f"{path}: truncated RIFF chunk header")
            chunk_id = chunk_header[:4]
            chunk_size = struct.unpack(f"{byte_order}I", chunk_header[4:])[0]
            if chunk_id != b"smpl":
                source.seek(chunk_size + (chunk_size & 1), 1)
                continue
            payload = source.read(chunk_size)
            if len(payload) != chunk_size or chunk_size < 36:
                raise ValueError(f"{path}: truncated RIFF smpl chunk")
            unity_note = struct.unpack_from(f"{byte_order}I", payload, 12)[0]
            loop_count = struct.unpack_from(f"{byte_order}I", payload, 28)[0]
            required = 36 + loop_count * 24
            if required > len(payload):
                raise ValueError(f"{path}: RIFF smpl loop table is truncated")
            loops: list[dict[str, int | str]] = []
            loop_modes = {0: "forward", 1: "alternating", 2: "backward"}
            for index in range(loop_count):
                offset = 36 + index * 24
                _cue, loop_type, start, inclusive_end, fraction, play_count = (
                    struct.unpack_from(f"{byte_order}6I", payload, offset)
                )
                end_exclusive = inclusive_end + 1
                if start >= end_exclusive or end_exclusive > frame_count:
                    raise ValueError(
                        f"{path}: embedded loop {index} lies outside audio frames"
                    )
                whole_file = start == 0 and end_exclusive == frame_count
                loops.append(
                    {
                        "mode": loop_modes.get(loop_type, f"unknown-{loop_type}"),
                        "start_frame": start,
                        "end_frame_exclusive": end_exclusive,
                        "fraction": fraction,
                        "play_count": play_count,
                        "playback_disposition": (
                            "ignored-whole-file-loop"
                            if whole_file
                            else "requires-reviewed-loop-policy"
                        ),
                    }
                )
            return (int(unity_note) if unity_note <= 127 else None), loops
    return None, []


def _region_record(
    root: Path,
    source: _SourceRegion,
    program_id: str,
    ordinal: int,
    file_id: str,
) -> dict[str, Any]:
    values = source.values
    trigger = values.get("trigger", "attack").casefold()
    if trigger not in ("attack", "release", "release_key"):
        raise ValueError(
            f"{source.source}:{source.line}: unsupported trigger mode {trigger}"
        )
    key_center = _midi_note(
        values.get("pitch_keycenter", values.get("key")), 60
    )
    key_lo = _midi_note(values.get("lokey", values.get("key")), key_center)
    key_hi = _midi_note(values.get("hikey", values.get("key")), key_center)
    articulation = values.get("sw_label", "default")
    return {
        "id": f"{program_id}.region-{ordinal}",
        "program_id": program_id,
        "articulation_id": _slug(articulation) or "default",
        "sample_id": file_id,
        "key_lo": key_lo,
        "key_hi": key_hi,
        "key_center": key_center,
        "tune_cents": _number(values.get("tune"), 0.0),
        "pitch_keytrack": 100,
        "velocity_lo": int(_number(values.get("lovel"), 0)),
        "velocity_hi": int(_number(values.get("hivel"), 127)),
        "gain_db": _number(values.get("volume"), 0.0),
        "trigger": trigger,
        "rr_group": values.get("group_label"),
        "rr_position": (
            int(values["seq_position"]) if "seq_position" in values else None
        ),
        "rr_length": int(values["seq_length"]) if "seq_length" in values else None,
        "random_lo": _number(values.get("lorand"), 0.0),
        "random_hi": _number(values.get("hirand"), 1.0),
        "envelope": {
            "attack_sec": _number(values.get("ampeg_attack"), 0.001),
            "release_sec": _number(values.get("ampeg_release"), 0.2),
            "dynamic": int(_number(values.get("ampeg_dynamic"), 0)),
        },
        "key_conditions": {
            "switch_lo": _midi_note(values.get("sw_lokey"), 0)
            if "sw_lokey" in values
            else None,
            "switch_hi": _midi_note(values.get("sw_hikey"), 127)
            if "sw_hikey" in values
            else None,
            "switch_last": _midi_note(values.get("sw_last"), -1)
            if "sw_last" in values
            else None,
        },
        "loop": {"mode": "none"},
        "provenance": {
            "source_file": source.source.name,
            "line": source.line,
        },
    }


def compile_vsco_manifest(root: Path) -> dict[str, Any]:
    root = root.resolve()
    sfz_files = sorted(root.glob("*.sfz"))
    if len(sfz_files) != 75:
        raise ValueError(f"expected 75 VSCO SFZ mappings, found {len(sfz_files)}")
    parsed = {path: parse_sfz(path) for path in sfz_files}
    referenced = {
        _relative_sample(root, region)
        for regions in parsed.values()
        for region in regions
    }
    all_audio = {
        path.resolve()
        for path in root.rglob("*")
        if path.is_file() and path.suffix.casefold() in (".wav", ".aif", ".aiff")
    }
    file_records = [_audio_record(root, path) for path in sorted(all_audio)]
    file_ids = {root / record["relative_path"]: record["id"] for record in file_records}
    programs: list[dict[str, Any]] = []
    regions: list[dict[str, Any]] = []
    for sfz_path, source_regions in parsed.items():
        program_id = "sample.vsco." + _slug(sfz_path.stem)
        first = source_regions[0].values
        program_regions = []
        for ordinal, source_region in enumerate(source_regions):
            sample_path = _relative_sample(root, source_region)
            record = _region_record(
                root,
                source_region,
                program_id,
                ordinal,
                file_ids[sample_path],
            )
            regions.append(record)
            program_regions.append(record["id"])
        default_switch = first.get("sw_default")
        default_articulation = next(
            (
                _slug(region.values.get("sw_label", "default")) or "default"
                for region in source_regions
                if default_switch is not None
                and region.values.get("sw_last") == default_switch
            ),
            "default",
        )
        programs.append(
            {
                "id": program_id,
                "display_name": sfz_path.stem.replace("-KS", ""),
                "source_mapping": sfz_path.name,
                "source_sha256": hashlib.sha256(sfz_path.read_bytes()).hexdigest(),
                "default_articulation": default_articulation,
                "articulations": sorted(
                    {
                        _slug(region.values.get("sw_label", "default")) or "default"
                        for region in source_regions
                    }
                ),
                "region_ids": program_regions,
            }
        )
    coverage = [
        {
            "sample_id": record["id"],
            "disposition": (
                "mapped-region"
                if (root / record["relative_path"]).resolve() in referenced
                else "unmapped-source-audio"
            ),
        }
        for record in file_records
    ]
    return {
        "schema_revision": 1,
        "compiler_version": COMPILER_VERSION,
        "bank": {
            "id": "vsco-2-ce",
            "source_pin": VSCO_SOURCE_PIN,
            "source_verification": "expected-pin; local extracted tree inventoried by hashes",
            "license": "CC0-1.0",
            "source_audio_count": len(all_audio),
            "mapping_count": len(sfz_files),
        },
        "files": file_records,
        "programs": programs,
        "regions": regions,
        "coverage": coverage,
    }


def write_manifest(manifest: dict[str, Any], output: Path) -> None:
    output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
