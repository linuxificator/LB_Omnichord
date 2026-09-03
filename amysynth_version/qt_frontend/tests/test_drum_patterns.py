#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from itertools import combinations
from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[1]
CODE = FRONTEND / "code"
sys.path.insert(0, str(CODE))

from amy_transport import (  # noqa: E402
    AMY_PPQ,
    AmySerialClient,
    _TaggedSequencerLane,
    _resolve_drum_catalog_directory,
)
from drum_patterns import (  # noqa: E402
    KIT_FAMILIES,
    load_drum_pattern_catalog,
)
from config_loader import load_resolved_amy_config  # noqa: E402
from rhythm_command_plan import (  # noqa: E402
    SEQUENCE_CONTROL_GATE,
    compile_fill_group,
    sequence_control_command,
)


class _WriterProbe:
    def new_low_generation(self, _lane: str) -> int:
        return 1

    def low(self, _lane: str, _generation: int, _command: str) -> None:
        pass


class DrumPatternTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_drum_pattern_catalog(FRONTEND / "music" / "drums")
        cls.config = json.loads(
            (FRONTEND / "config" / "amy_config.json").read_text(
                encoding="utf-8"
            )
        )
        cls.resolved_config = load_resolved_amy_config(
            FRONTEND / "config" / "amy_config.json"
        )

    def client(self) -> AmySerialClient:
        client = AmySerialClient.__new__(AmySerialClient)
        client.resolved_config = self.resolved_config
        client._group_ranges = {
            name: (start, count)
            for name, start, count in (
                self.resolved_config.layout.sequencer_group_ranges
            )
        }
        client._group_tag_high_waters = {}
        client.drum_catalog = self.catalog
        client.drum_kit = "tiny"
        client.synth_id = {"drums": 0}
        client.rhythm_running = True
        client._drum_roles = tuple(sorted({
            event.role
            for rhythm in self.catalog.rhythms.values()
            for level in rhythm.levels
            for event in level
        }))
        client._drum_role_index = {
            role: index for index, role in enumerate(client._drum_roles)
        }
        client._sequencer_lanes = {
            "drums": _TaggedSequencerLane("drums", 0, 56, _WriterProbe())
        }
        return client

    def test_drum_assets_resolve_in_source_frozen_and_android_layouts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            source_module = root / "source" / "code" / "amy_transport.py"
            source_drums = root / "source" / "music" / "drums"
            source_drums.mkdir(parents=True)
            self.assertEqual(
                _resolve_drum_catalog_directory(source_module),
                source_drums,
            )

            flat_module = root / "android" / "amy_transport.py"
            flat_drums = root / "android" / "music" / "drums"
            flat_drums.mkdir(parents=True)
            self.assertEqual(
                _resolve_drum_catalog_directory(flat_module),
                flat_drums,
            )

            frozen_root = root / "frozen"
            self.assertEqual(
                _resolve_drum_catalog_directory(
                    root / "irrelevant" / "amy_transport.py",
                    packaged_root=frozen_root,
                ),
                frozen_root / "music" / "drums",
            )

    def test_catalogue_has_complete_validated_coverage(self) -> None:
        self.assertEqual(len(self.catalog.rhythms), 54)
        fills = [
            fill
            for rhythm in self.catalog.rhythms.values()
            for fill in rhythm.fills
        ]
        self.assertEqual(len(fills), 270)
        self.assertEqual(len({fill.fill_id for fill in fills}), 270)
        self.assertEqual(len({fill.index for fill in fills}), 270)
        self.assertLess(max(fill.index for fill in fills), 1001)
        for rhythm in self.catalog.rhythms.values():
            self.assertEqual(len(rhythm.levels), 5)
            self.assertEqual(len(rhythm.fills), 5)
            for level in rhythm.levels:
                for event in level:
                    self.assertEqual(event.tick % 2, 0)
                    self.assertLess(event.tick, rhythm.period_ticks)
            for fill in rhythm.fills:
                self.assertEqual(fill.duration_ticks % 2, 0)
                for event in fill.events:
                    self.assertLess(event.tick, fill.duration_ticks)

    def test_catalogue_and_nested_kit_indexes_are_immutable(self) -> None:
        with self.assertRaises(TypeError):
            self.catalog.rhythms["new"] = self.catalog.rhythm("pop_8")
        tiny = self.catalog.kits["tiny"]
        with self.assertRaises(TypeError):
            tiny.activity_rhythm_profile["pop_8"] = "replacement"
        profile = next(iter(tiny.activity_profiles.values()))
        with self.assertRaises(TypeError):
            profile["low_primary"] = self.catalog.resolve(
                "tiny", "pop_8", "low_primary"
            )

    def test_activity_levels_are_selected_complete_not_concatenated(self) -> None:
        pop = self.catalog.rhythm("pop_8")
        level_one = {(event.tick, event.role) for event in pop.levels[0]}
        level_two = {(event.tick, event.role) for event in pop.levels[1]}
        self.assertTrue(level_one <= level_two)
        client = self.client()
        client.rhythm_config = {
            "id": "pop_8",
            "percussion_activity": 2,
        }
        commands = client._drum_activity_commands()
        authored_events = [
            command
            for command in commands
            if command.startswith("H") and command.count(",") >= 3
        ]
        self.assertEqual(len(authored_events), len(pop.levels[1]))
        self.assertNotEqual(
            len(authored_events),
            len(pop.levels[0]) + len(pop.levels[1]),
        )
        self.assertTrue(any(re.match(r"^zQ\d+,1,0,", command) for command in commands))
        group_length = pop.period_ticks // 2
        for command in authored_events:
            match = re.match(r"^H(\d+),(\d+),\d+,\d+", command)
            self.assertIsNotNone(match, command)
            assert match is not None
            tick, period = (int(value) for value in match.groups())
            self.assertEqual(period, group_length if tick == 0 else 0)

    def test_grouped_activity_preserves_every_catalogue_event_exactly(self) -> None:
        event_pattern = re.compile(
            r"^H(?P<tick>\d+),(?P<period>\d+),(?P<tag>\d+),"
            r"(?P<group>\d+)(?P<body>.+)Z$"
        )
        for rhythm in self.catalog.rhythms.values():
            for level_index, level in enumerate(rhythm.levels, start=1):
                client = self.client()
                client.rhythm_running = False
                client.rhythm_config = {
                    "id": rhythm.rhythm_id,
                    "percussion_activity": level_index,
                }
                actual = []
                for command in client._drum_activity_commands(
                    quantize_live=False
                ):
                    match = event_pattern.match(command)
                    if match is not None:
                        actual.append(
                            (
                                int(match.group("group")),
                                int(match.group("tick")),
                                int(match.group("period")),
                                int(match.group("tag")),
                                match.group("body"),
                            )
                        )

                expected = []
                length = rhythm.period_ticks // 2
                by_role: dict[str, list[object]] = {}
                for event in level:
                    by_role.setdefault(event.role, []).append(event)
                for role_index, role in enumerate(client._drum_roles):
                    group = 1001 + role_index
                    for tag, event in enumerate(by_role.get(role, [])):
                        tick = event.tick // 2
                        expected.append(
                            (
                                group,
                                tick,
                                length if tick == 0 else 0,
                                tag,
                                client._drum_hit_body(
                                    rhythm.rhythm_id,
                                    role,
                                    event.velocity,
                                    fill=False,
                                ),
                            )
                        )
                self.assertEqual(actual, expected, (rhythm.rhythm_id, level_index))

    def test_grouped_fills_preserve_events_and_only_add_generic_gates(self) -> None:
        event_pattern = re.compile(
            r"^H(?P<tick>\d+),(?P<period>\d+),(?P<tag>\d+),"
            r"(?P<group>\d+)(?P<body>.+)Z$"
        )
        client = self.client()
        for rhythm in self.catalog.rhythms.values():
            for fill in rhythm.fills:
                group = client._fill_group_tag(fill)
                definition = compile_fill_group(
                    rhythm_id=rhythm.rhythm_id,
                    fill=fill,
                    group=group,
                    roles=client._drum_roles,
                    role_indexes=client._drum_role_index,
                    drum_group_start=1001,
                    hit_body=client._drum_hit_body,
                )
                actual = []
                for command in definition.commands:
                    match = event_pattern.match(command)
                    if match is not None:
                        actual.append(
                            (
                                int(match.group("tick")),
                                int(match.group("period")),
                                int(match.group("tag")),
                                int(match.group("group")),
                                match.group("body"),
                            )
                        )

                length = fill.duration_ticks // 2
                expected = []
                tag = 0
                for role in client._drum_roles:
                    if role in fill.continue_roles:
                        continue
                    role_group = 1001 + client._drum_role_index[role]
                    gate = sequence_control_command(
                        role_group,
                        SEQUENCE_CONTROL_GATE,
                        length,
                        0,
                        role_group,
                    )[:-1]
                    expected.append((0, length, tag, group, gate))
                    tag += 1
                for event in fill.events:
                    tick = event.tick // 2
                    expected.append(
                        (
                            tick,
                            length if tick == 0 else 0,
                            tag,
                            group,
                            client._drum_hit_body(
                                rhythm.rhythm_id,
                                event.role,
                                event.velocity,
                                fill=True,
                            ),
                        )
                    )
                    tag += 1

                self.assertEqual(actual, expected, fill.fill_id)
                self.assertFalse(
                    any(re.match(r"^zQ\d+,1,", body) for *_, body in actual),
                    fill.fill_id,
                )

    def test_every_kit_resolves_without_changing_timing(self) -> None:
        for rhythm in self.catalog.rhythms.values():
            activity_timing = tuple(
                (event.tick, event.role, event.velocity)
                for event in rhythm.levels[4]
            )
            fill_timing = tuple(
                (event.tick, event.role, event.velocity)
                for fill in rhythm.fills
                for event in fill.events
            )
            for kit in KIT_FAMILIES:
                for _, role, _ in activity_timing:
                    self.catalog.resolve(kit, rhythm.rhythm_id, role)
                for _, role, _ in fill_timing:
                    self.catalog.resolve(
                        kit, rhythm.rhythm_id, role, fill=True
                    )
                self.assertEqual(
                    activity_timing,
                    tuple(
                        (event.tick, event.role, event.velocity)
                        for event in rhythm.levels[4]
                    ),
                )

        tiny = self.catalog.resolve("tiny", "pop_8", "low_primary")
        gamma = self.catalog.resolve("gamma9001", "pop_8", "low_primary")
        general_midi = self.catalog.resolve(
            "general_midi", "pop_8", "low_primary"
        )
        self.assertEqual((tiny.preset, tiny.synth_patch), (1, None))
        self.assertIsNotNone(gamma.preset)
        self.assertIsNone(gamma.synth_patch)
        self.assertEqual(
            (general_midi.preset, general_midi.synth_patch),
            (None, 258),
        )

    def test_every_gamma_patch_note_pair_has_a_direct_pcm_realization(self) -> None:
        resolved: set[tuple[int, int]] = set()
        for rhythm in self.catalog.rhythms.values():
            for level in rhythm.levels:
                for event in level:
                    sound = self.catalog.resolve(
                        "gamma9001", rhythm.rhythm_id, event.role
                    )
                    self.assertIsNotNone(sound.preset)
                    resolved.add((int(sound.preset), sound.note))
            for fill in rhythm.fills:
                for event in fill.events:
                    sound = self.catalog.resolve(
                        "gamma9001",
                        rhythm.rhythm_id,
                        event.role,
                        fill=True,
                    )
                    self.assertIsNotNone(sound.preset)
                    resolved.add((int(sound.preset), sound.note))
        self.assertGreater(len(resolved), 50)

    def test_kit_hit_wire_uses_pcm_presets_or_engine_gm_patch_notes(self) -> None:
        client = self.client()
        client.drum_kit = "tiny"
        tiny = client._drum_hit_body(
            "pop_8", "low_primary", 100, fill=False
        )
        self.assertTrue(tiny.startswith("p1n39"))

        client.drum_kit = "gamma9001"
        gamma = client._drum_hit_body(
            "pop_8", "low_primary", 100, fill=False
        )
        self.assertRegex(gamma, r"^p\d+n\d+")
        self.assertNotIn("p384", gamma)

        client.drum_kit = "general_midi"
        general_midi = client._drum_hit_body(
            "pop_8", "low_primary", 100, fill=False
        )
        self.assertTrue(general_midi.startswith("n36"))
        self.assertNotIn("p258", general_midi)

    def test_preloaded_library_fits_64_events_and_uses_all_fill_groups(self) -> None:
        client = self.client()
        commands: list[str] = []
        client._wire = commands.append  # type: ignore[method-assign]
        client._preload_drum_library()
        publishes = [
            command for command in commands if re.match(r"^zQ\d+,3,", command)
        ]
        self.assertEqual(len(publishes), 270)
        self.assertIn("zQ1,3,48,0Z", publishes)
        self.assertTrue(any(command.startswith("zQ270,3,") for command in publishes))

        current_count = 0
        current_length = 0
        maximum = 0
        for command in commands:
            if command.startswith("H"):
                match = re.match(r"^H(\d+),(\d+),\d+,\d+", command)
                self.assertIsNotNone(match, command)
                assert match is not None
                tick, period = (int(value) for value in match.groups())
                current_count += 1
            elif (publish := re.match(r"^zQ\d+,3,(\d+),0Z$", command)):
                current_length = int(publish.group(1))
                group_events = commands[commands.index(command) - current_count : commands.index(command)]
                for event_command in group_events:
                    event_match = re.match(r"^H(\d+),(\d+),", event_command)
                    assert event_match is not None
                    tick, period = (int(value) for value in event_match.groups())
                    self.assertEqual(period, current_length if tick == 0 else 0)
                maximum = max(maximum, current_count)
                self.assertLessEqual(current_count, 64)
                current_count = 0
        self.assertGreater(maximum, 0)

    def test_fill_policy_is_encoded_as_generic_role_tag_mutes(self) -> None:
        client = self.client()
        commands: list[str] = []
        client._wire = commands.append  # type: ignore[method-assign]
        client._preload_drum_library()
        first_commit = commands.index("zQ1,3,48,0Z")
        first = commands[:first_commit]
        fill = self.catalog.rhythm("pop_8").fills[0]
        length = fill.duration_ticks // 2
        for role in client._drum_roles:
            tag = 1001 + client._drum_role_index[role]
            mute_commands = [
                command for command in first if f"zQ{tag},2,{length},0,{tag}" in command
            ]
            muted = bool(mute_commands)
            self.assertEqual(muted, role not in fill.continue_roles)
            for command in mute_commands:
                self.assertRegex(command, rf"^H0,{length},\d+,1zQ{tag},2,")

    def test_fill_order_and_allowed_starts_form_a_finite_supercycle(self) -> None:
        client = self.client()
        client.rhythm_config = {
            "id": "pop_8",
            "fill_order": [1, 0],
            "fill_density_bars": 2,
        }
        occurrences = client._fill_occurrences(
            [1, 0],
            self.catalog.rhythm("pop_8").fills,
        )
        self.assertGreaterEqual(len(occurrences), 2)
        self.assertEqual(occurrences[0][0], self.catalog.rhythm("pop_8").fills[1])
        commands = client._fill_schedule_commands()
        self.assertEqual(
            sum(command.startswith("H") for command in commands),
            len(occurrences),
        )
        self.assertTrue(all(
            f",{index}zQ" in command
            for index, command in enumerate(
                command for command in commands if command.startswith("H")
            )
        ))

    def test_cold_start_is_immediate_but_live_drum_edits_are_quantized(self) -> None:
        client = self.client()
        client.rhythm_config = {
            "id": "pop_8",
            "percussion_activity": 1,
            "fill_order": [0],
            "fill_density_bars": 4,
        }

        cold = client._drum_commands(quantize_live=False)
        live = client._drum_commands(quantize_live=True)
        cold_triggers = [line for line in cold if re.match(r"^zQ\d+,1,0,", line)]
        live_triggers = [line for line in live if re.match(r"^zQ\d+,1,0,", line)]
        cold_roots = [line for line in cold if line.startswith("H") and "zQ" in line]
        live_roots = [line for line in live if line.startswith("H") and "zQ" in line]

        self.assertTrue(cold_triggers)
        self.assertTrue(cold_roots)
        self.assertTrue(all(line.split(",")[3] == "0" for line in cold_triggers))
        self.assertTrue(all(line.split(",")[3] == "192" for line in live_triggers))
        self.assertEqual(cold_roots, live_roots)

    def test_every_fill_subset_fits_root_lane_and_whole_beat_schedule(self) -> None:
        maximum = 0
        for rhythm in self.catalog.rhythms.values():
            beats_per_bar = int(rhythm.meter.split("/", 1)[0])
            for count in range(1, len(rhythm.fills) + 1):
                for order_tuple in combinations(range(len(rhythm.fills)), count):
                    order = list(order_tuple)
                    occurrences = AmySerialClient._fill_occurrences(
                        order,
                        rhythm.fills,
                    )
                    maximum = max(maximum, len(occurrences))
                    self.assertLessEqual(len(occurrences), 56)
                    for fill, start_beat in occurrences:
                        self.assertIn(start_beat, fill.allowed_start_beats)
                        self.assertGreaterEqual(start_beat, 1)
                        self.assertLessEqual(start_beat, beats_per_bar)
                        self.assertEqual(
                            fill.duration_ticks % fill.beat_unit_ticks,
                            0,
                        )
                        self.assertLessEqual(
                            (start_beat - 1) * fill.beat_unit_ticks
                            + fill.duration_ticks,
                            beats_per_bar * fill.beat_unit_ticks,
                        )
        self.assertEqual(maximum, 10)

    def test_lb_runtime_reserves_storage_but_not_hundreds_of_players(self) -> None:
        self.assertEqual(self.config["amy_max_sequence_groups"], 1024)
        self.assertEqual(self.config["amy_max_sequence_group_tags"], 64)
        self.assertEqual(self.config["amy_max_sequence_group_executions"], 40)


if __name__ == "__main__":
    unittest.main()
