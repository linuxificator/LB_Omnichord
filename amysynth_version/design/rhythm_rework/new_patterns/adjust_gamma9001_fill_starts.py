#!/usr/bin/env python3
"""Post-process regenerated fills with meter/style-aware rotating start positions.

Temporary integration helper. It keeps the established fill-start rotation
contract while making positions structurally musical for the refreshed grooves.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
DRUMS = ROOT / "qt_frontend" / "music" / "drums"
FILLS_PATH = DRUMS / "drum_fills_timing.json"
MANIFEST_PATH = HERE / "canonical_drum_data_manifest.json"
PROVENANCE_PATH = ROOT / "qt_frontend" / "music" / "catalogue_provenance.json"
TEST_PATH = ROOT / "qt_frontend" / "tests" / "test_drum_patterns.py"
HANDOVER_PATH = HERE / "CODEX_HANDOVER_GAMMA9001_FILL_REFRESH.md"

GROUPINGS = {
    "five_four": (3, 2),
    "seven_eight": (2, 2, 3),
    "seven_four_funk": (4, 3),
    "nine_eight": (2, 2, 2, 3),
    "eleven_eight": (3, 3, 3, 2),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def group_starts(grouping: tuple[int, ...]) -> list[tuple[int, int]]:
    result = []
    start = 1
    for size in grouping:
        result.append((start, size))
        start += size
    return result


def allowed_starts(
    *,
    rhythm_id: str,
    meter: str,
    duration_beats: int,
) -> list[int]:
    numerator, denominator = (int(value) for value in meter.split("/", 1))
    max_start = numerator - duration_beats + 1
    if max_start <= 1:
        return [1]

    grouping = GROUPINGS.get(rhythm_id)
    if grouping is not None:
        exact = [
            start
            for start, size in group_starts(grouping)
            if size == duration_beats and start <= max_start
        ]
        if exact:
            return exact[:2]
        structural = [
            start
            for start, _size in group_starts(grouping)
            if start <= max_start
        ]
        if len(structural) >= 2:
            return [structural[0], structural[-1]]
        return structural or [max_start]

    if denominator == 4:
        if duration_beats == 1:
            if numerator >= 4:
                return [2, max_start]
            if numerator == 3:
                return [2, 3]
            return [1, max_start]
        if duration_beats == 2 and numerator >= 4:
            return [1, max_start]
        return [1, max_start]

    # Compound /8 meters: align to dotted-quarter groups. 6/8 rotates halves;
    # 12/8 rotates between the ends of the two half-bars for short fills and
    # between half-bars for six-eighth fills.
    if denominator == 8 and numerator in {6, 12}:
        dotted = 3
        if duration_beats == dotted:
            if numerator == 6:
                return [1, 4]
            return [4, 10]
        if numerator == 12 and duration_beats == 6:
            return [1, 7]
        return [1]

    return [1, max_start]


def adjust() -> None:
    doc = json.loads(FILLS_PATH.read_text(encoding="utf-8"))
    for fill in doc["fills"]:
        duration_beats = int(fill["timing"]["duration_beats"])
        starts = allowed_starts(
            rhythm_id=str(fill["rhythm_id"]),
            meter=str(fill["meter"]),
            duration_beats=duration_beats,
        )
        numerator = int(str(fill["meter"]).split("/", 1)[0])
        if not starts or starts != sorted(set(starts)):
            raise SystemExit(f"{fill['fill_id']}: invalid start list {starts}")
        if any(start < 1 or start + duration_beats - 1 > numerator for start in starts):
            raise SystemExit(f"{fill['fill_id']}: start list does not fit meter")
        fill["allowed_start_beats"] = starts

    doc.setdefault("design_contract", {})["start_rotation_policy"] = (
        "Selected fills retain rotating whole-beat start positions. Short 4/4 fills use "
        "beat 2/4 positions, half-bar fills use beat 1/3, compound meters use dotted-quarter "
        "or half-bar positions, and odd meters prefer authored grouping boundaries."
    )
    doc["design_contract"]["bar_resolution_rule"] = (
        "Full-bar fills resolve at the next bar. Shorter fills use structurally meaningful "
        "whole-beat positions and the refreshed base groove resumes in phase immediately afterward."
    )
    FILLS_PATH.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if int(manifest.get("manifest_revision", 0)) != 1:
        raise SystemExit("unexpected drum manifest format revision")
    for entry in manifest["files"]:
        if entry["name"] == FILLS_PATH.name:
            entry["sha256"] = digest(FILLS_PATH)
            break
    else:
        raise SystemExit("manifest lacks fill timing entry")
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    provenance = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
    for entry in provenance["catalogues"]:
        if entry["path"] == "music/drums/drum_fills_timing.json":
            entry["sha256"] = digest(FILLS_PATH)
            entry["process"] = (
                "LB-authored 2026-09-05 fill refresh derived from each current level-3 activity groove; "
                "genre-specific transition overlays; Gamma9001 musical reference; rotating start positions "
                "are aligned to ordinary beat, half-bar, compound-meter or odd-meter grouping boundaries; "
                "Tiny is compatibility degradation only"
            )
            break
    else:
        raise SystemExit("provenance lacks fill timing entry")
    PROVENANCE_PATH.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")

    fix_regression_test()
    print("fill timing sha256:", digest(FILLS_PATH))


def fix_regression_test() -> None:
    text = TEST_PATH.read_text(encoding="utf-8")
    start = text.find("    def test_fills_end_on_bar_boundary_and_use_base_groove_profiles(self) -> None:\n")
    if start < 0:
        raise SystemExit("generated fill-fit regression not found")
    end_marker = "    def test_fill_sequences_preserve_events_and_only_add_generic_gates(self) -> None:\n"
    end = text.find(end_marker, start)
    if end < 0:
        raise SystemExit("fill-fit regression end marker not found")
    replacement = '''    def test_fill_start_rotation_and_base_groove_profiles(self) -> None:\n        maximum = 0\n        for rhythm in self.catalog.rhythms.values():\n            beats_per_bar = int(rhythm.meter.split("/", 1)[0])\n            occurrences = AmySerialClient._fill_occurrences(\n                list(range(len(rhythm.fills))),\n                rhythm.fills,\n            )\n            maximum = max(maximum, len(occurrences))\n            for fill, start in occurrences:\n                self.assertIn(start, fill.allowed_start_beats)\n                self.assertLessEqual(\n                    (start - 1) * fill.beat_unit_ticks + fill.duration_ticks,\n                    beats_per_bar * fill.beat_unit_ticks,\n                    fill.fill_id,\n                )\n        self.assertEqual(maximum, 10)\n        for kit_name in KIT_FAMILIES:\n            kit = self.catalog.kits[kit_name]\n            self.assertEqual(\n                dict(kit.fill_rhythm_profile),\n                dict(kit.activity_rhythm_profile),\n                kit_name,\n            )\n\n'''
    TEST_PATH.write_text(text[:start] + replacement + text[end:], encoding="utf-8")


def write_handover() -> None:
    hashes = {
        name: digest(DRUMS / name)
        for name in (
            "drum_fills_timing.json",
            "drum_fill_continuation_roles.json",
            "drum_fills_instruments_gamma9001.json",
            "drum_fills_instruments_tiny.json",
            "drum_fills_instruments_general_midi.json",
        )
    }
    content = f'''# Codex handover — Gamma9001-first drum fill refresh

Status: **canonical fill data regenerated against the refreshed drum grooves; focused and full unit validation passed**

Repository: `linuxificator/LB_Omnichord`
Branch: `feature/gamma9001-drum-pattern-refresh`
Active implementation: `amysynth_version` only. Sonic Pi remains frozen.

## Intent

The previous 270 fills were authored against the older drum activity catalogue and no longer sat naturally inside the richer Gamma9001-first grooves. This change replaces fill timing and continuation policy while preserving the existing five-F-button behavior, wire-only frontend architecture and nested AMY sequencer implementation.

## Hard architecture rules

- `drum_activity_timing.json` remains the authority for repeating groove timing.
- `drum_fills_timing.json` contains only kit-independent tick/role/velocity fill data.
- Concrete sounds remain in the three fill instrument realization files.
- Gamma9001 is the musical quality reference.
- Tiny exists for compatibility/tests only; its missing colour is accepted degradation and must never reduce authored Gamma9001 vocabulary.
- Fill realization uses the same per-rhythm profile assignment as the corresponding base groove for every kit family.
- Musical fill policy stays in LB Omnichord; AMY owns only generic nested-sequencer mechanics.

## Musical construction

All 54 rhythms still have exactly five fills (270 total). Each fill starts from the matching final window of the current level-3 refreshed groove, retains selected groove anchors, then overlays genre-specific transition vocabulary.

Fill start rotation is deliberately preserved. In ordinary 4/4, one-beat fills rotate through beats 2 and 4 and half-bar fills through beats 1 and 3. Compound meters use dotted-quarter or half-bar positions; odd meters prefer the authored grouping boundaries. Full-bar fills start on beat 1. The base groove remains phase-continuous and resumes immediately when a shorter fill ends.

Electronic fills retain the four-on-the-floor kick where appropriate; jazz can retain ride/foot timekeeping; Latin can retain timeline/shaker and uses the Gamma9001 patch-390 hand-percussion/timbale/conga vocabulary. Pop, rock, funk and breakbeat-family fills replace progressively more of the base groove as the fill becomes larger.

## Gamma9001 / Tiny policy

The Gamma9001 profiles expose TR-808, TR-909, Linn 9000, Tokyo Synthetics, 80s Power Kit and patch-390 percussion. The new fills exploit logical tom, open-hat, electronic-detail, side-stick, hand-percussion, cowbell/accent and timbale/conga functions where musically appropriate. Tiny resolves the same logical roles through surrogates only and is expected to sound less differentiated.

## Validation

The final branch data passed:

- `python tests/test_drum_patterns.py`;
- `python tests/test_catalogue_provenance.py`;
- `python tests/test_sequencer_tags.py`;
- `python tests/run_tests.py --suite unit --coverage` in the project's pinned desktop test environment.

Permanent regression coverage retains the established maximum 10-event fill-root rotation cycle and asserts that all fill kit-profile assignments equal the corresponding base-groove assignments.

## Canonical hashes

- `drum_fills_timing.json`: `{hashes['drum_fills_timing.json']}`
- `drum_fill_continuation_roles.json`: `{hashes['drum_fill_continuation_roles.json']}`
- `drum_fills_instruments_gamma9001.json`: `{hashes['drum_fills_instruments_gamma9001.json']}`
- `drum_fills_instruments_tiny.json`: `{hashes['drum_fills_instruments_tiny.json']}`
- `drum_fills_instruments_general_midi.json`: `{hashes['drum_fills_instruments_general_midi.json']}`

## Do not regress

Do not author around Tiny limitations. Do not remove fill-start rotation merely to make fills end at a bar. Do not add autonomous fills to activity level 5. Do not use host timers as a musical clock. Do not reset transport or sequencer phase to launch or edit fills.
'''
    HANDOVER_PATH.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adjust", action="store_true")
    parser.add_argument("--handover", action="store_true")
    args = parser.parse_args()
    if args.adjust == args.handover:
        raise SystemExit("choose exactly one of --adjust or --handover")
    if args.adjust:
        adjust()
    else:
        write_handover()


if __name__ == "__main__":
    main()
