from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from PySide6.QtGui import QColor, QImage


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from screenshot_state import (  # noqa: E402
    populate_screenshot_input_controls,
    populate_screenshot_instrument_browsers,
    save_png_screenshot,
)


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


class RecordingOmniBrowser:
    def __init__(self) -> None:
        self.kinds = {"chord": "synth", "strum": "sample", "bass": "synth"}
        self.events: list[tuple[object, ...]] = []

    def synthKind(self, role: str) -> str:
        return self.kinds[role]

    def toggleSynthKind(self, role: str) -> None:
        self.kinds[role] = "sample"
        self.events.append(("kind", role, "sample"))

    def synthBrowserNames(self, _role: str) -> list[str]:
        return ["Piano", "Organ", "Contrabass"]

    def setSynthBrowserIndex(self, role: str, index: int) -> None:
        self.events.append(("family", role, index))

    def setDrumKitIndex(self, index: int) -> None:
        self.events.append(("drums", index))


class RecordingMidiBrowser:
    def __init__(self) -> None:
        self.kinds = ["synth"] * 6
        self.events: list[tuple[object, ...]] = []

    def synthKind(self, row: int) -> str:
        return self.kinds[row]

    def toggleSynthKind(self, row: int) -> None:
        self.kinds[row] = "sample"
        self.events.append(("kind", row, "sample"))

    def synthBrowserNames(self, _row: int) -> list[str]:
        return ["Piano", "Organ", "Timpani"]

    def setSynthBrowserIndex(self, row: int, index: int) -> None:
        self.events.append(("family", row, index))

    def setDrumKitIndex(self, index: int) -> None:
        self.events.append(("drums", index))


class ScreenshotStateTests(unittest.TestCase):
    def test_png_capture_uses_qt_supported_suffix_inference(self) -> None:
        with tempfile.TemporaryDirectory(prefix="omnichord-capture-") as raw:
            path = Path(raw) / "screen.png"
            image = QImage(8, 8, QImage.Format.Format_RGBA8888)
            image.fill(QColor("#123456"))

            self.assertTrue(save_png_screenshot(image, path))
            self.assertFalse(QImage(str(path)).isNull())

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

    def test_browser_fixture_uses_public_selection_contracts(self) -> None:
        omni = RecordingOmniBrowser()
        midi = RecordingMidiBrowser()

        populate_screenshot_instrument_browsers(omni, midi)

        self.assertEqual(omni.kinds, {"chord": "sample", "strum": "sample", "bass": "sample"})
        self.assertIn(("family", "chord", 0), omni.events)
        self.assertIn(("family", "strum", 1), omni.events)
        self.assertIn(("family", "bass", 2), omni.events)
        self.assertIn(("drums", 2), omni.events)
        self.assertEqual(midi.kinds[:3], ["sample", "sample", "sample"])
        self.assertIn(("family", 0, 0), midi.events)
        self.assertIn(("family", 1, 1), midi.events)
        self.assertIn(("family", 2, 2), midi.events)
        self.assertIn(("drums", 3), midi.events)


if __name__ == "__main__":
    unittest.main()
