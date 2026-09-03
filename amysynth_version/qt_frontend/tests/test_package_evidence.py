from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUPPORT = ROOT / "tests" / "support"
import sys

sys.path.insert(0, str(SUPPORT))

from package_evidence import PNG_SIGNATURE, evaluate  # noqa: E402


class PackageEvidenceTests(unittest.TestCase):
    def test_one_manifest_covers_portable_platform_and_package_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            artifact = root / "LB_Omnichord.zip"
            artifact.write_bytes(b"package")
            audit = root / "audit.json"
            audit.write_text(
                json.dumps(
                    {
                        "platform": "Windows-x86_64",
                        "package_bytes": 7,
                        "forbidden_runtime_matches": [],
                    }
                ),
                encoding="utf-8",
            )
            qml = root / "qml.json"
            qml.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "source_imports": ["QtQuick"],
                        "reviewed_qml_modules": ["QtQuick"],
                        "scanner_result": [],
                    }
                ),
                encoding="utf-8",
            )
            app_log = root / "application.log"
            app_log.write_text(
                "AMY service session completed: 2 wire commands, 3 nonzero PCM samples\n",
                encoding="utf-8",
            )
            input_log = root / "input.log"
            input_log.write_text("Ran 2 tests\nOK\n", encoding="utf-8")
            screenshots = []
            for name in ("omni.png", "midi.png"):
                path = root / name
                path.write_bytes(PNG_SIGNATURE + bytes(2048))
                screenshots.append(path)

            manifest = evaluate(
                argparse.Namespace(
                    platform="Windows-x86_64",
                    artifact=artifact,
                    package_audit=audit,
                    qml_imports=qml,
                    application_log=app_log,
                    external_input_contract_log=input_log,
                    screenshot=screenshots,
                    regression_result="success",
                    audio_evidence=None,
                )
            )

        self.assertTrue(manifest["passed"])
        self.assertEqual(
            {item["evidence_class"] for item in manifest["scenarios"]},
            {"package", "portable-integration", "package-integration", "regression"},
        )

    def test_missing_runtime_marker_is_reported_without_hiding_other_results(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            artifact = root / "app"
            artifact.write_bytes(b"x")
            audit = root / "audit.json"
            audit.write_text(
                json.dumps(
                    {
                        "platform": "Linux-x86_64",
                        "package_bytes": 1,
                        "forbidden_runtime_matches": [],
                    }
                ),
                encoding="utf-8",
            )
            qml = root / "qml.json"
            qml.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "source_imports": ["QtQuick"],
                        "reviewed_qml_modules": ["QtQuick"],
                        "scanner_result": [],
                    }
                ),
                encoding="utf-8",
            )
            log = root / "log"
            log.write_text("OK\n", encoding="utf-8")
            pngs = []
            for name in ("a.png", "b.png"):
                path = root / name
                path.write_bytes(PNG_SIGNATURE + bytes(2048))
                pngs.append(path)
            manifest = evaluate(
                argparse.Namespace(
                    platform="Linux-x86_64",
                    artifact=artifact,
                    package_audit=audit,
                    qml_imports=qml,
                    application_log=log,
                    external_input_contract_log=log,
                    screenshot=pngs,
                    regression_result="success",
                    audio_evidence=None,
                )
            )

        failures = {
            item["identifier"]
            for item in manifest["scenarios"]
            if not item["passed"]
        }
        self.assertEqual(failures, {"packaged-runtime"})


if __name__ == "__main__":
    unittest.main()
