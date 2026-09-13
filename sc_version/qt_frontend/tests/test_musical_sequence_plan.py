from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from drum_patterns import load_drum_pattern_catalog  # noqa: E402
from musical_sequence_plan import (  # noqa: E402
    compile_bass_lane,
    compile_chord_lane,
    compile_drum_lane,
)


class MusicalSequencePlanTests(unittest.TestCase):
    def test_bass_slide_updates_owned_voice_without_retrigger(self) -> None:
        plan = compile_bass_lane(
            config={
                "id": "test",
                "length_beats": 4,
                "bass_mode": "riff",
                "bass_riff": {
                    "id": "acid",
                    "ppq": 96,
                    "phrase_ticks": 384,
                    "events": [
                        {
                            "tick": 0,
                            "duration_ticks": 96,
                            "note": 36,
                            "velocity": 100,
                            "accent": True,
                            "slide_to_next": True,
                        },
                        {
                            "tick": 48,
                            "duration_ticks": 48,
                            "note": 43,
                            "velocity": 90,
                            "accent": True,
                            "slide_to_next": False,
                        },
                    ],
                },
            },
            running=True,
            bass_notes=(36.0,),
            bass_gate_beats=0.3,
            program_id="sc.omni.acid303",
            program_revision=3,
            logical_bus=1,
            generation=2,
        )
        root, child = plan.definitions
        self.assertEqual(root.period_ticks, 192)
        self.assertEqual(
            [event.kind for event in child.events],
            ["noteOn", "voiceSet", "voiceSet", "noteOff"],
        )
        self.assertEqual(child.events[0].atoms[8], 1)
        self.assertEqual(child.events[1].atoms[1], "frequency_hz")
        self.assertEqual(child.events[2].atoms[1], "accent")

    def test_non_acid_bass_ignores_acid_articulation_flags(self) -> None:
        plan = compile_bass_lane(
            config={
                "id": "test",
                "length_beats": 4,
                "bass_mode": "riff",
                "bass_riff": {
                    "id": "not-acid",
                    "ppq": 96,
                    "phrase_ticks": 384,
                    "events": [
                        {
                            "tick": 0,
                            "duration_ticks": 96,
                            "note": 36,
                            "velocity": 100,
                            "accent": True,
                            "slide_to_next": True,
                        },
                        {
                            "tick": 48,
                            "duration_ticks": 48,
                            "note": 43,
                            "velocity": 90,
                            "accent": True,
                            "slide_to_next": False,
                        },
                    ],
                },
            },
            running=True,
            bass_notes=(36.0,),
            bass_gate_beats=0.3,
            program_id="sc.sclork.fmBass",
            program_revision=1,
            logical_bus=1,
            generation=1,
        )
        child = plan.definitions[1]
        self.assertEqual(
            [event.kind for event in child.events],
            ["noteOn", "noteOn", "noteOff", "noteOff"],
        )
        self.assertFalse(any(event.kind == "voiceSet" for event in child.events))
        self.assertTrue(
            all(
                event.atoms[8] == 0
                for event in child.events
                if event.kind == "noteOn"
            )
        )

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
