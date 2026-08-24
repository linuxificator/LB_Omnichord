from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from midi_player import MidiAmyEngine  # noqa: E402
from synth_state import SynthState  # noqa: E402


class _RecordingWriter:
    def __init__(self, events: list[tuple[str, object]]) -> None:
        self.events = events

    def delay(self, seconds: float) -> None:
        self.events.append(("delay", seconds))


class _Client:
    def __init__(self) -> None:
        self.events: list[tuple[str, object]] = []
        self.writer = _RecordingWriter(self.events)
        self.config = {
            "midi_player": {},
            "buses": {
                "midi_rows": [4, 5, 6, 7, 8, 9],
                "midi_drums": 10,
            },
            "performance": {"synth_alloc_guard_ms": 12.0},
        }
        self.patch_map = {"dx7_215": 215}

    def _wire(self, command: str) -> None:
        self.events.append(("wire", command))

    @staticmethod
    def _f(value: float) -> str:
        return f"{float(value):.9g}"

    @staticmethod
    def _patch_compatibility_commands(
        patch: int,
        synth: int,
    ) -> list[str]:
        return [f"compat-{patch}-{synth}"]


class MidiAmyEngineTests(unittest.TestCase):
    def test_rom_patch_waits_before_parameters_and_routing(self) -> None:
        client = _Client()
        engine = MidiAmyEngine(client)
        client.events.clear()

        engine.configure_row(
            0,
            "dx7_215",
            {"algorithm": 7.0},
            0.28,
        )
        self.assertEqual(
            client.events,
            [
                ("wire", "K215i5iv4iy4Z"),
                ("delay", 0.012),
                ("wire", "compat-215-5"),
                ("wire", "v0o7i5Z"),
                ("wire", "i5iy4Z"),
                ("wire", "i5iV0.28Z"),
            ],
        )

    def test_only_reconfiguration_silences_an_existing_synth(self) -> None:
        client = _Client()
        engine = MidiAmyEngine(client)
        client.events.clear()

        engine.configure_row(5, "dx7_215", {}, 0.5)
        first_commands = [value for kind, value in client.events if kind == "wire"]
        self.assertNotIn("l0i10Z", first_commands)

        client.events.clear()
        engine.configure_row(5, "dx7_215", {}, 0.5)
        second_commands = [value for kind, value in client.events if kind == "wire"]
        self.assertEqual(second_commands[0], "l0i10Z")

    def test_unallocated_drum_row_is_not_sent_a_note_off(self) -> None:
        client = _Client()
        engine = MidiAmyEngine(client)
        client.events.clear()

        engine.silence_row(5)

        self.assertEqual(client.events, [])

    def test_strum_preview_releases_before_exceeding_voice_count(self) -> None:
        client = _Client()
        engine = MidiAmyEngine(client)
        client.events.clear()

        class Timer:
            def __init__(self, _delay: float, callback: object) -> None:
                self.callback = callback
                self.daemon = False

            def start(self) -> None:
                return

        with patch("midi_player.threading.Timer", Timer):
            for note in (60.0, 64.0, 67.0, 71.0, 72.0):
                engine.preview_note(0, note)

        commands = [value for kind, value in client.events if kind == "wire"]
        fifth_on = commands.index("n72l0.826771654i5Z")
        self.assertEqual(commands[fifth_on - 1], "n60l0i5Z")
        self.assertEqual(
            engine._preview_active_notes[0],
            [64.0, 67.0, 71.0, 72.0],
        )

    def test_every_midi_instrument_has_an_isolated_effect_bus(self) -> None:
        client = _Client()
        engine = MidiAmyEngine(client)

        self.assertEqual(engine.row_buses, (4, 5, 6, 7, 8, 9))
        self.assertEqual(engine.drum_bus, 10)

        client.events.clear()
        engine.configure_row(2, "dx7_215", {}, 0.5)
        self.assertIn(("wire", "K215i7iv4iy6Z"), client.events)
        self.assertIn(("wire", "i7iy6Z"), client.events)

        client.events.clear()
        engine.set_reverb(0.4, 0.6, 0.7, False)
        reverb_commands = [
            value
            for kind, value in client.events
            if kind == "wire" and str(value).startswith("y")
        ]
        self.assertEqual(
            reverb_commands,
            [
                "y4h0.4,0.6,0.7Z",
                "y5h0.4,0.6,0.7Z",
                "y6h0.4,0.6,0.7Z",
                "y7h0.4,0.6,0.7Z",
                "y8h0.4,0.6,0.7Z",
                "y9h0.4,0.6,0.7Z",
                "y10h0,0.6,0.7Z",
            ],
        )

    def test_native_defaults_are_not_resent_by_midi_state(self) -> None:
        class Control:
            key = "filter_hz"
            label = "VCF base"
            group = "extra"
            default = 6000.0
            native_default = 6000.0
            minimum = 20.0
            maximum = 18000.0
            step = 1.0
            decimals = 0
            unit = "Hz"
            scale = "log"

        class Definition:
            key = "juno_068"
            label = "Harpsichord 1"
            controls = (Control(),)

        state = SynthState((Definition(),), 0)

        self.assertEqual(
            state.transport_payload(),
            {"name": "juno_068", "params": []},
        )


if __name__ == "__main__":
    unittest.main()
