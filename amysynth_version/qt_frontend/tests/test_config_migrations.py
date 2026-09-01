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
        legacy["voices"]["rhythm_chord"] = 4
        legacy["midi_input"]["tech_profile"] = "linux"
        legacy["serial"]["baud"] = 230_400
        before = copy.deepcopy(legacy)

        migrated = migrate_config_document(legacy)

        self.assertEqual(legacy, before)
        self.assertEqual(migrated.source_revision, 0)
        self.assertEqual(migrated.target_revision, CURRENT_CONFIG_REVISION)
        self.assertEqual(migrated.data["config_revision"], 2)
        self.assertEqual(migrated.data["voices"]["rhythm_chord"], 7)
        self.assertEqual(migrated.data["midi_input"]["tech_profile"], "auto")
        self.assertEqual(migrated.data["serial"]["baud"], 230_400)
        self.assertEqual(
            migrated.changed_paths,
            (
                "$.voices.rhythm_chord",
                "$.config_revision",
                "$.midi_input.tech_profile",
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
        legacy["midi_input"]["tech_profile"] = "linux"

        migrated = migrate_config_document(legacy)

        self.assertEqual(migrated.source_revision, 1)
        self.assertEqual(migrated.data["midi_input"]["tech_profile"], "auto")
        self.assertEqual(
            migrated.changed_paths,
            ("$.midi_input.tech_profile", "$.config_revision"),
        )

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
