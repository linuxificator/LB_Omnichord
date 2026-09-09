from __future__ import annotations

import ast
import json
import sys
import unittest
from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[1]
CODE = FRONTEND / "code"
sys.path.insert(0, str(CODE))

from app_core import load_chords, load_rhythm_catalog  # noqa: E402
from bass_riffs import load_bass_riff_catalog, transpose_riff_events  # noqa: E402
from rhythm_command_plan import (  # noqa: E402
    compile_bass_events,
    compile_sequence_definition,
)
from tb303 import Tb303Parameters  # noqa: E402
from wire_frames import MAX_WIRE_REQUEST_BYTES, validate_wire_request  # noqa: E402


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
        self.assertEqual(len(self.catalog.riffs), 1664)
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
        self.assertEqual(min(candidate_counts), 5)
        self.assertEqual(max(candidate_counts), 10)
        for rhythm in self.rhythms:
            for chord in self.chords:
                self.assertEqual(
                    {
                        riff.activity_rank
                        for riff in self.catalog.candidates(
                            rhythm.key,
                            chord.suffix,
                        )
                    },
                    {1, 2, 3, 4, 5},
                    f"{rhythm.key}/{chord.suffix}",
                )

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
        riff = self.catalog.by_id("bass_shared_0001")
        self.assertIsNotNone(riff)
        assert riff is not None
        c_events = transpose_riff_events(riff, 0)
        e_events = transpose_riff_events(riff, 4)
        self.assertEqual(
            [event["note"] + 4 for event in c_events],
            [event["note"] for event in e_events],
        )
        for key in (
            "tick",
            "duration_ticks",
            "velocity",
            "accent",
            "slide_to_next",
        ):
            self.assertEqual(
                [event[key] for event in c_events],
                [event[key] for event in e_events],
            )

    def test_articulation_flags_survive_validated_loading(self) -> None:
        accented = next(
            event
            for riff in self.catalog.riffs
            for event in riff.events
            if event.accent
        )
        sliding = next(
            event
            for riff in self.catalog.riffs
            for event in riff.events
            if event.slide_to_next
        )
        self.assertIs(accented.accent, True)
        self.assertIs(sliding.slide_to_next, True)

        riff = next(
            riff
            for riff in self.catalog.riffs
            if any(event.accent or event.slide_to_next for event in riff.events)
        )
        transposed = transpose_riff_events(riff, 11)
        self.assertEqual(
            [(event.accent, event.slide_to_next) for event in riff.events],
            [(event["accent"], event["slide_to_next"]) for event in transposed],
        )

    def test_rank_selection_uses_weight_and_can_retain_compatible_identity(
        self,
    ) -> None:
        preferred = self.catalog.choose("disco", "minor6", 5)
        self.assertIsNotNone(preferred)
        assert preferred is not None
        self.assertEqual(preferred.riff_id, "bass_shared_0725")

        retained = self.catalog.choose(
            "disco",
            "minor6",
            5,
            preserve_riff_id="bass_shared_0726",
        )
        self.assertIsNotNone(retained)
        assert retained is not None
        self.assertEqual(retained.riff_id, "bass_shared_0726")

        # Identity never overrides the requested musical activity rank.
        changed_rank = self.catalog.choose(
            "disco",
            "minor6",
            4,
            preserve_riff_id="bass_shared_0726",
        )
        self.assertIsNotNone(changed_rank)
        assert changed_rank is not None
        self.assertEqual(changed_rank.activity_rank, 4)

    def test_catalogue_is_c_normalized_and_unique_for_ordinary_basses(self) -> None:
        raw = json.loads(
            (FRONTEND / "music" / "omnichord_bass_riffs.json").read_text(
                encoding="utf-8"
            )
        )
        signatures: set[tuple[object, ...]] = set()
        for row in raw["riffs"]:
            self.assertEqual(row["normalized_root"], "C", row["riff_id"])
            self.assertEqual(row["normalized_anchor_midi"], 36, row["riff_id"])
            timing = row["timing"]
            signature = (
                row["meter"],
                timing["ppq"],
                timing["phrase_ticks"],
                tuple(
                    (
                        event["tick"],
                        event["duration_ticks"],
                        event["pitch_offset_semitones_from_C2"],
                        event["velocity"],
                    )
                    for event in timing["events"]
                ),
            )
            self.assertNotIn(signature, signatures, row["riff_id"])
            signatures.add(signature)

        # Root transposition is the only pitch transformation: every phrase
        # remains in the playable bass register for every chromatic root.
        for riff in self.catalog.riffs:
            for root in range(12):
                events = transpose_riff_events(riff, root)
                self.assertTrue(events, riff.riff_id)
                self.assertTrue(
                    all(0 <= event["note"] <= 127 for event in events),
                    f"{riff.riff_id}/root={root}",
                )

    def test_riff_loader_never_depends_on_legacy_bass_levels(self) -> None:
        path = CODE / "bass_riffs.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        referenced_names = {
            node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
        }
        referenced_attributes = {
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
        }
        self.assertNotIn("bass_levels", referenced_names | referenced_attributes)

    def test_catalogue_indexes_are_immutable_after_construction(self) -> None:
        riff = self.catalog.riffs[0]
        with self.assertRaises(TypeError):
            self.catalog._by_id[riff.riff_id] = riff
        with self.assertRaises(TypeError):
            self.catalog._by_context[("new", "context")] = (riff,)

    def test_every_tb303_riff_fits_native_sequence_and_wire_limits(self) -> None:
        largest: tuple[int, str] = (0, "")
        for riff in self.catalog.riffs:
            payload = {
                "ppq": riff.ppq,
                "phrase_ticks": riff.phrase_ticks,
                "events": list(transpose_riff_events(riff, 0)),
            }
            events = compile_bass_events(
                config={"length_beats": 4, "bass_mode": "riff"},
                running=True,
                bass_notes=(),
                bass_riff=payload,
                synth=1,
                bass_gate_beats=0.25,
                ppq=48,
                tb303_parameters=Tb303Parameters(),
            )
            largest = max(largest, (len(events), riff.riff_id))
            self.assertLessEqual(len(events), 64, riff.riff_id)
            definition = compile_sequence_definition(
                sequence_tag=113,
                events=events,
            )
            for command in definition.commands:
                encoded = command.encode("ascii")
                self.assertLessEqual(
                    len(encoded),
                    MAX_WIRE_REQUEST_BYTES,
                    riff.riff_id,
                )
                self.assertEqual(validate_wire_request(encoded), command)

        self.assertEqual(largest, (45, "bass_shared_0969"))


if __name__ == "__main__":
    unittest.main()
