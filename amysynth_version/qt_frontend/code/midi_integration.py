from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Property, Slot

from midi_player import MIDI_PRESET_COUNT, MidiPlayerBackend
from performance_backend import InstrumentBackend as OmniInstrumentBackend


class InstrumentBackend(OmniInstrumentBackend):
    """Narrow integration seam between Omnichord and independent MIDI player."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._syncing_tuning = False
        self._midi_player = MidiPlayerBackend(
            owner=self,
            synths=tuple(self._synths),
            client=self._client,
        )
        self._midi_player.stateChanged.connect(self.midiStateChanged)
        self._midi_player.tuningChanged.connect(self.midiTuningChanged)
        self._midi_player.tuningChanged.connect(
            self._sync_omni_tuning_when_coupled
        )
        self.tuningChanged.connect(self._sync_midi_tuning_when_coupled)
        self._midi_player.presetChanged.connect(self.midiPresetChanged)
        self._midi_player.presetStored.connect(self.midiPresetStored)

    @Property(QObject, constant=True)
    def midiPlayer(self) -> QObject:
        return self._midi_player

    @Property("QVariantList", constant=True)
    def midiSynthNames(self) -> list[str]:
        return self._midi_player.synthNames

    @Property(int, constant=True)
    def midiPresetCount(self) -> int:
        return MIDI_PRESET_COUNT

    # Kept as a read-only compatibility query for the integration harness.
    # QML observes MidiPlayerBackend.selectedPreset directly, where the notify
    # signal belongs to the same Qt meta-object.
    @Property(int)
    def selectedMidiPreset(self) -> int:
        return self._midi_player.selectedPreset

    @Slot(int, result=int)
    def midiSynthIndex(self, row: int) -> int:
        return self._midi_player.synthIndex(row)

    @Slot(int, result=int)
    def midiChannel(self, row: int) -> int:
        return self._midi_player.channel(row)

    @Slot(int, result=float)
    def midiVolume(self, row: int) -> float:
        return self._midi_player.volume(row)

    @Slot(int, result="QVariantList")
    def midiCommonControls(self, row: int) -> list[dict[str, Any]]:
        return self._midi_player.commonControls(row)

    @Slot(int, result="QVariantList")
    def midiExtraControls(self, row: int) -> list[dict[str, Any]]:
        return self._midi_player.extraControls(row)

    @Slot(int, int)
    def setMidiSynthIndex(self, row: int, index: int) -> None:
        self._midi_player.setSynthIndex(row, index)

    @Slot(int, str, float)
    def setMidiSynthControl(self, row: int, key: str, value: float) -> None:
        self._midi_player.setControl(row, key, value)

    @Slot(int, float)
    def setMidiVolume(self, row: int, value: float) -> None:
        self._midi_player.setVolume(row, value)

    @Slot(int)
    def cycleMidiChannel(self, row: int) -> None:
        self._midi_player.cycleChannel(row)

    @Slot(int)
    def resetMidiSynthRow(self, row: int) -> None:
        self._midi_player.resetRow(row)

    @Slot(int)
    def selectMidiPreset(self, number: int) -> None:
        self._midi_player.selectPreset(number)

    @Slot()
    def storeSelectedMidiPreset(self) -> None:
        self._midi_player.storeSelectedPreset()

    @Slot(bool)
    def setMidiTuningCoupled(self, coupled: bool) -> None:
        self._midi_player.setTuningCoupled(coupled)

    def _sync_midi_tuning_when_coupled(self) -> None:
        if not self._midi_player.tuningCoupled or self._syncing_tuning:
            return
        self._syncing_tuning = True
        try:
            self._midi_player.syncFromOmni()
        finally:
            self._syncing_tuning = False

    def _sync_omni_tuning_when_coupled(self) -> None:
        if not self._midi_player.tuningCoupled or self._syncing_tuning:
            return
        self._syncing_tuning = True
        try:
            self._copy_midi_tuning_to_omni()
        finally:
            self._syncing_tuning = False

    def _copy_midi_tuning_to_omni(self) -> None:
        self.setTuningModeIndex(self._midi_player.tuningModeIndex)
        self.setTuningReference(self._midi_player.tuningReference)

    @Slot()
    def syncMidiTuningFromOmni(self) -> None:
        self._midi_player.syncFromOmni()

    @Slot()
    def syncOmniTuningFromMidi(self) -> None:
        if self._syncing_tuning:
            return
        self._syncing_tuning = True
        try:
            self._copy_midi_tuning_to_omni()
        finally:
            self._syncing_tuning = False

    @Slot()
    def coupleTuningFromOmni(self) -> None:
        self._midi_player.syncFromOmni()
        self._midi_player.setTuningCoupled(True)

    @Slot()
    def coupleTuningFromMidi(self) -> None:
        self.syncOmniTuningFromMidi()
        self._midi_player.setTuningCoupled(True)

    @Slot(int)
    def setMidiTuningModeIndex(self, index: int) -> None:
        self._midi_player.setTuningModeIndex(index)

    @Slot(int)
    def setMidiTuningReference(self, value: int) -> None:
        self._midi_player.setTuningReference(value)

    @Slot(int)
    def beginMidiPitchBend(self, direction: int) -> None:
        self._midi_player.beginPitchBend(direction)

    @Slot()
    def endMidiPitchBend(self) -> None:
        self._midi_player.endPitchBend()

    @Slot(int, float, bool)
    def midiPreviewStart(
        self,
        row: int,
        normalized_y: float,
        coupled: bool,
    ) -> None:
        self._midi_player.setTuningCoupled(coupled)
        self._midi_player.previewStart(row, normalized_y)

    @Slot(int, float, bool)
    def midiPreviewMove(
        self,
        row: int,
        normalized_y: float,
        coupled: bool,
    ) -> None:
        self._midi_player.setTuningCoupled(coupled)
        self._midi_player.previewMove(row, normalized_y)

    @Slot()
    def midiPreviewEnd(self) -> None:
        self._midi_player.previewEnd()

    @Slot()
    def finishMidiPreview(self) -> None:
        self._midi_player.previewEnd()

    @Slot(int, int, int, bool)
    def injectMidiNote(
        self,
        channel: int,
        note: int,
        velocity: int,
        is_on: bool,
    ) -> None:
        self._midi_player.injectNote(channel, note, velocity, is_on)

    @Slot()
    def panic(self) -> None:
        super().panic()
        self._midi_player.rebuild_after_panic()

    def send_initial_state(self) -> None:
        super().send_initial_state()
        self._midi_player.send_initial_state()
