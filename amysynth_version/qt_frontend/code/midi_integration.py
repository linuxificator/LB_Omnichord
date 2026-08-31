from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Property, Slot

from midi_player import MIDI_PRESET_COUNT, MidiPlayerBackend
from performance_backend import InstrumentBackend as OmniInstrumentBackend


class InstrumentBackend(OmniInstrumentBackend):
    """Narrow integration seam between Omnichord and independent MIDI player."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._pending_omni_control_bindings: Any = []
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
        self.presetStored.connect(
            self._midi_player.refreshPresetBindingLocations
        )
        self._midi_player.replace_control_bindings(
            "omni",
            self._pending_omni_control_bindings,
        )

    def _apply_preset_data(self, data: dict[str, Any]) -> None:
        bindings = data.get("midi_control_bindings", [])
        self._pending_omni_control_bindings = bindings if isinstance(bindings, list) else []
        player = getattr(self, "_midi_player", None)
        protected = (
            player.capture_bound_control_values(
                "omni",
                incoming_bindings=self._pending_omni_control_bindings,
            )
            if player is not None
            else []
        )
        super()._apply_preset_data(data)
        if player is not None:
            player.restore_control_values(protected)
            player.replace_control_bindings(
                "omni",
                self._pending_omni_control_bindings,
            )

    def _midi_control_blocks(self, target: dict[str, Any]) -> bool:
        player = getattr(self, "_midi_player", None)
        return bool(
            player is not None
            and player.manual_change_blocked(target)
        )

    def _copy_strum_to_chord_state(self) -> None:
        player = getattr(self, "_midi_player", None)
        protected = (
            player.capture_bound_control_values("omni", role="chord")
            if player is not None
            else []
        )
        super()._copy_strum_to_chord_state()
        if player is not None:
            player.restore_control_values(protected)

    def _reset_synth_role_to_preset(self, role: str) -> None:
        player = getattr(self, "_midi_player", None)
        protected = (
            player.capture_bound_control_values("omni", role=role)
            if player is not None
            else []
        )
        controls = {
            (str(target["instrument"]), str(target["control"])): value
            for target, value in protected
            if str(target["kind"]) == "synth_control"
        }
        volume = next(
            (
                value
                for target, value in protected
                if str(target["kind"]) == "volume"
            ),
            None,
        )
        super()._reset_synth_role_to_preset(
            role,
            preserved_controls=controls,
            preserved_volume=volume,
        )

    def _preset_snapshot(self) -> dict[str, Any]:
        snapshot = super()._preset_snapshot()
        player = getattr(self, "_midi_player", None)
        if player is None:
            bindings = self._pending_omni_control_bindings
        else:
            bindings = player.control_bindings_snapshot("omni")
        snapshot["midi_control_bindings"] = bindings
        return snapshot

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

    @Slot(result=int)
    def midiTuningReference(self) -> int:
        return self._midi_player.tuningReference

    @Slot(result=float)
    def midiMasterVolume(self) -> float:
        return self._midi_player.masterVolume

    @Slot(result=bool)
    def midiMasterMuted(self) -> bool:
        return self._midi_player.masterMuted

    @Slot("QVariantMap", result=str)
    def midiControlTargetVisualState(self, target: dict[str, Any]) -> str:
        return self._midi_player.controlTargetVisualState(target)

    @Slot(int, result="QVariantList")
    def midiCommonControls(self, row: int) -> list[dict[str, Any]]:
        return self._midi_player.commonControls(row)

    @Slot(int, result="QVariantList")
    def midiExtraControls(self, row: int) -> list[dict[str, Any]]:
        return self._midi_player.extraControls(row)

    @Slot(result="QVariantList")
    def midiControlIndicators(self) -> list[dict[str, Any]]:
        return self._midi_player.commonControls(-1)

    @Slot(int, int, int)
    def injectMidiControl(
        self,
        channel: int,
        controller: int,
        value: int,
    ) -> None:
        self._midi_player.injectControl(channel, controller, value)

    @Slot(int, int)
    def injectMidiPitchBend(
        self,
        channel: int,
        value: int,
    ) -> None:
        self._midi_player.injectPitchBend(channel, value)

    @Slot(int, int, int)
    def injectMidiButton(
        self,
        channel: int,
        note: int,
        velocity: int,
    ) -> None:
        self._midi_player.injectButton(channel, note, velocity)

    @Slot(int, int)
    def selectMidiControlIndicator(self, channel: int, controller: int) -> None:
        self._midi_player.selectControlIndicator(channel, controller)

    @Slot("QVariantMap", result=bool)
    def activateMidiControlTarget(self, target: dict[str, Any]) -> bool:
        return self._midi_player.activateControlTarget(target)

    @Slot("QVariantMap")
    def doubleTapMidiControlTarget(self, target: dict[str, Any]) -> None:
        self._midi_player.controlTargetDoubleTapped(target)

    @Slot("QVariantMap")
    def moveMidiControlTarget(self, target: dict[str, Any]) -> None:
        self._midi_player.controlTargetMoved(target)

    @Slot(int, int)
    def setMidiSynthIndex(self, row: int, index: int) -> None:
        self._midi_player.setSynthIndex(row, index)

    @Slot(int, str, float)
    def setMidiSynthControl(self, row: int, key: str, value: float) -> None:
        self._midi_player.setControl(row, key, value)

    @Slot(int, float)
    def setMidiVolume(self, row: int, value: float) -> None:
        self._midi_player.setVolume(row, value)

    @Slot(float)
    def setMidiMasterVolume(self, value: float) -> None:
        self._midi_player.setMasterVolume(value)

    @Slot()
    def toggleMidiMasterMuted(self) -> None:
        self._midi_player.toggleMasterMuted()

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

    def _couple_tuning(self, preferred_screen: str) -> bool:
        omni_target = {"screen": "omni", "kind": "tuning_reference"}
        midi_target = {"screen": "midi", "kind": "tuning_reference"}
        omni_bound = self._midi_player.isControlTargetBound(omni_target)
        midi_bound = self._midi_player.isControlTargetBound(midi_target)

        if omni_bound and midi_bound:
            # Coupling may not choose between two independently MIDI-owned
            # values.  It is safe only when their references already agree.
            if self.tuningReference != self._midi_player.tuningReference:
                return False
            source = preferred_screen
        elif midi_bound:
            source = "midi"
        else:
            source = "omni"

        if source == "midi":
            self.syncOmniTuningFromMidi()
        else:
            self._midi_player.syncFromOmni()
        self._midi_player.setTuningCoupled(True)
        return True

    @Slot(result=bool)
    def coupleTuningFromOmni(self) -> bool:
        return self._couple_tuning("omni")

    @Slot(result=bool)
    def coupleTuningFromMidi(self) -> bool:
        return self._couple_tuning("midi")

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
