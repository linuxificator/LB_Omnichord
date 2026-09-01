from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from musical_state import (  # noqa: E402
    TuningSnapshot,
    chord_snapshot,
    freeze_intonation_tables,
    intonation_factor,
    tune_note,
)


class MusicalStateTests(unittest.TestCase):
    def test_equal_temperament_reference_and_bend_are_clamped(self) -> None:
        self.assertAlmostEqual(tune_note(TuningSnapshot("EQ", 440.0), 60), 60.0)
        high = TuningSnapshot("EQ", 460.0, bend_offset_hz=20.0)
        self.assertEqual(high.effective_reference_hz, 466.0)
        self.assertAlmostEqual(
            tune_note(high, 69),
            69 + 12 * math.log2(466.0 / 440.0),
        )

    def test_key_dependent_intonation_uses_rounded_note_pitch_class(self) -> None:
        unity = tuple(tuple(1.0 for _ in range(12)) for _ in range(12))
        altered = [list(row) for row in unity]
        altered[2][1] = 16.0 / 15.0
        tables = freeze_intonation_tables({"HARM": altered})
        snapshot = TuningSnapshot("HARM", 440.0, intonation_tables=tables)
        self.assertEqual(intonation_factor(snapshot, 2, 60.51), 16.0 / 15.0)
        self.assertAlmostEqual(
            tune_note(snapshot, 60.51, 2),
            60.51 + 12 * math.log2(16.0 / 15.0),
        )
        self.assertEqual(intonation_factor(snapshot, None, 60.51), 1.0)

    def test_chord_snapshot_is_immutable_identity_and_voicing_context(self) -> None:
        active = chord_snapshot(
            active_row=1,
            active_root_semitone=2,
            row_chord_indexes=(0, 1),
            suffixes=("", "m7"),
            intervals=((0, 4, 7), (0, 3, 7, 10)),
        )
        self.assertTrue(active.active)
        self.assertEqual(active.suffix, "m7")
        self.assertEqual(active.pitch_classes, frozenset({0, 2, 5, 9}))
        inactive = chord_snapshot(
            active_row=-1,
            active_root_semitone=-1,
            row_chord_indexes=(),
            suffixes=(),
            intervals=(),
        )
        self.assertFalse(inactive.active)
        self.assertEqual(inactive.pitch_classes, frozenset({0, 4, 7}))

    def test_midi_tuning_uses_public_snapshot_not_omni_private_fields(self) -> None:
        source = (ROOT / "code" / "midi_player.py").read_text(encoding="utf-8")
        context_start = source.index("def _chord_context(")
        context_end = source.index("def process_midi_note(", context_start)
        context = source[context_start:context_end]
        self.assertIn("performance_snapshot()", context)
        for private in (
            "owner._active_row",
            "owner._active_root_semitone",
            "owner._chords",
            "owner._row_chord_indexes",
            "owner._intonation_tables",
        ):
            self.assertNotIn(private, context)


if __name__ == "__main__":
    unittest.main()
