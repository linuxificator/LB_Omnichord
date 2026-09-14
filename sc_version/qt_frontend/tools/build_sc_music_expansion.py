#!/usr/bin/env python3
"""Compile the reviewed SC music-expansion bundle into runtime authorities.

The source bundle is deliberately verbose evidence.  Runtime code must not
depend on filesystem ordering or parse hundreds of megabytes at startup, so
this tool emits compact, deterministic JSON catalogues with shared event
sequences.  It is a build-time importer; the application never invokes it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SOURCE_FILES = (
    "pcm_drumkits.json",
    "pcm_sample_sets.json",
    "drum_arrangements.json",
    "drum_fill_variants.json",
    "bass_riffs_revised.json",
    "bass_voice_capabilities.json",
    "preset_index.json",
    "sc_drumkit_profiles.json",
)
PRESET_FILES = tuple(f"default_presets/p{index}.json" for index in range(1, 19))
PROGRAM_CANONICALIZATION = {
    "sample.vsco.contrabasssusnv": "sample.vsco.contrabass-ks",
    "sample.vsco.contrabasspizz": "sample.vsco.contrabass-ks.art.e6-pizzicato",
    "sample.vsco.flutesusnv": "sample.vsco.flute-ks",
}


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
    )


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _compact_kit_catalogue(data: Path) -> dict[str, Any]:
    kits = _read(data / "pcm_drumkits.json")
    sample_sets = _read(data / "pcm_sample_sets.json")
    return {
        "schema_version": 1,
        "source_commit": kits["source_commit"],
        "sample_repository": sample_sets["repository"],
        "sample_commit": sample_sets["commit"],
        "sample_sets": [
            {
                "sample_set_id": item["sample_set_id"],
                "layers": item["layers"],
            }
            for item in sample_sets["sample_sets"]
        ],
        "kits": [
            {
                "kit_id": item["kit_id"],
                "label": item["label"],
                "program_id": item["program_id"],
                "profile": item["profile"],
                "kit_gain_db": item["kit_gain_db"],
                "pads": item["pads"],
                "role_defaults": item["role_defaults"],
            }
            for item in kits["kits"]
        ],
    }


class _EventPool:
    def __init__(self, roles: list[str], slots: list[str]) -> None:
        self.roles = roles
        self.slots = slots
        self._role_index = {value: index for index, value in enumerate(roles)}
        self._slot_index = {value: index for index, value in enumerate(slots)}
        self.sequences: list[list[list[int]]] = []
        self._indexes: dict[tuple[tuple[int, int, int, int], ...], int] = {}

    def add(self, events: list[dict[str, Any]]) -> int:
        compact = tuple(
            (
                int(event["tick"]),
                self._role_index[str(event["role"])],
                int(event["velocity"]),
                self._slot_index[str(event["slot"])],
            )
            for event in events
        )
        existing = self._indexes.get(compact)
        if existing is not None:
            return existing
        index = len(self.sequences)
        self._indexes[compact] = index
        self.sequences.append([list(event) for event in compact])
        return index


def _compact_grooves(data: Path) -> dict[str, Any]:
    arrangements = _read(data / "drum_arrangements.json")
    fills = _read(data / "drum_fill_variants.json")
    all_events: list[dict[str, Any]] = []
    for arrangement in arrangements["arrangements"]:
        for level in arrangement["levels"]:
            all_events.extend(level["events"])
    for fill in fills["variants"]:
        all_events.extend(fill["events"])
    roles = sorted({str(event["role"]) for event in all_events})
    slots = sorted({str(event["slot"]) for event in all_events})
    pool = _EventPool(roles, slots)

    compact_arrangements = []
    arrangement_keys: set[tuple[str, str]] = set()
    for item in arrangements["arrangements"]:
        key = (str(item["kit_id"]), str(item["rhythm_id"]))
        if key in arrangement_keys:
            raise ValueError(f"duplicate arrangement {key}")
        arrangement_keys.add(key)
        compact_arrangements.append(
            {
                "kit_id": key[0],
                "rhythm_id": key[1],
                "meter": item["meter"],
                "period_ticks": int(item["period_ticks"]),
                "levels": [pool.add(level["events"]) for level in item["levels"]],
            }
        )

    compact_fills = []
    fill_keys: set[tuple[str, str, int]] = set()
    for item in fills["variants"]:
        key = (
            str(item["kit_id"]),
            str(item["rhythm_id"]),
            int(item["slot_level"]),
        )
        if key in fill_keys:
            raise ValueError(f"duplicate fill variant {key}")
        fill_keys.add(key)
        performance = item["performance"]
        continuation_keys = sorted(
            {
                (str(part["role"]), str(part["slot"]))
                for part in performance["continuation_parts"]
            }
        )
        compact_fills.append(
            {
                "variant_id": item["variant_id"],
                "base_fill_id": item["base_fill_id"],
                "kit_id": key[0],
                "rhythm_id": key[1],
                "slot_level": key[2],
                "duration_ticks": int(item["duration_ticks"]),
                "allowed_start_beats": item["allowed_start_beats"],
                "sequence": pool.add(item["events"]),
                "gain": float(item["gain"]),
                "continuation_keys": [list(value) for value in continuation_keys],
            }
        )

    expected = {
        (item["kit_id"], item["rhythm_id"]) for item in compact_arrangements
    }
    by_fill = {(item["kit_id"], item["rhythm_id"]) for item in compact_fills}
    if expected != by_fill:
        raise ValueError("arrangement and fill kit/rhythm coverage differ")
    if any(len(item["levels"]) != 5 for item in compact_arrangements):
        raise ValueError("every arrangement must contain five activity levels")
    if len(compact_fills) != len(expected) * 5:
        raise ValueError("every kit/rhythm must contain five fill variants")

    return {
        "schema_version": 1,
        "ppq": int(arrangements["ppq"]),
        "roles": roles,
        "slots": slots,
        "event_sequences": pool.sequences,
        "arrangements": compact_arrangements,
        "fills": compact_fills,
    }


def _compact_bass(data: Path) -> dict[str, Any]:
    source = _read(data / "bass_riffs_revised.json")
    keep_top = (
        "schema_version",
        "extension_version",
        "scale_vocabulary",
        "rhythm_types",
        "chord_types",
    )
    result = {key: source[key] for key in keep_top}
    result["riffs"] = []
    for riff in source["riffs"]:
        result["riffs"].append(
            {
                key: riff[key]
                for key in (
                    "index",
                    "riff_id",
                    "name",
                    "normalized_root",
                    "normalized_anchor_midi",
                    "compatible_scales",
                    "compatible_chords",
                    "compatible_rhythms",
                    "activity_rank",
                    "selection_weight",
                    "timing",
                )
            }
        )
    return result


def _canonical_program(program_id: object) -> str:
    value = str(program_id)
    return PROGRAM_CANONICALIZATION.get(value, value)


def _compact_preset_index(data: Path) -> dict[str, Any]:
    source = _read(data / "preset_index.json")
    for row in source["presets"]:
        for role in ("chord", "strum", "bass"):
            row[role] = _canonical_program(row[role])
    return source


def _canonical_preset(data: Path) -> dict[str, Any]:
    snapshot = _read(data)
    synths = snapshot["synths"]
    for role in ("chord", "strum", "bass"):
        synths[role]["selected"] = _canonical_program(synths[role]["selected"])
    return snapshot


def build(
    bundle: Path,
    destination: Path,
    preset_destination: Path | None = None,
) -> None:
    data = bundle / "data"
    source_names = (*SOURCE_FILES, *PRESET_FILES)
    missing = [name for name in source_names if not (data / name).is_file()]
    if missing:
        raise FileNotFoundError(f"music bundle is missing {', '.join(missing)}")
    outputs = {
        "sc_pcm_drumkits_v1.json": _compact_kit_catalogue(data),
        "sc_kit_grooves_v1.json": _compact_grooves(data),
        "omnichord_bass_riffs_v2.json": _compact_bass(data),
        "bass_voice_capabilities_v1.json": _read(data / "bass_voice_capabilities.json"),
        "sc_factory_presets_v1.json": _compact_preset_index(data),
        "sc_native_drumkits_v1.json": _read(data / "sc_drumkit_profiles.json"),
    }
    for name, value in outputs.items():
        _write(destination / name, value)
    if preset_destination is None:
        preset_destination = destination.parents[1] / "instruments" / "default_presets"
    preset_outputs: dict[str, str] = {}
    for relative_name in PRESET_FILES:
        source = data / relative_name
        output = preset_destination / Path(relative_name).name
        _write(output, _canonical_preset(source))
        preset_outputs[output.name] = _digest(output)
    manifest = {
        "schema_version": 1,
        "source_bundle": "LB_SC_Music_Expansion",
        "sources": {name: _digest(data / name) for name in source_names},
        "outputs": {name: _digest(destination / name) for name in sorted(outputs)},
        "preset_outputs": preset_outputs,
    }
    _write(destination / "manifest.json", manifest)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--preset-destination", type=Path)
    args = parser.parse_args()
    build(
        args.bundle.resolve(),
        args.destination.resolve(),
        None if args.preset_destination is None else args.preset_destination.resolve(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
