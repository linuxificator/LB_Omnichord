#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[1]
CODE = FRONTEND / "code"
sys.path.insert(0, str(CODE))

from amy_serial import _TaggedSequencerLane  # noqa: E402


class _WriterProbe:
    def __init__(self) -> None:
        self.generations: dict[str, int] = {}
        self.commands: list[tuple[str, int, str]] = []

    def new_low_generation(self, lane: str) -> int:
        generation = self.generations.get(lane, 0) + 1
        self.generations[lane] = generation
        return generation

    def low(self, lane: str, generation: int, command: str) -> None:
        self.commands.append((lane, generation, command))


class SequencerTagTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(
            (FRONTEND / "config" / "amy_config.json").read_text(encoding="utf-8")
        )
        cls.rhythms = json.loads(
            (FRONTEND / "music" / "rhythms.json").read_text(encoding="utf-8")
        )["rhythms"]
        cls.riffs = json.loads(
            (FRONTEND / "music" / "omnichord_bass_riffs.json").read_text(
                encoding="utf-8"
            )
        )["riffs"]

    def test_reserved_ranges_are_disjoint_and_inside_current_amy_limit(self) -> None:
        rhythm_cfg = self.config["rhythm"]
        max_tags = int(rhythm_cfg["max_sequencer_tags"])
        ranges = rhythm_cfg["tag_ranges"]

        occupied: set[int] = set()
        for name in ("drums", "bass", "chords"):
            start = int(ranges[name]["start"])
            count = int(ranges[name]["count"])
            self.assertGreaterEqual(start, 0)
            self.assertGreater(count, 0)
            self.assertLessEqual(start + count, max_tags)
            tags = set(range(start, start + count))
            self.assertFalse(tags & occupied, f"tag range overlap for {name}")
            occupied |= tags

        self.assertEqual(max_tags, 256)
        self.assertEqual(ranges["drums"], {"start": 0, "count": 56})
        self.assertEqual(ranges["bass"], {"start": 56, "count": 56})
        self.assertEqual(ranges["chords"], {"start": 112, "count": 140})
        self.assertEqual(len(occupied), 252)

    def test_every_catalogue_pattern_fits_its_reserved_range(self) -> None:
        ranges = self.config["rhythm"]["tag_ranges"]
        max_chord_notes = int(self.config["rhythm"]["max_rhythm_chord_notes"])

        worst = {"drums": (0, ""), "bass": (0, ""), "chords": (0, "")}
        for rhythm in self.rhythms:
            drum_events = sum(
                len(layer.get("events", []))
                for layer in rhythm.get("percussion_layers", [])
            )
            bass_hits = max(
                (len(level) for level in rhythm.get("bass_levels", [])),
                default=0,
            )
            chord_hits = max(
                (len(level) for level in rhythm.get("chord_levels", [])),
                default=0,
            )
            required = {
                "drums": drum_events,
                "bass": bass_hits * 2,
                "chords": chord_hits * (max_chord_notes + 1),
            }
            for lane, count in required.items():
                if count > worst[lane][0]:
                    worst[lane] = (count, str(rhythm["id"]))
                self.assertLessEqual(
                    count,
                    int(ranges[lane]["count"]),
                    f"{rhythm['id']} needs {count} {lane} tags",
                )

        self.assertEqual(worst["drums"], (56, "trance"))
        self.assertEqual(worst["bass"], (56, "seven_four_funk"))
        self.assertEqual(worst["chords"], (140, "seven_four_funk"))

        riff_tags = max(
            len(riff["timing"]["events"]) * 2
            for riff in self.riffs
        )
        self.assertEqual(riff_tags, 34)
        self.assertLessEqual(riff_tags, int(ranges["bass"]["count"]))

    def test_one_tag_tracks_one_event_and_clear_is_targeted(self) -> None:
        writer = _WriterProbe()
        lane = _TaggedSequencerLane("test", 10, 3, writer)

        # Tick 17 in a 16-tick repeating period wraps to tick 1. This protects
        # note-offs whose gate crosses the bar boundary from becoming events
        # that can never match AMY's modulo-period tick offset.
        commands = lane.commands([(17, 16, "n60l1i1")])
        self.assertEqual(commands, ["H1,16,10n60l1i1Z"])

        # Removing that one event addresses exactly its tag.
        self.assertEqual(lane.commands([]), ["H0,0,10Z"])

        # Two simultaneous events require two tags; the lane never groups them
        # under one tag because current AMY stores one sequencer entry per tag.
        commands = lane.commands(
            [(0, 16, "n60l1i1"), (0, 16, "n64l1i1")]
        )
        self.assertEqual(commands[0], "H0,16,10n60l1i1Z")
        self.assertEqual(commands[1], "H0,16,11n64l1i1Z")

    def test_lane_can_clear_onsets_while_retaining_existing_note_offs(self) -> None:
        writer = _WriterProbe()
        lane = _TaggedSequencerLane("chords", 112, 5, writer)
        events = [
            (0, 192, "n48l0.8i4"),
            (0, 192, "n52l0.8i4"),
            (35, 192, "l0i4"),
            (96, 192, "n48l0.8i4"),
            (227, 192, "l0i4"),
        ]
        lane.commands(events)

        lane.retain_only(events, {2, 4})

        self.assertEqual(
            [command for _, _, command in writer.commands],
            [
                "H35,192,114l0i4Z",
                "H35,192,116l0i4Z",
                "H0,0,112Z",
                "H0,0,113Z",
                "H0,0,115Z",
            ],
        )


if __name__ == "__main__":
    unittest.main()
