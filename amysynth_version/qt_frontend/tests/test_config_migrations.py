from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from config_migrations import (  # noqa: E402
    CURRENT_CONFIG_REVISION,
    REVISION_FIVE_GAMMA9001_MAP,
    REVISION_FOUR_SHIPPED_TINY_MAP,
    ConfigMigrationError,
    migrate_config_document,
)
from resolved_config import resolve_amy_config_data  # noqa: E402


class ConfigMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.shipped_path = ROOT / "config" / "amy_config.json"
        cls.shipped = json.loads(cls.shipped_path.read_text(encoding="utf-8"))

    def test_revision_zero_runs_every_transform_without_mutating_input(self) -> None:
        legacy = copy.deepcopy(self.shipped)
        legacy.pop("config_revision")
        legacy["rhythm"].pop("pattern_ranges")
        legacy["voices"]["rhythm_chord"] = 4
        legacy["midi_input"]["tech_profile"] = "linux"
        legacy["serial"]["baud"] = 230_400
        before = copy.deepcopy(legacy)

        migrated = migrate_config_document(legacy)

        self.assertEqual(legacy, before)
        self.assertEqual(migrated.source_revision, 0)
        self.assertEqual(migrated.target_revision, CURRENT_CONFIG_REVISION)
        self.assertEqual(
            migrated.data["config_revision"], CURRENT_CONFIG_REVISION
        )
        self.assertEqual(migrated.data["voices"]["rhythm_chord"], 7)
        self.assertEqual(migrated.data["midi_input"]["tech_profile"], "auto")
        self.assertEqual(migrated.data["serial"]["baud"], 230_400)
        self.assertEqual(
            migrated.changed_paths,
            (
                "$.voices.rhythm_chord",
                "$.config_revision",
                "$.midi_input.tech_profile",
                "$.rhythm.pattern_ranges",
            ),
        )
        resolved = resolve_amy_config_data(
            migrated.data,
            source_path=self.shipped_path,
            source_kind="user",
        )
        self.assertEqual(resolved.revision, CURRENT_CONFIG_REVISION)
        self.assertEqual(resolved.transport.serial_baud, 230_400)

    def test_revision_one_repairs_old_platform_default(self) -> None:
        legacy = copy.deepcopy(self.shipped)
        legacy["config_revision"] = 1
        legacy["rhythm"].pop("pattern_ranges")
        legacy["midi_input"]["tech_profile"] = "linux"

        migrated = migrate_config_document(legacy)

        self.assertEqual(migrated.source_revision, 1)
        self.assertEqual(migrated.data["midi_input"]["tech_profile"], "auto")
        self.assertEqual(
            migrated.changed_paths,
            (
                "$.midi_input.tech_profile",
                "$.config_revision",
                "$.rhythm.pattern_ranges",
            ),
        )

    def test_revision_two_adds_the_validated_pattern_layout(self) -> None:
        legacy = copy.deepcopy(self.shipped)
        legacy["config_revision"] = 2
        legacy["rhythm"].pop("pattern_ranges")

        migrated = migrate_config_document(legacy)

        self.assertEqual(
            migrated.data["rhythm"]["pattern_ranges"],
            {
                "fills": {"start": 0, "count": 936},
                "chords": {"start": 936, "count": 64},
                "drum_bases": {"start": 1000, "count": 24},
            },
        )
        self.assertEqual(
            migrated.changed_paths,
            ("$.rhythm.pattern_ranges", "$.config_revision"),
        )

    def test_revision_three_adds_missing_pattern_capacities(self) -> None:
        legacy = copy.deepcopy(self.shipped)
        legacy["config_revision"] = 3
        for key in (
            "amy_max_patterns",
            "amy_max_pattern_tags",
            "amy_max_pattern_instances",
        ):
            legacy.pop(key)

        migrated = migrate_config_document(legacy)

        self.assertEqual(
            migrated.data["config_revision"], CURRENT_CONFIG_REVISION
        )
        self.assertEqual(migrated.data["amy_max_patterns"], 1024)
        self.assertEqual(migrated.data["amy_max_pattern_tags"], 64)
        self.assertEqual(migrated.data["amy_max_pattern_instances"], 32)
        self.assertEqual(
            migrated.changed_paths,
            (
                "$.amy_max_patterns",
                "$.amy_max_pattern_tags",
                "$.amy_max_pattern_instances",
                "$.config_revision",
            ),
        )
        resolved = resolve_amy_config_data(
            migrated.data,
            source_path=self.shipped_path,
            source_kind="user",
        )
        self.assertEqual(resolved.capacities.max_patterns, 1024)
        self.assertEqual(resolved.capacities.max_pattern_tags, 64)
        self.assertEqual(resolved.capacities.max_pattern_instances, 32)

    def test_historical_schemas_make_revision_four_capacities_optional(self) -> None:
        capacity_keys = {
            "amy_max_patterns",
            "amy_max_pattern_tags",
            "amy_max_pattern_instances",
        }
        schema_root = ROOT / "config" / "schema"
        for revision in (1, 2, 3, 4, 5, 6):
            schema = json.loads(
                (schema_root / f"amy_config_v{revision}.schema.json").read_text(
                    encoding="utf-8"
                )
            )
            required = set(schema["required"])
            with self.subTest(revision=revision):
                if revision < 4:
                    self.assertTrue(capacity_keys.isdisjoint(required))
                else:
                    self.assertTrue(capacity_keys.issubset(required))
                midi_required = set(schema["properties"]["midi_input"]["required"])
                drum_required = set(schema["properties"]["drums"]["required"])
                added_midi = {"tech_profile", "alsa_raw_globs", "oss_midi_globs"}
                if revision < 4:
                    self.assertTrue(added_midi.isdisjoint(midi_required))
                    self.assertNotIn("kit", drum_required)
                else:
                    self.assertTrue(added_midi.issubset(midi_required))
                    self.assertIn("kit", drum_required)
                if revision < 6:
                    self.assertNotIn("osc_input", required)
                else:
                    self.assertNotIn("osc_input", required)
                    osc_schema = schema["properties"]["osc_input"]
                    self.assertEqual(osc_schema["required"], ["enabled"])
                    self.assertEqual(
                        osc_schema["dependencies"],
                        {
                            "listen_address": ["listen_port"],
                            "listen_port": ["listen_address"],
                        },
                    )

    def test_revision_four_infers_gamma_and_general_midi_kits(self) -> None:
        gamma = copy.deepcopy(self.shipped)
        gamma["config_revision"] = 3
        gamma["drums"].pop("kit")
        gamma["drums"]["sample_map"]["bd_haus"] = {"preset": 0, "note": 60}
        gamma["drums"]["sample_map"]["drum_snare_hard"] = {
            "preset": 12,
            "note": 45,
        }
        self.assertEqual(
            migrate_config_document(gamma).data["drums"]["kit"],
            "gamma9001",
        )

        general_midi = copy.deepcopy(self.shipped)
        general_midi["config_revision"] = 3
        general_midi["drums"].pop("kit")
        for sample in general_midi["drums"]["sample_map"].values():
            sample["preset"] = 258
        self.assertEqual(
            migrate_config_document(general_midi).data["drums"]["kit"],
            "general_midi",
        )

    def test_revision_four_rejects_an_unknown_legacy_drum_map(self) -> None:
        unknown = copy.deepcopy(self.shipped)
        unknown["config_revision"] = 3
        unknown["drums"].pop("kit")
        unknown["drums"]["sample_map"]["bd_haus"] = {"preset": 99, "note": 1}
        with self.assertRaisesRegex(ConfigMigrationError, "cannot infer"):
            migrate_config_document(unknown)

    def test_revision_five_repairs_the_published_tiny_default(self) -> None:
        released = copy.deepcopy(self.shipped)
        released["config_revision"] = 4
        released["drums"]["kit"] = "tiny"
        released["drums"]["sample_map"] = copy.deepcopy(
            REVISION_FOUR_SHIPPED_TINY_MAP
        )

        migrated = migrate_config_document(released)

        self.assertEqual(
            migrated.data["config_revision"], CURRENT_CONFIG_REVISION
        )
        self.assertEqual(migrated.data["drums"]["kit"], "gamma9001")
        self.assertEqual(
            migrated.data["drums"]["sample_map"],
            REVISION_FIVE_GAMMA9001_MAP,
        )
        self.assertEqual(
            migrated.changed_paths,
            ("$.drums.kit", "$.drums.sample_map", "$.config_revision"),
        )

    def test_revision_five_preserves_existing_gamma_and_general_midi(self) -> None:
        for kit in ("gamma9001", "general_midi"):
            existing = copy.deepcopy(self.shipped)
            existing["config_revision"] = 4
            existing["drums"]["kit"] = kit
            if kit == "general_midi":
                for sample in existing["drums"]["sample_map"].values():
                    sample["preset"] = 258
            before = copy.deepcopy(existing["drums"])

            migrated = migrate_config_document(existing)

            with self.subTest(kit=kit):
                self.assertEqual(migrated.data["drums"], before)
                self.assertEqual(
                    migrated.changed_paths, ("$.config_revision",)
                )

    def test_revision_six_adds_portable_osc_defaults(self) -> None:
        revision_five = copy.deepcopy(self.shipped)
        revision_five["config_revision"] = 5
        revision_five.pop("osc_input")

        migrated = migrate_config_document(revision_five)

        self.assertEqual(
            migrated.data["osc_input"],
            {
                "enabled": True,
                "listen_address": "0.0.0.0",
                "listen_port": 8000,
            },
        )
        self.assertEqual(
            migrated.changed_paths,
            ("$.osc_input", "$.config_revision"),
        )

    def test_revision_five_rejects_a_custom_tiny_mapping(self) -> None:
        custom = copy.deepcopy(self.shipped)
        custom["config_revision"] = 4
        custom["drums"]["kit"] = "tiny"
        custom["drums"]["sample_map"] = copy.deepcopy(
            REVISION_FOUR_SHIPPED_TINY_MAP
        )
        custom["drums"]["sample_map"]["perc_snap"]["note"] = 93

        with self.assertRaisesRegex(
            ConfigMigrationError, "custom Tiny mapping"
        ):
            migrate_config_document(custom)

    def test_current_revision_is_idempotent(self) -> None:
        migrated = migrate_config_document(self.shipped)
        self.assertFalse(migrated.changed)
        self.assertEqual(migrated.changed_paths, ())
        self.assertEqual(migrated.data, self.shipped)
        self.assertIsNot(migrated.data, self.shipped)

    def test_invalid_and_future_revisions_report_the_config_path(self) -> None:
        for revision in (True, -1, "one"):
            invalid = copy.deepcopy(self.shipped)
            invalid["config_revision"] = revision
            with self.subTest(revision=revision):
                with self.assertRaises(ConfigMigrationError) as caught:
                    migrate_config_document(invalid)
                self.assertEqual(caught.exception.path, "$.config_revision")

        future = copy.deepcopy(self.shipped)
        future["config_revision"] = 99
        with self.assertRaisesRegex(ConfigMigrationError, "newer than supported"):
            migrate_config_document(future)


if __name__ == "__main__":
    unittest.main()
