from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

import run_tests  # noqa: E402


class TestRunnerTests(unittest.TestCase):
    def test_script_result_records_failure_and_duration_without_hiding_output(self) -> None:
        script = run_tests.TESTS / "sample.py"
        with tempfile.TemporaryDirectory() as directory:
            artifacts = Path(directory)
            with (
                patch.object(
                    run_tests.subprocess,
                    "run",
                    return_value=subprocess.CompletedProcess([], 7),
                ) as invoke,
                patch.object(
                    run_tests.time,
                    "monotonic",
                    side_effect=(10.0, 10.25),
                ),
            ):
                result = run_tests.run_script(
                    script,
                    suite="unit",
                    suite_artifacts=artifacts,
                )

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.returncode, 7)
        self.assertEqual(result.duration_seconds, 0.25)
        self.assertEqual(
            invoke.call_args.args[0],
            [sys.executable, str(script)],
        )
        self.assertFalse(invoke.call_args.kwargs.get("capture_output", False))

    def test_atomic_report_has_no_temporary_file_after_replace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reports" / "unit.json"
            run_tests._write_json_atomic(
                path,
                {"schema_version": 1, "status": "passed"},
            )

            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {"schema_version": 1, "status": "passed"},
            )
            self.assertFalse(path.with_name(".unit.json.tmp").exists())

    def test_coverage_command_keeps_each_test_in_its_own_process(self) -> None:
        script = run_tests.TESTS / "sample.py"
        command = run_tests._command_for_script(script, Path("coverage"))

        self.assertEqual(command[:4], [sys.executable, "-m", "coverage", "run"])
        self.assertEqual(command[-1], str(script))
        self.assertNotEqual(command[0], str(script))


if __name__ == "__main__":
    unittest.main()
