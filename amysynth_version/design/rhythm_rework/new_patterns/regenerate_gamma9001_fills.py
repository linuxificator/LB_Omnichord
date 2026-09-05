#!/usr/bin/env python3
"""Regenerate the canonical drum fills against the Gamma9001-first activity catalogue.

Temporary integration utility for feature/gamma9001-drum-pattern-refresh.
The runtime JSON remains canonical; remove this tool after generation, tests and commit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DRUMS = ROOT / "qt_frontend" / "music" / "drums"
ACTIVITY_PATH = DRUMS / "drum_activity_timing.json"
FILLS_PATH = DRUMS / "drum_fills_timing.json"
CONT_PATH = DRUMS / "drum_fill_continuation_roles.json"
MANIFEST_PATH = Path(__file__).resolve().parent / "canonical_drum_data_manifest.json"
PROVENANCE_PATH = ROOT / "qt_frontend" / "music" / "catalogue_provenance.json"
TEST_PATH = ROOT / "qt_frontend" / "tests" / "test_drum_patterns.py"
HANDOVER_PATH = Path(__file__).resolve().parent / "CODEX_HANDOVER_GAMMA9001_FILL_REFRESH.md"
PPQ = 96
MAX_FILL_EVENTS = 40

STYLE_GROUPS = {
    "pop": {
        "pop_8", "pop_16", "slow_ballad", "rock", "punk", "metal",
        "straight_blues", "rnb", "soul",
    },
    "swing": {
        "shuffle", "twelve_eight_blues", "jazz_shuffle", "soul_shuffle",
        "six_eight_ballad", "gospel_6_8",
    },
    "jazz": {"jazz_swing", "jazz_waltz"},
    "funk": {"funk", "jazz_funk", "seven_four_funk"},
    "country": {"country_train", "country_waltz", "waltz"},
    "march": {"polka", "march"},
    "electronic": {"disco", "house", "techno", "trance"},
    "breaks": {
        "garage_2step", "breakbeat", "drum_and_bass", "dubstep",
        "hip_hop", "boom_bap", "trap",
    },
    "latin": {
        "bossa", "samba", "salsa", "cha_cha", "mambo", "merengue",
        "cumbia", "bolero", "tango", "son_clave_3_2",
        "rumba_clave_3_2", "afro_cuban_6_8", "calypso_soca",
    },
    "reggae": {"reggae"},
    "odd": {"five_four", "seven_eight", "nine_eight", "eleven_eight"},
}

GROUPINGS = {
    "five_four": (3, 2),
    "seven_eight": (2, 2, 3),
    "seven_four_funk": (4, 3),
    "nine_eight": (2, 2, 2, 3),
    "eleven_eight": (3, 3, 3, 2),
}

ROLE_CYCLES = {
    "pop": (
        ("backbeat_primary", "tonal_high", "tonal_mid", "tonal_low"),
        ("backbeat_primary", "tonal_high", "tonal_mid", "tonal_low", "low_secondary"),
        ("backbeat_primary", "ghost_detail", "tonal_high", "tonal_mid", "tonal_low", "low_secondary"),
        ("backbeat_primary", "low_secondary", "tonal_high", "low_secondary", "tonal_mid", "low_secondary"),
        ("backbeat_primary", "ghost_detail", "tonal_high", "tonal_mid", "tonal_low", "low_secondary"),
    ),
    "swing": (
        ("backbeat_soft", "tonal_high", "tonal_mid"),
        ("backbeat_soft", "tonal_high", "tonal_mid", "tonal_low"),
        ("backbeat_soft", "ghost_detail", "tonal_high", "tonal_mid", "tonal_low"),
        ("backbeat_primary", "tonal_high", "low_secondary", "tonal_mid", "low_secondary", "tonal_low"),
        ("backbeat_soft", "ghost_detail", "tonal_high", "tonal_mid", "tonal_low", "low_secondary"),
    ),
    "jazz": (
        ("backbeat_soft", "tonal_high", "tonal_mid"),
        ("backbeat_soft", "ghost_detail", "tonal_high", "tonal_mid"),
        ("backbeat_soft", "ghost_detail", "tonal_high", "tonal_mid", "tonal_low"),
        ("backbeat_primary", "tonal_high", "tonal_mid", "low_secondary", "tonal_low", "low_secondary"),
        ("backbeat_soft", "ghost_detail", "tonal_high", "tonal_mid", "tonal_low", "low_secondary"),
    ),
    "funk": (
        ("ghost_detail", "backbeat_primary", "low_secondary", "ghost_detail"),
        ("ghost_detail", "low_secondary", "backbeat_primary", "tonal_high", "ghost_detail"),
        ("low_secondary", "ghost_detail", "backbeat_primary", "tonal_high", "tonal_mid", "tonal_low"),
        ("ghost_detail", "low_secondary", "backbeat_primary", "low_secondary", "ghost_detail", "tonal_high"),
        ("low_secondary", "ghost_detail", "backbeat_primary", "tonal_high", "tonal_mid", "tonal_low", "ghost_detail"),
    ),
    "country": (
        ("backbeat_soft", "tonal_high", "tonal_mid"),
        ("backbeat_soft", "tonal_high", "tonal_mid", "tonal_low"),
        ("backbeat_soft", "backbeat_primary", "tonal_high", "tonal_mid", "tonal_low"),
        ("backbeat_primary", "tonal_high", "low_secondary", "tonal_mid", "low_secondary", "tonal_low"),
        ("backbeat_soft", "backbeat_primary", "tonal_high", "tonal_mid", "tonal_low", "low_secondary"),
    ),
    "march": (
        ("backbeat_primary", "ghost_detail", "backbeat_primary", "ghost_detail"),
        ("backbeat_primary", "ghost_detail", "tonal_high", "ghost_detail", "tonal_mid"),
        ("backbeat_primary", "ghost_detail", "backbeat_primary", "tonal_high", "tonal_mid", "tonal_low"),
        ("backbeat_primary", "ghost_detail", "backbeat_primary", "ghost_detail", "tonal_high", "tonal_mid"),
        ("backbeat_primary", "ghost_detail", "tonal_high", "tonal_mid", "tonal_low", "low_secondary"),
    ),
    "electronic": (
        ("backbeat_primary", "electronic_detail", "backbeat_primary", "electronic_detail"),
        ("backbeat_primary", "electronic_detail", "tonal_high", "electronic_detail", "tonal_mid"),
        ("backbeat_primary", "electronic_detail", "tonal_high", "tonal_mid", "tonal_low"),
        ("electronic_detail", "backbeat_primary", "electronic_detail", "backbeat_primary"),
        ("backbeat_primary", "electronic_detail", "tonal_high", "tonal_mid", "tonal_low", "timekeeper_open"),
    ),
    "breaks": (
        ("backbeat_primary", "ghost_detail", "low_secondary", "ghost_detail"),
        ("low_secondary", "ghost_detail", "backbeat_primary", "electronic_detail", "ghost_detail"),
        ("low_secondary", "backbeat_primary", "ghost_detail", "tonal_high", "tonal_mid", "tonal_low"),
        ("electronic_detail", "ghost_detail", "backbeat_primary", "low_secondary"),
        ("low_secondary", "ghost_detail", "backbeat_primary", "electronic_detail", "tonal_high", "tonal_mid", "tonal_low"),
    ),
    "latin": (
        ("hand_high", "hand_low", "tonal_high", "hand_accent"),
        ("hand_high", "hand_low", "tonal_high", "tonal_mid", "hand_accent"),
        ("hand_low", "hand_high", "tonal_high", "tonal_mid", "tonal_low", "hand_accent"),
        ("tonal_high", "hand_high", "tonal_mid", "hand_low", "tonal_low", "hand_accent"),
        ("hand_low", "hand_high", "tonal_high", "tonal_mid", "tonal_low", "hand_accent"),
    ),
    "reggae": (
        ("dry_click", "backbeat_soft", "tonal_high"),
        ("dry_click", "tonal_high", "tonal_mid", "backbeat_soft"),
        ("dry_click", "backbeat_soft", "tonal_high", "tonal_mid", "tonal_low"),
        ("backbeat_soft", "low_secondary", "tonal_high", "tonal_mid"),
        ("dry_click", "backbeat_soft", "tonal_high", "tonal_mid", "tonal_low", "low_secondary"),
    ),
    "odd": (
        ("backbeat_primary", "tonal_high", "tonal_mid"),
        ("backbeat_primary", "tonal_high", "tonal_mid", "tonal_low"),
        ("low_secondary", "backbeat_primary", "tonal_high", "tonal_mid", "tonal_low"),
        ("backbeat_primary", "low_secondary", "tonal_high", "tonal_mid", "tonal_low"),
        ("low_secondary", "backbeat_primary", "tonal_high", "tonal_mid", "tonal_low", "ghost_detail"),
    ),
}

ANCHOR_ROLES = {
    "pop": {"low_primary", "backbeat_primary"},
    "swing": {"low_primary", "backbeat_primary", "backbeat_soft"},
    "jazz": {"backbeat_soft", "low_secondary"},
    "funk": {"low_primary", "backbeat_primary", "ghost_detail"},
    "country": {"low_primary", "backbeat_soft", "backbeat_primary"},
    "march": {"low_primary", "backbeat_primary", "ghost_detail"},
    "electronic": {"backbeat_primary", "timekeeper_open"},
    "breaks": {"low_primary", "low_secondary", "backbeat_primary", "ghost_detail"},
    "latin": {"hand_high", "hand_low", "hand_accent", "tonal_high", "tonal_mid", "tonal_low"},
    "reggae": {"backbeat_soft", "dry_click", "low_primary"},
    "odd": {"low_primary", "backbeat_primary"},
}

ROLE_BASE_VELOCITY = {
    "low_primary": 106,
    "low_secondary": 98,
    "backbeat_primary": 108,
    "backbeat_soft": 82,
    "ghost_detail": 62,
    "timekeeper_primary": 78,
    "timekeeper_open": 92,
    "timekeeper_foot": 72,
    "sustain_primary": 88,
    "sustain_bell": 96,
    "section_accent": 112,
    "tonal_high": 96,
    "tonal_mid": 98,
    "tonal_low": 102,
    "timeline_primary": 90,
    "texture_shaker": 72,
    "hand_high": 92,
    "hand_low": 98,
    "hand_accent": 104,
    "dry_click": 82,
    "electronic_detail": 78,
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def style_map(rhythm_ids: set[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for style, ids in STYLE_GROUPS.items():
        for rhythm_id in ids:
            if rhythm_id in result:
                raise SystemExit(f"duplicate style assignment for {rhythm_id}")
            result[rhythm_id] = style
    missing = rhythm_ids - set(result)
    extra = set(result) - rhythm_ids
    if missing or extra:
        raise SystemExit(f"style coverage mismatch; missing={sorted(missing)} extra={sorted(extra)}")
    return result


def meter_parts(rhythm: dict) -> tuple[int, int, int]:
    numerator, denominator = (int(value) for value in str(rhythm["meter"]).split("/", 1))
    beat_ticks = PPQ * 4 // denominator
    return numerator, denominator, beat_ticks


def durations(rhythm_id: str, numerator: int, denominator: int) -> tuple[int, ...]:
    grouping = GROUPINGS.get(rhythm_id)
    if denominator == 8:
        if grouping:
            tail = grouping[-1]
            medium = min(numerator, sum(grouping[-2:])) if len(grouping) > 1 else tail
        else:
            tail = 3 if numerator >= 6 else max(1, numerator // 2)
            medium = min(numerator, tail * 2)
        return (tail, medium, numerator, tail, numerator)
    tail = 1
    medium = min(2, numerator)
    if grouping:
        medium = min(numerator, grouping[-1])
    return (tail, medium, numerator, medium, numerator)


def continuation(style: str, rhythm_id: str, variant: int, active_roles: set[str]) -> list[str]:
    if style == "electronic":
        candidates = {"low_primary", "timekeeper_primary"} if variant <= 2 else {"low_primary"}
    elif style == "latin":
        candidates = {"timeline_primary", "texture_shaker"}
        if rhythm_id in {"bossa", "samba", "cumbia", "calypso_soca"}:
            candidates.add("low_primary")
        if variant >= 4:
            candidates.discard("texture_shaker")
    elif style == "jazz":
        candidates = {"sustain_primary", "timekeeper_foot"} if variant <= 2 else {"timekeeper_foot"}
    elif style == "swing":
        candidates = {"timekeeper_primary"} if variant == 1 else set()
    elif style == "country":
        candidates = (
            {"timekeeper_primary", "dry_click"}
            if rhythm_id == "country_train" and variant == 1
            else ({"timekeeper_primary"} if variant == 1 else set())
        )
    elif style == "reggae":
        candidates = {"timekeeper_primary"} if variant <= 2 else set()
    elif style in {"pop", "march", "odd"}:
        candidates = {"timekeeper_primary"} if variant == 1 else set()
    else:
        candidates = set()
    return sorted(candidates & active_roles)


def subdivisions(style: str, denominator: int, variant: int) -> int:
    if style in {"swing", "jazz"}:
        return 3 if denominator == 4 else 2
    if style in {"breaks", "electronic"} and variant == 4:
        return 8 if denominator == 4 else 4
    return 4 if denominator == 4 else 2


def add_event(merged: dict[tuple[int, str], dict], tick: int, role: str, velocity: int) -> None:
    velocity = max(1, min(127, int(velocity)))
    key = (int(tick), str(role))
    event = {"tick": int(tick), "role": str(role), "velocity": velocity}
    prior = merged.get(key)
    if prior is None or velocity > int(prior["velocity"]):
        merged[key] = event


def generate() -> None:
    activity = json.loads(ACTIVITY_PATH.read_text(encoding="utf-8"))
    old_fills = json.loads(FILLS_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    provenance = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))

    rhythms = activity["rhythms"]
    rhythm_ids = {str(item["id"]) for item in rhythms}
    if len(rhythms) != 54 or len(rhythm_ids) != 54:
        raise SystemExit("activity catalogue must contain 54 unique rhythms")
    if len(old_fills["fills"]) != 270:
        raise SystemExit("existing fill shell must contain 270 fills")
    style_for = style_map(rhythm_ids)

    old_by_index = {int(item["index"]): item for item in old_fills["fills"]}
    old_index = {
        str(key): [int(value) for value in values]
        for key, values in old_fills["rhythm_fill_index"].items()
    }
    if set(old_index) != rhythm_ids:
        raise SystemExit("fill/rhythm coverage differs from activity catalogue")

    generated_fills: list[dict] = []
    generated_continuation: list[dict] = []
    generated_index: dict[str, list[int]] = {}

    for rhythm in rhythms:
        rhythm_id = str(rhythm["id"])
        style = style_for[rhythm_id]
        numerator, denominator, beat_ticks = meter_parts(rhythm)
        bar_ticks = numerator * beat_ticks
        period_ticks = int(rhythm["period_ticks"])
        if period_ticks < bar_ticks:
            raise SystemExit(f"{rhythm_id}: period shorter than one bar")
        core_level = rhythm["levels"][2]["events"]
        active_roles = {
            str(event["role"])
            for level in rhythm["levels"]
            for event in level["events"]
        }
        duration_values = durations(rhythm_id, numerator, denominator)
        indexes = old_index[rhythm_id]
        if len(indexes) != 5:
            raise SystemExit(f"{rhythm_id}: expected five fill indexes")
        generated_index[rhythm_id] = indexes
        bar_start = period_ticks - bar_ticks

        for variant, (index, duration_beats) in enumerate(zip(indexes, duration_values), start=1):
            old = deepcopy(old_by_index[index])
            fill_id = str(old["fill_id"])
            duration_ticks = duration_beats * beat_ticks
            start_beat = numerator - duration_beats + 1
            window_start = bar_start + (start_beat - 1) * beat_ticks
            continue_roles = continuation(style, rhythm_id, variant, active_roles)
            continue_set = set(continue_roles)
            merged: dict[tuple[int, str], dict] = {}

            for event in core_level:
                tick = int(event["tick"])
                role = str(event["role"])
                if window_start <= tick < window_start + duration_ticks:
                    if role in ANCHOR_ROLES[style] and role not in continue_set:
                        add_event(
                            merged,
                            tick - window_start,
                            role,
                            round(int(event["velocity"]) * 0.88),
                        )

            subdiv = subdivisions(style, denominator, variant)
            step = beat_ticks // subdiv
            if step <= 0 or step % 2:
                raise SystemExit(f"{rhythm_id} f{variant}: subdivision not exact at AMY 48 PPQ")
            count = min(MAX_FILL_EVENTS - 4, max(3, duration_beats * subdiv))
            cycle = ROLE_CYCLES[style][variant - 1]
            for i in range(count):
                tick = i * step
                if tick >= duration_ticks:
                    break
                role = cycle[i % len(cycle)]
                base = ROLE_BASE_VELOCITY[role]
                ramp = 0 if count <= 1 else round(12 * i / (count - 1))
                accent = 7 if i == 0 or tick % beat_ticks == 0 else 0
                if variant == 1:
                    ramp //= 2
                velocity = base + ramp + accent
                if role == "ghost_detail":
                    velocity = min(76, velocity)
                add_event(merged, tick, role, velocity)

            final_step = max(2, step)
            final_tick = duration_ticks - final_step
            if variant in {3, 5}:
                closing_role = (
                    "hand_accent"
                    if style == "latin"
                    else "backbeat_soft"
                    if style in {"jazz", "reggae"}
                    else "backbeat_primary"
                )
                add_event(merged, final_tick, closing_role, 116 if style != "jazz" else 94)
            if variant == 5 and style not in {"jazz", "latin", "reggae"}:
                add_event(merged, max(0, final_tick - final_step), "tonal_low", 112)

            events = sorted(
                merged.values(),
                key=lambda event: (int(event["tick"]), str(event["role"])),
            )
            if not events or len(events) > MAX_FILL_EVENTS:
                raise SystemExit(f"{fill_id}: invalid generated event count {len(events)}")
            if any(int(event["tick"]) % 2 or int(event["tick"]) >= duration_ticks for event in events):
                raise SystemExit(f"{fill_id}: generated invalid event tick")

            old["rhythm_id"] = rhythm_id
            old["meter"] = str(rhythm["meter"])
            old["allowed_start_beats"] = [start_beat]
            old["generation"] = {
                "activity_source_level": 3,
                "activity_window": "final matching window of current groove period",
                "style_family": style,
                "variant": variant,
                "gamma9001_quality_reference": True,
                "tiny_policy": "compatibility degradation only",
            }
            timing = deepcopy(old.get("timing", {}))
            timing["ppq"] = PPQ
            timing["duration_beats"] = duration_beats
            timing["duration_ticks"] = duration_ticks
            timing["leading_rest_ticks"] = 0
            timing["event_count"] = len(events)
            timing["events"] = events
            old["timing"] = timing
            generated_fills.append(old)
            generated_continuation.append(
                {"fill_id": fill_id, "continue_roles": continue_roles}
            )

    if len(generated_fills) != 270:
        raise SystemExit("generated fill count is not 270")
    if len({str(item["fill_id"]) for item in generated_fills}) != 270:
        raise SystemExit("generated fill ids are not unique")
    if len({int(item["index"]) for item in generated_fills}) != 270:
        raise SystemExit("generated fill indexes are not unique")

    fill_doc = deepcopy(old_fills)
    fill_doc["title"] = (
        "LB Omnichord Gamma9001-first kit-independent drum fills matched to refreshed activity grooves"
    )
    fill_doc["repository_contract"] = {
        "repository": "linuxificator/LB_Omnichord",
        "branch": "feature/gamma9001-drum-pattern-refresh",
        "design_status": "canonical runtime fill catalogue matched to the 2026-09-05 Gamma9001-first activity refresh",
    }
    fill_doc.setdefault("design_contract", {})
    fill_doc["design_contract"].update(
        {
            "ppq": PPQ,
            "fills_per_rhythm": 5,
            "instrument_data_forbidden_here": True,
            "kit_independence": "Events contain only tick, logical role and velocity; kit choice never changes timing.",
            "activity_coupling": "Every fill starts from the final matching window of the current level-3 refreshed groove, then overlays genre-specific transition vocabulary.",
            "bar_resolution_rule": "Every allowed fill start makes the fill end exactly at the next written bar boundary.",
            "gamma9001_policy": "Gamma9001 is the musical quality reference; fills may use its tom, ride/bell, side-stick, electronic and patch-390 Latin percussion vocabulary.",
            "tiny_policy": "Tiny resolves all logical roles for tests/compatibility; reduced sounds are accepted degradation and never constrain authoring.",
            "continuation_policy": "Continuation roles are style-specific and intersected with roles actually present in the refreshed activity catalogue.",
            "amy_48ppq_rule": "All event ticks are even at 96 PPQ and exactly convertible to AMY 48 PPQ.",
            "fill_event_budget": MAX_FILL_EVENTS,
        }
    )
    fill_doc["coverage_summary"] = {
        "rhythm_count": 54,
        "fill_count": 270,
        "fills_per_rhythm_min": 5,
        "fills_per_rhythm_max": 5,
        "rhythms_not_having_exactly_5": [],
    }
    fill_doc["fills"] = generated_fills
    fill_doc["rhythm_fill_index"] = generated_index

    continuation_doc = {
        "schema_version": 1,
        "title": "LB Omnichord fill continuation policy matched to Gamma9001-first refreshed grooves",
        "design_contract": {
            "activity_aware": True,
            "gamma9001_quality_reference": True,
            "tiny_degradation_only": True,
            "rule": "Listed refreshed base-groove roles continue; other active roles are gated for the fill duration without resetting phase.",
        },
        "fills": generated_continuation,
    }

    FILLS_PATH.write_text(json.dumps(fill_doc, indent=2) + "\n", encoding="utf-8")
    CONT_PATH.write_text(json.dumps(continuation_doc, indent=2) + "\n", encoding="utf-8")

    changed_kit_paths: list[Path] = []
    for family in ("gamma9001", "tiny", "general_midi"):
        activity_kit_path = DRUMS / f"drum_activity_instruments_{family}.json"
        fill_kit_path = DRUMS / f"drum_fills_instruments_{family}.json"
        activity_kit = json.loads(activity_kit_path.read_text(encoding="utf-8"))
        fill_kit = json.loads(fill_kit_path.read_text(encoding="utf-8"))
        assignment = deepcopy(activity_kit["rhythm_profile"])
        missing_profiles = {
            str(profile)
            for profile in assignment.values()
            if str(profile) not in fill_kit["profiles"]
        }
        if missing_profiles:
            raise SystemExit(f"{family}: fill mapping lacks {sorted(missing_profiles)}")
        fill_kit["rhythm_profile"] = assignment
        fill_kit.setdefault("separation_contract", {})["quality_reference"] = (
            "Gamma9001 determines authored musical colour; Tiny is compatibility degradation only."
        )
        fill_kit_path.write_text(json.dumps(fill_kit, indent=2) + "\n", encoding="utf-8")
        changed_kit_paths.append(fill_kit_path)

    if int(manifest.get("manifest_revision", 0)) != 1:
        raise SystemExit("unexpected canonical drum manifest revision")
    manifest_by_name = {entry["name"]: entry for entry in manifest["files"]}
    changed_paths = [FILLS_PATH, CONT_PATH, *changed_kit_paths]
    for path in changed_paths:
        manifest_by_name[path.name]["sha256"] = sha(path)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    process_by_path = {
        "music/drums/drum_fills_timing.json": (
            "LB-authored 2026-09-05 fill refresh derived from each current level-3 activity groove; "
            "genre-specific transition overlays; Gamma9001 musical reference; every allowed start "
            "resolves exactly at a bar boundary; Tiny is compatibility degradation only"
        ),
        "music/drums/drum_fill_continuation_roles.json": (
            "LB-authored 2026-09-05 activity-aware continuation policy; electronic kick, jazz "
            "timekeeping and Latin timeline/shaker continuities are retained where appropriate"
        ),
        "music/drums/drum_fills_instruments_gamma9001.json": (
            "Gamma9001 fill realization synchronized to the corresponding refreshed activity profile per rhythm"
        ),
        "music/drums/drum_fills_instruments_tiny.json": (
            "Tiny compatibility/degradation realization synchronized to the corresponding activity profile; not an authoring constraint"
        ),
        "music/drums/drum_fills_instruments_general_midi.json": (
            "General-MIDI compatibility realization synchronized to the corresponding activity profile"
        ),
    }
    provenance["recorded"] = "2026-09-05"
    provenance_by_path = {entry["path"]: entry for entry in provenance["catalogues"]}
    for path in changed_paths:
        rel = path.relative_to(ROOT / "qt_frontend").as_posix()
        provenance_by_path[rel]["sha256"] = sha(path)
        provenance_by_path[rel]["process"] = process_by_path[rel]
    PROVENANCE_PATH.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")

    add_regression_test()
    write_handover(validated=False)

    print(f"generated fills: {len(generated_fills)}")
    print(f"max authored fill events: {max(len(item['timing']['events']) for item in generated_fills)}")
    print(f"drum_fills_timing sha256: {sha(FILLS_PATH)}")
    print(f"continuation sha256: {sha(CONT_PATH)}")


def add_regression_test() -> None:
    text = TEST_PATH.read_text(encoding="utf-8")
    if "def test_fills_end_on_bar_boundary_and_use_base_groove_profiles" in text:
        return
    marker = "    def test_fill_sequences_preserve_events_and_only_add_generic_gates(self) -> None:\n"
    method = (
        "    def test_fills_end_on_bar_boundary_and_use_base_groove_profiles(self) -> None:\n"
        "        for rhythm in self.catalog.rhythms.values():\n"
        "            numerator = int(rhythm.meter.split(\"/\", 1)[0])\n"
        "            bar_ticks = numerator * rhythm.fills[0].beat_unit_ticks\n"
        "            for fill in rhythm.fills:\n"
        "                for start in fill.allowed_start_beats:\n"
        "                    self.assertEqual(\n"
        "                        (start - 1) * fill.beat_unit_ticks + fill.duration_ticks,\n"
        "                        bar_ticks,\n"
        "                        fill.fill_id,\n"
        "                    )\n"
        "        for kit_name in KIT_FAMILIES:\n"
        "            kit = self.catalog.kits[kit_name]\n"
        "            self.assertEqual(\n"
        "                dict(kit.fill_rhythm_profile),\n"
        "                dict(kit.activity_rhythm_profile),\n"
        "                kit_name,\n"
        "            )\n\n"
    )
    if marker not in text:
        raise SystemExit("fill regression insertion marker not found")
    TEST_PATH.write_text(text.replace(marker, method + marker, 1), encoding="utf-8")


def write_handover(*, validated: bool) -> None:
    status = (
        "canonical fill data regenerated against the refreshed drum grooves; focused and full unit validation passed"
        if validated
        else "canonical fill data regenerated against the refreshed drum grooves; validation pending"
    )
    hashes = {
        name: sha(DRUMS / name)
        for name in (
            "drum_fills_timing.json",
            "drum_fill_continuation_roles.json",
            "drum_fills_instruments_gamma9001.json",
            "drum_fills_instruments_tiny.json",
            "drum_fills_instruments_general_midi.json",
        )
    }
    lines = [
        "# Codex handover — Gamma9001-first drum fill refresh",
        "",
        f"Status: **{status}**",
        "",
        "Repository: `linuxificator/LB_Omnichord`",
        "Branch: `feature/gamma9001-drum-pattern-refresh`",
        "Active implementation: `amysynth_version` only. Sonic Pi remains frozen.",
        "",
        "## Intent",
        "",
        "The previous 270 fills were authored against the older drum activity catalogue and no longer sat naturally inside the richer Gamma9001-first grooves. This change replaces fill timing and continuation policy while preserving the existing five-F-button behavior, wire-only frontend architecture and nested AMY sequencer implementation.",
        "",
        "## Hard architecture rules",
        "",
        "- `drum_activity_timing.json` remains the authority for repeating groove timing.",
        "- `drum_fills_timing.json` contains only kit-independent tick/role/velocity fill data.",
        "- Concrete sounds remain in the three fill instrument realization files.",
        "- Gamma9001 is the musical quality reference.",
        "- Tiny exists for compatibility/tests only; its missing colour is accepted degradation and must never reduce authored Gamma9001 vocabulary.",
        "- Fill realization uses the same per-rhythm profile assignment as the corresponding base groove for every kit family.",
        "- Do not move musical fill policy into AMY. AMY owns generic nested-sequencer mechanics only.",
        "",
        "## Musical construction",
        "",
        "All 54 rhythms still have exactly five fills (270 total). Each fill starts from the final matching window of the current level-3 refreshed groove, retains essential non-continuing groove anchors, then overlays genre-specific transition vocabulary.",
        "",
        "Every allowed start is selected so the complete fill ends exactly at the written bar boundary. The following bar's normal groove owns the resolving downbeat.",
        "",
        "Electronic fills retain four-on-the-floor kick continuity where appropriate; jazz can retain ride/foot timekeeping; Latin can retain timeline/shaker and uses the Gamma9001 patch-390 hand-percussion/timbale/conga vocabulary. Pop, rock, funk, breakbeat and related fills replace more of the base groove as the fill becomes larger.",
        "",
        "## Validation",
        "",
        "- `python tests/test_drum_patterns.py`",
        "- `python tests/test_catalogue_provenance.py`",
        "- `python tests/test_sequencer_tags.py`",
        "- `python tests/run_tests.py --suite unit --coverage` in the pinned desktop test environment",
        "",
        "A permanent regression asserts that every allowed fill start resolves exactly at a bar boundary and that fill profile assignment equals base-groove profile assignment for Gamma9001, Tiny and General MIDI.",
        "",
        "## Canonical hashes",
        "",
        f"- `drum_fills_timing.json`: `{hashes['drum_fills_timing.json']}`",
        f"- `drum_fill_continuation_roles.json`: `{hashes['drum_fill_continuation_roles.json']}`",
        f"- `drum_fills_instruments_gamma9001.json`: `{hashes['drum_fills_instruments_gamma9001.json']}`",
        f"- `drum_fills_instruments_tiny.json`: `{hashes['drum_fills_instruments_tiny.json']}`",
        f"- `drum_fills_instruments_general_midi.json`: `{hashes['drum_fills_instruments_general_midi.json']}`",
        "",
        "## Do not regress",
        "",
        "Do not re-author fills around Tiny limitations. Do not concatenate activity levels. Do not add autonomous fills to activity level 5. Do not use host timers as a musical clock. Do not reset transport or sequencer phase to launch or edit fills.",
        "",
    ]
    HANDOVER_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--finalize-handover", action="store_true")
    args = parser.parse_args()
    if args.generate == args.finalize_handover:
        raise SystemExit("choose exactly one of --generate or --finalize-handover")
    if args.generate:
        generate()
    else:
        write_handover(validated=True)


if __name__ == "__main__":
    main()
