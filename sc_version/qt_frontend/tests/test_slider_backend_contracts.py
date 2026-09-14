from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from app_core import InstrumentBackend  # noqa: E402
from midi_player import MidiPlayerBackend  # noqa: E402


class SliderBackendContractTests(unittest.TestCase):
    def test_omni_ui_live_edits_do_not_republish_synth_control_models(
        self,
    ) -> None:
        backend = InstrumentBackend.__new__(InstrumentBackend)
        calls: list[tuple[str, str, float, bool]] = []

        def record_setter(
            self: InstrumentBackend,
            role: str,
            key: str,
            value: float,
            *,
            emit_controls: bool = True,
        ) -> None:
            calls.append((role, key, float(value), bool(emit_controls)))

        backend._set_synth_control = types.MethodType(record_setter, backend)

        backend.setChordSynthControl("attack_ms", 12)
        backend.editChordSynthControl("attack_ms", 13)
        backend.setStrumSynthControl("release_ms", 21)
        backend.editStrumSynthControl("release_ms", 22)
        backend.setBassSynthControl("filter_hz", 440)
        backend.editBassSynthControl("filter_hz", 441)

        self.assertEqual(
            calls,
            [
                ("chord", "attack_ms", 12.0, True),
                ("chord", "attack_ms", 13.0, False),
                ("strum", "release_ms", 21.0, True),
                ("strum", "release_ms", 22.0, False),
                ("bass", "filter_hz", 440.0, True),
                ("bass", "filter_hz", 441.0, False),
            ],
        )

    def test_midi_ui_live_edits_do_not_republish_row_state(self) -> None:
        backend = MidiPlayerBackend.__new__(MidiPlayerBackend)
        calls: list[tuple[int, str, float, bool]] = []

        def record_setter(
            self: MidiPlayerBackend,
            row: int,
            key: str,
            value: float,
            *,
            emit_state: bool,
        ) -> None:
            calls.append((int(row), key, float(value), bool(emit_state)))

        backend._set_control = types.MethodType(record_setter, backend)

        backend.setControl(2, "sustain", 0.5)
        backend.editControl(2, "sustain", 0.6)

        self.assertEqual(
            calls,
            [
                (2, "sustain", 0.5, True),
                (2, "sustain", 0.6, False),
            ],
        )


if __name__ == "__main__":
    unittest.main()
