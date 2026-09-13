from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "quality"))

from qml_lint import new_warning_buckets, normalize_report  # noqa: E402


class QmlLintQualityTests(unittest.TestCase):
    def test_report_paths_are_portable_and_locations_are_preserved(self) -> None:
        raw = {
            "files": [
                {
                    "filename": str(ROOT / "gui" / "Main.qml"),
                    "success": False,
                    "warnings": [
                        {
                            "id": "unqualified",
                            "type": "warning",
                            "line": 42,
                            "column": 7,
                            "length": 4,
                            "message": "Unqualified access",
                        }
                    ],
                }
            ]
        }

        report = normalize_report(raw, ROOT)

        self.assertEqual(report["files"][0]["path"], "gui/Main.qml")
        self.assertEqual(report["files"][0]["warnings"][0]["line"], 42)
        self.assertEqual(report["files"][0]["warnings"][0]["column"], 7)

    def test_ratchet_allows_reduction_but_rejects_new_warning_bucket(self) -> None:
        baseline = {
            "warnings": [
                {"path": "gui/Main.qml", "id": "unqualified", "count": 2}
            ]
        }
        reduced = {
            "files": [
                {
                    "path": "gui/Main.qml",
                    "warnings": [{"id": "unqualified"}],
                }
            ]
        }
        increased = {
            "files": [
                *reduced["files"],
                {
                    "path": "gui/New.qml",
                    "warnings": [{"id": "missing-property"}],
                },
            ]
        }

        self.assertFalse(new_warning_buckets(reduced, baseline))
        self.assertEqual(
            new_warning_buckets(increased, baseline)[
                ("gui/New.qml", "missing-property")
            ],
            1,
        )


if __name__ == "__main__":
    unittest.main()
