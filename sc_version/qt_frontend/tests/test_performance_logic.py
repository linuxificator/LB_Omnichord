from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE_DIR = ROOT / "code"
sys.path.insert(0, str(CODE_DIR))

from performance_logic import (  # noqa: E402
    clamp_bass_voicing_shift,
    roll_bass_voicing,
    roll_chord_indexes,
)


class PerformanceLogicTests(unittest.TestCase):
    def test_bass_voicing_walks_adjacent_inversions(self) -> None:
        chord = [48, 52, 55]  # C3 E3 G3
        self.assertEqual(roll_bass_voicing(chord, 0), [48, 52, 55])
        self.assertEqual(roll_bass_voicing(chord, -1), [43, 48, 52])
        self.assertEqual(roll_bass_voicing(chord, 1), [52, 55, 60])
        self.assertEqual(roll_bass_voicing(chord, -2), [40, 43, 48])
        self.assertEqual(roll_bass_voicing(chord, 2), [55, 60, 64])

    def test_bass_voicing_preserves_pitch_classes(self) -> None:
        original = [48, 52, 55, 58]
        for shift in range(-6, 7):
            rolled = roll_bass_voicing(original, shift)
            self.assertEqual(
                sorted(note % 12 for note in rolled),
                sorted(note % 12 for note in original),
            )
            self.assertEqual(len(rolled), len(original))
            self.assertEqual(rolled, sorted(rolled))

    def test_bass_voicing_shift_is_integer_and_bounded(self) -> None:
        self.assertEqual(clamp_bass_voicing_shift(-99), -6)
        self.assertEqual(clamp_bass_voicing_shift(99), 6)
        self.assertEqual(clamp_bass_voicing_shift(1.49), 1)
        self.assertEqual(clamp_bass_voicing_shift(1.51), 2)

    def test_chord_row_roll_matches_requested_down_example(self) -> None:
        # chords.csv indexes:
        # minor=1, 5=6, 7_sus4=20, major13=28
        # diminished=2, major6=7, dominant9=21, minor13=29
        self.assertEqual(
            roll_chord_indexes([1, 6, 20, 28], 36, 1),
            [2, 7, 21, 29],
        )

    def test_chord_row_roll_wraps_both_directions(self) -> None:
        self.assertEqual(roll_chord_indexes([0, 35], 36, -1), [35, 34])
        self.assertEqual(roll_chord_indexes([0, 35], 36, 1), [1, 0])


if __name__ == "__main__":
    unittest.main()
