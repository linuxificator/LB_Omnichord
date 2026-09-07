from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AMYSYNTH_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "code"))

from amy_transport import AmySerialClient  # noqa: E402
from shared_reverb import (  # noqa: E402
    MIDI_REVERB_PROCESSOR,
    OMNI_REVERB_PROCESSOR,
    SHARED_REVERB_PROCESSOR_COUNT,
    bus_commands,
    processor_command,
)


class SharedReverbRoutingTests(unittest.TestCase):
    def test_processor_and_bus_wire_commands_are_canonical(self) -> None:
        self.assertEqual(
            processor_command(0, 0.4, 0.6, 0.7),
            "hR0,0.4,0.6,0.7Z",
        )
        self.assertEqual(bus_commands(3, 0, 0.25), ("y3h0Z", "y3hS0,0.25Z"))

    def test_omni_uses_one_processor_and_a_zero_drum_send(self) -> None:
        client = object.__new__(AmySerialClient)
        client.bus_id = {"drums": 0, "bass": 1, "strum": 2, "chord": 3}
        client.reverb = {
            "level": 0.4,
            "liveness": 0.6,
            "damping": 0.7,
            "drums": False,
        }
        commands: list[str] = []
        client._wire = commands.append

        client._apply_reverb_buses()

        self.assertEqual(
            commands,
            [
                "hR0,0.4,0.6,0.7Z",
                "y0h0Z",
                "y0hS0,0Z",
                "y1h0Z",
                "y1hS0,1Z",
                "y2h0Z",
                "y2hS0,1Z",
                "y3h0Z",
                "y3hS0,1Z",
            ],
        )

        commands.clear()
        client._set_reverb({**client.reverb, "drums": True})
        self.assertEqual(commands, ["y0hS0,1Z"])

        commands.clear()
        client._set_reverb({**client.reverb, "level": 0.8})
        self.assertEqual(commands, ["hR0,0.8,0.6,0.7Z"])

    def test_host_and_p4_reserve_the_same_two_processors(self) -> None:
        self.assertEqual(
            (OMNI_REVERB_PROCESSOR, MIDI_REVERB_PROCESSOR),
            tuple(range(SHARED_REVERB_PROCESSOR_COUNT)),
        )

        service_tree = ast.parse((ROOT / "code/local_amy_service.py").read_text())
        live_calls = [
            node
            for node in ast.walk(service_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "live"
        ]
        self.assertEqual(len(live_calls), 1)
        keywords = {item.arg: item.value for item in live_calls[0].keywords}
        configured = keywords["max_reverb_rooms"]
        self.assertIsInstance(configured, ast.Name)
        self.assertEqual(configured.id, "SHARED_REVERB_PROCESSOR_COUNT")

        p4_source = (AMYSYNTH_ROOT / "esp32p4/main/main.c").read_text()
        self.assertIn(
            f"#define AMY_REVERB_BANK_COUNT {SHARED_REVERB_PROCESSOR_COUNT}U",
            p4_source,
        )


if __name__ == "__main__":
    unittest.main()
