from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from app_core import InstrumentBackend, PRESET_COUNT


class PresetMigrationTests(unittest.TestCase):
    @staticmethod
    def _backend(preset_dir: Path) -> InstrumentBackend:
        backend = InstrumentBackend.__new__(InstrumentBackend)
        backend._preset_dir = preset_dir
        return backend

    @staticmethod
    def _legacy_preset() -> dict[str, object]:
        return {
            "version": 1,
            "synths": {
                "chord": {"selected": "prophet"},
                "strum": {"selected": "pluck"},
                "bass": {"selected": "fm"},
            },
            "rhythm": {"selected": "waltz"},
        }

    def _write_bank(self, preset_dir: Path) -> None:
        for number in range(1, PRESET_COUNT + 1):
            (preset_dir / f"p{number}.json").write_text(
                json.dumps(self._legacy_preset()), encoding="utf-8"
            )

    def test_identical_legacy_bootstrap_bank_is_archived(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            preset_dir = Path(temporary_dir)
            self._write_bank(preset_dir)

            archive = self._backend(
                preset_dir
            )._archive_legacy_bootstrap_presets()

            self.assertIsNotNone(archive)
            assert archive is not None
            self.assertEqual(len(list(archive.glob("p*.json"))), PRESET_COUNT)
            self.assertFalse((preset_dir / "p1.json").exists())

    def test_modified_legacy_bank_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            preset_dir = Path(temporary_dir)
            self._write_bank(preset_dir)
            changed = self._legacy_preset()
            changed["rhythm"] = {"selected": "rock"}
            (preset_dir / "p7.json").write_text(
                json.dumps(changed), encoding="utf-8"
            )

            archive = self._backend(
                preset_dir
            )._archive_legacy_bootstrap_presets()

            self.assertIsNone(archive)
            self.assertTrue((preset_dir / "p1.json").exists())
            self.assertTrue((preset_dir / "p7.json").exists())


if __name__ == "__main__":
    unittest.main()
