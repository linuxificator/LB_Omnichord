#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNIT = ROOT / "amysynth_version" / "qt_frontend" / "tests" / "test_instrument_defaults.py"


def replace_once(old: str, new: str) -> None:
    text = UNIT.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one unit-test anchor, found {count}: {old[:100]!r}")
    UNIT.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    '''        client.rhythm_running = False\n        return client\n''',
    '''        client.rhythm_running = False\n        client._wire = lambda command: None\n        return client\n''',
)

replace_once(
    '''    def test_live_chord_instrument_transaction_preserves_phase(self) -> None:\n        client = self.bare_client()\n        client.patch_map = {"juno_050": 50}\n        client.rhythm_running = True\n\n        calls: list[tuple[str, object]] = []\n\n        def prepare(*, reset_phase: bool):\n            calls.append(("prepare", reset_phase))\n            return 17, {"tempo": 108.0}\n\n        client._prepare_rhythm_rebuild = prepare\n        client._configure_synth = lambda role: calls.append(("configure", role))\n        client.writer = SimpleNamespace(\n            delay=lambda seconds: calls.append(("delay", seconds))\n        )\n        client._rhythm_guard_seconds = lambda: 0.01\n        client._install_rhythm_schedule = (\n            lambda generation, config: calls.append(("install", generation))\n        )\n\n        AmySerialClient._set_synth_state(\n            client,\n            "chord",\n            {\n                "name": "juno_050",\n                "params": ["resonance", 7.5],\n            },\n        )\n\n        self.assertEqual(\n            calls,\n            [\n                ("prepare", False),\n                ("configure", "chord"),\n                ("delay", 0.01),\n                ("install", 17),\n            ],\n        )\n''',
    '''    def test_live_chord_instrument_change_does_not_rebuild_sequencer(self) -> None:\n        client = self.bare_client()\n        client.patch_map = {"juno_050": 50}\n        client.rhythm_running = True\n\n        calls: list[tuple[str, object]] = []\n        client._wire = lambda command: calls.append(("wire", command))\n        client._configure_synth = lambda role: calls.append(("configure", role))\n\n        AmySerialClient._set_synth_state(\n            client,\n            "chord",\n            {\n                "name": "juno_050",\n                "params": ["resonance", 7.5],\n            },\n        )\n\n        self.assertEqual(\n            calls,\n            [("wire", "l0i4Z"), ("configure", "chord")],\n        )\n        self.assertFalse(\n            any(\n                command in {"zY0Z", "zY1Z", "S4096Z"}\n                for kind, command in calls\n                if kind == "wire"\n            )\n        )\n''',
)

replace_once(
    '''    def test_stopped_rhythm_is_not_rebuilt_on_chord_instrument_change(self) -> None:\n        client = self.bare_client()\n        client.patch_map = {"juno_050": 50}\n        calls: list[tuple[str, object]] = []\n        client._configure_synth = lambda role: calls.append(("configure", role))\n\n        AmySerialClient._set_synth_state(\n            client,\n            "chord",\n            {"name": "juno_050", "params": ["resonance", 7.5]},\n        )\n\n        self.assertEqual(calls, [("configure", "chord")])\n''',
    '''    def test_stopped_rhythm_is_not_rebuilt_on_chord_instrument_change(self) -> None:\n        client = self.bare_client()\n        client.patch_map = {"juno_050": 50}\n        calls: list[tuple[str, object]] = []\n        client._wire = lambda command: calls.append(("wire", command))\n        client._configure_synth = lambda role: calls.append(("configure", role))\n\n        AmySerialClient._set_synth_state(\n            client,\n            "chord",\n            {"name": "juno_050", "params": ["resonance", 7.5]},\n        )\n\n        self.assertEqual(\n            calls,\n            [("wire", "l0i4Z"), ("configure", "chord")],\n        )\n''',
)

# SimpleNamespace is no longer needed after removing the legacy rebuild fixture.
text = UNIT.read_text(encoding="utf-8")
text = text.replace("from types import SimpleNamespace\n", "")
UNIT.write_text(text, encoding="utf-8")
compile(text, str(UNIT), "exec")
