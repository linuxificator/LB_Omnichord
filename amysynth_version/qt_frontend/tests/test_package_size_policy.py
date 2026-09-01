from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[1]
PACKAGING = FRONTEND / "packaging"
sys.path.insert(0, str(PACKAGING))

from package_audit import audit  # noqa: E402
from qt_runtime_policy import (  # noqa: E402
    load_manifest,
    source_qml_imports,
    validate_source_imports,
)


class PackageSizePolicyTests(unittest.TestCase):
    def test_source_qml_imports_match_the_reviewed_runtime_surface(self) -> None:
        manifest = load_manifest()
        validate_source_imports(FRONTEND / "gui", manifest)
        self.assertEqual(
            source_qml_imports(FRONTEND / "gui"),
            tuple(manifest["source_qml_imports"]),
        )
        self.assertEqual(manifest["quick_controls_style"], "Basic")
        self.assertIn("QtQuick/Controls/Basic", manifest["qml_modules"])
        self.assertNotIn("QtQuick/Controls/Material", manifest["qml_modules"])

    def test_audit_writes_evidence_and_rejects_forbidden_qt_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "test.apk"
            report = root / "report.json"
            with zipfile.ZipFile(package, "w") as archive:
                archive.writestr("lib/arm64-v8a/libQt6Core_arm64-v8a.so", b"ok")
                archive.writestr(
                    "lib/arm64-v8a/libQt6Quick3D_arm64-v8a.so", b"unused"
                )

            with self.assertRaisesRegex(ValueError, "forbidden Qt runtime content"):
                audit(
                    platform="android-arm64",
                    output=report,
                    package=package,
                    tree=None,
                    max_package_bytes=10_000,
                )

            evidence = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(evidence["package_bytes"], package.stat().st_size)
            self.assertIn("Qt6Quick3D", evidence["qt_inventory"])
            self.assertEqual(
                evidence["forbidden_runtime_matches"][0]["fragment"],
                "Qt6Quick3D",
            )

    def test_audit_enforces_compressed_size_budget(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "test.zip"
            report = root / "report.json"
            with zipfile.ZipFile(package, "w") as archive:
                archive.writestr("payload.bin", b"x" * 100)

            with self.assertRaisesRegex(ValueError, "budget is 1 bytes"):
                audit(
                    platform="test",
                    output=report,
                    package=package,
                    tree=None,
                    max_package_bytes=1,
                )


if __name__ == "__main__":
    unittest.main()
