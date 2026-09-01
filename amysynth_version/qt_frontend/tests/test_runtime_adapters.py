from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
sys.path.insert(0, str(CODE))

from package_test_hooks import (  # noqa: E402
    PACKAGE_SMOKE_STATUS_ENV,
    PackageTestHooks,
)
from runtime_diagnostics import display_diagnostic_lines  # noqa: E402
from windows_launcher import guarded_package_main  # noqa: E402


class RuntimeAdapterTests(unittest.TestCase):
    def test_diagnostics_are_structured_from_an_explicit_environment(self) -> None:
        lines = display_diagnostic_lines(
            "wayland",
            {
                "XDG_SESSION_TYPE": "wayland",
                "WAYLAND_DISPLAY": "wayland-1",
                "DISPLAY": ":1",
            },
        )
        self.assertEqual(lines[0], "Qt Omnichord display diagnostics:")
        self.assertTrue(any("QPA platform: wayland" in line for line in lines))
        self.assertTrue(any("XDG_SESSION_TYPE: wayland" in line for line in lines))
        self.assertTrue(any("QT_QPA_PLATFORM: <auto>" in line for line in lines))

    def test_package_hook_records_only_when_enabled_and_can_redirect(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            initial = Path(directory) / "initial.status"
            redirected = Path(directory) / "android.status"
            disabled = PackageTestHooks(False, initial)
            disabled.checkpoint("ignored")
            self.assertFalse(initial.exists())

            active = disabled.redirected(enabled=True, status=redirected)
            active.checkpoint("qgui-created")
            self.assertEqual(redirected.read_text(), "qgui-created\n")

    def test_environment_factory_preserves_package_status_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            status = Path(directory) / "smoke.status"
            with patch.dict(os.environ, {PACKAGE_SMOKE_STATUS_ENV: str(status)}):
                hooks = PackageTestHooks.from_environment(True)
            hooks.checkpoint("frontend-entered")
            self.assertEqual(status.read_text(), "frontend-entered\n")

    def test_guarded_windowed_entry_records_fatal_package_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            status = Path(directory) / "fatal.status"
            with patch.dict(os.environ, {PACKAGE_SMOKE_STATUS_ENV: str(status)}):
                result = guarded_package_main(
                    lambda: (_ for _ in ()).throw(RuntimeError("boom"))
                )
            self.assertEqual(result, 1)
            self.assertIn("fatal-error RuntimeError: boom", status.read_text())

    def test_portable_core_contains_no_platform_runtime_details(self) -> None:
        app_core = (CODE / "app_core.py").read_text(encoding="utf-8")
        main = (CODE / "main.py").read_text(encoding="utf-8")
        for forbidden in (
            "QStandardPaths",
            "ANDROID_SMOKE_ENABLE",
            "XDG_SESSION_TYPE",
            "WAYLAND_DISPLAY",
        ):
            self.assertNotIn(forbidden, app_core)
        self.assertNotIn("sys.stdout is None", main)
        self.assertNotIn("fatal-error", main)


if __name__ == "__main__":
    unittest.main()
