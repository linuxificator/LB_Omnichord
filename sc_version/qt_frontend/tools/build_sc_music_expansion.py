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
    "bass_contexts.json",
    "bass_voice_capabilities.json",
    "preset_index.json",
    "sc_drumkit_profiles.json",
)
PRESET_FILES = tuple(f"default_presets/p{index}.json" for index in range(1, 19))
DEFAULT_REQUIRED_SAMPLES = (
    Path(__file__).resolve().parents[2] / "supercollider" / "required-samples.json"
)
PROGRAM_CANONICALIZATION = {
    "sample.vsco.contrabasssusnv": "sample.vsco.contrabass-ks",
    "sample.vsco.contrabasspizz": "sample.vsco.contrabass-ks.art.e6-pizzicato",
    "sample.vsco.flutesusnv": "sample.vsco.flute-ks",
    # The 50-mode source keeps every strummed voice alive for about 5.5 s and
    # can exceed the realtime DSP budget under an ordinary continuous sweep.
    # Preserve the source bundle as evidence, but compile factory snapshots to
    # the already-qualified lightweight guitar voice.
    "sc.sclork.modalElectricGuitar": "sc.sclork.pluck",
}
RHYTHM_FAMILIES = {
    rhythm_id: family
    for family, rhythm_ids in {
        "pop": ("pop_8", "pop_16", "slow_ballad", "rock", "punk", "metal", "straight_blues", "rnb", "soul"),
        "swing": ("shuffle", "twelve_eight_blues", "jazz_shuffle", "soul_shuffle", "six_eight_ballad", "gospel_6_8"),
        "jazz": ("jazz_swing", "jazz_waltz"),
        "funk": ("funk", "jazz_funk", "seven_four_funk"),
        "country": ("country_train", "country_waltz", "waltz"),
        "march": ("polka", "march"),
        "four_floor": ("disco", "house", "techno", "trance"),
        "breaks": ("garage_2step", "breakbeat", "drum_and_bass", "dubstep", "hip_hop", "boom_bap", "trap"),
        "latin": ("bossa", "samba", "salsa", "cha_cha", "mambo", "merengue", "cumbia", "bolero", "tango", "son_clave_3_2", "rumba_clave_3_2", "afro_cuban_6_8", "calypso_soca"),
        "reggae": ("reggae",),
        "odd": ("five_four", "seven_eight", "nine_eight", "eleven_eight"),
    }.items()
    for rhythm_id in rhythm_ids
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


def _write_pretty(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _compact_kit_catalogue(
    bundle: Path,
    runtime_samples: dict[str, Any],
) -> dict[str, Any]:
    data = bundle / "data"
    kits = _read(data / "pcm_drumkits.json")
    sample_sets = _read(data / "pcm_sample_sets.json")
    measurements = _read(bundle / "evidence" / "sample_measurements.json")
    measured = {str(row["sample_id"]): row for row in measurements["samples"]}
    selected = {
        str(sample_id)
        for sample_set in sample_sets["sample_sets"]
        for layer in sample_set["layers"]
        for sample_id in layer["round_robin_sample_ids"]
    }
    if set(measured) != selected:
        raise ValueError("PCM drum measurements do not match selected samples")
    runtime_repository = str(runtime_samples.get("repository", "")).removesuffix(
        ".git"
    )
    source_repository = str(sample_sets.get("repository", "")).removesuffix(".git")
    if runtime_repository.casefold() != source_repository.casefold():
        raise ValueError("runtime and source sample repositories do not match")

    def alias(sample_id: object) -> str:
        return f"sc-drum-{sample_id}"

    return {
        "schema_version": 1,
        "source_commit": kits["source_commit"],
        "sample_repository": sample_sets["repository"],
        "sample_commit": runtime_samples["commit"],
        "sample_files": [
            {
                "id": alias(sample_id),
                "source_sample_id": sample_id,
                "relative_path": row["relative_path"],
                "sha256": row["sha256"],
                "sample_rate": int(row["sample_rate"]),
                "channels": int(row["channels"]),
                "frames": int(row["frames"]) - int(row["suggested_start_frame"]),
                "start_frame": int(row["suggested_start_frame"]),
                "decoded_bytes": (
                    int(row["frames"]) - int(row["suggested_start_frame"])
                )
                * int(row["channels"])
                * 4,
            }
            for sample_id, row in sorted(measured.items())
        ],
        "sample_sets": [
            {
                "sample_set_id": item["sample_set_id"],
                "layers": [
                    {
                        **layer,
                        "round_robin_sample_ids": [
                            alias(sample_id)
                            for sample_id in layer["round_robin_sample_ids"]
                        ],
                    }
                    for layer in item["layers"]
                ],
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
                "kit_calibration": item["kit_calibration"],
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
        self.semantic_role_sets: list[list[int]] = []
        self._semantic_indexes: dict[tuple[int, ...], int] = {}
        self.sequences: list[list[list[int]]] = []
        self._indexes: dict[tuple[tuple[int, int, int, int, int, int], ...], int] = {}

    def _semantic_index(self, event: dict[str, Any]) -> int:
        roles = tuple(
            sorted(
                {
                    self._role_index[str(value)]
                    for value in event.get("roles", (event["role"],))
                }
            )
        )
        existing = self._semantic_indexes.get(roles)
        if existing is not None:
            return existing
        index = len(self.semantic_role_sets)
        self._semantic_indexes[roles] = index
        self.semantic_role_sets.append(list(roles))
        return index

    def add(self, events: list[dict[str, Any]]) -> int:
        compact = tuple(
            (
                int(event["tick"]),
                self._role_index[str(event["role"])],
                int(event["velocity"]),
                self._slot_index[str(event["slot"])],
                self._semantic_index(event),
                int(event.get("max_duration_ms", 0)),
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
        for level in fill["performance"]["continuation_by_activity"]:
            all_events.extend(level["events"])
    roles = sorted(
        {
            str(role)
            for event in all_events
            for role in event.get("roles", (event["role"],))
        }
    )
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
                "continuation_levels": [
                    pool.add(level["events"])
                    for level in performance["continuation_by_activity"]
                ],
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
        "semantic_role_sets": pool.semantic_role_sets,
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
        timing = dict(riff["source_timing"])
        timing["events"] = [
            {
                **event,
                "link_to_next": "none",
                "gate_policy": "authored_detached",
                "accent_amount": 0.65 if bool(event["accent"]) else 0.0,
            }
            for event in timing["events"]
        ]
        result["riffs"].append(
            {
                **{
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
                    )
                },
                "timing": timing,
            }
        )
    return result


def _compact_bass_contexts(data: Path) -> dict[str, Any]:
    source = _read(data / "bass_contexts.json")
    examples = {
        str(row["context_id"]): row for row in source["resolved_examples"]
    }
    contexts = []
    seen: set[tuple[str, str]] = set()
    for row in source["contexts"]:
        key = (str(row["kit_id"]), str(row["rhythm_id"]))
        if key in seen:
            raise ValueError(f"duplicate bass context {key!r}")
        seen.add(key)
        try:
            family = RHYTHM_FAMILIES[key[1]]
        except KeyError as exc:
            raise ValueError(f"unknown bass rhythm family for {key[1]!r}") from exc
        contexts.append(
            {
                "kit_id": key[0],
                "rhythm_id": key[1],
                "profile": str(row["profile"]),
                "family": family,
                "reference": {
                    "riff_id": str(examples[str(row["context_id"])]["riff_id"]),
                    "percussion_activity": int(
                        examples[str(row["context_id"])]["percussion_activity"]
                    ),
                    "events_sha256": hashlib.sha256(
                        json.dumps(
                            [
                                _bass_event_projection(event)
                                for event in examples[str(row["context_id"])]["events"]
                            ],
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8")
                    ).hexdigest(),
                },
            }
        )
    if len(contexts) != 810:
        raise ValueError(f"expected 810 bass contexts, got {len(contexts)}")
    return {"schema_version": 1, "contexts": contexts}


def _bass_event_projection(event: dict[str, Any]) -> dict[str, Any]:
    fallback = event.get("fallback")
    return {
        "tick": int(event["tick"]),
        "duration_ticks": int(event["duration_ticks"]),
        "pitch_offset": int(event["pitch_offset_semitones_from_C2"]),
        "role": str(event["role"]),
        "velocity": int(event["velocity"]),
        "accent": bool(event["accent"]),
        "slide_to_next": bool(event["slide_to_next"]),
        "link_to_next": str(event["link_to_next"]),
        "accent_amount": float(event["accent_amount"]),
        "gate_policy": str(event["gate_policy"]),
        "glide_time_ms": float(event.get("glide_time_ms", 0.0)),
        "fallback_duration_ticks": int(
            fallback.get("duration_ticks", event["duration_ticks"])
            if isinstance(fallback, dict)
            else event["duration_ticks"]
        ),
        "link_target_index": int(event.get("link_target_index", -1)),
        "link_target_cycle_offset": int(event.get("link_target_cycle_offset", 0)),
    }


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
    required_samples: Path = DEFAULT_REQUIRED_SAMPLES,
) -> None:
    data = bundle / "data"
    evidence = bundle / "evidence"
    source_names = (*SOURCE_FILES, *PRESET_FILES)
    missing = [name for name in source_names if not (data / name).is_file()]
    if missing:
        raise FileNotFoundError(f"music bundle is missing {', '.join(missing)}")
    runtime_samples = _read(required_samples)
    outputs = {
        "sc_pcm_drumkits_v1.json": _compact_kit_catalogue(
            bundle, runtime_samples
        ),
        "sc_kit_grooves_v1.json": _compact_grooves(data),
        "omnichord_bass_riffs_v2.json": _compact_bass(data),
        "sc_bass_contexts_v1.json": _compact_bass_contexts(data),
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
        _write_pretty(output, _canonical_preset(source))
        preset_outputs[output.name] = _digest(output)
    validation = _read(evidence / "validation_report.json")
    if validation.get("status") != "PASS":
        raise ValueError("music expansion validation report does not pass")
    manifest = {
        "schema_version": 1,
        "source_bundle": "LB_SC_Music_Expansion",
        "runtime_sample_selection": _digest(required_samples),
        "sources": {name: _digest(data / name) for name in source_names},
        "evidence_sources": {
            "sample_measurements.json": _digest(
                evidence / "sample_measurements.json"
            ),
            "validation_report.json": _digest(evidence / "validation_report.json"),
        },
        "validation_summary": {
            "status": validation["status"],
            "counts": validation["counts"],
            "max_groove_pad_events": validation["max_groove_pad_events"],
            "max_fill_foreground_events": validation["max_fill_foreground_events"],
            "max_combined_fill_window_pad_events_all_levels": validation[
                "max_combined_fill_window_pad_events_all_levels"
            ],
            "explicit_right_foot_fill_exceptions": validation[
                "explicit_right_foot_fill_exceptions"
            ],
        },
        "outputs": {name: _digest(destination / name) for name in sorted(outputs)},
        "preset_outputs": preset_outputs,
    }
    _write(destination / "manifest.json", manifest)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--preset-destination", type=Path)
    parser.add_argument(
        "--required-samples",
        type=Path,
        default=DEFAULT_REQUIRED_SAMPLES,
    )
    args = parser.parse_args()
    build(
        args.bundle.resolve(),
        args.destination.resolve(),
        None if args.preset_destination is None else args.preset_destination.resolve(),
        args.required_samples.resolve(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
