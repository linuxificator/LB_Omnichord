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

sys.path.insert(0, str(PACKAGING))
from appimage_entry import packaged_asset_root  # noqa: E402

sys.path.insert(0, str(FRONTEND / "tools"))
from clean_package_outputs import clean  # noqa: E402


class PackageSizePolicyTests(unittest.TestCase):
    def test_package_cleanup_is_dry_run_by_default_and_exact_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            frontend = Path(directory) / "qt_frontend"
            kept = frontend / "code" / "main.py"
            build_file = frontend / "build" / "cache.bin"
            dist_file = frontend / "dist" / "old.AppImage"
            for path in (kept, build_file, dist_file):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"data")

            dry_run = clean(frontend, delete=False)
            self.assertEqual(sum(item[1] for item in dry_run), 2)
            self.assertTrue(build_file.exists())
            self.assertTrue(dist_file.exists())

            clean(frontend, delete=True)
            self.assertFalse((frontend / "build").exists())
            self.assertFalse((frontend / "dist").exists())
            self.assertTrue(kept.exists())

    def test_packaged_asset_root_accepts_pyinstaller_internal_layout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            internal = root / "_internal"
            for name in ("config", "gui", "instruments", "music"):
                (internal / name).mkdir(parents=True)
            self.assertEqual(
                packaged_asset_root(meipass=root, executable=root / "app"),
                internal,
            )

    def test_catalog_schema_location_is_supplied_by_the_catalog_owner(self) -> None:
        catalogue_schema = (FRONTEND / "code" / "catalog_schema.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("SCHEMA_DIRECTORY", catalogue_schema)
        self.assertIn("schema_directory: Path", catalogue_schema)

        drum_patterns = (FRONTEND / "code" / "drum_patterns.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('schema_directory=path.parent.parent / "schema"', drum_patterns)

        bass_riffs = (FRONTEND / "code" / "bass_riffs.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('schema_directory=path.parent / "schema"', bass_riffs)

    def test_source_qml_imports_match_the_reviewed_runtime_surface(self) -> None:
        manifest = load_manifest()
        validate_source_imports(FRONTEND / "gui", manifest)
        self.assertEqual(
            source_qml_imports(FRONTEND / "gui"),
            tuple(manifest["source_qml_imports"]),
        )
        self.assertEqual(manifest["quick_controls_style"], "Basic")
        self.assertIn("PySide6.QtWidgets", manifest["python_modules"])
        self.assertIn("QtQuick/Controls/Basic", manifest["qml_modules"])
        self.assertNotIn("QtQuick/Controls/Material", manifest["qml_modules"])

    def test_every_desktop_builder_uses_the_local_qml_hook_and_audit(self) -> None:
        builders = (
            PACKAGING / "build_appimage.sh",
            PACKAGING / "build_macos_dmg.sh",
            PACKAGING / "build_windows.ps1",
        )
        for builder in builders:
            source = builder.read_text(encoding="utf-8")
            self.assertIn("pyinstaller_hooks", source, builder.name)
            self.assertIn("qt_runtime_policy.py", source, builder.name)
            self.assertIn("package_audit.py", source, builder.name)
        qml_hook = PACKAGING / "pyinstaller_hooks" / "hook-PySide6.QtQml.py"
        qml_source = qml_hook.read_text(encoding="utf-8")
        self.assertIn('manifest["qml_modules"]', qml_source)
        self.assertNotIn("collect_qtqml_files", qml_source)
        self.assertIn('"/qmltooling/"', qml_source)
        gui_hook = PACKAGING / "pyinstaller_hooks" / "hook-PySide6.QtGui.py"
        gui_source = gui_hook.read_text(encoding="utf-8")
        self.assertIn('"/imageformats/"', gui_source)
        self.assertIn('"virtualkeyboard"', gui_source)

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

    def test_manifest_budget_is_used_when_no_override_is_given(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "test.zip"
            report = root / "report.json"
            with zipfile.ZipFile(package, "w") as archive:
                archive.writestr("payload.bin", b"small")

            evidence = audit(
                platform="Linux-x86_64",
                output=report,
                package=package,
                tree=None,
                max_package_bytes=None,
            )
            self.assertEqual(evidence["package_budget_bytes"], 105_000_000)


if __name__ == "__main__":
    unittest.main()
