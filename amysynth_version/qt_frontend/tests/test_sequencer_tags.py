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
    SEQUENCE_CONTROL_PUBLISH,
    compile_group_definition,
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
        self.assertEqual(int(self.config["voices"]["rhythm_chord"]), 7)

    def test_every_catalogue_pattern_fits_its_reserved_range(self) -> None:
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

        max_instances = int(self.config["amy_max_pattern_instances"])
        worst_total = (0, ())
        worst_bank = (0, ())
        for rhythm in self.rhythms:
            period = round(float(rhythm["length_beats"]) * 48)
            for source_level in (0, 1, 2, 4):
                chord_events = rhythm["chord_levels"][source_level]
                velocity_count = len({
                    float(event.get("amp", 1.0))
                    for event in chord_events
                })
                for note_count in range(2, 8):
                    bank_size = velocity_count * (1 + 4 * note_count)
                    if bank_size > worst_bank[0]:
                        worst_bank = (
                            bank_size,
                            (str(rhythm["id"]), source_level, note_count),
                        )
                    self.assertLessEqual(bank_size, 64)
                    for rate in range(1, 5):
                        client = AmySerialClient.__new__(AmySerialClient)
                        client.resolved_config = self.resolved_config
                        client._pattern_ranges = {
                            name: (start, count)
                            for name, start, count in (
                                self.resolved_config.layout.sequencer_pattern_ranges
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
                        pattern_commands, triggers = (
                            client._chord_pattern_plan()
                        )
                        pattern_ids = {
                            int(match.group(1))
                            for command in pattern_commands
                            if (match := re.match(r"^zQB(\d+),", command))
                        }
                        self.assertEqual(
                            len(pattern_ids), velocity_count * note_count
                        )
                        self.assertTrue(all(
                            936
                            <= pattern
                            < 1000
                            for pattern in pattern_ids
                        ))
                        self.assertLessEqual(
                            len(triggers),
                            int(ranges["chords"]["count"]),
                        )

                        gate = max(1, round(0.72 * round(48 / rate)))
                        length = gate + 1
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

        self.assertEqual(worst_bank[0], 58)
        self.assertEqual(
            worst_total,
            (30, ("jazz_shuffle", 4, 1, 7, 7, 22)),
        )

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

    def test_group_wire_adapter_uses_ticks_namespace_and_atomic_publish(self) -> None:
        plan = compile_group_definition(
            group=7,
            length=48,
            events=((0, 48, "i2n60l1"), (35, 0, "i2n60l0Z")),
            previous_high_water=3,
        )
        self.assertEqual(
            plan.commands,
            (
                "H0,48,0,7i2n60l1Z",
                "H35,0,1,7i2n60l0Z",
                "H0,0,2,7Z",
                f"zQ7,{SEQUENCE_CONTROL_PUBLISH},48,0Z",
            ),
        )
        self.assertEqual(plan.tag_count, 2)
        self.assertEqual(plan.high_water, 3)
        self.assertEqual(
            sequence_control_command(7, SEQUENCE_CONTROL_GATE, 48, 0, 11),
            "zQ7,2,48,0,11Z",
        )

    def test_group_wire_adapter_rejects_invalid_identity_and_bounds(self) -> None:
        with self.assertRaisesRegex(ValueError, "start at 1"):
            compile_group_definition(group=0, length=48, events=())
        with self.assertRaisesRegex(ValueError, "outside length"):
            compile_group_definition(
                group=1,
                length=48,
                events=((48, 0, "i2n60l1"),),
            )

    def test_lane_clear_removes_only_future_child_triggers(self) -> None:
        writer = _WriterProbe()
        lane = _TaggedSequencerLane("chords", 112, 3, writer)
        events = [
            (0, 192, "zQT940,0,0"),
            (48, 192, "zQT941,0,0"),
            (96, 192, "zQT942,0,0"),
        ]
        self.assertEqual(
            lane.commands(events),
            [
                "H0,192,112zQT940,0,0Z",
                "H48,192,113zQT941,0,0Z",
                "H96,192,114zQT942,0,0Z",
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
        client._pattern_ranges = {
            name: (start, count)
            for name, start, count in (
                self.resolved_config.layout.sequencer_pattern_ranges
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

        commands, events = client._chord_pattern_plan()
        self.assertEqual(
            events,
            [
                (0, 192, "zQT941,0,0"),
                (48, 192, "zQT940,0,0"),
                (96, 192, "zQT939,0,0"),
                (144, 192, "zQT938,0,0"),
                (0, 192, "zQT937,0,0"),
            ],
        )
        for pattern, note in zip(range(937, 942), client.chord_notes):
            self.assertIn(f"zQB{pattern},36Z", commands)
            self.assertIn(
                f"zQE{pattern},0,36,0n{note:g}l0.8i4Z",
                commands,
            )
            self.assertIn(
                f"zQE{pattern},35,0,1n{note:g}l0i4Z",
                commands,
            )
            self.assertIn(f"zQC{pattern}Z", commands)

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
