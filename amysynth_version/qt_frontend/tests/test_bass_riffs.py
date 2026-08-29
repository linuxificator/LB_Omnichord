from __future__ import annotations

import sys
import unittest
from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[1]
CODE = FRONTEND / "code"
sys.path.insert(0, str(CODE))

from app_core import load_chords, load_rhythm_catalog  # noqa: E402
from bass_riffs import load_bass_riff_catalog, transpose_riff_events  # noqa: E402


class BassRiffCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.chords = load_chords(FRONTEND / "music" / "chords.csv")
        cls.rhythms = load_rhythm_catalog(FRONTEND / "music" / "rhythms.json")
        cls.catalog = load_bass_riff_catalog(
            FRONTEND / "music" / "omnichord_bass_riffs.json",
            rhythm_ids=(rhythm.key for rhythm in cls.rhythms),
            chord_suffixes=(chord.suffix for chord in cls.chords),
        )

    def test_catalog_has_stable_unique_ids_and_full_coverage(self) -> None:
        self.assertEqual(len(self.catalog.riffs), 756)
        self.assertEqual(
            len({riff.index for riff in self.catalog.riffs}),
            len(self.catalog.riffs),
        )
        self.assertEqual(
            len({riff.riff_id for riff in self.catalog.riffs}),
            len(self.catalog.riffs),
        )
        candidate_counts = [
            len(self.catalog.candidates(rhythm.key, chord.suffix))
            for rhythm in self.rhythms
            for chord in self.chords
        ]
        self.assertEqual(min(candidate_counts), 4)
        self.assertEqual(max(candidate_counts), 9)

    def test_every_event_is_ordered_and_inside_its_own_phrase(self) -> None:
        for riff in self.catalog.riffs:
            self.assertEqual(riff.ppq, 96)
            self.assertEqual(riff.normalized_anchor_midi, 36)
            ticks = [event.tick for event in riff.events]
            self.assertEqual(ticks, sorted(ticks), riff.riff_id)
            for event in riff.events:
                self.assertGreaterEqual(event.tick, 0, riff.riff_id)
                self.assertLess(event.tick, riff.phrase_ticks, riff.riff_id)
                self.assertGreater(event.duration_ticks, 0, riff.riff_id)

    def test_transposition_changes_only_pitch(self) -> None:
        riff = self.catalog.by_id("riff_0004_pop_8_root_fifth")
        self.assertIsNotNone(riff)
        assert riff is not None
        c_events = transpose_riff_events(riff, 0)
        e_events = transpose_riff_events(riff, 4)
        self.assertEqual(
            [event["note"] + 4 for event in c_events],
            [event["note"] for event in e_events],
        )
        for key in ("tick", "duration_ticks", "velocity"):
            self.assertEqual(
                [event[key] for event in c_events],
                [event[key] for event in e_events],
            )

    def test_riff_loader_never_depends_on_legacy_bass_levels(self) -> None:
        source = (CODE / "bass_riffs.py").read_text(encoding="utf-8")
        self.assertNotIn("bass_levels", source)


if __name__ == "__main__":
    unittest.main()
