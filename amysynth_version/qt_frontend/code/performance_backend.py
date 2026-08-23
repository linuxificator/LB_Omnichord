from __future__ import annotations

import json
import math
from typing import Any

from PySide6.QtCore import Property, QTimer, Signal, Slot

import app_core
from performance_logic import (
    clamp_bass_voicing_shift,
    roll_bass_voicing,
    roll_chord_indexes,
)
from synth_state import SynthState


CHORD_GATE_NONE = 0
CHORD_GATE_ON = 1
CHORD_GATE_OFF = 2
BASS_VOICING_LIMIT = 6
REVERB_LEVEL_MAX = 2.0
MIDI_ROW_COUNT = 6
MIDI_DRUM_KIT_KEY = "drum_kit_0"
MIDI_DRUM_PREVIEW_STEPS = 8


class InstrumentBackend(app_core.InstrumentBackend):
    """Live-performance state layered on the stable application core.

    The base class still owns catalogue/preset loading, touch dropout handling,
    tuning, synth state and transport.  This layer owns performance concepts
    that must survive independently of the sounding chord: remembered chord
    identity, chord gate state, bass inversion/voicing and grouped row rolls.
    """

    chordGateChanged = Signal()
    bassVoicingChanged = Signal()
    midiStateChanged = Signal()
    midiTuningChanged = Signal()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Base construction loads a preset through virtual methods, so these
        # fields must exist before super().__init__() starts.
        self._chord_gate_state = CHORD_GATE_NONE
        self._bass_voicing_shift = 0
        super().__init__(*args, **kwargs)

        # MIDI setup deliberately owns its own six UI instrument states.  The
        # normal Omnichord catalogue is reused verbatim and the one ESP32 drum
        # kit is appended only to this MIDI-facing catalogue.
        drum_kit = app_core.SynthDefinition(
            key=MIDI_DRUM_KIT_KEY,
            label="Drum Kit 0",
            controls=(),
        )
        self._midi_synth_definitions = tuple(self._synths) + (drum_kit,)
        self._midi_synth_rows = [
            SynthState(self._midi_synth_definitions, 0)
            for _ in range(MIDI_ROW_COUNT)
        ]
        self._midi_channels = [index + 1 for index in range(MIDI_ROW_COUNT)]
        self._midi_volumes = [0.5] * MIDI_ROW_COUNT
        self._midi_state_version = 0

        # The MIDI tuning shadow is only used while tuning is decoupled.  When
        # coupled, MIDI UI and preview use the live Omnichord tuning directly.
        self._midi_tuning_mode_index = self._tuning_mode_index
        self._midi_tuning_reference = float(self._effective_tuning_reference())
        self._midi_pitch_bend_offset_hz = 0.0
        self._midi_pitch_bend_timer = QTimer(self)
        self._midi_pitch_bend_timer.setInterval(100)
        self._midi_pitch_bend_timer.timeout.connect(self._midi_pitch_bend_tick)
        self._midi_pitch_bend_direction = 0
        self._midi_pitch_bend_returning = False

        self._midi_preview_row = -1
        self._midi_preview_last_index: int | None = None

    def _reset_synth_role_to_preset(self, role: app_core.SynthRole) -> None:
        """Restore a synth role's preset instrument, parameters and volume.

        The stable core's reset helper intentionally restores only parameters
        of the *currently selected* synth.  The section RST buttons have a
        different contract: return the whole role to the stored preset, or to
        the application's role default when the preset has no synth selection.
        """
        runtime = self._runtime(role)
        previous_index = runtime.selected_index

        # load_preset() already implements the desired sparse-preset fallback:
        # missing/unknown selected -> role default, missing controls -> catalogue
        # defaults.  The base reset helper then restores the role volume and
        # publishes the resulting complete synth state to AMY.
        runtime.load_preset(self._preset_role_data(role))
        super()._reset_synth_role_to_preset(role)

        # The base helper emits control changes but deliberately assumes that
        # selection cannot change.  RST can now change it, so notify the wheel.
        if runtime.selected_index != previous_index:
            if role == "chord":
                self.chordSynthStateChanged.emit()
            elif role == "strum":
                self.strumSynthStateChanged.emit()
            else:
                self.bassSynthStateChanged.emit()

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

    @Property(int, notify=midiStateChanged)
    def midiStateVersion(self) -> int:
        return self._midi_state_version

    @Property("QVariantList", constant=True)
    def midiSynthNames(self) -> list[str]:
        return [definition.label for definition in self._midi_synth_definitions]

    @Property(int, notify=midiTuningChanged)
    def midiTuningModeIndex(self) -> int:
        return self._midi_tuning_mode_index

    @Property(int, notify=midiTuningChanged)
    def midiTuningReference(self) -> int:
        return int(round(self._effective_midi_tuning_reference()))

    def _valid_midi_row(self, row_index: int) -> bool:
        return 0 <= int(row_index) < MIDI_ROW_COUNT

    def _midi_runtime(self, row_index: int) -> SynthState:
        return self._midi_synth_rows[int(row_index)]

    def _emit_midi_state_changed(self) -> None:
        self._midi_state_version += 1
        self.midiStateChanged.emit()

    @Slot(int, result=int)
    def midiSynthIndex(self, row_index: int) -> int:
        if not self._valid_midi_row(row_index):
            return 0
        return self._midi_runtime(row_index).selected_index

    @Slot(int, result="QVariantList")
    def midiCommonControls(self, row_index: int) -> list[dict[str, Any]]:
        if not self._valid_midi_row(row_index):
            return []
        return self._midi_runtime(row_index).control_model("common")

    @Slot(int, result="QVariantList")
    def midiExtraControls(self, row_index: int) -> list[dict[str, Any]]:
        if not self._valid_midi_row(row_index):
            return []
        return self._midi_runtime(row_index).control_model("extra")

    @Slot(int, result=float)
    def midiVolume(self, row_index: int) -> float:
        if not self._valid_midi_row(row_index):
            return 0.5
        return float(self._midi_volumes[int(row_index)])

    @Slot(int, result=int)
    def midiChannel(self, row_index: int) -> int:
        if not self._valid_midi_row(row_index):
            return 1
        return int(self._midi_channels[int(row_index)])

    @Slot(int, int)
    def setMidiSynthIndex(self, row_index: int, synth_index: int) -> None:
        if not self._valid_midi_row(row_index):
            return
        if self._midi_runtime(row_index).select(synth_index):
            self._emit_midi_state_changed()

    @Slot(int, str, float)
    def setMidiSynthControl(
        self,
        row_index: int,
        key: str,
        value: float,
    ) -> None:
        if not self._valid_midi_row(row_index):
            return
        if self._midi_runtime(row_index).set_control(key, value):
            self._emit_midi_state_changed()

    @Slot(int, float)
    def setMidiVolume(self, row_index: int, value: float) -> None:
        if not self._valid_midi_row(row_index):
            return
        row = int(row_index)
        clamped = max(0.0, min(1.0, float(value)))
        if math.isclose(clamped, self._midi_volumes[row], abs_tol=1e-4):
            return
        self._midi_volumes[row] = clamped
        self._emit_midi_state_changed()

    @Slot(int)
    def cycleMidiChannel(self, row_index: int) -> None:
        if not self._valid_midi_row(row_index):
            return
        row = int(row_index)
        current = self._midi_channels[row]
        self._midi_channels[row] = 0 if current == 16 else current + 1
        if current == 0:
            self._midi_channels[row] = 1
        self._emit_midi_state_changed()

    @Slot(int)
    def resetMidiSynthRow(self, row_index: int) -> None:
        if not self._valid_midi_row(row_index):
            return
        row = int(row_index)
        self._midi_synth_rows[row].reset_to_defaults()
        self._midi_volumes[row] = 0.5
        # MIDI channel is routing state, not part of an instrument reset.
        self._emit_midi_state_changed()

    def _effective_midi_tuning_reference(self) -> float:
        return max(
            415.0,
            min(
                466.0,
                float(self._midi_tuning_reference)
                + self._midi_pitch_bend_offset_hz,
            ),
        )

    @Slot()
    def syncMidiTuningFromOmni(self) -> None:
        self._stop_midi_pitch_bend()
        self._midi_pitch_bend_offset_hz = 0.0
        self._midi_tuning_mode_index = self._tuning_mode_index
        self._midi_tuning_reference = self._effective_tuning_reference()
        self.midiTuningChanged.emit()

    @Slot(int)
    def setMidiTuningModeIndex(self, index: int) -> None:
        clamped = max(
            0,
            min(len(app_core.TUNING_MODE_NAMES) - 1, int(index)),
        )
        if clamped == self._midi_tuning_mode_index:
            return
        self._midi_tuning_mode_index = clamped
        self.midiTuningChanged.emit()

    @Slot(int)
    def setMidiTuningReference(self, value: int) -> None:
        clamped = max(415, min(466, int(value)))
        self._stop_midi_pitch_bend()
        self._midi_pitch_bend_offset_hz = 0.0
        if clamped == int(round(self._midi_tuning_reference)):
            self.midiTuningChanged.emit()
            return
        self._midi_tuning_reference = float(clamped)
        self.midiTuningChanged.emit()

    def _stop_midi_pitch_bend(self) -> None:
        self._midi_pitch_bend_timer.stop()
        self._midi_pitch_bend_direction = 0
        self._midi_pitch_bend_returning = False

    def _midi_pitch_bend_tick(self) -> None:
        previous = self._midi_pitch_bend_offset_hz
        if self._midi_pitch_bend_returning:
            if abs(previous) <= 1.0:
                self._midi_pitch_bend_offset_hz = 0.0
                self._stop_midi_pitch_bend()
            else:
                self._midi_pitch_bend_offset_hz = (
                    previous - math.copysign(1.0, previous)
                )
        else:
            candidate = previous + float(self._midi_pitch_bend_direction)
            base = float(self._midi_tuning_reference)
            self._midi_pitch_bend_offset_hz = max(
                415.0 - base,
                min(466.0 - base, candidate),
            )
            if math.isclose(
                self._midi_pitch_bend_offset_hz,
                previous,
                abs_tol=1e-9,
            ):
                return
        if not math.isclose(
            previous,
            self._midi_pitch_bend_offset_hz,
            abs_tol=1e-9,
        ):
            self.midiTuningChanged.emit()

    @Slot(int)
    def beginMidiPitchBend(self, direction: int) -> None:
        self._midi_pitch_bend_direction = 1 if int(direction) > 0 else -1
        self._midi_pitch_bend_returning = False
        if not self._midi_pitch_bend_timer.isActive():
            self._midi_pitch_bend_timer.start()

    @Slot()
    def endMidiPitchBend(self) -> None:
        self._midi_pitch_bend_direction = 0
        if math.isclose(self._midi_pitch_bend_offset_hz, 0.0, abs_tol=1e-9):
            self._stop_midi_pitch_bend()
            return
        self._midi_pitch_bend_returning = True
        if not self._midi_pitch_bend_timer.isActive():
            self._midi_pitch_bend_timer.start()

    def _midi_preview_chord(self) -> tuple[int, set[int]]:
        if self._active_row >= 0 and self._active_root_semitone >= 0:
            root = self._active_root_semitone
            chord = self._chords[self._row_chord_indexes[self._active_row]]
            pitch_classes = {
                (root + interval) % 12
                for interval in chord.intervals
            }
            return root, pitch_classes

        # Before the player has selected an Omnichord chord, preview C major.
        return 0, {0, 4, 7}

    def _midi_preview_notes(self) -> tuple[list[int], int]:
        root, pitch_classes = self._midi_preview_chord()
        notes = [
            note
            for note in range(app_core.STRUM_LOW_MIDI, app_core.STRUM_HIGH_MIDI + 1)
            if note % 12 in pitch_classes
        ]
        return notes, root

    def _midi_preview_index(self, normalized_y: float) -> int | None:
        notes, _ = self._midi_preview_notes()
        if not notes:
            return None
        y = max(0.0, min(1.0, float(normalized_y)))
        return round((1.0 - y) * (len(notes) - 1))

    @staticmethod
    def _midi_drum_preview_index(normalized_y: float) -> int:
        y = max(0.0, min(1.0, float(normalized_y)))
        return round((1.0 - y) * (MIDI_DRUM_PREVIEW_STEPS - 1))

    def _midi_preview_is_drum(self, row_index: int) -> bool:
        return (
            self._midi_runtime(row_index).selected_definition.key
            == MIDI_DRUM_KIT_KEY
        )

    def _midi_preview_tuned_note(
        self,
        note: int | float,
        root_semitone: int,
        coupled: bool,
    ) -> float:
        if coupled:
            return self._tuned_note(note, root_semitone)

        reference_offset = 12.0 * math.log2(
            self._effective_midi_tuning_reference() / 440.0
        )
        mode = app_core.TUNING_MODE_NAMES[self._midi_tuning_mode_index]
        factor = 1.0
        if mode in self._intonation_tables:
            root_pc = int(root_semitone) % 12
            note_pc = int(math.floor(float(note) + 0.5)) % 12
            factor = self._intonation_tables[mode][root_pc][note_pc]
        return float(note) + reference_offset + 12.0 * math.log2(factor)

    def _prepare_midi_preview(self, row_index: int) -> None:
        runtime = self._midi_runtime(row_index)
        self._client.send_message(
            self._strum_synth_address,
            runtime.transport_payload(),
        )
        self._client.send_message(
            self._strum_amp_address,
            self._midi_volumes[int(row_index)],
        )

    def _play_midi_preview_index(
        self,
        row_index: int,
        index: int,
        coupled: bool,
    ) -> None:
        if self._midi_preview_is_drum(row_index):
            preview_drum = getattr(self._client, "preview_drum", None)
            if callable(preview_drum):
                preview_drum(int(index))
            return

        notes, root = self._midi_preview_notes()
        if not 0 <= int(index) < len(notes):
            return
        tuned = self._midi_preview_tuned_note(
            notes[int(index)],
            root,
            bool(coupled),
        )
        self._client.send_message(
            self._strum_note_address,
            f"{tuned:.12f}",
        )

    @Slot(int, float, bool)
    def midiPreviewStart(
        self,
        row_index: int,
        normalized_y: float,
        coupled: bool,
    ) -> None:
        if not self._valid_midi_row(row_index):
            return
        row = int(row_index)
        self._midi_preview_row = row

        if self._midi_preview_is_drum(row):
            index = self._midi_drum_preview_index(normalized_y)
        else:
            self._prepare_midi_preview(row)
            index = self._midi_preview_index(normalized_y)
            if index is None:
                self._midi_preview_last_index = None
                return

        self._midi_preview_last_index = int(index)
        self._play_midi_preview_index(row, int(index), bool(coupled))

    @Slot(int, float, bool)
    def midiPreviewMove(
        self,
        row_index: int,
        normalized_y: float,
        coupled: bool,
    ) -> None:
        if not self._valid_midi_row(row_index):
            return
        row = int(row_index)
        if row != self._midi_preview_row:
            self.midiPreviewStart(row, normalized_y, coupled)
            return

        if self._midi_preview_is_drum(row):
            new_index = self._midi_drum_preview_index(normalized_y)
        else:
            candidate = self._midi_preview_index(normalized_y)
            if candidate is None:
                self._midi_preview_last_index = None
                return
            new_index = int(candidate)

        if self._midi_preview_last_index is None:
            self._midi_preview_last_index = new_index
            self._play_midi_preview_index(row, new_index, bool(coupled))
            return
        old_index = self._midi_preview_last_index
        if new_index == old_index:
            return

        direction = 1 if new_index > old_index else -1
        for index in range(old_index + direction, new_index + direction, direction):
            self._play_midi_preview_index(row, index, bool(coupled))
        self._midi_preview_last_index = new_index

    @Slot()
    def midiPreviewEnd(self) -> None:
        self._midi_preview_last_index = None
        self._midi_preview_row = -1

    @Slot()
    def finishMidiPreview(self) -> None:
        """Return the borrowed physical strum synth to Omnichord state."""
        self.midiPreviewEnd()
        self._send_synth_state("strum")
        self._client.send_message(
            self._strum_amp_address,
            self._strum_volume,
        )

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

    @Slot(float)
    def setReverbLevel(self, value: float) -> None:
        """Expose AMY reverb wet-return gain through 2.0 (about +6 dB)."""
        clamped = max(0.0, min(REVERB_LEVEL_MAX, float(value)))
        if abs(clamped - self._reverb_level) < 0.0001:
            return
        self._reverb_level = clamped
        self.reverbLevelChanged.emit()
        self._send_reverb_state()

    @Slot(int)
    def setRhythmIndex(self, rhythm_index: int) -> None:
        """Switch rhythm style without changing a running transport tempo.

        Stopped transport retains the core behaviour: each rhythm recalls its
        own stored tempo.  While running, the destination rhythm inherits the
        tempo that is already sounding and the transport remains running.
        """
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
        effects = self._defaults.get("effects", {})
        self._reverb_level = max(
            0.0,
            min(REVERB_LEVEL_MAX, float(effects.get("reverb_level", 0.0))),
        )

    def _apply_preset_data(self, data: dict[str, Any]) -> None:
        # Drum transport is live session state, not preset state.  Preserve it
        # across preset selection; during startup its pre-preset value comes
        # from defaults.json and is therefore always False.
        rhythm_was_running = bool(getattr(self, "_rhythm_running", False))
        super()._apply_preset_data(data)
        self._rhythm_running = rhythm_was_running

        rhythm = data.get("rhythm", {})
        if not isinstance(rhythm, dict):
            rhythm = {}
        self._bass_voicing_shift = clamp_bass_voicing_shift(
            rhythm.get("bass_voicing_shift", self._bass_voicing_shift),
            limit=BASS_VOICING_LIMIT,
        )

        # The stable core predates the extended wet-return range and clamps
        # preset reverb to 1.0. Re-read just this value with the live 0..2 range.
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

        # Chord identity/gating is live performance state, never preset state.
        self._chord_gate_state = CHORD_GATE_NONE

    def _preset_snapshot(self) -> dict[str, Any]:
        snapshot = super()._preset_snapshot()

        # Do not persist drum start/stop.  Existing preset files that still
        # contain rhythm_running are harmless because _apply_preset_data()
        # restores the live value after the core has parsed them.
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
        self._chord_gate_state = CHORD_GATE_NONE
        super().send_initial_state()
        self.chordGateChanged.emit()
        self.bassVoicingChanged.emit()

    @Slot()
    def panic(self) -> None:
        self._chord_gate_state = CHORD_GATE_NONE
        super().panic()
        self.finishMidiPreview()
        self.chordGateChanged.emit()
