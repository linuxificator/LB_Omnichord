from __future__ import annotations

import hashlib
import runpy
import unittest
from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[1]
REPOSITORY = FRONTEND.parents[1]
DESIGN_ROOT = REPOSITORY / "amysynth_version" / "design"
RUNTIME_DRUM_DATA = FRONTEND / "music" / "drums"


class RepositoryDataHygieneTests(unittest.TestCase):
    def test_runtime_drum_directory_is_the_only_designated_data_source(self) -> None:
        expected = {
            "drum_activity_instruments_gamma9001.json",
            "drum_activity_instruments_general_midi.json",
            "drum_activity_instruments_tiny.json",
            "drum_activity_timing.json",
            "drum_fill_continuation_roles.json",
            "drum_fill_levels.json",
            "drum_fills_instruments_gamma9001.json",
            "drum_fills_instruments_general_midi.json",
            "drum_fills_instruments_tiny.json",
            "drum_fills_timing.json",
        }
        self.assertEqual(
            {path.name for path in RUNTIME_DRUM_DATA.glob("*.json")}, expected
        )

    def test_design_tree_does_not_duplicate_runtime_drum_json(self) -> None:
        runtime_hashes = {
            hashlib.sha256(path.read_bytes()).hexdigest(): path
            for path in RUNTIME_DRUM_DATA.glob("*.json")
        }
        duplicates = []
        for path in DESIGN_ROOT.rglob("*.json"):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest in runtime_hashes:
                duplicates.append((path, runtime_hashes[digest]))
        self.assertEqual(duplicates, [])


class RepositoryToolLayoutTests(unittest.TestCase):
    def test_tracked_temporary_tools_are_rejected(self) -> None:
        offenders = sorted(
            path.relative_to(REPOSITORY).as_posix()
            for root in (REPOSITORY / "tools", FRONTEND / "tools")
            if root.is_dir()
            for path in root.rglob("tmp_*")
            if "fixtures" not in path.parts
        )
        self.assertEqual(offenders, [])

    def test_diagnostics_are_paired_and_read_only_by_location(self) -> None:
        diagnostics = FRONTEND / "tools" / "diagnostics"
        scripts = sorted(diagnostics.glob("*_baseline.py"))
        self.assertTrue(scripts)
        for script in scripts:
            self.assertTrue(script.with_suffix(".qml").is_file(), script.name)
            namespace = runpy.run_path(str(script), run_name="diagnostic_check")
            self.assertEqual(namespace["ROOT"], FRONTEND, script.name)
            self.assertEqual(
                namespace["QML_FILE"], script.with_suffix(".qml"), script.name
            )

    def test_test_control_server_is_not_production_code(self) -> None:
        self.assertFalse((FRONTEND / "code" / "test_control.py").exists())
        self.assertTrue(
            (FRONTEND / "tests" / "support" / "control_server.py").is_file()
        )
        for path in (FRONTEND / "code").glob("*.py"):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("control_server", source, path.name)


if __name__ == "__main__":
    unittest.main()
