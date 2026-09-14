from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from app_core import load_chords, load_rhythm_catalog  # noqa: E402
from bass_riffs import load_bass_riff_catalog  # noqa: E402
from bass_voice_capabilities import CAPABILITIES, capability_for  # noqa: E402
from musical_sequence_plan import compile_bass_lane  # noqa: E402


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
                (event["tick"], event["pitch_offset_semitones_from_C2"])
                for event in row["timing"]["events"]
            ]
            actual = [(event.tick, event.pitch_offset) for event in revised.events]
            self.assertEqual(actual, expected, revised.riff_id)

    def test_capabilities_are_explicit_and_unknown_programs_detach(self) -> None:
        self.assertGreaterEqual(len(CAPABILITIES), 20)
        self.assertTrue(capability_for("sc.omni.acid303").supports("legato_glide"))
        self.assertTrue(capability_for("sc.sclork.bassWarsaw").supports("tie"))
        self.assertFalse(capability_for("sc.sclork.fmBass").supports("tie"))
        self.assertFalse(capability_for("unknown").supports("legato_glide"))

    @staticmethod
    def _plan(program: str):
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
                            "duration_ticks": 96,
                            "fallback_duration_ticks": 40,
                            "note": 36,
                            "velocity": 88,
                            "accent": False,
                            "accent_amount": 0.0,
                            "slide_to_next": False,
                            "link_to_next": "legato_glide",
                            "glide_time_ms": 70,
                        },
                        {
                            "tick": 96,
                            "duration_ticks": 48,
                            "note": 43,
                            "velocity": 104,
                            "accent": True,
                            "accent_amount": 0.6,
                            "slide_to_next": False,
                            "link_to_next": "none",
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
