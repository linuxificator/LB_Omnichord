from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SUPPORT = ROOT / "tests" / "support"
CODE = ROOT / "code"
for module_dir in (SUPPORT, CODE):
    if str(module_dir) not in sys.path:
        sys.path.insert(0, str(module_dir))

from backend_control_surface import BackendControlSurface  # noqa: E402


class _Writer:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def high(self, command: str) -> None:
        self.commands.append(command)


class BackendControlSurfaceTests(unittest.TestCase):
    def test_firmware_diagnostics_are_an_explicit_read_only_allowlist(
        self,
    ) -> None:
        writer = _Writer()
        adapter = BackendControlSurface(
            object(),
            SimpleNamespace(writer=writer),
        )

        adapter.requestAmyDiagnostics("load")
        adapter.requestAmyDiagnostics("reverb")
        adapter.requestAmyDiagnostics("sequence")

        self.assertEqual(writer.commands, ["?loadZ", "?reverbZ", "D1Z"])
        with self.assertRaisesRegex(ValueError, "load, reverb, or sequence"):
            adapter.requestAmyDiagnostics("v0w0f440Z")
        self.assertEqual(writer.commands, ["?loadZ", "?reverbZ", "D1Z"])

    def test_firmware_diagnostics_require_a_real_transport(self) -> None:
        adapter = BackendControlSurface(object())
        with self.assertRaisesRegex(RuntimeError, "transport is unavailable"):
            adapter.requestAmyDiagnostics()


if __name__ == "__main__":
    unittest.main()
