from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from screenshot_state import populate_screenshot_input_controls  # noqa: E402


class RecordingInjector:
    def __init__(self) -> None:
        self.events: list[tuple[object, ...]] = []

    def process_midi_control(self, channel: int, controller: int, value: int) -> None:
        self.events.append(("midi-control", channel, controller, value))

    def process_midi_button(self, channel: int, note: int, velocity: int) -> None:
        self.events.append(("midi-button", channel, note, velocity))

    def process_osc_control(
        self,
        address: str,
        argument: int,
        value: float,
        value_type: str,
    ) -> None:
        self.events.append(
            ("osc-control", address, argument, value, value_type)
        )


class ScreenshotStateTests(unittest.TestCase):
    def test_fixture_stages_rotaries_and_released_buttons_for_both_protocols(
        self,
    ) -> None:
        injector = RecordingInjector()

        populate_screenshot_input_controls(injector, injector)

        midi_controls = [
            event for event in injector.events if event[0] == "midi-control"
        ]
        osc_controls = [event for event in injector.events if event[0] == "osc-control"]
        self.assertGreaterEqual(len(midi_controls), 4)
        self.assertTrue(any(event[-1] == "continuous" for event in osc_controls))
        self.assertEqual(
            [event[-1] for event in injector.events if event[0] == "midi-button"],
            [127, 0],
        )
        self.assertEqual(
            [event[3] for event in osc_controls if event[-1] == "button"],
            [1.0, 0.0],
        )


if __name__ == "__main__":
    unittest.main()
