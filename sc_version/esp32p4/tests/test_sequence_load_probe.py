from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "diagnostics"
    / "sequence_load_probe.py"
)
SPEC = importlib.util.spec_from_file_location("sequence_load_probe", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)


class SequenceLoadProbeTest(unittest.TestCase):
    def test_modes_have_identical_event_payloads(self) -> None:
        root = PROBE.workload("root")
        stored = PROBE.workload("stored")

        root_events = [message.split(",", 1)[1] for message in root if message.startswith("H")]
        stored_events = []
        for message in stored:
            if not message.startswith("H") or message.startswith(("HC", "HR")):
                continue
            prefix, rest = message.split(",", 1)
            period, tagged_payload = rest.split(",", 1)
            payload = tagged_payload.lstrip("0123456789")
            stored_events.append(f"{period}{payload}")

        self.assertEqual(root_events, stored_events)
        self.assertEqual(len(root_events), PROBE.PATTERN_COUNT * 4)

    def test_root_uses_no_stored_sequence_commands(self) -> None:
        messages = PROBE.workload("root")
        self.assertFalse(any(message.startswith(("HC", "HR")) for message in messages))

    def test_shared_reverb_option_configures_two_rooms(self) -> None:
        messages = PROBE.workload("root", shared_reverb=True)
        self.assertIn("hR0,0.25,0.5,0.5,3000Z", messages)
        self.assertIn("hR1,0.25,0.5,0.5,3000Z", messages)
        self.assertEqual(sum(message.startswith("hR") for message in messages), 2)


if __name__ == "__main__":
    unittest.main()
