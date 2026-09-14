from __future__ import annotations

from typing import Any

from midi_control import PITCH_BEND_CONTROLLER


class BackendControlSurface:
    """Test-process adapter around the production backend's public behavior.

    The localhost integration controller can exercise normal UI slots through
    the wrapped backend. Input-specific helpers deliberately live here so the
    production QObject does not expose synthetic MIDI or OSC injection slots.
    """

    def __init__(self, backend: Any) -> None:
        self._backend = backend

    def __getattr__(self, name: str) -> Any:
        return getattr(self._backend, name)

    def injectMidiControl(self, channel: int, controller: int, value: int) -> None:
        self._backend.midiPlayer.process_midi_control(channel, controller, value)

    def injectMidiPitchBend(self, channel: int, value: int) -> None:
        self._backend.midiPlayer.process_midi_control(
            channel,
            PITCH_BEND_CONTROLLER,
            value,
        )

    def injectMidiButton(self, channel: int, note: int, velocity: int) -> None:
        self._backend.midiPlayer.process_midi_button(channel, note, velocity)

    def injectMidiNote(
        self,
        channel: int,
        note: int,
        velocity: int,
        is_on: bool,
    ) -> None:
        self._backend.midiPlayer.process_midi_note(
            channel,
            note,
            velocity,
            is_on,
        )

    def midiChordInputChannel(self) -> int:
        return int(self._backend.midiPlayer.chordInputChannel)

    def cycleMidiChordInputChannel(self) -> None:
        self._backend.midiPlayer.cycleChordInputChannel()

    def setMidiDrumKitIndex(self, index: int) -> None:
        self._backend.midiPlayer.setDrumKitIndex(index)

    def toggleMidiSynthKind(self, row: int) -> None:
        self._backend.midiPlayer.toggleSynthKind(row)

    def setMidiSynthBrowserIndex(self, row: int, index: int) -> None:
        self._backend.midiPlayer.setSynthBrowserIndex(row, index)

    def selectMidiSampleChoice(self, row: int, synth_index: int) -> None:
        self._backend.midiPlayer.selectSampleChoice(row, synth_index)

    def toggleMidiSustain(self, row: int) -> None:
        self._backend.midiPlayer.toggleSustain(row)

    def ensureRhythmRunning(self, enabled: bool) -> None:
        if bool(self._backend.rhythmRunning) != bool(enabled):
            self._backend.toggleRhythm()

    def ensureBassRunning(self, enabled: bool) -> None:
        if bool(self._backend.bassRunning) != bool(enabled):
            self._backend.toggleBassRunning()

    def ensureChordArpeggioRunning(self, enabled: bool) -> None:
        if bool(self._backend.chordArpeggioEnabled) != bool(enabled):
            self._backend.toggleChordArpeggio()

    def injectOscControl(
        self,
        address: str,
        argument: int,
        value: float,
        value_type: str = "continuous",
    ) -> None:
        self._backend.midiPlayer.process_osc_control(
            address,
            argument,
            value,
            value_type,
        )
