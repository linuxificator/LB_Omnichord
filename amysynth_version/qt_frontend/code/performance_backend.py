from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

from PySide6.QtCore import Property, Signal, Slot

import app_core
from bass_riffs import BassRiffDefinition, transpose_riff_events
from performance_logic import (
    clamp_bass_voicing_shift,
    roll_bass_voicing,
    roll_chord_indexes,
)
from musical_state import OmniPerformanceSnapshot, PerformanceStateSnapshot


CHORD_GATE_ON = 1
CHORD_GATE_OFF = 2
BASS_VOICING_LIMIT = 6
BASS_RIFF_ACTIVITY = 5
CHORD_ARPEGGIO_RATE_MIN = 1
CHORD_ARPEGGIO_RATE_MAX = 4
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
    chordArpeggioChanged = Signal()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._chord_gate_state = CHORD_GATE_OFF
        self._bass_voicing_shift = 0
        self._bass_riff_selector = 1
        self._active_bass_riff_id: str | None = None
        self._bass_riff_context: tuple[str, str] | None = None
        self._chord_arpeggio_enabled = False
        self._chord_arpeggio_rate = CHORD_ARPEGGIO_RATE_MIN
        self._chord_arpeggio_descending = False
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

    def performance_snapshot(self) -> OmniPerformanceSnapshot:
        snapshot = super().performance_snapshot()
        return replace(
            snapshot,
            performance=PerformanceStateSnapshot(
                chord_gate_state=self._chord_gate_state,
                bass_voicing_shift=self._bass_voicing_shift,
                chord_arpeggio_enabled=self._chord_arpeggio_enabled,
                chord_arpeggio_rate=self._chord_arpeggio_rate,
                chord_arpeggio_descending=self._chord_arpeggio_descending,
                bass_notes=tuple(self._current_bass_notes()),
            ),
        )

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
            return "CHORD\nON"
        return "CHORD\nOFF"

    @Property(bool, notify=chordGateChanged)
    def isOff(self) -> bool:
        return self._chord_gate_state != CHORD_GATE_ON

    @Property(bool, notify=chordArpeggioChanged)
    def chordArpeggioEnabled(self) -> bool:
        return self._chord_arpeggio_enabled

    @Property(int, notify=chordArpeggioChanged)
    def chordArpeggioRate(self) -> int:
        return self._chord_arpeggio_rate

    @Property(bool, notify=chordArpeggioChanged)
    def chordArpeggioDescending(self) -> bool:
        return self._chord_arpeggio_descending

    @Property(str, notify=chordArpeggioChanged)
    def chordArpeggioDirectionLabel(self) -> str:
        return "D" if self._chord_arpeggio_descending else "U"

    @Property(int, notify=bassVoicingChanged)
    def bassVoicingShift(self) -> int:
        return self._bass_voicing_shift

    @Property(bool, notify=bassVoicingChanged)
    def bassRiffMode(self) -> bool:
        return self.rhythmBassActivity == BASS_RIFF_ACTIVITY

    @Property(int, notify=bassVoicingChanged)
    def bassRiffSelector(self) -> int:
        return self._bass_riff_selector

    @Property(int, notify=bassVoicingChanged)
    def bassRiffSelectorMaximum(self) -> int:
        candidates = self._available_bass_riffs()
        if candidates:
            return len(candidates)
        return max(1, self._bass_riff_selector)

    @Property(str, notify=bassVoicingChanged)
    def selectedBassRiffId(self) -> str:
        return self._active_bass_riff_id or ""

    @Property(str, notify=bassVoicingChanged)
    def selectedBassRiffName(self) -> str:
        riff = self._bass_riffs.by_id(self._active_bass_riff_id)
        return riff.name if riff is not None else ""

    def _current_bass_riff_context(self) -> tuple[str, str] | None:
        if self._active_row < 0 or self._active_root_semitone < 0:
            return None
        chord = self._chords[self._row_chord_indexes[self._active_row]]
        return self._selected_rhythm().key, chord.suffix

    def _available_bass_riffs(self) -> tuple[BassRiffDefinition, ...]:
        context = self._current_bass_riff_context()
        if context is None:
            return ()
        return self._bass_riffs.candidates(*context)

    def _default_bass_riff_selector(self) -> int:
        rhythm = self._defaults.get("rhythm", {})
        if not isinstance(rhythm, dict):
            return 1
        return max(1, int(rhythm.get("bass_riff_selector", 1)))

    def _preset_bass_riff_selector(
        self,
        data: dict[str, Any] | None = None,
    ) -> int:
        source = self._preset_reference_data if data is None else data
        rhythm = source.get("rhythm", {})
        if not isinstance(rhythm, dict):
            return self._default_bass_riff_selector()
        return max(
            1,
            int(
                rhythm.get(
                    "bass_riff_selector",
                    self._default_bass_riff_selector(),
                )
            ),
        )

    def _bass_riff_is_playing(self) -> bool:
        return bool(
            self._rhythm_running
            and self._bass_running
            and self.bassRiffMode
            and self._active_bass_riff_id
        )

    def _choose_bass_riff(
        self,
        *,
        fallback_selector: int,
        preserve_riff_id: str | None = None,
    ) -> bool:
        previous = (
            self._bass_riff_selector,
            self._active_bass_riff_id,
            self._bass_riff_context,
        )
        candidates = self._available_bass_riffs()
        self._bass_riff_context = self._current_bass_riff_context()
        selected_index: int | None = None
        if preserve_riff_id:
            selected_index = next(
                (
                    index
                    for index, riff in enumerate(candidates)
                    if riff.riff_id == preserve_riff_id
                ),
                None,
            )
        if selected_index is None and candidates:
            selected_index = max(
                0,
                min(len(candidates) - 1, int(fallback_selector) - 1),
            )
        if selected_index is None:
            self._bass_riff_selector = max(1, int(fallback_selector))
            self._active_bass_riff_id = None
        else:
            self._bass_riff_selector = selected_index + 1
            self._active_bass_riff_id = candidates[selected_index].riff_id
        return previous != (
            self._bass_riff_selector,
            self._active_bass_riff_id,
            self._bass_riff_context,
        )

    def _reconcile_bass_riff_context(
        self,
        *,
        fallback_selector: int | None = None,
        preserve_riff_id: str | None = None,
        force: bool = False,
    ) -> bool:
        context = self._current_bass_riff_context()
        if not force and context == self._bass_riff_context:
            return False
        changed = self._choose_bass_riff(
            fallback_selector=(
                self._preset_bass_riff_selector()
                if fallback_selector is None
                else fallback_selector
            ),
            preserve_riff_id=preserve_riff_id,
        )
        if changed:
            self.bassVoicingChanged.emit()
        return changed

    def _current_bass_riff_payload(self) -> dict[str, Any] | None:
        if not self.bassRiffMode:
            return None
        if self._current_bass_riff_context() != self._bass_riff_context:
            self._reconcile_bass_riff_context(
                preserve_riff_id=(
                    self._active_bass_riff_id if self._bass_riff_is_playing() else None
                )
            )
        riff = self._bass_riffs.by_id(self._active_bass_riff_id)
        if riff is None or self._active_root_semitone < 0:
            return None
        events = transpose_riff_events(riff, self._active_root_semitone)
        return {
            "id": riff.riff_id,
            "index": riff.index,
            "name": riff.name,
            "ppq": riff.ppq,
            "phrase_ticks": riff.phrase_ticks,
            "events": [
                {
                    **event,
                    "note": self._tuned_note(event["note"], self._active_root_semitone),
                }
                for event in events
            ],
        }

    def _rhythm_payload(self) -> dict[str, Any]:
        payload = super()._rhythm_payload()
        payload["bass_mode"] = "riff" if self.bassRiffMode else "activity"
        payload["bass_riff"] = self._current_bass_riff_payload()
        payload["chord_arpeggio"] = {
            "enabled": self._chord_arpeggio_enabled,
            "notes_per_beat": self._chord_arpeggio_rate,
            "direction": ("down" if self._chord_arpeggio_descending else "up"),
        }
        return payload

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
            "play_now": bool(play_now and self._chord_gate_state == CHORD_GATE_ON),
            "rhythm_running": bool(self._rhythm_running),
            "rhythm_chord_enabled": self._chord_gate_enabled(),
            "bass_riff": self._current_bass_riff_payload(),
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

    @Slot()
    def toggleChordArpeggio(self) -> None:
        self._chord_arpeggio_enabled = not self._chord_arpeggio_enabled
        self.chordArpeggioChanged.emit()
        self._send_rhythm_config()

    @Slot(float)
    def setChordArpeggioRate(self, value: float) -> None:
        rate = max(
            CHORD_ARPEGGIO_RATE_MIN,
            min(CHORD_ARPEGGIO_RATE_MAX, int(round(float(value)))),
        )
        if rate == self._chord_arpeggio_rate:
            return
        self._chord_arpeggio_rate = rate
        self.chordArpeggioChanged.emit()
        if self._chord_arpeggio_enabled:
            self._send_rhythm_config()

    @Slot()
    def toggleChordArpeggioDirection(self) -> None:
        self._chord_arpeggio_descending = not self._chord_arpeggio_descending
        self.chordArpeggioChanged.emit()
        if self._chord_arpeggio_enabled:
            self._send_rhythm_config()

    def _current_bass_notes(self) -> list[int]:
        return roll_bass_voicing(
            super()._current_bass_notes(),
            self._bass_voicing_shift,
        )

    @Slot(float)
    def setBassVoicingShift(self, value: float) -> None:
        if self._midi_control_blocks({"screen": "omni", "kind": "bass_voicing"}):
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
    def setBassRiffSelector(self, value: float) -> None:
        if self._midi_control_blocks({"screen": "omni", "kind": "bass_riff_selector"}):
            return
        candidates = self._available_bass_riffs()
        if not candidates:
            return
        selected = max(1, min(len(candidates), int(round(float(value)))))
        riff = candidates[selected - 1]
        if (
            selected == self._bass_riff_selector
            and riff.riff_id == self._active_bass_riff_id
            and self._bass_riff_context == self._current_bass_riff_context()
        ):
            return
        self._bass_riff_selector = selected
        self._active_bass_riff_id = riff.riff_id
        self._bass_riff_context = self._current_bass_riff_context()
        self.bassVoicingChanged.emit()
        if self.bassRiffMode:
            self._send_rhythm_config()

    @Slot(float)
    def setRhythmBassActivity(self, value: float) -> None:
        previous = self.rhythmBassActivity
        super().setRhythmBassActivity(value)
        if previous != self.rhythmBassActivity:
            self.bassVoicingChanged.emit()

    @Slot(float)
    def setReverbLevel(self, value: float) -> None:
        """Expose AMY reverb wet-return gain through 3.0."""
        if self._midi_control_blocks({"screen": "omni", "kind": "reverb_level"}):
            return
        clamped = max(0.0, min(REVERB_LEVEL_MAX, float(value)))
        if abs(clamped - self._reverb_level) < 0.0001:
            return
        self._reverb_level = clamped
        self.reverbLevelChanged.emit()
        self._send_reverb_state()

    @Slot(int)
    def setRhythmIndex(self, rhythm_index: int) -> None:
        """Switch style without replacing controls shaping a running rhythm."""
        self._stop_tempo_nudge()
        if not 0 <= rhythm_index < len(self._rhythms):
            return
        previous_index = self._rhythm.selected_index
        if rhythm_index == previous_index:
            return
        preserve_riff_id = self._active_bass_riff_id if self._bass_riff_is_playing() else None
        live_controls = (
            self._rhythm.tempo_by_rhythm[previous_index],
            self._rhythm.busyness_by_rhythm[previous_index],
            self._rhythm.chord_activity_by_rhythm[previous_index],
            self._rhythm.bass_activity_by_rhythm[previous_index],
            list(self._rhythm.fill_order_by_rhythm[previous_index]),
            self._rhythm.fill_density_index_by_rhythm[previous_index],
        )
        self._rhythm.selected_index = rhythm_index
        if self._rhythm_running:
            (
                self._rhythm.tempo_by_rhythm[rhythm_index],
                self._rhythm.busyness_by_rhythm[rhythm_index],
                self._rhythm.chord_activity_by_rhythm[rhythm_index],
                self._rhythm.bass_activity_by_rhythm[rhythm_index],
                self._rhythm.fill_order_by_rhythm[rhythm_index],
                self._rhythm.fill_density_index_by_rhythm[rhythm_index],
            ) = live_controls
        self._reconcile_bass_riff_context(
            preserve_riff_id=preserve_riff_id,
            force=True,
        )
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
        self._bass_riff_selector = self._default_bass_riff_selector()
        self._active_bass_riff_id = None
        self._bass_riff_context = None
        self._chord_arpeggio_enabled = bool(rhythm.get("chord_arpeggio_enabled", False))
        self._chord_arpeggio_rate = max(
            CHORD_ARPEGGIO_RATE_MIN,
            min(
                CHORD_ARPEGGIO_RATE_MAX,
                int(rhythm.get("chord_arpeggio_rate", 1)),
            ),
        )
        self._chord_arpeggio_descending = (
            str(rhythm.get("chord_arpeggio_direction", "up")).lower() == "down"
        )
        effects = self._defaults.get("effects", {})
        self._reverb_level = max(
            0.0,
            min(REVERB_LEVEL_MAX, float(effects.get("reverb_level", 0.0))),
        )

    def _apply_preset_data(self, data: dict[str, Any]) -> None:
        rhythm_was_running = bool(getattr(self, "_rhythm_running", False))
        live_chord_arpeggio = (
            (
                self._chord_arpeggio_enabled,
                self._chord_arpeggio_rate,
                self._chord_arpeggio_descending,
            )
            if rhythm_was_running
            else None
        )
        live_bass_voicing = self._bass_voicing_shift if rhythm_was_running else None
        live_bass_riff_id = self._active_bass_riff_id if self._bass_riff_is_playing() else None
        super()._apply_preset_data(data)
        self._rhythm_running = rhythm_was_running
        rhythm = data.get("rhythm", {})
        if not isinstance(rhythm, dict):
            rhythm = {}
        if live_chord_arpeggio is not None:
            (
                self._chord_arpeggio_enabled,
                self._chord_arpeggio_rate,
                self._chord_arpeggio_descending,
            ) = live_chord_arpeggio
        else:
            self._chord_arpeggio_enabled = bool(
                rhythm.get(
                    "chord_arpeggio_enabled",
                    self._chord_arpeggio_enabled,
                )
            )
            self._chord_arpeggio_rate = max(
                CHORD_ARPEGGIO_RATE_MIN,
                min(
                    CHORD_ARPEGGIO_RATE_MAX,
                    int(
                        rhythm.get(
                            "chord_arpeggio_rate",
                            self._chord_arpeggio_rate,
                        )
                    ),
                ),
            )
            self._chord_arpeggio_descending = (
                str(
                    rhythm.get(
                        "chord_arpeggio_direction",
                        ("down" if self._chord_arpeggio_descending else "up"),
                    )
                ).lower()
                == "down"
            )
        self._bass_voicing_shift = clamp_bass_voicing_shift(
            live_bass_voicing
            if live_bass_voicing is not None
            else rhythm.get("bass_voicing_shift", self._bass_voicing_shift),
            limit=BASS_VOICING_LIMIT,
        )
        stored_riff_selector = self._preset_bass_riff_selector(data)
        self._reconcile_bass_riff_context(
            fallback_selector=stored_riff_selector,
            preserve_riff_id=live_bass_riff_id,
            force=True,
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
        rhythm["bass_riff_selector"] = self._bass_riff_selector
        rhythm["chord_arpeggio_enabled"] = self._chord_arpeggio_enabled
        rhythm["chord_arpeggio_rate"] = self._chord_arpeggio_rate
        rhythm["chord_arpeggio_direction"] = "down" if self._chord_arpeggio_descending else "up"
        return snapshot

    def _emit_full_preset_state(self) -> None:
        super()._emit_full_preset_state()
        self.bassVoicingChanged.emit()
        self.chordGateChanged.emit()
        self.chordArpeggioChanged.emit()

    def send_initial_state(self) -> None:
        self._chord_gate_state = CHORD_GATE_OFF
        self._active_bass_riff_id = None
        self._bass_riff_context = None
        super().send_initial_state()
        self.chordGateChanged.emit()
        self.bassVoicingChanged.emit()
        self.chordArpeggioChanged.emit()

    @Slot()
    def panic(self) -> None:
        self._chord_gate_state = CHORD_GATE_OFF
        self._active_bass_riff_id = None
        self._bass_riff_context = None
        super().panic()
        self.chordGateChanged.emit()
        self.chordArpeggioChanged.emit()
