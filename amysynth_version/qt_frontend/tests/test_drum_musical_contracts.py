#!/usr/bin/env python3
"""Source-backed musical contracts for the complete drum catalogue."""

from __future__ import annotations

import json
import statistics
import unittest
from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[1]
DRUMS = FRONTEND / "music" / "drums"

# Every catalogue rhythm is deliberately assigned to one reviewed musical
# vocabulary.  The accompanying handover records the source and per-rhythm
# result; this map prevents future additions from silently escaping that audit.
AUDIT_FAMILIES = {
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
    "country_waltz": {"country_train", "country_waltz", "waltz"},
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


class DrumMusicalContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.activity = json.loads(
            (DRUMS / "drum_activity_timing.json").read_text(encoding="utf-8")
        )
        cls.fills = json.loads(
            (DRUMS / "drum_fills_timing.json").read_text(encoding="utf-8")
        )
        cls.rhythms = {item["id"]: item for item in cls.activity["rhythms"]}

    @staticmethod
    def _events(rhythm: dict, level: int = 1) -> list[dict]:
        return rhythm["levels"][level - 1]["events"]

    @staticmethod
    def _ticks(events: list[dict], role: str) -> set[int]:
        return {int(event["tick"]) for event in events if event["role"] == role}

    def test_every_rhythm_is_in_exactly_one_source_review_family(self) -> None:
        assigned = [rhythm for group in AUDIT_FAMILIES.values() for rhythm in group]
        self.assertEqual(len(assigned), len(set(assigned)))
        self.assertEqual(set(assigned), set(self.rhythms))

    def test_all_activity_levels_are_complete_cumulative_grooves(self) -> None:
        for rhythm in self.rhythms.values():
            prior: set[tuple[int, str]] = set()
            for level in rhythm["levels"]:
                events = level["events"]
                current = {(int(event["tick"]), str(event["role"])) for event in events}
                self.assertTrue(prior <= current, (rhythm["id"], level["level"]))
                self.assertEqual(level["event_count"], len(events))
                self.assertLessEqual(len(events), 56, (rhythm["id"], level["level"]))
                prior = current

    def test_no_two_complete_activity_catalogues_are_identical(self) -> None:
        signatures: dict[tuple[object, ...], str] = {}
        for rhythm in self.rhythms.values():
            signature = tuple(
                (
                    int(event["tick"]),
                    str(event["role"]),
                    int(event["velocity"]),
                )
                for level in rhythm["levels"]
                for event in level["events"]
            )
            prior = signatures.setdefault(signature, rhythm["id"])
            self.assertEqual(prior, rhythm["id"], (prior, rhythm["id"]))

    def test_conventional_backbeat_and_four_on_floor_foundations(self) -> None:
        for rhythm_id in AUDIT_FAMILIES["pop"] | {"march"}:
            rhythm = self.rhythms[rhythm_id]
            events = self._events(rhythm)
            period = int(rhythm["period_ticks"])
            for bar in range(int(rhythm["period_bars"])):
                offset = bar * (period // int(rhythm["period_bars"]))
                backbeats = self._ticks(events, "backbeat_primary") | self._ticks(
                    events, "backbeat_soft"
                )
                self.assertTrue({offset + 96, offset + 288} <= backbeats, rhythm_id)
                self.assertIn(offset, self._ticks(events, "low_primary"), rhythm_id)

        polka = self._events(self.rhythms["polka"])
        self.assertEqual(self._ticks(polka, "backbeat_primary"), {96, 288})
        self.assertEqual(self._ticks(polka, "low_primary"), {0, 192})

        for rhythm_id in AUDIT_FAMILIES["electronic"]:
            events = self._events(self.rhythms[rhythm_id])
            self.assertEqual(self._ticks(events, "low_primary"), {0, 96, 192, 288})
            self.assertEqual(self._ticks(events, "backbeat_primary"), {96, 288})
            self.assertEqual(self._ticks(events, "timekeeper_primary"), {48, 144, 240, 336})

    def test_swing_jazz_and_halftime_foundations_keep_their_feel(self) -> None:
        for rhythm_id in {"shuffle", "jazz_shuffle", "soul_shuffle"}:
            events = self._events(self.rhythms[rhythm_id])
            keeper = self._ticks(events, "timekeeper_primary") | self._ticks(
                events, "sustain_primary"
            )
            self.assertTrue(any(tick % 96 == 64 for tick in keeper), rhythm_id)

        for rhythm_id in {"six_eight_ballad", "gospel_6_8", "twelve_eight_blues"}:
            rhythm = self.rhythms[rhythm_id]
            numerator, denominator = (int(value) for value in rhythm["meter"].split("/", 1))
            self.assertEqual(denominator, 8)
            self.assertIn(numerator, {6, 12})
            self.assertTrue(self._ticks(self._events(rhythm), "timekeeper_primary"))

        for rhythm_id in AUDIT_FAMILIES["jazz"]:
            events = self._events(self.rhythms[rhythm_id])
            self.assertTrue(self._ticks(events, "sustain_primary"), rhythm_id)
            self.assertTrue(self._ticks(events, "timekeeper_foot"), rhythm_id)

        for rhythm_id in {"dubstep", "trap"}:
            events = self._events(self.rhythms[rhythm_id])
            period = int(self.rhythms[rhythm_id]["period_ticks"])
            expected = {offset + 192 for offset in range(0, period, 384)}
            self.assertEqual(self._ticks(events, "backbeat_primary"), expected)

    def test_latin_timeline_reggae_and_odd_meter_identities(self) -> None:
        son = self._events(self.rhythms["son_clave_3_2"])
        rumba = self._events(self.rhythms["rumba_clave_3_2"])
        self.assertEqual(self._ticks(son, "timeline_primary"), {0, 144, 288, 480, 576})
        self.assertEqual(self._ticks(rumba, "timeline_primary"), {0, 144, 336, 480, 576})

        for rhythm_id in AUDIT_FAMILIES["latin"]:
            roles = {event["role"] for event in self._events(self.rhythms[rhythm_id])}
            minimum = 2 if rhythm_id in {"son_clave_3_2", "rumba_clave_3_2"} else 3
            self.assertGreaterEqual(len(roles), minimum, rhythm_id)

        reggae = self._events(self.rhythms["reggae"])
        self.assertEqual(self._ticks(reggae, "low_primary"), {192, 576})
        self.assertEqual(self._ticks(reggae, "backbeat_primary"), {192, 576})

        expected_group_starts = {
            "five_four": ({0, 288}, 480),
            "seven_eight": ({0, 96, 192}, 336),
            "nine_eight": ({0, 96, 192, 288}, 432),
            "eleven_eight": ({0, 144, 288, 432}, 528),
        }
        for rhythm_id, (starts, period) in expected_group_starts.items():
            rhythm = self.rhythms[rhythm_id]
            events = self._events(rhythm)
            anchors = self._ticks(events, "timekeeper_primary") | self._ticks(
                events, "low_primary"
            ) | self._ticks(events, "backbeat_primary")
            self.assertEqual(int(rhythm["period_ticks"]), period)
            self.assertTrue(starts <= anchors, rhythm_id)

    def test_every_fill_is_phrase_ending_and_metadata_is_consistent(self) -> None:
        for fill in self.fills["fills"]:
            numerator, denominator = (int(value) for value in fill["meter"].split("/", 1))
            beat_ticks = 96 * 4 // denominator
            duration_ticks = int(fill["timing"]["duration_ticks"])
            duration_beats = duration_ticks // beat_ticks
            self.assertEqual(duration_ticks % beat_ticks, 0, fill["fill_id"])
            self.assertEqual(fill["duration_beats"], duration_beats, fill["fill_id"])
            self.assertEqual(fill["timing"]["duration_beats"], duration_beats, fill["fill_id"])
            self.assertEqual(fill["duration_quarter_notes"], duration_ticks / 96, fill["fill_id"])
            self.assertEqual(fill["leading_rest"]["ticks"], fill["timing"]["leading_rest_ticks"], fill["fill_id"])
            self.assertEqual(fill["allowed_start_beats"], [numerator - duration_beats + 1], fill["fill_id"])
            self.assertEqual(
                (fill["allowed_start_beats"][0] - 1) * beat_ticks + duration_ticks,
                numerator * beat_ticks,
                fill["fill_id"],
            )

    def test_each_rhythm_has_five_distinct_fill_contours(self) -> None:
        by_rhythm: dict[str, list[dict]] = {}
        for fill in self.fills["fills"]:
            by_rhythm.setdefault(fill["rhythm_id"], []).append(fill)
        for rhythm_id, fills in by_rhythm.items():
            signatures = {
                (
                    int(fill["timing"]["duration_ticks"]),
                    tuple(sorted({int(event["tick"]) for event in fill["timing"]["events"]})),
                )
                for fill in fills
            }
            self.assertEqual(len(fills), 5, rhythm_id)
            self.assertEqual(len(signatures), 5, rhythm_id)

    def test_fill_velocity_balance_retains_dynamic_shape(self) -> None:
        velocities = [
            int(event["velocity"])
            for fill in self.fills["fills"]
            for event in fill["timing"]["events"]
        ]
        self.assertLessEqual(max(velocities), 103)
        self.assertLessEqual(statistics.median(velocities), 85)
        self.assertGreaterEqual(len(set(velocities)), 40)
        for fill in self.fills["fills"]:
            values = {int(event["velocity"]) for event in fill["timing"]["events"]}
            self.assertGreaterEqual(len(values), 2, fill["fill_id"])

    def test_every_fill_cites_the_authoritative_review_sources(self) -> None:
        sources = {source["id"]: source for source in self.fills["sources"]}
        for source_id in (
            "src_yamaha_fill_arrangement",
            "src_berklee_drum_performance",
            "src_berklee_afro_latin",
            "src_ableton_beat_programming",
        ):
            self.assertIn(source_id, sources)
            self.assertTrue(sources[source_id]["url"].startswith("https://"))
        for fill in self.fills["fills"]:
            refs = set(fill["source_refs"])
            self.assertTrue(refs <= set(sources), fill["fill_id"])
            self.assertIn("src_yamaha_fill_arrangement", refs, fill["fill_id"])
            self.assertIn("src_berklee_drum_performance", refs, fill["fill_id"])
            if fill.get("generation", {}).get("style_family") == "latin":
                self.assertIn("src_berklee_afro_latin", refs, fill["fill_id"])


if __name__ == "__main__":
    unittest.main()
