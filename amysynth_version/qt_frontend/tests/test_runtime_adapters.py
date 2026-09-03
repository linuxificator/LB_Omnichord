from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
sys.path.insert(0, str(CODE))

from runtime_diagnostics import display_diagnostic_lines  # noqa: E402


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
