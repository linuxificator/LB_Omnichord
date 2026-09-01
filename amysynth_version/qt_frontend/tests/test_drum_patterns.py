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
        client._pattern_ranges = {
            name: (start, count)
            for name, start, count in (
                self.resolved_config.layout.sequencer_pattern_ranges
            )
        }
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
            command for command in commands if command.startswith("zQE")
        ]
        self.assertEqual(len(authored_events), len(pop.levels[1]))
        self.assertNotEqual(
            len(authored_events),
            len(pop.levels[0]) + len(pop.levels[1]),
        )
        self.assertTrue(any(command.startswith("zQT") for command in commands))
        self.assertFalse(any(command.startswith("H") for command in commands))
        pattern_length = pop.period_ticks // 2
        for command in authored_events:
            match = re.match(r"^zQE\d+,(\d+),(\d+),\d+", command)
            self.assertIsNotNone(match, command)
            assert match is not None
            tick, period = (int(value) for value in match.groups())
            self.assertEqual(period, pattern_length if tick == 0 else 0)

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

    def test_preloaded_library_fits_64_events_and_uses_all_fill_slots(self) -> None:
        client = self.client()
        commands: list[str] = []
        client._wire = commands.append  # type: ignore[method-assign]
        client._preload_drum_library()
        begins = [command for command in commands if command.startswith("zQB")]
        commits = [command for command in commands if command.startswith("zQC")]
        self.assertEqual(len(begins), 270)
        self.assertEqual(len(commits), 270)
        self.assertIn("zQB0,48Z", begins)
        self.assertTrue(any(command.startswith("zQB269,") for command in begins))

        current_count = 0
        current_length = 0
        maximum = 0
        for command in commands:
            if command.startswith("zQB"):
                match = re.fullmatch(r"zQB\d+,(\d+)Z", command)
                self.assertIsNotNone(match, command)
                assert match is not None
                current_length = int(match.group(1))
                current_count = 0
            elif command.startswith("zQE"):
                match = re.match(r"^zQE\d+,(\d+),(\d+),\d+", command)
                self.assertIsNotNone(match, command)
                assert match is not None
                tick, period = (int(value) for value in match.groups())
                self.assertEqual(
                    period,
                    current_length if tick == 0 else 0,
                    command,
                )
                current_count += 1
            elif command.startswith("zQC"):
                maximum = max(maximum, current_count)
                self.assertLessEqual(current_count, 64)
        self.assertGreater(maximum, 0)

    def test_fill_policy_is_encoded_as_generic_role_tag_mutes(self) -> None:
        client = self.client()
        commands: list[str] = []
        client._wire = commands.append  # type: ignore[method-assign]
        client._preload_drum_library()
        first_commit = commands.index("zQC0Z")
        first = commands[:first_commit]
        fill = self.catalog.rhythm("pop_8").fills[0]
        length = fill.duration_ticks // 2
        for role in client._drum_roles:
            tag = (
                1000
                + client._drum_role_index[role]
            )
            mute_commands = [
                command for command in first if f"zQM{tag},{length}Z" in command
            ]
            muted = bool(mute_commands)
            self.assertEqual(muted, role not in fill.continue_roles)
            for command in mute_commands:
                self.assertRegex(command, rf"^zQE0,0,{length},\d+zQM")

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
            sum(command.startswith("zQA") for command in commands),
            len(occurrences),
        )
        self.assertTrue(all(
            f",{index}Z" in command
            for index, command in enumerate(
                command for command in commands if command.startswith("zQA")
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
        cold_triggers = [line for line in cold if line.startswith("zQT")]
        live_triggers = [line for line in live if line.startswith("zQT")]
        cold_roots = [line for line in cold if line.startswith("zQA")]
        live_roots = [line for line in live if line.startswith("zQA")]

        self.assertTrue(cold_triggers)
        self.assertTrue(cold_roots)
        self.assertTrue(all(line.split(",")[2] == "0" for line in cold_triggers))
        self.assertTrue(all(line.split(",")[-2] == "0" for line in cold_roots))
        self.assertTrue(all(line.split(",")[2] == "192" for line in live_triggers))
        self.assertTrue(all(line.split(",")[-2] == "192" for line in live_roots))

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
        self.assertEqual(self.config["amy_max_patterns"], 1024)
        self.assertEqual(self.config["amy_max_pattern_tags"], 64)
        self.assertEqual(self.config["amy_max_pattern_instances"], 32)


if __name__ == "__main__":
    unittest.main()
