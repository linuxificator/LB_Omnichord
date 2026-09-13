from __future__ import annotations

from pathlib import Path
from typing import Protocol


class ScreenshotMidiInputInjector(Protocol):
    """Internal input-processing surface used by deterministic screenshots."""

    def process_midi_control(self, channel: int, controller: int, value: int) -> None: ...

    def process_midi_button(self, channel: int, note: int, velocity: int) -> None: ...


class ScreenshotOscInputInjector(Protocol):
    """Internal OSC processing surface used by deterministic screenshots."""

    def process_osc_control(
        self,
        address: str,
        argument: int,
        value: float,
        value_type: str,
    ) -> None: ...


class ScreenshotImage(Protocol):
    """Small image surface needed by the deterministic capture path."""

    def isNull(self) -> bool: ...

    def save(self, file_name: str) -> bool: ...


def save_png_screenshot(image: ScreenshotImage, path: Path) -> bool:
    """Save a non-null image, letting Qt infer PNG from the file suffix."""

    return not image.isNull() and image.save(str(path))


def populate_screenshot_input_controls(
    midi_injector: ScreenshotMidiInputInjector,
    osc_injector: ScreenshotOscInputInjector,
) -> None:
    """Stage representative MIDI and OSC rotary and pushbutton input."""

    # Continuous controls need a baseline packet followed by genuine movement.
    for channel, controller, value in (
        (2, 7, 104),
        (2, 11, 72),
    ):
        midi_injector.process_midi_control(channel, controller, 0)
        midi_injector.process_midi_control(channel, controller, value)

    # A complete press/release keeps a neutral MIDI pushbutton visible.
    midi_injector.process_midi_button(2, 48, 127)
    midi_injector.process_midi_button(2, 48, 0)

    for address, osc_value in (
        ("/tone", 0.78),
        ("/level", 0.46),
    ):
        osc_injector.process_osc_control(address, 0, 0.0, "continuous")
        osc_injector.process_osc_control(address, 0, osc_value, "continuous")

    # OSC buttons use the same press/release presentation contract as MIDI.
    osc_injector.process_osc_control("/fill", 0, 1.0, "button")
    osc_injector.process_osc_control("/fill", 0, 0.0, "button")
