from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from engine_protocol import (  # noqa: E402
    NoteOff,
    NoteOn,
    ProtocolValidationError,
    SequenceDefinition,
    SequenceEvent,
    VoiceSet,
)


class EngineProtocolTests(unittest.TestCase):
    def test_frozen_note_contract_preserves_logical_key_and_tuned_frequency(self) -> None:
        event = NoteOn(
            owner="midi/row/2",
            handle="session-1/note-8",
            program_id="sc.sclork.FMRhodes1",
            program_revision=3,
            logical_key=60,
            frequency_hz=261.81234,
            velocity=0.5,
            logical_bus=5,
        )
        self.assertEqual(event.logical_key, 60)
        self.assertEqual(event.frequency_hz, 261.81234)

    def test_note_and_voice_values_must_be_finite(self) -> None:
        with self.assertRaisesRegex(ProtocolValidationError, "frequency_hz"):
            NoteOn("owner", "handle", "program", 1, 60, math.nan, 0.5, 0)
        with self.assertRaisesRegex(ProtocolValidationError, "value"):
            VoiceSet("handle", "cutoff", math.inf)
        with self.assertRaisesRegex(ProtocolValidationError, "release_velocity"):
            NoteOff("owner", "handle", -0.1)

    def test_definition_requires_stable_event_order_and_lifetime(self) -> None:
        events = (
            SequenceEvent(0, 0, "noteOn", ("voice/0",)),
            SequenceEvent(48, 1, "noteOff", ("voice/0",)),
        )
        definition = SequenceDefinition(
            "bass/gesture/00", 1, "finite", "bass", 0, events, "riff/42"
        )
        self.assertEqual(definition.max_end_tick, 48)
        with self.assertRaisesRegex(ProtocolValidationError, "ordered"):
            SequenceDefinition(
                "bad", 1, "finite", "bass", 0, tuple(reversed(events)), "fixture"
            )
        with self.assertRaisesRegex(ProtocolValidationError, "root period"):
            SequenceDefinition("root/bass", 1, "root", "bass", 0, (), "fixture")


if __name__ == "__main__":
    unittest.main()
