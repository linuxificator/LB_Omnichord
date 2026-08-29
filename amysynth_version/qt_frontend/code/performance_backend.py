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


CHORD_GATE_ON = 1
CHORD_GATE_OFF = 2
BASS_VOICING_LIMIT = 6
REVERB_LEVEL_MAX = app_core.REVERB_LEVEL_MAX


class InstrumentBackend(app_core.InstrumentBackend):
    """Live-performance state layered on the stable application core.

    The base class still owns catalogue/preset loading, chord-contact handling,
    tuning, synth state and transport.  This layer owns performance concepts
    that must survive independently of the sounding chord: remembered chord
    identity, chord gate state, bass inversion/voicing and grouped row rolls.
    """

    chordGateChanged = Signal()
    bassVoicingChanged = Signal()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Base construction loads a preset through virtual methods, so these
        # fields must exist before super().__init__() starts.
        self._chord_gate_state = CHORD_GATE_OFF
        self._bass_voicing_shift = 0
        super().__init__(*args, **kwargs)

    def _reset_synth_role_to_preset(
        self,
        role: app_core.SynthRole,
        *,
        preserved_controls: dict[tuple[str, str], float] | None = None,
        preserved_volume: float | None = None,
    ) -> None:
        """Restore a synth role's preset instrument, parameters and volume.

        The stable core's reset helper intentionally restores only parameters
        of the *currently selected* synth.  The section RST buttons have a
        different contract: return the whole role to the stored preset, or to
        the application's role default when the preset has no synth selection.
        """
        runtime = self._runtime(role)
        previous_index = runtime.selected_index
        runtime.load_preset(self._preset_role_data(role))
        super()._reset_synth_role_to_preset(
            role,
            preserved_controls=preserved_controls,
            preserved_volume=preserved_volume,
        )
        if runtime.selected_index != previous_index:
            if role == "chord":
                self.chordSynthStateChanged.emit()
            elif role == "strum":
                self.strumSynthStateChanged.emit()
            else:
                self.bassSynthStateChanged.emit()

    def _set_chord_gate_state(self, state: int, *, emit: bool = True) -> bool:
        state = max(CHORD_GATE_ON, min(CHORD_GATE_OFF, int(state)))
        if state == self._chord_gate_state:
            return False
        self._chord_gate_state = state
        if emit:
            self.chordGateChanged.emit()
            self._emit_state_changed()
        return True

    @Property(int, notify=chordGateChanged)
    def chordGateState(self) -> int:
        return self._chord_gate_state

    @Property(str, notify=chordGateChanged)
    def chordGateButtonText(self) -> str:
        if self._chord_gate_state == CHORD_GATE_ON:
            return "CHORD\nOFF"
        return "CHORD\nON"

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
        if self._chord_gate_state == CHORD_GATE_ON:
            self.turnOff()
            return
        self._set_chord_gate_state(CHORD_GATE_ON)
        self._send_rhythm_chord_enabled()
        # CHORD ON controls only the automatic synth-4 sequencer lane. The
        # remembered chord identity supplies its pitch, but must not trigger a
        # one-shot manual synth-3 chord.
        if self._active_row >= 0 and self._active_root_semitone >= 0:
            self._send_chord_state(play_now=False)

    @Slot()
    def turnOff(self) -> None:
        self._set_chord_gate_state(CHORD_GATE_OFF)
        self._strum_last_index = None
        self._send_rhythm_chord_enabled()
        if self._active_row >= 0 and self._active_root_semitone >= 0:
            self._send_chord_state(play_now=False)

    def _current_bass_notes(self) -> list[int]:
        return roll_bass_voicing(
            super()._current_bass_notes(),
            self._bass_voicing_shift,
        )

    @Slot(float)
    def setBassVoicingShift(self, value: float) -> None:
        if self._midi_control_blocks(
            {"screen": "omni", "kind": "bass_voicing"}
        ):
            return
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

    @Slot(float)
    def setReverbLevel(self, value: float) -> None:
        """Expose AMY reverb wet-return gain through 3.0."""
        if self._midi_control_blocks(
            {"screen": "omni", "kind": "reverb_level"}
        ):
            return
        clamped = max(0.0, min(REVERB_LEVEL_MAX, float(value)))
        if abs(clamped - self._reverb_level) < 0.0001:
            return
        self._reverb_level = clamped
        self.reverbLevelChanged.emit()
        self._send_reverb_state()

    @Slot(int)
    def setRhythmIndex(self, rhythm_index: int) -> None:
        """Switch rhythm style without changing a running transport tempo."""
        self._stop_tempo_nudge()
        if not 0 <= rhythm_index < len(self._rhythms):
            return
        previous_index = self._rhythm.selected_index
        if rhythm_index == previous_index:
            return
        running_tempo = self._rhythm.tempo_by_rhythm[previous_index]
        self._rhythm.selected_index = rhythm_index
        if self._rhythm_running:
            self._rhythm.tempo_by_rhythm[rhythm_index] = running_tempo
        self.rhythmStateChanged.emit()
        self.rhythmControlsChanged.emit()
        self._send_rhythm_config()

    @Slot(int)
    def rollChordRows(self, direction: int) -> None:
        if int(direction) == 0:
            return
        self._row_chord_indexes = roll_chord_indexes(
            self._row_chord_indexes,
            len(self._chords),
            direction,
        )
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
        effects = self._defaults.get("effects", {})
        self._reverb_level = max(
            0.0,
            min(REVERB_LEVEL_MAX, float(effects.get("reverb_level", 0.0))),
        )

    def _apply_preset_data(self, data: dict[str, Any]) -> None:
        rhythm_was_running = bool(getattr(self, "_rhythm_running", False))
        live_bass_voicing = (
            self._bass_voicing_shift
            if rhythm_was_running
            else None
        )
        super()._apply_preset_data(data)
        self._rhythm_running = rhythm_was_running
        rhythm = data.get("rhythm", {})
        if not isinstance(rhythm, dict):
            rhythm = {}
        self._bass_voicing_shift = clamp_bass_voicing_shift(
            live_bass_voicing
            if live_bass_voicing is not None
            else rhythm.get("bass_voicing_shift", self._bass_voicing_shift),
            limit=BASS_VOICING_LIMIT,
        )
        effects = data.get("effects", {})
        if not isinstance(effects, dict):
            effects = {}
        default_effects = self._defaults.get("effects", {})
        legacy_main = effects.get(
            "main_reverb",
            default_effects.get("reverb_level", 0.0),
        )
        self._reverb_level = max(
            0.0,
            min(
                REVERB_LEVEL_MAX,
                float(effects.get("reverb_level", legacy_main)),
            ),
        )
        # Chord-gate state is live performance state. Keeping it lets an
        # active row/root converge to the destination preset's chord voicing
        # instead of muting the accompaniment on every preset selection.

    def _preset_snapshot(self) -> dict[str, Any]:
        snapshot = super()._preset_snapshot()
        transport = snapshot.get("transport")
        if isinstance(transport, dict):
            transport.pop("rhythm_running", None)
        rhythm = snapshot.setdefault("rhythm", {})
        rhythm["bass_voicing_shift"] = self._bass_voicing_shift
        return snapshot

    def _emit_full_preset_state(self) -> None:
        super()._emit_full_preset_state()
        self.bassVoicingChanged.emit()
        self.chordGateChanged.emit()

    def send_initial_state(self) -> None:
        self._chord_gate_state = CHORD_GATE_OFF
        super().send_initial_state()
        self.chordGateChanged.emit()
        self.bassVoicingChanged.emit()

    @Slot()
    def panic(self) -> None:
        self._chord_gate_state = CHORD_GATE_OFF
        super().panic()
        self.chordGateChanged.emit()
