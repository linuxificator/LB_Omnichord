from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Property, Signal, Slot


class PerformanceQmlAdapter(QObject):
    """Stable direct-QObject surface for live-performance QML controls.

    PySide 6.7 on aarch64 does not reliably append Qt meta-object members from
    a Python QObject subclass after inherited slots. The performance backend
    keeps its domain behavior; this narrow adapter only exposes that existing
    behavior through a QObject whose complete Qt surface is declared here.
    """

    chordGateChanged = Signal()
    bassVoicingChanged = Signal()
    chordArpeggioChanged = Signal()

    def __init__(self, controller: Any) -> None:
        super().__init__(controller)
        self._controller = controller
        controller.chordGateChanged.connect(self.chordGateChanged.emit)
        controller.bassVoicingChanged.connect(self.bassVoicingChanged.emit)
        controller.chordArpeggioChanged.connect(self.chordArpeggioChanged.emit)

    @Property(int, notify=chordGateChanged)
    def chordGateState(self) -> int:
        return int(self._controller.chordGateState)

    @Property(str, notify=chordGateChanged)
    def chordGateButtonText(self) -> str:
        return str(self._controller.chordGateButtonText)

    @Property(bool, notify=chordArpeggioChanged)
    def chordArpeggioEnabled(self) -> bool:
        return bool(self._controller.chordArpeggioEnabled)

    @Property(int, notify=chordArpeggioChanged)
    def chordArpeggioRate(self) -> int:
        return int(self._controller.chordArpeggioRate)

    @Property(bool, notify=chordArpeggioChanged)
    def chordArpeggioDescending(self) -> bool:
        return bool(self._controller.chordArpeggioDescending)

    @Property(str, notify=chordArpeggioChanged)
    def chordArpeggioDirectionLabel(self) -> str:
        return str(self._controller.chordArpeggioDirectionLabel)

    @Property(int, notify=bassVoicingChanged)
    def bassVoicingShift(self) -> int:
        return int(self._controller.bassVoicingShift)

    @Property(bool, notify=bassVoicingChanged)
    def bassRiffMode(self) -> bool:
        return bool(self._controller.bassRiffMode)

    @Property(int, notify=bassVoicingChanged)
    def bassRiffSelector(self) -> int:
        return int(self._controller.bassRiffSelector)

    @Property(int, notify=bassVoicingChanged)
    def bassRiffSelectorMaximum(self) -> int:
        return int(self._controller.bassRiffSelectorMaximum)

    @Slot()
    def toggleChordGate(self) -> None:
        self._controller.toggleChordGate()

    @Slot()
    def toggleChordArpeggio(self) -> None:
        self._controller.toggleChordArpeggio()

    @Slot(float)
    def setChordArpeggioRate(self, value: float) -> None:
        self._controller.setChordArpeggioRate(value)

    @Slot()
    def toggleChordArpeggioDirection(self) -> None:
        self._controller.toggleChordArpeggioDirection()

    @Slot(float)
    def setBassVoicingShift(self, value: float) -> None:
        self._controller.setBassVoicingShift(value)

    @Slot(float)
    def setBassRiffSelector(self, value: float) -> None:
        self._controller.setBassRiffSelector(value)

    @Slot(float)
    def setRhythmBassActivity(self, value: float) -> None:
        self._controller.setRhythmBassActivity(value)

    @Slot(int)
    def setRhythmIndex(self, index: int) -> None:
        self._controller.setRhythmIndex(index)

    @Slot(int)
    def rollChordRows(self, direction: int) -> None:
        self._controller.rollChordRows(direction)

    @Slot()
    def panic(self) -> None:
        self._controller.panic()

    @Slot(bool)
    def setMidiTuningCoupled(self, coupled: bool) -> None:
        self._controller.setMidiTuningCoupled(coupled)

    @Slot(result=bool)
    def coupleTuningFromOmni(self) -> bool:
        return bool(self._controller.coupleTuningFromOmni())

    @Slot(result=bool)
    def coupleTuningFromMidi(self) -> bool:
        return bool(self._controller.coupleTuningFromMidi())

    @Slot(int, float, bool)
    def midiPreviewStart(
        self,
        row: int,
        normalized_y: float,
        coupled: bool,
    ) -> None:
        self._controller.midiPreviewStart(row, normalized_y, coupled)

    @Slot(int, float, bool)
    def midiPreviewMove(
        self,
        row: int,
        normalized_y: float,
        coupled: bool,
    ) -> None:
        self._controller.midiPreviewMove(row, normalized_y, coupled)

    @Slot()
    def midiPreviewEnd(self) -> None:
        self._controller.midiPreviewEnd()
