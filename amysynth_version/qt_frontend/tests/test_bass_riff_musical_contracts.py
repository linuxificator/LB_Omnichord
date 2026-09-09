from __future__ import annotations

import json
import unittest
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any


FRONTEND = Path(__file__).resolve().parents[1]
CATALOGUE = FRONTEND / "music" / "omnichord_bass_riffs.json"


class BassRiffMusicalContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw: dict[str, Any] = json.loads(CATALOGUE.read_text(encoding="utf-8"))
        cls.chords = {
            row["id"]: {int(value) % 12 for value in row["intervals_semitones"]}
            for row in cls.raw["chord_types"]
        }
        cls.scales = {
            row["id"]: {int(value) % 12 for value in row["pitch_classes_semitones"]}
            for row in cls.raw["scale_vocabulary"]
        }

    def test_phrase_timing_matches_meter_and_has_no_overlapping_gates(self) -> None:
        for riff in self.raw["riffs"]:
            numerator, denominator = map(int, riff["meter"].split("/"))
            bars = riff["phrase_bars"]
            timing = riff["timing"]
            self.assertEqual(
                Fraction(timing["phrase_ticks"], timing["ppq"]),
                Fraction(numerator * 4, denominator)
                * Fraction(bars["numerator"], bars["denominator"]),
                riff["riff_id"],
            )
            events = timing["events"]
            self.assertEqual(events[0]["role"], "chord_tone", riff["riff_id"])
            for event, following in zip(events, events[1:]):
                self.assertLess(
                    event["tick"] + event["duration_ticks"],
                    following["tick"],
                    riff["riff_id"],
                )
            self.assertLessEqual(
                events[-1]["tick"] + events[-1]["duration_ticks"],
                timing["phrase_ticks"],
                riff["riff_id"],
            )

    def test_note_roles_are_harmonically_valid_in_every_declared_context(self) -> None:
        for riff in self.raw["riffs"]:
            events = riff["timing"]["events"]
            stable_pitch_classes = {
                int(event["pitch_offset_semitones_from_C2"]) % 12
                for event in events
                if event["role"] != "chromatic_approach"
            }
            for scale_id in riff["compatible_scales"]:
                self.assertLessEqual(
                    stable_pitch_classes,
                    self.scales[scale_id],
                    f"{riff['riff_id']}/{scale_id}",
                )

            for index, event in enumerate(events):
                pitch = int(event["pitch_offset_semitones_from_C2"])
                if event["role"] == "chord_tone":
                    for chord_id in riff["compatible_chords"]:
                        self.assertIn(
                            pitch % 12,
                            self.chords[chord_id],
                            f"{riff['riff_id']}/{chord_id}",
                        )
                    continue
                if event["role"] == "scale_colour":
                    continue

                self.assertLess(index + 1, len(events), riff["riff_id"])
                following = events[index + 1]
                resolution = event["resolution"]
                self.assertEqual(following["tick"], resolution["target_tick"])
                self.assertEqual(
                    following["pitch_offset_semitones_from_C2"],
                    resolution["target_pitch_offset_semitones_from_C2"],
                )
                self.assertEqual(
                    abs(
                        int(following["pitch_offset_semitones_from_C2"])
                        - pitch
                    ),
                    1,
                    riff["riff_id"],
                )
                self.assertLessEqual(following["tick"] - event["tick"], 32)
                self.assertFalse(event["accent"], riff["riff_id"])
                for chord_id in riff["compatible_chords"]:
                    self.assertNotIn(pitch % 12, self.chords[chord_id])
                    self.assertIn(
                        int(following["pitch_offset_semitones_from_C2"]) % 12,
                        self.chords[chord_id],
                    )

    def test_activity_ranks_increase_density_without_losing_variety(self) -> None:
        contexts: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for riff in self.raw["riffs"]:
            for rhythm_id in riff["compatible_rhythms"]:
                for chord_id in riff["compatible_chords"]:
                    contexts[(rhythm_id, chord_id)].append(riff)

        self.assertEqual(len(contexts), 54 * 36)
        for context, riffs in contexts.items():
            counts: list[int] = []
            contours: set[tuple[tuple[int, int], ...]] = set()
            for rank in range(1, 6):
                ranked = [riff for riff in riffs if riff["activity_rank"] == rank]
                self.assertTrue(ranked, f"{context}/rank={rank}")
                note_counts = {len(riff["timing"]["events"]) for riff in ranked}
                self.assertEqual(len(note_counts), 1, f"{context}/rank={rank}")
                counts.append(note_counts.pop())
            self.assertTrue(
                all(left < right for left, right in zip(counts, counts[1:])),
                f"{context}/{counts}",
            )
            for riff in riffs:
                contours.add(
                    tuple(
                        (
                            int(event["tick"]),
                            int(event["pitch_offset_semitones_from_C2"]),
                        )
                        for event in riff["timing"]["events"]
                    )
                )
            self.assertGreaterEqual(len(contours), 5, str(context))

    def test_chromatic_approaches_avoid_strong_four_four_beats(self) -> None:
        for riff in self.raw["riffs"]:
            if riff["meter"] != "4/4":
                continue
            for event in riff["timing"]["events"]:
                if event["role"] == "chromatic_approach":
                    self.assertNotIn(
                        int(event["tick"]) % (4 * int(riff["timing"]["ppq"])),
                        {0, 2 * int(riff["timing"]["ppq"])},
                        riff["riff_id"],
                    )


if __name__ == "__main__":
    unittest.main()
