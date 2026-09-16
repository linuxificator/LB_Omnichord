from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SC_ROOT = ROOT.parent / "supercollider"
CATALOG_ROOT = ROOT / "music" / "sc_expansion"
sys.path.insert(0, str(ROOT / "code"))

from sc_drum_kits import DRUM_KITS, resolve_hit  # noqa: E402
from catalog_extensions import load_synth_catalog  # noqa: E402
from sc_music_catalog import load_sc_music_catalog  # noqa: E402
from musical_sequence_plan import compile_drum_lane  # noqa: E402


class ScMusicExpansionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_sc_music_catalog(CATALOG_ROOT / "sc_kit_grooves_v1.json")
        cls.rhythm_ids = tuple(
            str(row["id"])
            for row in json.loads(
                (ROOT / "music" / "rhythms.json").read_text(encoding="utf-8")
            )["rhythms"]
        )

    def test_generated_authorities_match_their_recorded_hashes(self) -> None:
        manifest = json.loads((CATALOG_ROOT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(
            set(manifest["evidence_sources"]),
            {"sample_measurements.json", "validation_report.json"},
        )
        validation = manifest["validation_summary"]
        self.assertEqual(validation["status"], "PASS")
        self.assertEqual(validation["counts"]["kit_rhythm_contexts"], 810)
        self.assertEqual(validation["counts"]["fill_variants"], 4050)
        self.assertEqual(validation["max_groove_pad_events"], 57)
        self.assertEqual(validation["max_fill_foreground_events"], 40)
        self.assertEqual(
            validation["max_combined_fill_window_pad_events_all_levels"],
            84,
        )
        self.assertLessEqual(
            validation["max_combined_fill_window_pad_events_all_levels"],
            96,
        )
        self.assertEqual(validation["explicit_right_foot_fill_exceptions"], 10)
        for name, expected in manifest["outputs"].items():
            with self.subTest(name=name):
                self.assertEqual(
                    hashlib.sha256((CATALOG_ROOT / name).read_bytes()).hexdigest(),
                    expected,
                )
        for name, expected in manifest["preset_outputs"].items():
            with self.subTest(preset=name):
                self.assertEqual(
                    hashlib.sha256(
                        (ROOT / "instruments" / "default_presets" / name).read_bytes()
                    ).hexdigest(),
                    expected,
                )

    def test_every_kit_rhythm_has_five_levels_and_five_fills(self) -> None:
        self.assertEqual(len(DRUM_KITS), 15)
        self.assertEqual(len(self.rhythm_ids), 54)
        for kit in DRUM_KITS:
            for rhythm_id in self.rhythm_ids:
                with self.subTest(kit=kit.kit_id, rhythm=rhythm_id):
                    arrangement = self.catalog.arrangement(kit.kit_id, rhythm_id)
                    fills = self.catalog.fills(kit.kit_id, rhythm_id)
                    self.assertEqual(len(arrangement.levels), 5)
                    self.assertEqual([fill.slot_level for fill in fills], [1, 2, 3, 4, 5])
                    self.assertTrue(all(fill.events for fill in fills))

    def test_every_activity_and_fill_compiles_with_exact_continuation(self) -> None:
        for kit in DRUM_KITS:
            for rhythm_id in self.rhythm_ids:
                arrangement = self.catalog.arrangement(kit.kit_id, rhythm_id)
                fills = self.catalog.fills(kit.kit_id, rhythm_id)
                denominator = int(arrangement.meter.split("/", 1)[1])
                beat_ticks = 96 if denominator == 4 else 48
                for activity in range(1, 6):
                    plan = compile_drum_lane(
                        config={
                            "id": rhythm_id,
                            "percussion_activity": activity,
                            "fill_order": [0, 1, 2, 3, 4],
                            "fill_density_bars": 2,
                        },
                        catalog=self.catalog,
                        kit=kit.kit_id,
                        logical_bus=1,
                        generation=1,
                        program_resolver=lambda _kit, slot: ("test", slot, 1.0),
                    )
                    definitions = {
                        definition.definition_id: definition
                        for definition in plan.definitions
                    }
                    root = arrangement.levels[activity - 1]
                    for fill in fills:
                        for start_beat in fill.allowed_start_beats:
                            start = (start_beat - 1) * beat_ticks
                            finite = definitions[
                                f"drums/fill/{fill.slot_level}/{start_beat}"
                            ]
                            gated = {
                                str(event.atoms[0])
                                for event in finite.events
                                if event.kind == "gateBegin"
                            }
                            actual = {
                                (
                                    (event.tick - start) % arrangement.period_ticks,
                                    event.slot,
                                ): event.velocity / 127.0
                                for event in root
                                if (event.tick - start) % arrangement.period_ticks
                                < fill.duration_ticks
                                and event.gate_key not in gated
                            }
                            for event in finite.events:
                                if event.kind == "drumHit":
                                    actual[(event.tick * 2, str(event.atoms[4]))] = float(
                                        event.atoms[6]
                                    )
                            expected = {
                                (
                                    (event.tick - start) % arrangement.period_ticks,
                                    event.slot,
                                ): event.velocity / 127.0
                                for event in fill.continuation_levels[activity - 1]
                                if (event.tick - start) % arrangement.period_ticks
                                < fill.duration_ticks
                            }
                            for event in fill.events:
                                key = (event.tick, event.slot)
                                expected[key] = max(
                                    expected.get(key, 0.0),
                                    event.velocity / 127.0 * fill.gain,
                                )
                            with self.subTest(
                                kit=kit.kit_id,
                                rhythm=rhythm_id,
                                activity=activity,
                                fill=fill.slot_level,
                            ):
                                self.assertEqual(actual.keys(), expected.keys())
                                for key, level in expected.items():
                                    self.assertAlmostEqual(actual[key], level)

    def test_every_drum_sample_is_in_the_pinned_vsco_manifest(self) -> None:
        kit_data = json.loads(
            (CATALOG_ROOT / "sc_pcm_drumkits_v1.json").read_text(encoding="utf-8")
        )
        sample_ids = {
            sample_id
            for sample_set in kit_data["sample_sets"]
            for layer in sample_set["layers"]
            for sample_id in layer["round_robin_sample_ids"]
        }
        manifest_ids = {
            row["id"]
            for row in json.loads(
                (SC_ROOT / "vsco-manifest.json").read_text(encoding="utf-8")
            )["files"]
        }
        self.assertEqual(len(sample_ids), 262)
        files = {row["id"]: row for row in kit_data["sample_files"]}
        self.assertEqual(sample_ids, set(files))
        self.assertLessEqual(
            {row["source_sample_id"] for row in files.values()}, manifest_ids
        )
        self.assertTrue(all(row["start_frame"] >= 0 for row in files.values()))
        self.assertTrue(any(row["start_frame"] > 0 for row in files.values()))

    def test_pcm_velocity_layers_are_complete_and_every_role_resolves(self) -> None:
        kit_data = json.loads(
            (CATALOG_ROOT / "sc_pcm_drumkits_v1.json").read_text(encoding="utf-8")
        )
        expected_roles = self.catalog.roles
        sets = {
            row["sample_set_id"]: row for row in kit_data["sample_sets"]
        }
        self.assertEqual(len(sets), 51)
        for sample_set_id, sample_set in sets.items():
            covered: list[int] = []
            for layer in sample_set["layers"]:
                self.assertTrue(layer["round_robin_sample_ids"], sample_set_id)
                covered.extend(range(layer["velocity_lo"], layer["velocity_hi"] + 1))
            self.assertEqual(covered, list(range(1, 128)), sample_set_id)
        for kit in kit_data["kits"]:
            defaults = kit["role_defaults"]
            with self.subTest(kit=kit["kit_id"]):
                self.assertEqual(set(defaults), expected_roles)
                self.assertLessEqual(set(defaults.values()), set(kit["pads"]))
                self.assertTrue(
                    all(
                        pad["sample_set_id"] in sets
                        and pad["pitch_mode"] == "unpitched_fixed_rate"
                        and pad["playback_rate"] == 1.0
                        for pad in kit["pads"].values()
                    )
                )

    def test_legacy_vsco_sequence_keeps_distinct_drum_roles(self) -> None:
        plan = compile_drum_lane(
            config={
                "id": "pop_8",
                "percussion_activity": 5,
                "fill_order": [0, 1, 2, 3, 4],
                "fill_density_bars": 2,
            },
            catalog=self.catalog,
            kit="pcm-vsco",
            logical_bus=1,
            generation=1,
            program_resolver=resolve_hit,
        )
        pads = {
            str(event.atoms[4])
            for definition in plan.definitions
            if definition.kind == "root"
            for event in definition.events
            if event.kind == "drumHit"
        }
        expected = {"low_primary", "backbeat_primary", "timekeeper_primary"}
        self.assertLessEqual(expected, pads)
        self.assertFalse(any(pad.startswith("legacy/") for pad in pads))
        role_keys = json.loads(
            (SC_ROOT / "drum-key-map.json").read_text(encoding="utf-8")
        )["role_keys"]
        self.assertEqual(len({role_keys[role] for role in expected}), len(expected))

    def test_reviewed_groove_budget_is_real_and_bounded(self) -> None:
        counts = [
            len(level)
            for kit in DRUM_KITS
            for rhythm_id in self.rhythm_ids
            for level in self.catalog.arrangement(kit.kit_id, rhythm_id).levels
        ]
        self.assertEqual(max(counts), 57)
        self.assertTrue(all(count <= 64 for count in counts))

    def test_reviewed_short_drum_caps_survive_catalogue_and_protocol_compilation(self) -> None:
        catalog_caps = {
            event.max_duration_ms
            for kit in DRUM_KITS
            for rhythm_id in self.rhythm_ids
            for level in self.catalog.arrangement(kit.kit_id, rhythm_id).levels
            for event in level
        }
        self.assertEqual(catalog_caps, {0, 140, 180})
        compiled_caps = {
            int(event.atoms[8])
            for kit in ("pcm-tight-studio", "sc-basic")
            for definition in compile_drum_lane(
                config={
                    "id": "punk",
                    "percussion_activity": 5,
                    "fill_order": [0, 1, 2, 3, 4],
                    "fill_density_bars": 2,
                },
                catalog=self.catalog,
                kit=kit,
                logical_bus=1,
                generation=1,
                program_resolver=lambda _kit, slot: ("test", slot, 1.0),
            ).definitions
            for event in definition.events
            if event.kind == "drumHit"
        }
        self.assertIn(140, compiled_caps)
        self.assertIn(180, compiled_caps)

    def test_explicit_pad_identity_is_not_encoded_as_a_gm_note(self) -> None:
        for kit in (item for item in DRUM_KITS if item.engine == "sample"):
            program, pad, _gain = resolve_hit(kit.kit_id, "backbeat_primary")
            self.assertIn(program, kit.sample_programs)
            self.assertIsInstance(pad, str)
            self.assertFalse(pad.isdecimal())

    def test_factory_presets_use_exact_reviewed_sc_programs_and_kits(self) -> None:
        synths, *_defaults = load_synth_catalog(
            ROOT / "instruments" / "supercollider-legacy-map.json"
        )
        programs = {synth.key for synth in synths}
        kits = {kit.kit_id for kit in DRUM_KITS}
        index = json.loads(
            (CATALOG_ROOT / "sc_factory_presets_v1.json").read_text(encoding="utf-8")
        )["presets"]
        self.assertEqual(len(index), 18)
        for row in index:
            number = int(row["slot"])
            preset = json.loads(
                (ROOT / "instruments" / "default_presets" / f"p{number}.json")
                .read_text(encoding="utf-8")
            )
            with self.subTest(preset=number):
                self.assertEqual(preset["factory_name"], row["name"])
                self.assertEqual(preset["synths"]["chord"]["selected"], row["chord"])
                self.assertEqual(preset["synths"]["strum"]["selected"], row["strum"])
                self.assertEqual(preset["synths"]["bass"]["selected"], row["bass"])
                self.assertLessEqual(
                    {
                        preset["synths"][role]["selected"]
                        for role in ("chord", "strum", "bass")
                    },
                    programs,
                )
                rhythm = preset["rhythm"]
                self.assertEqual(rhythm["selected"], row["rhythm_id"])
                self.assertEqual(rhythm["drum_kit"], row["kit_id"])
                self.assertIn(rhythm["drum_kit"], kits)
                settings = rhythm["settings"][rhythm["selected"]]
                self.assertEqual(settings["tempo"], row["tempo"])
                self.assertEqual(settings["percussion_activity"], row["drum_activity"])
                self.assertEqual(settings["chord_activity"], row["chord_activity"])
                self.assertEqual(settings["bass_activity"], row["bass_activity"])

    def test_factory_presets_do_not_select_the_realtime_unsafe_modal_guitar(self) -> None:
        index = json.loads(
            (CATALOG_ROOT / "sc_factory_presets_v1.json").read_text(
                encoding="utf-8"
            )
        )["presets"]
        selected = {
            str(row[role])
            for row in index
            for role in ("chord", "strum", "bass")
        }
        self.assertNotIn("sc.sclork.modalElectricGuitar", selected)
        self.assertEqual(index[3]["strum"], "sc.sclork.pluck")
        self.assertEqual(index[7]["strum"], "sc.sclork.pluck")


if __name__ == "__main__":
    unittest.main()
