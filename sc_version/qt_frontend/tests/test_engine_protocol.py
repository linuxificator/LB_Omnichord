from __future__ import annotations

import math
from pathlib import Path
import sys
import unittest


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
            SequenceEvent(
                0,
                0,
                "noteOn",
                (
                    "voice/0",
                    "bass",
                    "sc.sclork.fmBass",
                    1,
                    36,
                    65.4,
                    0.8,
                    "ordinary",
                    0,
                    0.0,
                    1,
                ),
            ),
            SequenceEvent(48, 1, "noteOff", ("voice/0", 0.0)),
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


class SequenceEventContractTests(unittest.TestCase):
    def test_every_supported_action_accepts_its_exact_payload(self) -> None:
        fixtures = (
            ("launch", ("child",)),
            ("gateBegin", ("snare", "fill/snare", 48, "drumHit")),
            ("rootStop", ("bass/root",)),
            ("rootStart", ("bass/root",)),
            (
                "noteOn",
                (
                    "voice",
                    "bass",
                    "sc.sclork.fmBass",
                    1,
                    36,
                    65.4,
                    0.8,
                    "ordinary",
                    0,
                    0.0,
                    1,
                ),
            ),
            ("noteOff", ("voice", 0.0)),
            ("voiceSet", ("voice", "frequency_hz", 73.4)),
            (
                "drumHit",
                ("low_primary/kick", "sample.vsco.kit.old-parlour", 1, "kick", 36, 0.8, 0),
            ),
        )
        for kind, atoms in fixtures:
            with self.subTest(kind=kind):
                SequenceEvent(0, 0, kind, atoms)  # type: ignore[arg-type]

    def test_payload_size_is_action_specific(self) -> None:
        with self.assertRaisesRegex(
            ProtocolValidationError,
            "launch requires 1 atoms, received 0",
        ):
            SequenceEvent(0, 0, "launch", ())

    def test_musical_ranges_are_checked_before_udp_delivery(self) -> None:
        with self.assertRaisesRegex(ProtocolValidationError, "logical bus"):
            SequenceEvent(
                0,
                0,
                "drumHit",
                ("low_primary/kick", "sample.vsco.kit.old-parlour", 1, "kick", 36, 0.8, 11),
            )
        with self.assertRaisesRegex(ProtocolValidationError, "velocity"):
            SequenceEvent(0, 0, "noteOff", ("voice", 1.1))

    def test_gate_must_be_bounded_and_explicitly_scoped(self) -> None:
        with self.assertRaisesRegex(ProtocolValidationError, "must be positive"):
            SequenceEvent(0, 0, "gateBegin", ("snare", "fill", 0, "drumHit"))
        with self.assertRaisesRegex(ProtocolValidationError, "gate scope"):
            SequenceEvent(0, 0, "gateBegin", ("snare", "fill", 48, "everything"))


if __name__ == "__main__":
    unittest.main()
