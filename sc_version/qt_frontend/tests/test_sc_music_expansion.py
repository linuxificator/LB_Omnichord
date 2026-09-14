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
from drum_patterns import load_drum_pattern_catalog  # noqa: E402


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
        self.assertLessEqual(sample_ids, manifest_ids)

    def test_pcm_velocity_layers_are_complete_and_every_role_resolves(self) -> None:
        kit_data = json.loads(
            (CATALOG_ROOT / "sc_pcm_drumkits_v1.json").read_text(encoding="utf-8")
        )
        expected_roles = {
            event.role
            for rhythm in load_drum_pattern_catalog(ROOT / "music" / "drums").rhythms.values()
            for level in rhythm.levels
            for event in level
        } | {
            event.role
            for rhythm in load_drum_pattern_catalog(ROOT / "music" / "drums").rhythms.values()
            for fill in rhythm.fills
            for event in fill.events
        }
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

    def test_legacy_pcm_arrangements_preserve_the_original_patterns(self) -> None:
        original = load_drum_pattern_catalog(ROOT / "music" / "drums")
        for rhythm_id in self.rhythm_ids:
            revised = self.catalog.arrangement("pcm-vsco", rhythm_id)
            source = original.rhythm(rhythm_id)
            self.assertEqual(revised.period_ticks, source.period_ticks)
            for source_level, revised_level in zip(source.levels, revised.levels):
                with self.subTest(rhythm=rhythm_id):
                    self.assertEqual(
                        [(event.tick, event.role, event.velocity) for event in source_level],
                        [(event.tick, event.role, event.velocity) for event in revised_level],
                    )

    def test_reviewed_groove_budget_is_real_and_bounded(self) -> None:
        counts = [
            len(level)
            for kit in DRUM_KITS
            for rhythm_id in self.rhythm_ids
            for level in self.catalog.arrangement(kit.kit_id, rhythm_id).levels
        ]
        self.assertEqual(max(counts), 57)
        self.assertTrue(all(count <= 64 for count in counts))

    def test_explicit_pad_identity_is_not_encoded_as_a_gm_note(self) -> None:
        for kit in (item for item in DRUM_KITS if item.engine == "sample"):
            program, pad, _gain = resolve_hit(kit.kit_id, "backbeat_primary")
            self.assertIn(program, kit.sample_programs)
            self.assertIsInstance(pad, str)
            self.assertFalse(pad.isdecimal())

    def test_factory_presets_use_exact_reviewed_sc_programs_and_kits(self) -> None:
        synths, *_defaults = load_synth_catalog(ROOT / "instruments" / "synths.json")
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


if __name__ == "__main__":
    unittest.main()
