#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import re
import sys
import unittest
from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[1]
CODE = FRONTEND / "code"
sys.path.insert(0, str(CODE))

from amy_serial import (  # noqa: E402
    AmySerialClient,
    _TaggedSequencerLane,
    _compact_repeating_events,
)
from drum_patterns import load_drum_pattern_catalog  # noqa: E402
from config_loader import load_resolved_amy_config  # noqa: E402
from rhythm_command_plan import (  # noqa: E402
    SEQUENCE_CONTROL_GATE,
    compile_sequence_definition,
    sequence_control_command,
)


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
        cls.resolved_config = load_resolved_amy_config(
            FRONTEND / "config" / "amy_config.json"
        )
        cls.rhythms = json.loads(
            (FRONTEND / "music" / "rhythms.json").read_text(encoding="utf-8")
        )["rhythms"]
        cls.riffs = json.loads(
            (FRONTEND / "music" / "omnichord_bass_riffs.json").read_text(
                encoding="utf-8"
            )
        )["riffs"]
        cls.drum_catalog = load_drum_pattern_catalog(
            FRONTEND / "music" / "drums"
        )

    def test_reserved_ranges_are_disjoint_and_inside_current_amy_limit(self) -> None:
        rhythm_cfg = self.config["rhythm"]
        max_tags = int(self.config["amy_max_sequencer_tags"])
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

        self.assertEqual(max_tags, 1280)
        self.assertEqual(ranges["drums"], {"start": 0, "count": 56})
        self.assertEqual(ranges["bass"], {"start": 56, "count": 56})
        self.assertEqual(ranges["chords"], {"start": 112, "count": 140})
        self.assertEqual(len(occupied), 252)
        sequence_ranges = rhythm_cfg["sequence_ranges"]
        for name in ("fills", "chords", "drum_bases"):
            start = int(sequence_ranges[name]["start"])
            count = int(sequence_ranges[name]["count"])
            tags = set(range(start, start + count))
            self.assertFalse(tags & occupied, f"sequence range overlap for {name}")
            occupied |= tags
        self.assertEqual(sequence_ranges["fills"], {"start": 256, "count": 936})
        self.assertEqual(sequence_ranges["chords"], {"start": 1192, "count": 64})
        self.assertEqual(sequence_ranges["drum_bases"], {"start": 1256, "count": 24})
        self.assertEqual(len(occupied), 1276)
        self.assertEqual(int(self.config["voices"]["rhythm_chord"]), 7)

    def test_every_catalogue_phrase_fits_sequence_and_execution_limits(self) -> None:
        ranges = self.config["rhythm"]["tag_ranges"]
        worst_bass = (0, "")
        worst_chord_roots = (0, "")
        for rhythm in self.rhythms:
            bass_hits = max(
                (len(level) for level in rhythm.get("bass_levels", [])),
                default=0,
            )
            chord_hits = max(
                (len(level) for level in rhythm.get("chord_levels", [])),
                default=0,
            )
            if bass_hits * 2 > worst_bass[0]:
                worst_bass = (bass_hits * 2, str(rhythm["id"]))
            if chord_hits > worst_chord_roots[0]:
                worst_chord_roots = (chord_hits, str(rhythm["id"]))

        self.assertEqual(worst_bass, (56, "seven_four_funk"))
        self.assertLessEqual(worst_bass[0], int(ranges["bass"]["count"]))
        self.assertEqual(worst_chord_roots, (28, "seven_four_funk"))
        self.assertLessEqual(
            worst_chord_roots[0],
            int(ranges["chords"]["count"]),
        )

        max_instances = int(self.config["amy_max_sequence_executions"])
        worst_total = (0, ())
        worst_sequence_count = (0, ())
        for rhythm in self.rhythms:
            period = round(float(rhythm["length_beats"]) * 48)
            for source_level in (0, 1, 2, 4):
                chord_events = rhythm["chord_levels"][source_level]
                velocity_count = len({
                    float(event.get("amp", 1.0))
                    for event in chord_events
                })
                for note_count in range(2, 8):
                    sequence_count = velocity_count
                    if sequence_count > worst_sequence_count[0]:
                        worst_sequence_count = (
                            sequence_count,
                            (str(rhythm["id"]), source_level, note_count),
                        )
                    self.assertLessEqual(sequence_count, 64)
                    for rate in range(1, 5):
                        client = AmySerialClient.__new__(AmySerialClient)
                        client.resolved_config = self.resolved_config
                        client._sequence_ranges = {
                            name: (start, count)
                            for name, start, count in (
                                self.resolved_config.layout.sequencer_sequence_ranges
                            )
                        }
                        client.synth_id = {"rhythm_chord": 4}
                        client.rhythm_chord_enabled = True
                        client.chord_notes = [
                            float(60 + index) for index in range(note_count)
                        ]
                        client.rhythm_config = {
                            "id": rhythm["id"],
                            "length_beats": rhythm["length_beats"],
                            "chord_events": chord_events,
                            "chord_arpeggio": {
                                "enabled": True,
                                "notes_per_beat": rate,
                                "direction": "up",
                            },
                        }
                        sequence_commands, triggers = (
                            client._chord_sequence_plan()
                        )
                        sequence_ids = {
                            int(match.group(1))
                            for command in sequence_commands
                            if (match := re.match(r"^HR(\d+)Z$", command))
                        }
                        self.assertEqual(
                            len(sequence_ids), velocity_count
                        )
                        self.assertTrue(all(
                            1192
                            <= sequence_tag
                            < 1256
                            for sequence_tag in sequence_ids
                        ))
                        self.assertLessEqual(
                            len(triggers),
                            int(ranges["chords"]["count"]),
                        )

                        gate = max(1, round(0.72 * round(48 / rate)))
                        step = max(1, round(48 / rate))
                        length = (note_count - 1) * step + gate + 1
                        copies = math.ceil(length / period) + 2
                        base_starts = [
                            start
                            for tick, repeat, _ in triggers
                            for start in range(tick, period, repeat)
                        ]
                        starts = [
                            start + copy * period
                            for start in base_starts
                            for copy in range(-copies - 1, copies + 2)
                        ]
                        chord_instances = max(
                            (
                                sum(
                                    start <= tick < start + length
                                    for start in starts
                                )
                                for tick in range(period)
                            ),
                            default=0,
                        )
                        drum_roles = max(
                            len({event.role for event in level})
                            for level in self.drum_catalog.rhythm(
                                str(rhythm["id"])
                            ).levels
                        )
                        total = drum_roles + chord_instances + 1
                        details = (
                            str(rhythm["id"]),
                            source_level,
                            rate,
                            note_count,
                            drum_roles,
                            chord_instances,
                        )
                        if total > worst_total[0]:
                            worst_total = (total, details)
                        self.assertLessEqual(total, max_instances, details)

        self.assertEqual(worst_sequence_count[0], 2)
        self.assertEqual(
            worst_total,
            (34, ("merengue", 4, 1, 7, 6, 27)),
        )
        self.assertLessEqual(worst_total[0], max_instances)

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

    def test_sequence_wire_adapter_uses_explicit_h_family_operations(self) -> None:
        plan = compile_sequence_definition(
            sequence_tag=7,
            events=((0, 48, "i2n60l1"), (35, 0, "i2n60l0Z")),
        )
        self.assertEqual(
            plan.commands,
            (
                "HR7Z",
                "HA7,0,48i2n60l1Z",
                "HA7,35,0i2n60l0Z",
            ),
        )
        self.assertEqual(plan.event_count, 2)
        self.assertEqual(
            sequence_control_command(
                7,
                SEQUENCE_CONTROL_GATE,
                duration=48,
                alignment=11,
            ),
            "HC7,2,48,11Z",
        )

    def test_sequence_wire_adapter_rejects_invalid_identity_and_bounds(self) -> None:
        with self.assertRaisesRegex(ValueError, "must not be negative"):
            compile_sequence_definition(sequence_tag=-1, events=())
        with self.assertRaisesRegex(ValueError, "below its period"):
            compile_sequence_definition(
                sequence_tag=1,
                events=((48, 48, "i2n60l1"),),
            )

    def test_lane_clear_removes_only_future_child_triggers(self) -> None:
        writer = _WriterProbe()
        lane = _TaggedSequencerLane("chords", 112, 3, writer)
        events = [
            (0, 192, "HC1195,1,1"),
            (48, 192, "HC1196,1,1"),
            (96, 192, "HC1197,1,1"),
        ]
        self.assertEqual(
            lane.commands(events),
            [
                "H0,192,112HC1195,1,1Z",
                "H48,192,113HC1196,1,1Z",
                "H96,192,114HC1197,1,1Z",
            ],
        )

        self.assertEqual(
            lane.commands([]),
            [
                "H0,0,112Z",
                "H0,0,113Z",
                "H0,0,114Z",
            ],
        )

    def test_arpeggio_uses_all_notes_wraps_and_reverses(self) -> None:
        client = AmySerialClient.__new__(AmySerialClient)
        client.resolved_config = self.resolved_config
        client._sequence_ranges = {
            name: (start, count)
            for name, start, count in (
                self.resolved_config.layout.sequencer_sequence_ranges
            )
        }
        client.synth_id = {"rhythm_chord": 4}
        client.rhythm_chord_enabled = True
        client.chord_notes = [60.0, 64.0, 67.0, 71.0, 74.0]
        client.rhythm_config = {
            "length_beats": 4.0,
            "chord_events": [{"time": 0.0, "amp": 0.8}],
            "chord_arpeggio": {
                "enabled": True,
                "notes_per_beat": 1,
                "direction": "down",
            },
        }

        commands, events = client._chord_sequence_plan()
        self.assertEqual(
            events,
            [(0, 192, "HC1192,1,1Z")],
        )
        for sequence_index, note in enumerate(reversed(client.chord_notes)):
            tick = sequence_index * 48
            self.assertIn(
                f"HA1192,{tick},0n{note:g}l0.8i4Z",
                commands,
            )
            self.assertIn(
                f"HA1192,{tick + 35},0n{note:g}l0i4Z",
                commands,
            )
        self.assertEqual(commands[0], "HR1192Z")

    def test_dense_arpeggio_is_compacted_without_changing_tick_set(self) -> None:
        period = 192
        occurrences = [
            (start + offset, f"n{note}l1i4")
            for start in range(0, period, 24)
            for offset, note in enumerate((60, 64, 67, 71))
        ]
        compacted = _compact_repeating_events(occurrences, period)

        expanded = {
            (tick, body)
            for start, repeat, body in compacted
            for tick in range(start, period, repeat)
        }
        expected = {(tick % period, body) for tick, body in occurrences}
        self.assertEqual(expanded, expected)
        self.assertLess(len(compacted), len(expected))


if __name__ == "__main__":
    unittest.main()
