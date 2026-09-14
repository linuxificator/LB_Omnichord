from __future__ import annotations

import json
import hashlib
from dataclasses import asdict
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from app_core import load_chords, load_rhythm_catalog  # noqa: E402
from bass_riffs import load_bass_riff_catalog  # noqa: E402
from bass_voice_capabilities import CAPABILITIES, capability_for  # noqa: E402
from musical_sequence_plan import compile_bass_lane  # noqa: E402
from sc_bass_articulation import load_sc_bass_articulation  # noqa: E402
from sc_music_catalog import load_sc_music_catalog  # noqa: E402


class ScBassExpansionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        rhythms = load_rhythm_catalog(ROOT / "music" / "rhythms.json")
        chords = load_chords(ROOT / "music" / "chords.csv")
        cls.catalog = load_bass_riff_catalog(
            ROOT / "music" / "sc_expansion" / "omnichord_bass_riffs_v2.json",
            rhythm_ids=[item.key for item in rhythms],
            chord_suffixes=[item.suffix for item in chords],
        )
        cls.context_path = (
            ROOT / "music" / "sc_expansion" / "sc_bass_contexts_v1.json"
        )
        cls.articulation = load_sc_bass_articulation(cls.context_path)
        cls.drums = load_sc_music_catalog(
            ROOT / "music" / "sc_expansion" / "sc_kit_grooves_v1.json"
        )

    def test_revised_catalogue_preserves_every_original_onset_and_pitch(self) -> None:
        original = json.loads(
            (ROOT / "music" / "omnichord_bass_riffs.json").read_text(encoding="utf-8")
        )
        by_id = {riff.riff_id: riff for riff in self.catalog.riffs}
        self.assertEqual(len(by_id), 1664)
        self.assertEqual(set(by_id), {str(row["riff_id"]) for row in original["riffs"]})
        for row in original["riffs"]:
            revised = by_id[str(row["riff_id"])]
            expected = [
                (
                    event["tick"],
                    event["duration_ticks"],
                    event["pitch_offset_semitones_from_C2"],
                    event["role"],
                    event["velocity"],
                    event["accent"],
                    event["slide_to_next"],
                )
                for event in row["timing"]["events"]
            ]
            actual = [
                (
                    event.tick,
                    event.duration_ticks,
                    event.pitch_offset,
                    event.role,
                    event.velocity,
                    event.accent,
                    event.slide_to_next,
                )
                for event in revised.events
            ]
            self.assertEqual(actual, expected, revised.riff_id)

    def test_all_contexts_match_reviewed_reference_resolutions(self) -> None:
        raw = json.loads(self.context_path.read_text(encoding="utf-8"))
        self.assertEqual(self.articulation.context_count, 810)
        self.assertEqual(len(raw["contexts"]), 810)
        for context in raw["contexts"]:
            reference = context["reference"]
            riff = self.catalog.by_id(reference["riff_id"])
            self.assertIsNotNone(riff)
            assert riff is not None
            original = tuple(riff.events)
            resolved = self.articulation.resolve(
                riff,
                kit_id=context["kit_id"],
                rhythm_id=context["rhythm_id"],
                percussion_activity=reference["percussion_activity"],
                drum_catalog=self.drums,
            )
            payload = json.dumps(
                [asdict(event) for event in resolved.events],
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            with self.subTest(context=(context["kit_id"], context["rhythm_id"])):
                self.assertEqual(hashlib.sha256(payload).hexdigest(), reference["events_sha256"])
                self.assertEqual(riff.events, original)
                self.assertEqual(
                    resolved,
                    self.articulation.resolve(
                        riff,
                        kit_id=context["kit_id"],
                        rhythm_id=context["rhythm_id"],
                        percussion_activity=reference["percussion_activity"],
                        drum_catalog=self.drums,
                    ),
                )

    def test_every_context_and_rank_resolves_without_changing_harmony(self) -> None:
        raw = json.loads(self.context_path.read_text(encoding="utf-8"))
        for context in raw["contexts"]:
            for rank in range(1, 6):
                riff = self.catalog.choose(context["rhythm_id"], "major", rank)
                self.assertIsNotNone(riff)
                assert riff is not None
                resolved = self.articulation.resolve(
                    riff,
                    kit_id=context["kit_id"],
                    rhythm_id=context["rhythm_id"],
                    percussion_activity=rank,
                    drum_catalog=self.drums,
                )
                with self.subTest(
                    kit=context["kit_id"], rhythm=context["rhythm_id"], rank=rank
                ):
                    self.assertEqual(
                        [(event.tick, event.pitch_offset) for event in resolved.events],
                        [(event.tick, event.pitch_offset) for event in riff.events],
                    )
                    self.assertIn(
                        "none",
                        {event.link_to_next for event in resolved.events},
                        "a bass phrase must retain a finite release boundary",
                    )
                    for index, event in enumerate(resolved.events):
                        next_event = resolved.events[(index + 1) % len(resolved.events)]
                        gap = (next_event.tick - event.tick) % resolved.phrase_ticks
                        gap = gap or resolved.phrase_ticks
                        self.assertLessEqual(event.duration_ticks, gap)
                        if event.link_to_next == "tie":
                            self.assertEqual(event.pitch_offset, next_event.pitch_offset)
                        if event.link_to_next != "none":
                            self.assertEqual(
                                event.link_target_index,
                                (index + 1) % len(resolved.events),
                            )

    def test_capabilities_are_explicit_and_unknown_programs_detach(self) -> None:
        self.assertGreaterEqual(len(CAPABILITIES), 20)
        self.assertTrue(capability_for("sc.omni.acid303").supports("legato_glide"))
        self.assertTrue(capability_for("sc.sclork.bassWarsaw").supports("tie"))
        self.assertFalse(capability_for("sc.sclork.fmBass").supports("tie"))
        self.assertFalse(capability_for("unknown").supports("legato_glide"))

    @staticmethod
    def _plan(
        program: str,
        *,
        link: str = "legato_glide",
        second_note: int = 43,
        second_link: str = "none",
        first_duration_ticks: int = 96,
    ):
        return compile_bass_lane(
            config={
                "id": "test",
                "bass_mode": "riff",
                "bass_riff": {
                    "id": "linked",
                    "ppq": 96,
                    "phrase_ticks": 384,
                    "events": [
                        {
                            "tick": 0,
                            "duration_ticks": first_duration_ticks,
                            "fallback_duration_ticks": 40,
                            "note": 36,
                            "velocity": 88,
                            "accent": False,
                            "accent_amount": 0.0,
                            "slide_to_next": False,
                            "link_to_next": link,
                            "glide_time_ms": 70,
                        },
                        {
                            "tick": 96,
                            "duration_ticks": 48,
                            "note": second_note,
                            "velocity": 104,
                            "accent": True,
                            "accent_amount": 0.6,
                            "slide_to_next": False,
                            "link_to_next": second_link,
                        },
                    ],
                },
            },
            running=True,
            bass_notes=(36.0,),
            bass_gate_beats=0.3,
            program_id=program,
            program_revision=1,
            logical_bus=1,
            generation=1,
        )

    def test_gated_native_voice_glides_without_retrigger_or_fake_accent(self) -> None:
        child = self._plan("sc.sclork.bassWarsaw").definitions[1]
        attacks = [event for event in child.events if event.kind == "noteOn"]
        controls = [event.atoms[1] for event in child.events if event.kind == "voiceSet"]
        self.assertEqual(len(attacks), 1)
        self.assertEqual(controls, ["glide_time_ms", "frequency_hz"])

    def test_owned_accent_is_applied_at_the_slide_destination(self) -> None:
        child = self._plan("sc.omni.acid303").definitions[1]
        attacks = [event for event in child.events if event.kind == "noteOn"]
        destination = [
            event
            for event in child.events
            if event.tick == 48 and event.kind == "voiceSet"
        ]
        self.assertEqual(len(attacks), 1)
        self.assertEqual(
            [event.atoms[1] for event in destination],
            [
                "glide_time_ms",
                "frequency_hz",
                "accent_amount",
                "accent",
            ],
        )
        self.assertEqual(float(destination[0].atoms[2]), 70.0)
        self.assertGreater(float(destination[1].atoms[2]), 0.0)
        self.assertEqual(float(destination[2].atoms[2]), 0.6)
        self.assertEqual(float(destination[3].atoms[2]), 1.0)
        self.assertEqual(
            [event.kind for event in child.events].count("noteOff"),
            1,
        )

    def test_same_pitch_tie_reuses_gate_without_pitch_or_attack_event(self) -> None:
        child = self._plan(
            "sc.sclork.bassWarsaw", link="tie", second_note=36
        ).definitions[1]
        self.assertEqual(
            [event.kind for event in child.events],
            ["noteOn", "noteOff"],
        )

    def test_a_real_pause_splits_owned_notes_into_separate_gestures(self) -> None:
        plan = self._plan(
            "sc.omni.acid303",
            link="none",
            first_duration_ticks=80,
        )
        children = plan.definitions[1:]
        self.assertEqual(len(children), 2)
        self.assertTrue(
            all(
                [event.kind for event in child.events] == ["noteOn", "noteOff"]
                for child in children
            )
        )

    def test_a_closed_wraparound_link_chain_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "silent handover"):
            self._plan("sc.omni.acid303", second_link="legato_glide")

    def test_incapable_voice_uses_detached_fallback_and_retriggers(self) -> None:
        children = self._plan("sc.sclork.fmBass").definitions[1:]
        attacks = [
            event for child in children for event in child.events if event.kind == "noteOn"
        ]
        releases = [
            event for child in children for event in child.events if event.kind == "noteOff"
        ]
        self.assertEqual(len(attacks), 2)
        self.assertEqual(len(releases), 2)
        self.assertEqual(releases[0].tick, 20)
        self.assertFalse(
            any(event.kind == "voiceSet" for child in children for event in child.events)
        )


if __name__ == "__main__":
    unittest.main()
