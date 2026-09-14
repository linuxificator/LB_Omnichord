from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
sys.path.insert(0, str(CODE))

from performance_qml_adapter import PerformanceQmlAdapter  # noqa: E402


class FakeController(QObject):
    performanceChanged = Signal()
    chordGateChanged = Signal()
    bassVoicingChanged = Signal()
    chordArpeggioChanged = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.chordGateState = 1
        self.chordGateButtonText = "CHORD\nON"
        self.chordArpeggioEnabled = True
        self.chordArpeggioRate = 3
        self.chordArpeggioDescending = True
        self.chordArpeggioDirectionLabel = "down"
        self.bassVoicingShift = -2
        self.bassRiffMode = True
        self.bassRiffSelector = 4
        self.bassRiffSelectorMaximum = 9
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def _record(self, name: str, *args: Any) -> None:
        self.calls.append((name, args))

    def __getattr__(self, name: str) -> Any:
        def call(*args: Any) -> Any:
            self._record(name, *args)
            return name != "coupleTuningFromOmni"

        return call


class PerformanceQmlAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.controller = FakeController()
        self.adapter = PerformanceQmlAdapter(self.controller)

    def test_complete_qml_surface_is_in_direct_meta_object(self) -> None:
        meta = self.adapter.metaObject()
        for name in (
            "chordGateState",
            "chordGateButtonText",
            "chordArpeggioEnabled",
            "chordArpeggioRate",
            "chordArpeggioDescending",
            "chordArpeggioDirectionLabel",
            "bassVoicingShift",
            "bassRiffMode",
            "bassRiffSelector",
            "bassRiffSelectorMaximum",
        ):
            self.assertGreaterEqual(meta.indexOfProperty(name), 0, name)
        for signature in (
            "toggleChordGate()",
            "toggleChordArpeggio()",
            "setChordArpeggioRate(double)",
            "toggleChordArpeggioDirection()",
            "setBassVoicingShift(double)",
            "setBassRiffSelector(double)",
            "setRhythmBassActivity(double)",
            "setRhythmIndex(int)",
            "rollChordRows(int)",
            "panic()",
            "setMidiTuningCoupled(bool)",
            "coupleTuningFromOmni()",
            "coupleTuningFromMidi()",
            "midiPreviewStart(int,double,bool)",
            "midiPreviewMove(int,double,bool)",
            "midiPreviewEnd()",
        ):
            self.assertGreaterEqual(meta.indexOfMethod(signature), 0, signature)

    def test_properties_and_notify_signals_delegate_to_controller(self) -> None:
        self.assertEqual(self.adapter.chordGateState, 1)
        self.assertEqual(self.adapter.chordGateButtonText, "CHORD\nON")
        self.assertTrue(self.adapter.chordArpeggioEnabled)
        self.assertEqual(self.adapter.chordArpeggioRate, 3)
        self.assertTrue(self.adapter.chordArpeggioDescending)
        self.assertEqual(self.adapter.chordArpeggioDirectionLabel, "down")
        self.assertEqual(self.adapter.bassVoicingShift, -2)
        self.assertTrue(self.adapter.bassRiffMode)
        self.assertEqual(self.adapter.bassRiffSelector, 4)
        self.assertEqual(self.adapter.bassRiffSelectorMaximum, 9)

        counts = {"gate": 0, "bass": 0, "arp": 0}
        self.adapter.chordGateChanged.connect(
            lambda: counts.__setitem__("gate", counts["gate"] + 1)
        )
        self.adapter.bassVoicingChanged.connect(
            lambda: counts.__setitem__("bass", counts["bass"] + 1)
        )
        self.adapter.chordArpeggioChanged.connect(
            lambda: counts.__setitem__("arp", counts["arp"] + 1)
        )
        self.controller.performanceChanged.emit()
        self.assertEqual(counts, {"gate": 1, "bass": 1, "arp": 1})

    def test_actions_delegate_without_duplicating_domain_logic(self) -> None:
        self.adapter.toggleChordGate()
        self.adapter.toggleChordArpeggio()
        self.adapter.setChordArpeggioRate(4.0)
        self.adapter.toggleChordArpeggioDirection()
        self.adapter.setBassVoicingShift(2.0)
        self.adapter.setBassRiffSelector(5.0)
        self.adapter.setRhythmBassActivity(3.0)
        self.adapter.setRhythmIndex(7)
        self.adapter.rollChordRows(-1)
        self.adapter.panic()
        self.adapter.setMidiTuningCoupled(False)
        self.assertFalse(self.adapter.coupleTuningFromOmni())
        self.assertTrue(self.adapter.coupleTuningFromMidi())
        self.adapter.midiPreviewStart(2, 0.25, True)
        self.adapter.midiPreviewMove(2, 0.75, True)
        self.adapter.midiPreviewEnd()

        self.assertEqual(
            self.controller.calls,
            [
                ("toggleChordGate", ()),
                ("toggleChordArpeggio", ()),
                ("setChordArpeggioRate", (4.0,)),
                ("toggleChordArpeggioDirection", ()),
                ("setBassVoicingShift", (2.0,)),
                ("setBassRiffSelector", (5.0,)),
                ("setRhythmBassActivity", (3.0,)),
                ("setRhythmIndex", (7,)),
                ("rollChordRows", (-1,)),
                ("panic", ()),
                ("setMidiTuningCoupled", (False,)),
                ("coupleTuningFromOmni", ()),
                ("coupleTuningFromMidi", ()),
                ("midiPreviewStart", (2, 0.25, True)),
                ("midiPreviewMove", (2, 0.75, True)),
                ("midiPreviewEnd", ()),
            ],
        )


if __name__ == "__main__":
    unittest.main()
