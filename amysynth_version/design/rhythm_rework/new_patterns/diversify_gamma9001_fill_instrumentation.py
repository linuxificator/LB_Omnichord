#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path("amysynth_version")
FRONTEND = ROOT / "qt_frontend"
DRUMS = FRONTEND / "music/drums"
CODE = FRONTEND / "code"
TESTS = FRONTEND / "tests"
SCHEMA = FRONTEND / "music/schema"
MANIFEST = ROOT / "design/rhythm_rework/new_patterns/canonical_drum_data_manifest.json"
PROVENANCE = FRONTEND / "music/catalogue_provenance.json"
HANDOVER = ROOT / "design/rhythm_rework/new_patterns/CODEX_HANDOVER_GAMMA9001_FILL_REFRESH.md"


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"{path}: expected JSON object")
    return value


def write_json(path: Path, value: dict) -> str:
    encoded = (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    path.write_bytes(encoded)
    return hashlib.sha256(encoded).hexdigest()


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"{path}: replacement marker not found:\n{old[:240]}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Fill data: preserve event ticks but broaden the logical orchestration.
# ---------------------------------------------------------------------------

fills_path = DRUMS / "drum_fills_timing.json"
fills = read_json(fills_path)
fill_items = fills.get("fills")
fill_index = fills.get("rhythm_fill_index")
if not isinstance(fill_items, list) or len(fill_items) != 270:
    raise SystemExit("expected 270 canonical fills")
if not isinstance(fill_index, dict) or len(fill_index) != 54:
    raise SystemExit("expected 54 rhythm fill-index entries")

style_groups = {
    "pop": {"pop_8", "pop_16", "slow_ballad", "rock", "punk", "metal", "straight_blues", "rnb", "soul"},
    "swing": {"shuffle", "twelve_eight_blues", "jazz_shuffle", "soul_shuffle", "six_eight_ballad", "gospel_6_8"},
    "jazz": {"jazz_swing", "jazz_waltz"},
    "funk": {"funk", "jazz_funk", "seven_four_funk"},
    "country": {"country_train", "country_waltz", "waltz"},
    "march": {"polka", "march"},
    "electronic": {"disco", "house", "techno", "trance"},
    "breaks": {"garage_2step", "breakbeat", "drum_and_bass", "dubstep", "hip_hop", "boom_bap", "trap"},
    "latin": {"bossa", "samba", "salsa", "cha_cha", "mambo", "merengue", "cumbia", "bolero", "tango", "son_clave_3_2", "rumba_clave_3_2", "afro_cuban_6_8", "calypso_soca"},
    "reggae": {"reggae"},
    "odd": {"five_four", "seven_eight", "nine_eight", "eleven_eight"},
}
style_for: dict[str, str] = {}
for style, rhythm_ids in style_groups.items():
    for rhythm_id in rhythm_ids:
        if rhythm_id in style_for:
            raise SystemExit(f"duplicate style assignment: {rhythm_id}")
        style_for[rhythm_id] = style
if set(style_for) != set(fill_index):
    raise SystemExit(f"fill style coverage mismatch: {sorted(set(fill_index) ^ set(style_for))}")

# Each of the five fill buttons gets a recognisably different orchestration.
# Timing is deliberately untouched: this pass changes instrument function only.
role_palettes: dict[str, tuple[tuple[str, ...], ...]] = {
    "pop": (
        ("backbeat_primary", "backbeat_soft", "dry_click", "backbeat_primary"),
        ("low_secondary", "backbeat_primary", "hand_accent", "timekeeper_open"),
        ("tonal_high", "tonal_mid", "tonal_low", "backbeat_primary"),
        ("low_secondary", "ghost_detail", "backbeat_primary", "electronic_detail", "low_secondary"),
        ("backbeat_primary", "tonal_high", "tonal_mid", "tonal_low", "hand_accent", "section_accent"),
    ),
    "swing": (
        ("backbeat_soft", "ghost_detail", "sustain_bell"),
        ("backbeat_soft", "tonal_high", "backbeat_soft", "tonal_mid"),
        ("tonal_high", "tonal_mid", "tonal_low", "sustain_primary"),
        ("low_secondary", "backbeat_soft", "ghost_detail", "low_secondary", "backbeat_primary"),
        ("backbeat_soft", "tonal_high", "tonal_mid", "tonal_low", "section_accent"),
    ),
    "jazz": (
        ("backbeat_soft", "ghost_detail", "sustain_bell"),
        ("backbeat_soft", "sustain_bell", "tonal_high", "backbeat_soft"),
        ("tonal_high", "tonal_mid", "tonal_low", "low_secondary"),
        ("ghost_detail", "backbeat_soft", "low_secondary", "sustain_bell"),
        ("backbeat_soft", "tonal_high", "tonal_mid", "tonal_low", "section_accent"),
    ),
    "funk": (
        ("ghost_detail", "dry_click", "backbeat_primary", "ghost_detail"),
        ("low_secondary", "ghost_detail", "hand_accent", "backbeat_primary", "dry_click"),
        ("tonal_high", "tonal_mid", "tonal_low", "backbeat_primary"),
        ("low_secondary", "ghost_detail", "backbeat_primary", "low_secondary", "electronic_detail"),
        ("hand_accent", "ghost_detail", "tonal_high", "tonal_mid", "tonal_low", "section_accent"),
    ),
    "country": (
        ("dry_click", "backbeat_soft", "backbeat_primary"),
        ("backbeat_soft", "tonal_high", "backbeat_soft", "tonal_mid"),
        ("tonal_high", "tonal_mid", "tonal_low", "backbeat_primary"),
        ("low_secondary", "backbeat_primary", "tonal_high", "low_secondary", "tonal_low"),
        ("backbeat_primary", "tonal_high", "tonal_mid", "tonal_low", "section_accent"),
    ),
    "march": (
        ("backbeat_primary", "ghost_detail", "backbeat_primary", "ghost_detail"),
        ("backbeat_primary", "dry_click", "backbeat_primary", "hand_accent"),
        ("tonal_high", "tonal_mid", "tonal_low", "backbeat_primary"),
        ("backbeat_primary", "ghost_detail", "low_secondary", "backbeat_primary"),
        ("backbeat_primary", "tonal_high", "tonal_mid", "tonal_low", "section_accent"),
    ),
    "electronic": (
        ("electronic_detail", "backbeat_primary", "electronic_detail", "timekeeper_open"),
        ("hand_accent", "backbeat_primary", "hand_accent", "timekeeper_open"),
        ("tonal_high", "tonal_mid", "tonal_low", "section_accent"),
        ("electronic_detail", "electronic_detail", "backbeat_primary", "electronic_detail", "low_secondary"),
        ("low_secondary", "backbeat_primary", "tonal_high", "tonal_mid", "tonal_low", "timekeeper_open", "section_accent"),
    ),
    "breaks": (
        ("dry_click", "ghost_detail", "backbeat_primary", "low_secondary"),
        ("low_secondary", "ghost_detail", "hand_accent", "backbeat_primary", "electronic_detail"),
        ("tonal_high", "tonal_mid", "tonal_low", "backbeat_primary"),
        ("electronic_detail", "ghost_detail", "low_secondary", "backbeat_primary", "electronic_detail"),
        ("low_secondary", "backbeat_primary", "tonal_high", "tonal_mid", "tonal_low", "hand_accent", "section_accent"),
    ),
    "latin": (
        ("hand_high", "hand_low", "timeline_primary", "hand_accent"),
        ("hand_high", "hand_low", "texture_shaker", "hand_accent", "hand_high"),
        ("tonal_high", "tonal_mid", "tonal_low", "hand_accent"),
        ("timeline_primary", "hand_high", "hand_low", "hand_accent", "tonal_high", "tonal_low"),
        ("hand_low", "hand_high", "tonal_high", "tonal_mid", "tonal_low", "timeline_primary", "section_accent"),
    ),
    "reggae": (
        ("dry_click", "backbeat_soft", "timekeeper_open"),
        ("hand_accent", "dry_click", "backbeat_soft", "timekeeper_open"),
        ("tonal_high", "tonal_mid", "tonal_low", "dry_click"),
        ("low_secondary", "dry_click", "backbeat_soft", "ghost_detail"),
        ("dry_click", "tonal_high", "tonal_mid", "tonal_low", "section_accent"),
    ),
    "odd": (
        ("backbeat_primary", "dry_click", "backbeat_primary"),
        ("low_secondary", "backbeat_primary", "hand_accent", "timekeeper_open"),
        ("tonal_high", "tonal_mid", "tonal_low", "backbeat_primary"),
        ("low_secondary", "ghost_detail", "backbeat_primary", "electronic_detail"),
        ("backbeat_primary", "tonal_high", "tonal_mid", "tonal_low", "section_accent"),
    ),
}

by_index = {int(item["index"]): item for item in fill_items}
for rhythm_id, indexes in fill_index.items():
    if not isinstance(indexes, list) or len(indexes) != 5:
        raise SystemExit(f"{rhythm_id}: expected five fills")
    style = style_for[str(rhythm_id)]
    for variant, raw_index in enumerate(indexes, start=1):
        item = by_index[int(raw_index)]
        timing = item.get("timing")
        if not isinstance(timing, dict) or not isinstance(timing.get("events"), list):
            raise SystemExit(f"{rhythm_id} F{variant}: malformed timing")
        palette = role_palettes[style][variant - 1]
        recoloured = []
        for position, raw_event in enumerate(timing["events"]):
            event = dict(raw_event)
            event["role"] = palette[position % len(palette)]
            recoloured.append(event)
        # Avoid doubled hits when two pre-existing simultaneous events collapse
        # onto the same new role. Keep the stronger authored velocity.
        merged: dict[tuple[int, str], dict] = {}
        for event in recoloured:
            key = (int(event["tick"]), str(event["role"]))
            prior = merged.get(key)
            if prior is None or int(event["velocity"]) > int(prior["velocity"]):
                merged[key] = event
        events = sorted(merged.values(), key=lambda event: (int(event["tick"]), str(event["role"])))
        timing["events"] = events
        if "event_count" in timing:
            timing["event_count"] = len(events)
        if len(events) > 40:
            raise SystemExit(f"{item['fill_id']}: recoloured fill exceeds 40 authored events")

fills.setdefault("design_contract", {})["instrumentation_diversity_rule"] = (
    "Fill event timing is kit-independent, but F1-F5 deliberately use different logical orchestration. "
    "Gamma9001 may additionally select a fill-specific realization profile; Tiny remains a compatibility fallback."
)
fills_sha = write_json(fills_path, fills)

# ---------------------------------------------------------------------------
# 2. Gamma9001: select a different compatible kit/profile for every fill.
# ---------------------------------------------------------------------------

gamma_path = DRUMS / "drum_fills_instruments_gamma9001.json"
gamma = read_json(gamma_path)
profiles = gamma.get("profiles")
rhythm_profile = gamma.get("rhythm_profile")
if not isinstance(profiles, dict) or not isinstance(rhythm_profile, dict):
    raise SystemExit("Gamma9001 fill catalogue lacks profiles/rhythm_profile")

required_profiles = {
    "gamma_808", "gamma_909", "gamma_linn", "gamma_tokyo", "gamma_power",
    "gamma_jazz_linn", "gamma_latin_dual", "gamma_reggae_808",
}
missing = required_profiles - set(profiles)
if missing:
    raise SystemExit(f"Gamma9001 profiles missing: {sorted(missing)}")

# Build five Latin hybrids: conventional kit anchors plus patch-390 percussion
# colour. This exploits Gamma9001 without forcing the base groove onto patch 390.
latin_source = profiles["gamma_latin_dual"]
for base_name in ("gamma_808", "gamma_909", "gamma_linn", "gamma_tokyo", "gamma_power"):
    hybrid_name = "gamma_latin_" + base_name.removeprefix("gamma_")
    hybrid = deepcopy(profiles[base_name])
    for role, sound in latin_source.items():
        if isinstance(sound, dict) and int(sound.get("patch", -1)) == 390:
            hybrid[role] = deepcopy(sound)
    profiles[hybrid_name] = hybrid

core = ["gamma_808", "gamma_909", "gamma_linn", "gamma_tokyo", "gamma_power"]

def core_with_base_first(base: str) -> list[str]:
    result = [base] if base in core else []
    result.extend(profile for profile in core if profile != base)
    if len(result) < 5:
        raise SystemExit(f"cannot build five-profile palette for {base}")
    return result[:5]

fill_profile: dict[str, str] = {}
for rhythm_id, indexes in fill_index.items():
    style = style_for[str(rhythm_id)]
    base = str(rhythm_profile[str(rhythm_id)])
    if style == "latin":
        palette = ["gamma_latin_808", "gamma_latin_909", "gamma_latin_linn", "gamma_latin_tokyo", "gamma_latin_power"]
    elif style in {"jazz", "swing"}:
        palette = ["gamma_jazz_linn", "gamma_linn", "gamma_power", "gamma_909", "gamma_808"]
    elif style == "electronic":
        palette = ["gamma_909", "gamma_808", "gamma_tokyo", "gamma_linn", "gamma_power"]
    elif style == "breaks":
        palette = ["gamma_tokyo", "gamma_808", "gamma_linn", "gamma_909", "gamma_power"]
    elif style == "funk":
        palette = ["gamma_linn", "gamma_808", "gamma_power", "gamma_tokyo", "gamma_909"]
    elif style == "reggae":
        palette = ["gamma_reggae_808", "gamma_808", "gamma_linn", "gamma_tokyo", "gamma_909"]
    else:
        palette = core_with_base_first(base)
    if len(set(palette)) != 5:
        raise SystemExit(f"{rhythm_id}: fill palette is not five distinct profiles")
    for variant, raw_index in enumerate(indexes, start=1):
        fill_id = str(by_index[int(raw_index)]["fill_id"])
        fill_profile[fill_id] = palette[variant - 1]

if len(fill_profile) != 270:
    raise SystemExit(f"expected 270 fill-specific Gamma profiles, got {len(fill_profile)}")
gamma["fill_profile"] = fill_profile
gamma["separation_contract"]["rule"] = (
    "Resolve each event logical_role using fill_profile[fill_id] when present, otherwise the rhythm_profile fallback. "
    "Velocity comes from the timing catalogue and may be scaled but not used to move events."
)
gamma["gamma_fill_selection_policy"] = {
    "fill_specific_profiles": True,
    "profiles_per_rhythm": 5,
    "quality_reference": "Gamma9001",
    "tiny_policy": "Tiny does not mirror this colour layer; it is a compatibility/test degradation path.",
    "rule": "F1-F5 must not collapse to one kit profile. Profile changes are deliberate orchestration, not randomness.",
}
gamma_sha = write_json(gamma_path, gamma)

# ---------------------------------------------------------------------------
# 3. Loader/runtime: optional fill_id-specific profile selection.
# ---------------------------------------------------------------------------

schema_path = SCHEMA / "drum_kit_v1.schema.json"
schema = read_json(schema_path)
props = schema.setdefault("properties", {})
props["fill_profile"] = {"type": "object"}
write_json(schema_path, schema)

drum_patterns = CODE / "drum_patterns.py"
replace_once(
    drum_patterns,
    "    fill_profiles: Mapping[str, Mapping[str, DrumSound]]\n    fill_rhythm_profile: Mapping[str, str]\n",
    "    fill_profiles: Mapping[str, Mapping[str, DrumSound]]\n    fill_rhythm_profile: Mapping[str, str]\n    fill_id_profile: Mapping[str, str]\n",
)
replace_once(
    drum_patterns,
    "        *,\n        fill: bool = False,\n    ) -> DrumSound:\n",
    "        *,\n        fill: bool = False,\n        fill_id: str | None = None,\n    ) -> DrumSound:\n",
)
replace_once(
    drum_patterns,
    "        try:\n            profile_name = assignments[str(rhythm_id)]\n            return profiles[profile_name][str(role)]\n",
    "        try:\n            profile_name = (\n                kit.fill_id_profile.get(str(fill_id))\n                if fill and fill_id is not None\n                else None\n            )\n            if profile_name is None:\n                profile_name = assignments[str(rhythm_id)]\n            return profiles[profile_name][str(role)]\n",
)
replace_once(
    drum_patterns,
    ") -> tuple[Mapping[str, Mapping[str, DrumSound]], Mapping[str, str]]:\n",
    ") -> tuple[\n    Mapping[str, Mapping[str, DrumSound]],\n    Mapping[str, str],\n    Mapping[str, str],\n]:\n",
)
replace_once(
    drum_patterns,
    "    assignments = raw.get(\"rhythm_profile\")\n    if not isinstance(raw_profiles, dict) or not isinstance(assignments, dict):\n        raise ValueError(f\"{path} lacks profiles or rhythm_profile\")\n",
    "    assignments = raw.get(\"rhythm_profile\")\n    fill_assignments = raw.get(\"fill_profile\", {})\n    if (\n        not isinstance(raw_profiles, dict)\n        or not isinstance(assignments, dict)\n        or not isinstance(fill_assignments, dict)\n    ):\n        raise ValueError(f\"{path} lacks valid profiles/rhythm_profile/fill_profile\")\n",
)
replace_once(
    drum_patterns,
    "    return immutable_profiles, MappingProxyType(\n        {str(key): str(value) for key, value in assignments.items()}\n    )\n",
    "    return (\n        immutable_profiles,\n        MappingProxyType({str(key): str(value) for key, value in assignments.items()}),\n        MappingProxyType({str(key): str(value) for key, value in fill_assignments.items()}),\n    )\n",
)
replace_once(
    drum_patterns,
    "        fill_roles = {event.role for fill in rhythm.fills for event in fill.events}\n        for kit_family in KIT_FAMILIES:\n            for role in active_roles:\n                catalog.resolve(kit_family, rhythm.rhythm_id, role)\n            for role in fill_roles:\n                catalog.resolve(kit_family, rhythm.rhythm_id, role, fill=True)\n",
    "        for kit_family in KIT_FAMILIES:\n            for role in active_roles:\n                catalog.resolve(kit_family, rhythm.rhythm_id, role)\n            for fill in rhythm.fills:\n                for event in fill.events:\n                    catalog.resolve(\n                        kit_family,\n                        rhythm.rhythm_id,\n                        event.role,\n                        fill=True,\n                        fill_id=fill.fill_id,\n                    )\n",
)
replace_once(
    drum_patterns,
    "        activity_profiles, activity_assignments = _load_kit(\n",
    "        activity_profiles, activity_assignments, _ = _load_kit(\n",
)
replace_once(
    drum_patterns,
    "        fill_profiles, fill_assignments = _load_kit(\n",
    "        fill_profiles, fill_assignments, fill_id_assignments = _load_kit(\n",
)
replace_once(
    drum_patterns,
    "            fill_profiles=fill_profiles,\n            fill_rhythm_profile=fill_assignments,\n",
    "            fill_profiles=fill_profiles,\n            fill_rhythm_profile=fill_assignments,\n            fill_id_profile=fill_id_assignments,\n",
)

plan_path = CODE / "rhythm_command_plan.py"
replace_once(
    plan_path,
    "class FillLike(Protocol):\n    @property\n    def index(self) -> int: ...\n",
    "class FillLike(Protocol):\n    @property\n    def index(self) -> int: ...\n\n    @property\n    def fill_id(self) -> str: ...\n",
)
replace_once(
    plan_path,
    "        *,\n        fill: bool,\n    ) -> str: ...\n",
    "        *,\n        fill: bool,\n        fill_id: str | None = None,\n    ) -> str: ...\n",
)
replace_once(
    plan_path,
    "                hit_body(rhythm_id, event.role, event.velocity, fill=True),\n",
    "                hit_body(\n                    rhythm_id,\n                    event.role,\n                    event.velocity,\n                    fill=True,\n                    fill_id=fill.fill_id,\n                ),\n",
)

transport_path = CODE / "amy_transport.py"
replace_once(
    transport_path,
    "        *,\n        fill: bool,\n    ) -> str:\n",
    "        *,\n        fill: bool,\n        fill_id: str | None = None,\n    ) -> str:\n",
)
replace_once(
    transport_path,
    "            role,\n            fill=fill,\n        )\n",
    "            role,\n            fill=fill,\n            fill_id=fill_id,\n        )\n",
)

# ---------------------------------------------------------------------------
# 4. Regression tests: diversity is now an explicit contract.
# ---------------------------------------------------------------------------

test_path = TESTS / "test_drum_patterns.py"
replace_once(
    test_path,
    "    def test_fill_start_rotation_and_base_groove_profiles(self) -> None:\n        maximum = 0\n        for rhythm in self.catalog.rhythms.values():\n            beats_per_bar = int(rhythm.meter.split(\"/\", 1)[0])\n            occurrences = AmySerialClient._fill_occurrences(\n                list(range(len(rhythm.fills))),\n                rhythm.fills,\n            )\n            maximum = max(maximum, len(occurrences))\n            for fill, start in occurrences:\n                self.assertIn(start, fill.allowed_start_beats)\n                self.assertLessEqual(\n                    (start - 1) * fill.beat_unit_ticks + fill.duration_ticks,\n                    beats_per_bar * fill.beat_unit_ticks,\n                    fill.fill_id,\n                )\n        self.assertEqual(maximum, 10)\n        for kit_name in KIT_FAMILIES:\n            kit = self.catalog.kits[kit_name]\n            self.assertEqual(\n                dict(kit.fill_rhythm_profile),\n                dict(kit.activity_rhythm_profile),\n                kit_name,\n            )\n",
    "    def test_fill_start_rotation_and_gamma_profile_diversity(self) -> None:\n        maximum = 0\n        for rhythm in self.catalog.rhythms.values():\n            beats_per_bar = int(rhythm.meter.split(\"/\", 1)[0])\n            occurrences = AmySerialClient._fill_occurrences(\n                list(range(len(rhythm.fills))),\n                rhythm.fills,\n            )\n            maximum = max(maximum, len(occurrences))\n            for fill, start in occurrences:\n                self.assertIn(start, fill.allowed_start_beats)\n                self.assertLessEqual(\n                    (start - 1) * fill.beat_unit_ticks + fill.duration_ticks,\n                    beats_per_bar * fill.beat_unit_ticks,\n                    fill.fill_id,\n                )\n        self.assertEqual(maximum, 10)\n\n        gamma = self.catalog.kits[\"gamma9001\"]\n        self.assertEqual(len(gamma.fill_id_profile), 270)\n        for rhythm in self.catalog.rhythms.values():\n            profiles = {gamma.fill_id_profile[fill.fill_id] for fill in rhythm.fills}\n            self.assertEqual(len(profiles), 5, rhythm.rhythm_id)\n\n        for kit_name in (\"tiny\", \"general_midi\"):\n            kit = self.catalog.kits[kit_name]\n            self.assertFalse(kit.fill_id_profile, kit_name)\n            self.assertEqual(\n                dict(kit.fill_rhythm_profile),\n                dict(kit.activity_rhythm_profile),\n                kit_name,\n            )\n",
)
replace_once(
    test_path,
    "                                event.velocity,\n                                fill=True,\n                            ),\n",
    "                                event.velocity,\n                                fill=True,\n                                fill_id=fill.fill_id,\n                            ),\n",
)
# Exercise the actual per-fill Gamma profile rather than only its rhythm fallback.
replace_once(
    test_path,
    "                        event.role,\n                        fill=True,\n                    )\n",
    "                        event.role,\n                        fill=True,\n                        fill_id=fill.fill_id,\n                    )\n",
)

# ---------------------------------------------------------------------------
# 5. Provenance / canonical manifest / handover.
# ---------------------------------------------------------------------------

manifest = read_json(MANIFEST)
for entry in manifest.get("files", []):
    if entry.get("name") == "drum_fills_timing.json":
        entry["sha256"] = fills_sha
    elif entry.get("name") == "drum_fills_instruments_gamma9001.json":
        entry["sha256"] = gamma_sha
write_json(MANIFEST, manifest)

provenance = read_json(PROVENANCE)
for entry in provenance.get("catalogues", []):
    if entry.get("path") == "music/drums/drum_fills_timing.json":
        entry["sha256"] = fills_sha
        entry["process"] = (
            "LB-authored 2026-09-05 Gamma9001-first fill refresh; timing remains kit-independent, "
            "while F1-F5 use deliberately different logical orchestrations at unchanged event ticks"
        )
    elif entry.get("path") == "music/drums/drum_fills_instruments_gamma9001.json":
        entry["sha256"] = gamma_sha
        entry["process"] = (
            "Gamma9001-first fill realization with deterministic fill_id-specific profiles; each rhythm's "
            "five fills use five distinct compatible profiles, including patch-390 Latin hybrid colour"
        )
write_json(PROVENANCE, provenance)

handover = HANDOVER.read_text(encoding="utf-8")
appendix = f"""

## Instrumentation diversity correction — 2026-09-05

Listening review found that the first fill refresh changed timing vocabulary but still selected only one Gamma9001 profile per rhythm. That made F1-F5 timbrally repetitive.

The corrected contract is:

- fill timing remains kit-independent;
- F1-F5 use distinct logical orchestrations at the existing event ticks;
- Gamma9001 may select a profile by `fill_id`, with the old per-rhythm profile retained only as fallback;
- all five fills of every rhythm use five distinct Gamma9001 profiles;
- Latin fills combine changing main-kit anchors with patch-390 timbale/conga/claves/maracas/cowbell colour;
- Tiny and General MIDI do not need to mirror this colour layer. Tiny remains test/compatibility degradation and must not constrain Gamma9001 authoring.

Canonical hashes after this correction:

- `drum_fills_timing.json`: `{fills_sha}`
- `drum_fills_instruments_gamma9001.json`: `{gamma_sha}`
"""
if "## Instrumentation diversity correction — 2026-09-05" not in handover:
    HANDOVER.write_text(handover.rstrip() + appendix + "\n", encoding="utf-8")

print("fills_sha", fills_sha)
print("gamma_sha", gamma_sha)
print("fill_specific_profiles", len(fill_profile))
print("gamma_profiles", len(profiles))
