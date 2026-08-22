from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import Property, Signal, Slot

import app_core
from performance_logic import (
    clamp_bass_voicing_shift,
    roll_bass_voicing,
    roll_chord_indexes,
)


CHORD_GATE_NONE = 0
CHORD_GATE_ON = 1
CHORD_GATE_OFF = 2
BASS_VOICING_LIMIT = 6


class InstrumentBackend(app_core.InstrumentBackend):
    """Live-performance state layered on the stable application core.

    The base class still owns catalogue/preset loading, touch dropout handling,
    tuning, synth state and transport.  This layer owns performance concepts
    that must survive independently of the sounding chord: remembered chord
    identity, chord gate state, bass inversion/voicing and grouped row rolls.
    """

    chordGateChanged = Signal()
    bassVoicingChanged = Signal()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Base construction loads a preset through virtual methods, so these
        # fields must exist before super().__init__() starts.
        self._chord_gate_state = CHORD_GATE_NONE
        self._bass_voicing_shift = 0
        super().__init__(*args, **kwargs)

    def _set_chord_gate_state(self, state: int, *, emit: bool = True) -> bool:
        state = max(CHORD_GATE_NONE, min(CHORD_GATE_OFF, int(state)))
        if state == self._chord_gate_state:
            return False
        self._chord_gate_state = state
        if emit:
            self.chordGateChanged.emit()
            # isOff remains a compatibility property but now follows the gate.
            self._emit_state_changed()
        return True

    @Property(int, notify=chordGateChanged)
    def chordGateState(self) -> int:
        return self._chord_gate_state

    @Property(str, notify=chordGateChanged)
    def chordGateButtonText(self) -> str:
        if self._chord_gate_state == CHORD_GATE_ON:
            return "CHORD\nOFF"
        if self._chord_gate_state == CHORD_GATE_OFF:
            return "CHORD\nON"
        return ""

    @Property(bool, notify=chordGateChanged)
    def isOff(self) -> bool:
        return self._chord_gate_state != CHORD_GATE_ON

    @Property(int, notify=bassVoicingChanged)
    def bassVoicingShift(self) -> int:
        return self._bass_voicing_shift

    def _chord_gate_enabled(self) -> bool:
        return (
            self._chord_gate_state == CHORD_GATE_ON
            and self._active_row >= 0
            and self._active_root_semitone >= 0
            and self._effective_chord_activity() > 0
        )

    def _set_active_chord(self, row_index: int, root_semitone: int) -> None:
        # Any newly selected chord becomes the remembered chord and explicitly
        # re-opens the chord gate.  Releasing the physical chord does not erase
        # its identity; strum and bass continue to use this remembered chord.
        self._set_chord_gate_state(CHORD_GATE_ON)
        super()._set_active_chord(row_index, root_semitone)

    def _send_rhythm_chord_enabled(self) -> None:
        enabled = self._chord_gate_enabled()
        self._debug(
            "osc_rhythm_chord_enabled",
            value=1 if enabled else 0,
            chord_gate_state=self._chord_gate_state,
            **self._debug_chord_state(),
        )
        self._client.send_message(
            self._rhythm_chord_enabled_address,
            1 if enabled else 0,
        )

    def _send_chord_state(self, play_now: bool) -> None:
        # Keep notes in the receiver even while chord sound is gated off.  This
        # is what lets the strum and bass keep using the last selected chord.
        payload = {
            "notes": self._tuned_notes(
                self._current_notes(),
                self._active_root_semitone,
            ),
            "bass_notes": self._tuned_notes(
                self._current_bass_notes(),
                self._active_root_semitone,
            ),
            "play_now": bool(
                play_now and self._chord_gate_state == CHORD_GATE_ON
            ),
            "rhythm_running": bool(self._rhythm_running),
            "rhythm_chord_enabled": self._chord_gate_enabled(),
        }
        self._debug(
            "osc_chord_state",
            play_now=payload["play_now"],
            notes=payload["notes"],
            bass_notes=payload["bass_notes"],
            packet_rhythm_running=payload["rhythm_running"],
            chord_gate_state=self._chord_gate_state,
            **self._debug_chord_state(),
        )
        self._client.send_message(
            self._chord_state_address,
            json.dumps(payload, separators=(",", ":")),
        )

    @Slot()
    def toggleChordGate(self) -> None:
        if self._chord_gate_state == CHORD_GATE_NONE:
            return
        if self._chord_gate_state == CHORD_GATE_ON:
            self.turnOff()
            return

        # Re-enable the automatic chord lane first while the receiver still has
        # the remembered note list, then publish/retrigger the same chord.
        self._set_chord_gate_state(CHORD_GATE_ON)
        self._send_rhythm_chord_enabled()
        self._send_chord_state(play_now=True)

    @Slot()
    def turnOff(self) -> None:
        # Compatibility slot retained for older QML/tests.  Unlike the previous
        # implementation it does not destroy the active/remembered chord.
        self._release_all_pressed_chords()
        if self._active_row < 0 or self._active_root_semitone < 0:
            self._set_chord_gate_state(CHORD_GATE_NONE)
        else:
            self._set_chord_gate_state(CHORD_GATE_OFF)
        self._strum_last_index = None

        # Important ordering: close the explicit receiver gate while it still
        # believes the lane is enabled, so it sends note-off to a sounding
        # rhythm chord.  Then update the remembered note/bass state.
        self._send_rhythm_chord_enabled()
        self._send_chord_state(play_now=False)

    def _current_bass_notes(self) -> list[int]:
        return roll_bass_voicing(
            super()._current_bass_notes(),
            self._bass_voicing_shift,
        )

    @Slot(float)
    def setBassVoicingShift(self, value: float) -> None:
        shifted = clamp_bass_voicing_shift(
            value,
            limit=BASS_VOICING_LIMIT,
        )
        if shifted == self._bass_voicing_shift:
            return
        self._bass_voicing_shift = shifted
        self.bassVoicingChanged.emit()
        if self._active_row >= 0 and self._active_root_semitone >= 0:
            self._send_chord_state(play_now=False)

    @Slot(int)
    def rollChordRows(self, direction: int) -> None:
        if int(direction) == 0:
            return
        self._row_chord_indexes = roll_chord_indexes(
            self._row_chord_indexes,
            len(self._chords),
            direction,
        )
        # This mirrors a manual wheel change: changing chord type returns the
        # row to root position rather than carrying an inversion across types.
        self._row_inversion_indexes = [0] * app_core.ROW_COUNT
        self._strum_last_index = None
        self._emit_state_changed()
        for row_index in range(app_core.ROW_COUNT):
            self._refresh_row_chord_notes(row_index)

    def _reset_presettable_state_to_defaults(self) -> None:
        super()._reset_presettable_state_to_defaults()
        rhythm = self._defaults.get("rhythm", {})
        self._bass_voicing_shift = clamp_bass_voicing_shift(
            rhythm.get("bass_voicing_shift", 0),
            limit=BASS_VOICING_LIMIT,
        )

    def _apply_preset_data(self, data: dict[str, Any]) -> None:
        super()._apply_preset_data(data)
        rhythm = data.get("rhythm", {})
        if not isinstance(rhythm, dict):
            rhythm = {}
        self._bass_voicing_shift = clamp_bass_voicing_shift(
            rhythm.get("bass_voicing_shift", self._bass_voicing_shift),
            limit=BASS_VOICING_LIMIT,
        )
        # Chord identity/gating is live performance state, never preset state.
        self._chord_gate_state = CHORD_GATE_NONE

    def _preset_snapshot(self) -> dict[str, Any]:
        snapshot = super()._preset_snapshot()
        rhythm = snapshot.setdefault("rhythm", {})
        rhythm["bass_voicing_shift"] = self._bass_voicing_shift
        return snapshot

    def _emit_full_preset_state(self) -> None:
        super()._emit_full_preset_state()
        self.bassVoicingChanged.emit()
        self.chordGateChanged.emit()

    def send_initial_state(self) -> None:
        self._chord_gate_state = CHORD_GATE_NONE
        super().send_initial_state()
        self.chordGateChanged.emit()
        self.bassVoicingChanged.emit()

    @Slot()
    def panic(self) -> None:
        self._chord_gate_state = CHORD_GATE_NONE
        super().panic()
        self.chordGateChanged.emit()
