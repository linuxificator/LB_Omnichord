from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from musical_sequence_plan import (  # noqa: E402
    compile_bass_lane,
    compile_chord_lane,
    compile_drum_lane,
)
from sc_drum_kits import resolve_hit  # noqa: E402
from sc_music_catalog import load_sc_music_catalog  # noqa: E402


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
            ["noteOn", "voiceSet", "voiceSet", "voiceSet", "noteOff"],
        )
        self.assertEqual(child.events[0].atoms[8], 1)
        self.assertEqual(child.events[1].atoms[1], "frequency_hz")
        self.assertEqual(child.events[2].atoms[1], "accent_amount")
        self.assertEqual(child.events[3].atoms[1], "accent")

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

    def test_dense_bass_activity_has_bounded_stable_source_identity(self) -> None:
        config = {
            "id": "dense-source-identity",
            "length_beats": 16,
            "bass_mode": "activity",
            "bass_activity": 4,
            "bass_events": [
                {"time": index * 0.5, "degree": index, "amp": 0.7}
                for index in range(32)
            ],
        }
        arguments = dict(
            config=config,
            running=True,
            bass_notes=(36.0, 40.0, 43.0, 47.0, 50.0),
            bass_gate_beats=0.3,
            program_id="sc.sclork.fmBass",
            program_revision=1,
            logical_bus=1,
            generation=1,
        )

        first = compile_bass_lane(**arguments)
        second = compile_bass_lane(**arguments)

        identities = [item.source_identity for item in first.definitions]
        self.assertEqual(
            identities,
            [item.source_identity for item in second.definitions],
        )
        self.assertTrue(identities)
        self.assertTrue(all(identity.startswith("bass:") for identity in identities))
        self.assertTrue(
            all(1 <= len(identity.encode("utf-8")) <= 192 for identity in identities)
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

    def test_seven_note_arpeggios_preserve_every_rate_direction_and_overlap(self) -> None:
        notes = (48.0, 52.0, 55.0, 59.0, 62.0, 65.0, 69.0)
        for rate in range(1, 5):
            for direction in ("up", "down"):
                with self.subTest(rate=rate, direction=direction):
                    plan = compile_chord_lane(
                        config={
                            "id": "overlapping-seven",
                            "length_beats": 1,
                            "chord_events": [
                                {"time": 0, "amp": 0.8},
                                {"time": 0.5, "amp": 0.8},
                            ],
                            "chord_arpeggio": {
                                "enabled": True,
                                "notes_per_beat": rate,
                                "direction": direction,
                            },
                        },
                        enabled=True,
                        chord_notes=notes,
                        max_chord_notes=7,
                        chord_gate_beats=0.72,
                        program_id="test.program",
                        program_revision=1,
                        logical_bus=3,
                        generation=1,
                    )
                    root, child = plan.definitions
                    step = max(1, round(48 / rate))
                    attacks = [
                        event for event in child.events if event.kind == "noteOn"
                    ]
                    self.assertEqual(
                        [event.tick for event in attacks],
                        [index * step for index in range(7)],
                    )
                    expected_notes = notes if direction == "up" else notes[::-1]
                    self.assertEqual(
                        [event.atoms[4] for event in attacks],
                        [round(note) for note in expected_notes],
                    )
                    self.assertEqual(
                        [event.tick for event in root.events], [0, 24]
                    )
                    self.assertEqual(
                        [event.atoms[0] for event in root.events],
                        [child.definition_id, child.definition_id],
                    )
                    self.assertGreater(
                        max(event.tick for event in child.events),
                        root.events[1].tick,
                    )

    def test_drum_timing_uses_floor_conversion_and_fills_are_finite(self) -> None:
        catalog = load_sc_music_catalog(
            ROOT / "music" / "sc_expansion" / "sc_kit_grooves_v1.json"
        )
        config = {
            "id": "funk",
            "percussion_activity": 1,
            "fill_order": [4],
            "fill_density_bars": 2,
        }
        plan = compile_drum_lane(
            config=config,
            catalog=catalog,
            kit="pcm-vsco",
            logical_bus=0,
            generation=1,
            program_resolver=resolve_hit,
        )
        arrangement = catalog.arrangement("pcm-vsco", "funk")
        gate_key = sorted(event.gate_key for event in arrangement.levels[0])[0]
        activity = next(
            definition
            for definition in plan.definitions
            if definition.definition_id == f"drums/activity/{gate_key}"
        )
        source_ticks = [
            event.tick // 2
            for event in arrangement.levels[0]
            if event.gate_key == gate_key
        ]
        self.assertEqual([event.tick for event in activity.events], source_ticks)
        fill = next(
            definition
            for definition in plan.definitions
            if definition.definition_id
            == "drums/fill/5/"
            + str(catalog.fills("pcm-vsco", "funk")[4].allowed_start_beats[0])
        )
        self.assertEqual(fill.kind, "finite")
        self.assertTrue(any(event.kind == "gateBegin" for event in fill.events))
        self.assertTrue(any(event.kind == "drumHit" for event in fill.events))

    def test_drum_resolver_applies_program_and_clamps_final_velocity(self) -> None:
        catalog = load_sc_music_catalog(
            ROOT / "music" / "sc_expansion" / "sc_kit_grooves_v1.json"
        )
        plan = compile_drum_lane(
            config={
                "id": "funk",
                "percussion_activity": 5,
                "fill_order": [2],
                "fill_density_bars": 1,
            },
            catalog=catalog,
            kit="pcm-vsco",
            logical_bus=2,
            generation=4,
            program_resolver=lambda _kit, role: (f"sc.test.{role}", role, 2.5),
        )
        hits = [
            event
            for definition in plan.definitions
            for event in definition.events
            if event.kind == "drumHit"
        ]
        self.assertTrue(hits)
        self.assertTrue(all(str(event.atoms[2]).startswith("sc.test.") for event in hits))
        self.assertTrue(all(0.0 <= float(event.atoms[6]) <= 1.0 for event in hits))


if __name__ == "__main__":
    unittest.main()
