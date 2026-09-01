from __future__ import annotations

import sys
import threading
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from midi_binding_service import MidiBindingService  # noqa: E402
from midi_control import (  # noqa: E402
    NOTE_BUTTON_OFFSET,
    PITCH_BEND_CONTROLLER,
    MidiControlState,
)


def normalize_target(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict) or "id" not in value:
        return None
    return {"id": str(value["id"]), "screen": str(value["screen"])}


class MidiBindingServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = MidiControlState(capacity=8)
        self.service = MidiBindingService(self.state, threading.RLock())

    def test_normalizes_all_supported_source_types(self) -> None:
        entries = self.service.normalize_entries(
            "midi",
            [
                {"channel": 1, "controller": 7, "target": {"id": "volume"}},
                {"channel": 2, "source_type": "pitch_bend", "target": {"id": "bend"}},
                {"channel": 3, "source_type": "note_button", "note": 60, "target": {"id": "tap"}},
                {"channel": 4, "source_type": "unknown", "target": {"id": "bad"}},
                {"channel": 4, "controller": 8, "target": {}},
            ],
            normalize_target,
        )

        self.assertEqual(
            tuple(entry.key for entry in entries),
            ((1, 7), (2, PITCH_BEND_CONTROLLER), (3, NOTE_BUTTON_OFFSET + 60)),
        )

    def test_screen_replacement_is_separate_and_round_trips(self) -> None:
        midi = self.service.normalize_entries(
            "midi",
            [{"channel": 1, "controller": 7, "target": {"id": "m"}}],
            normalize_target,
        )
        omni = self.service.normalize_entries(
            "omni",
            [{"channel": 2, "controller": 8, "target": {"id": "o"}}],
            normalize_target,
        )
        self.service.replace_screen("midi", midi)
        self.service.replace_screen("omni", omni)

        self.assertEqual(self.service.serialize("midi")[0]["target"]["screen"], "midi")
        self.assertEqual(self.service.serialize("omni")[0]["target"]["screen"], "omni")

    def test_presentation_is_an_immutable_detached_snapshot(self) -> None:
        self.state.observe(1, 7, 0, now=1.0)
        self.state.observe(1, 7, 10, now=2.0)
        snapshot = self.service.presentation()
        qml_model = snapshot.qml_model()
        qml_model[0]["value"] = 99

        self.assertNotEqual(self.service.presentation().qml_model()[0]["value"], 99)
        with self.assertRaises(AttributeError):
            snapshot.indicator_items = ()  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
