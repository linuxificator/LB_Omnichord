from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from drum_patterns import load_drum_pattern_catalog  # noqa: E402
from musical_sequence_plan import compile_chord_lane, compile_drum_lane  # noqa: E402


class MusicalSequencePlanTests(unittest.TestCase):
    def test_chord_arpeggio_owns_exact_note_handles_and_48_ppq_releases(self) -> None:
        plan = compile_chord_lane(
            config={
                "id": "test",
                "length_beats": 4,
                "chord_events": [{"time": 0, "amp": 0.8}],
                "chord_arpeggio": {
                    "enabled": True,
                    "notes_per_beat": 2,
                    "direction": "up",
                },
            },
            enabled=True,
            chord_notes=(60.0, 64.0, 67.0),
            max_chord_notes=4,
            chord_gate_beats=0.72,
            program_id="test.program",
            program_revision=2,
            logical_bus=3,
            generation=7,
        )
        root, child = plan.definitions
        self.assertEqual(root.period_ticks, 192)
        self.assertEqual([event.tick for event in child.events], [0, 17, 24, 41, 48, 65])
        self.assertEqual(
            [event.atoms[0] for event in child.events if event.kind == "noteOff"],
            ["note/0", "note/1", "note/2"],
        )

    def test_drum_timing_uses_floor_conversion_and_fills_are_finite(self) -> None:
        catalog = load_drum_pattern_catalog(ROOT / "music" / "drums")
        config = {
            "id": "funk",
            "percussion_activity": 1,
            "fill_order": [4],
            "fill_density_bars": 2,
        }
        plan = compile_drum_lane(
            config=config,
            catalog=catalog,
            kit="gamma9001",
            logical_bus=0,
            generation=1,
        )
        activity = next(
            definition
            for definition in plan.definitions
            if definition.definition_id.startswith("drums/activity/")
        )
        source_role = activity.definition_id.rsplit("/", 1)[-1]
        source_ticks = [
            event.tick // 2
            for event in catalog.rhythm("funk").levels[0]
            if event.role == source_role
        ]
        self.assertEqual([event.tick for event in activity.events], source_ticks)
        fill = next(
            definition
            for definition in plan.definitions
            if definition.definition_id.endswith(
                "/" + catalog.rhythm("funk").fills[4].fill_id
            )
        )
        self.assertEqual(fill.kind, "finite")
        self.assertTrue(any(event.kind == "gateBegin" for event in fill.events))
        self.assertTrue(any(event.kind == "drumHit" for event in fill.events))


if __name__ == "__main__":
    unittest.main()
