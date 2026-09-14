from __future__ import annotations

import json
import math
import threading
import time
from pathlib import Path
from typing import Any, final

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot

import app_core
from engine_protocol import NoteOff, NoteOn
from json_store import JsonStore
from midi_control import (
    NOTE_BUTTON_OFFSET,
    MidiControlState,
)
from midi_binding_service import MidiBindingService
from midi_input import (
    MIDI_INPUT_ACTIVITY_SECONDS,
    MidiInputEvent,
    MidiInputPort,
    MidiInputPortFactory,
)
from network_availability import qt_listener_network_available
from osc_input import (
    OSC_INPUT_ACTIVITY_SECONDS,
    OscInputEvent,
    OscInputPort,
    OscInputPortFactory,
)
from musical_state import TuningSnapshot, tune_note
from gm_percussion import midi_drum_amplitude, resolve_gm_percussion
from midi_levels import midi_pitched_synth_level, normalized_midi_velocity
from synth_state import SynthState
from sc_drum_kits import DEFAULT_DRUM_KIT_ID, DRUM_KITS
from user_data import MIDI_PRESET_DIR


MIDI_ROW_COUNT = 6
MIDI_PRESET_COUNT = 18
DEFAULT_CHORD_INPUT_CHANNEL = 1
DEFAULT_MIDI_CHANNELS = (2, 3, 4, 5, 6, 10)
LEGACY_FACTORY_MIDI_CHANNELS = (1, 2, 3, 4, 5, 6)
MIDI_DRUM_KEY = "drum_kit_0"
MIDI_FACTORY_DIR = app_core.INSTRUMENT_DIR / "midi_default_presets"
MIDI_LAST_PRESET_FILE = "last_preset.json"
MIDI_PREVIEW_LOW = app_core.STRUM_LOW_MIDI
MIDI_PREVIEW_HIGH = app_core.STRUM_HIGH_MIDI
MIDI_REVERB_MAX = app_core.REVERB_LEVEL_MAX
MIDI_SUSTAIN_CONTROLLER = 64

PREVIEW_DRUM_NOTES = (36, 38, 42, 46, 41, 45, 48, 51)


class _QueuedMidiInputEventRelay:
    """Non-QObject callable used by native threads to emit one Qt signal."""

    def __init__(self, emit: Any) -> None:
        self._emit = emit

    def __call__(self, event: MidiInputEvent) -> None:
        self._emit(event)


class _QueuedOscInputEventRelay:
    """Non-QObject callable used by the OSC worker to emit one Qt signal."""

    def __init__(self, emit: Any) -> None:
        self._emit = emit

    def __call__(self, event: OscInputEvent) -> None:
        self._emit(event)


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    JsonStore(path).write(data)


def _migrated_factory_channel_defaults(
    stored: dict[str, Any],
    factory: dict[str, Any],
) -> dict[str, Any] | None:
    """Upgrade only an untouched copy of the former factory channel layout."""
    legacy_factory = json.loads(json.dumps(factory))
    rows = legacy_factory.get("rows")
    if not isinstance(rows, list) or len(rows) != MIDI_ROW_COUNT:
        return None
    for row, channel in zip(rows, LEGACY_FACTORY_MIDI_CHANNELS):
        if not isinstance(row, dict):
            return None
        row["channel"] = channel
    if legacy_factory.get("factory_name") == "Experimental":
        rows[-1]["selected"] = "physical_strings"
        rows[-1]["volume"] = 0.34
    if stored != legacy_factory:
        return None
    return json.loads(json.dumps(factory))


class MidiEngine:
    """Own MIDI voices through the engine-neutral typed control boundary."""

    def __init__(self, client: Any) -> None:
        self.client = client
        resolved = client.resolved_config
        self.voices = resolved.capacities.voices.midi_per_synth
        self.row_buses = resolved.layout.midi_row_buses
        self.drum_bus = resolved.layout.midi_drum_bus
        if (
            len(self.row_buses) != MIDI_ROW_COUNT
            or len(set(self.row_buses)) != MIDI_ROW_COUNT
            or self.drum_bus in self.row_buses
            or any(bus < 4 for bus in (*self.row_buses, self.drum_bus))
        ):
            raise ValueError("six MIDI row buses and the MIDI drum bus must be distinct buses >= 4")
        self._configured_rows: set[int] = set()
        self._drum_configured = False
        self._active_notes: dict[tuple[int, int, int], str] = {}
        self._sustain_rows: set[int] = set()
        self._programs = ["builtin.safe"] * MIDI_ROW_COUNT
        self._program_revisions = [0] * MIDI_ROW_COUNT
        self._row_levels = [1.0] * MIDI_ROW_COUNT
        self._preview_ordinals = [0] * MIDI_ROW_COUNT
        self.drum_kit_id = DEFAULT_DRUM_KIT_ID
        self.master_volume = 1.0
        self.reverb = {
            "level": 0.0,
            "liveness": 0.5,
            "damping": 0.5,
            "drums": False,
        }
        self._reverb_routing_initialized = False
        self.configure_drum_synth()

    @staticmethod
    def _row_owner(row: int) -> str:
        return f"midi/row/{int(row)}"

    @staticmethod
    def _preview_owner(row: int) -> str:
        return f"midi/preview/{int(row)}"

    def pitched_row_level(self, key: str, volume: float) -> float:
        """Resolve the row UI level to the calibrated engine gain."""
        return midi_pitched_synth_level(
            volume,
            self.client.resolved_config.instrument_level(str(key)),
        )

    def configure_drum_synth(self) -> None:
        if self._drum_configured:
            return
        self.client.configure_part(
            "midi/drums",
            "sample.gm.percussion",
            self.client.allocate_program_revision(),
            self.drum_bus,
            {},
        )
        self._apply_reverb_bus(self.drum_bus)
        self._apply_master_bus(self.drum_bus)
        self._drum_configured = True

    def _apply_master_bus(self, bus: int) -> None:
        level = self.master_volume
        if bus in self.row_buses:
            level *= self._row_levels[self.row_buses.index(bus)]
        self.client.set_logical_bus_level(int(bus), level)

    def set_master_volume(self, volume: float) -> None:
        self.master_volume = max(0.0, min(1.0, float(volume)))
        for bus in (*self.row_buses, self.drum_bus):
            self._apply_master_bus(bus)

    def silence_row(self, row: int) -> None:
        if row not in self._configured_rows:
            return
        self.client.release_owner(self._row_owner(row))
        self.client.release_owner(self._preview_owner(row))
        self._sustain_rows.discard(row)
        for key in [key for key in self._active_notes if key[0] == row]:
            self._active_notes.pop(key, None)

    def set_sustain(self, row: int, enabled: bool) -> None:
        if row not in self._configured_rows:
            return
        active = row in self._sustain_rows
        if bool(enabled) == active:
            return
        if enabled:
            self._sustain_rows.add(row)
        else:
            self._sustain_rows.discard(row)
        self.client.set_owner_sustain(self._row_owner(row), bool(enabled))

    def sustain_enabled(self, row: int) -> bool:
        return int(row) in self._sustain_rows

    def configure_row(
        self,
        row: int,
        key: str,
        params: dict[str, float],
        volume: float,
    ) -> None:
        bus = self.row_buses[row]
        self.silence_row(row)
        previous_program = self._programs[row]
        previous_revision = self._program_revisions[row]
        if previous_revision > 0:
            self.client.release_program(previous_program, previous_revision)
        self._programs[row] = str(key)
        self._program_revisions[row] = self.client.allocate_program_revision()
        self.client.configure_part(
            self._row_owner(row),
            str(key),
            self._program_revisions[row],
            bus,
            params,
        )
        self._configured_rows.add(row)
        self.set_row_volume(row, self.pitched_row_level(key, volume))
        self._apply_reverb_bus(bus)

    def set_row_volume(self, row: int, volume: float) -> None:
        self._row_levels[row] = max(0.0, float(volume))
        self._apply_master_bus(self.row_buses[row])

    def set_reverb(
        self,
        level: float,
        liveness: float,
        damping: float,
        drums: bool,
    ) -> None:
        level = max(0.0, min(MIDI_REVERB_MAX, float(level)))
        liveness = max(0.0, min(1.0, float(liveness)))
        damping = max(0.0, min(1.0, float(damping)))
        previous = self.reverb
        self.reverb = {
            "level": level,
            "liveness": liveness,
            "damping": damping,
            "drums": bool(drums),
        }
        if not self._reverb_routing_initialized or any(
            self.reverb[key] != previous[key]
            for key in ("level", "liveness", "damping")
        ):
            self.client.set_room(1, level, liveness, damping)
        if not self._reverb_routing_initialized:
            for bus in (*self.row_buses, self.drum_bus):
                self._apply_reverb_bus(bus)
            self._reverb_routing_initialized = True
        elif bool(drums) != bool(previous["drums"]):
            self.client.set_room_send(self.drum_bus, 1.0 if drums else 0.0)

    def _apply_reverb_bus(self, bus: int) -> None:
        send = 0.0 if int(bus) == self.drum_bus and not self.reverb["drums"] else 1.0
        self.client.set_room_send(int(bus), send)

    def note_on(
        self,
        row: int,
        channel: int,
        source_note: int,
        note: float,
        velocity: int,
    ) -> None:
        key = (row, channel, source_note)
        old_handle = self._active_notes.pop(key, None)
        owner = self._row_owner(row)
        if old_handle is not None:
            self.client.note_off(NoteOff(owner, old_handle))
        level = normalized_midi_velocity(velocity)
        handle = f"{owner}/ch{channel}/key{source_note}"
        self.client.note_on(
            NoteOn(
                owner=owner,
                handle=handle,
                program_id=self._programs[row],
                program_revision=max(1, self._program_revisions[row]),
                logical_key=max(0, min(127, int(source_note))),
                frequency_hz=self.client.note_to_frequency(note),
                velocity=level,
                logical_bus=self.row_buses[row],
            )
        )
        self._active_notes[key] = handle

    def note_off(self, row: int, channel: int, source_note: int) -> None:
        key = (row, channel, source_note)
        handle = self._active_notes.pop(key, None)
        if handle is not None:
            self.client.note_off(NoteOff(self._row_owner(row), handle))

    def preview_note(
        self,
        row: int,
        note: float,
        velocity: int = 105,
    ) -> None:
        level = normalized_midi_velocity(velocity)
        self._preview_ordinals[row] += 1
        self.client.gesture_note(
            owner=self._preview_owner(row),
            handle=f"{self._preview_owner(row)}/{self._preview_ordinals[row]}",
            program_id=self._programs[row],
            program_revision=max(1, self._program_revisions[row]),
            logical_key=max(0, min(127, int(round(note)))),
            note=note,
            velocity=level,
            logical_bus=self.row_buses[row],
            tail_seconds=max(
                0.01,
                self.client.resolved_config.performance.strum_tail_ms / 1000.0,
            ),
        )

    def close(self) -> None:
        self.all_notes_off()

    def drum_hit(
        self,
        midi_note: int,
        velocity: int,
        row_volume: float,
    ) -> None:
        drums = self.client.resolved_config.drums
        hit = resolve_gm_percussion(
            midi_note,
            kit=drums.kit,
            configured_samples=dict(drums.sample_map),
        )
        if hit is None:
            return
        amp = midi_drum_amplitude(velocity, row_volume, drums.velocity_gain)
        self.client.drum_hit(
            owner="midi/drums",
            logical_key=int(hit.note),
            velocity=amp,
            logical_bus=self.drum_bus,
            kit_id=self.drum_kit_id,
        )

    def all_notes_off(self) -> None:
        for row in sorted(self._configured_rows):
            self.client.release_owner(self._row_owner(row))
            self.client.release_owner(self._preview_owner(row))
        if self._drum_configured:
            self.client.release_owner("midi/drums")
        self._active_notes.clear()
        self._sustain_rows.clear()

    def rebuild(self) -> None:
        self._configured_rows.clear()
        self._drum_configured = False
        self._active_notes.clear()
        self._sustain_rows.clear()
        self.configure_drum_synth()


@final
class MidiPlayerBackend(QObject):
    """MIDI-player state, shared control binding, inputs and AMY routing."""

    stateChanged = Signal()
    tuningChanged = Signal()
    presetChanged = Signal()
    presetStored = Signal(int)
    reverbLevelChanged = Signal()
    reverbLivenessChanged = Signal()
    reverbDampingChanged = Signal()
    reverbDrumsIncludedChanged = Signal()
    drumKitChanged = Signal()
    masterVolumeChanged = Signal()
    masterMutedChanged = Signal()
    bindingStateChanged = Signal()
    bindingLocationRequested = Signal(str, int)
    _queuedMidiInputEvent = Signal(object)
    _queuedOscInputEvent = Signal(object)
    midiInputTechsChanged = Signal()

    def __init__(
        self,
        owner: Any,
        synths: tuple[Any, ...],
        client: Any,
        midi_input_port_factory: MidiInputPortFactory,
        osc_input_port_factory: OscInputPortFactory,
    ) -> None:
        super().__init__(owner)
        self.owner = owner
        self.client = client
        drum = app_core.SynthDefinition(
            key=MIDI_DRUM_KEY,
            label="Drum Kit 0",
            controls=(),
        )
        self.definitions = tuple(synths) + (drum,)
        self.rows = [SynthState(self.definitions, 0) for _ in range(MIDI_ROW_COUNT)]
        self.channels = list(DEFAULT_MIDI_CHANNELS)
        self._chord_input_channel = DEFAULT_CHORD_INPUT_CHANNEL
        self.volumes = [0.5] * MIDI_ROW_COUNT
        self._state_version = 0
        self._selected_preset = 1
        self._preset_reference: dict[str, Any] = {}

        self._tuning_coupled = True
        self._tuning_mode_index = int(owner.selectedTuningModeIndex)
        self._tuning_reference = float(owner.tuningReference)

        self._reverb_level = 0.0
        self._reverb_liveness = 0.5
        self._reverb_damping = 0.5
        self._reverb_drums = False
        self._drum_kit_index = 0
        # MIDI master output is live state and is not replaced by presets.
        self._master_volume = 1.0
        self._master_muted = False
        self._midi_control_state = MidiControlState(capacity=17)
        self._midi_control_lock = threading.Lock()
        self._midi_binding_service = MidiBindingService(
            self._midi_control_state,
            self._midi_control_lock,
        )
        self._preset_binding_locations: dict[tuple[int, int], tuple[tuple[str, int], ...]] = {}
        self._binding_version = 0
        self._applying_midi_control = 0
        self._held_midi_button_targets: set[str] = set()
        self._queuedMidiInputEvent.connect(self._accept_midi_input_event)
        self._midi_input_event_relay = _QueuedMidiInputEventRelay(self._queuedMidiInputEvent.emit)
        self._last_midi_input_sequence = 0
        self._pending_midi_input_events: dict[int, MidiInputEvent] = {}
        self._midi_input_closed = False
        self._queuedOscInputEvent.connect(self._accept_osc_input_event)
        self._osc_input_event_relay = _QueuedOscInputEventRelay(
            self._queuedOscInputEvent.emit
        )
        self._last_osc_input_sequence = 0
        self._pending_osc_input_events: dict[int, OscInputEvent] = {}
        self._osc_input_closed = False
        self._osc_input_activity_until = 0.0
        self._blue_expiry_timer = QTimer(self)
        self._blue_expiry_timer.setInterval(250)
        self._blue_expiry_timer.timeout.connect(self._expire_blue_controls)
        self._preset_feedback_timer = QTimer(self)
        self._preset_feedback_timer.setInterval(100)
        self._preset_feedback_timer.timeout.connect(self._expire_preset_feedback)
        self._midi_input_activity_until: dict[str, float] = {}
        self._input_tech_snapshot: list[dict[str, Any]] = []
        self._input_tech_refresh_timer = QTimer(self)
        self._input_tech_refresh_timer.setInterval(1000)
        self._input_tech_refresh_timer.timeout.connect(self._refresh_input_techs)
        self._input_tech_activity_timer = QTimer(self)
        self._input_tech_activity_timer.setInterval(120)
        self._input_tech_activity_timer.timeout.connect(self._refresh_input_techs)

        self.engine = MidiEngine(client)
        self._preview_row = -1
        self._preview_last_index: int | None = None

        self._ensure_preset_storage()
        self._load_startup_preset()
        self._refresh_preset_binding_locations()
        self.syncFromOmni()
        self._apply_all_to_engine()

        self._midi_input_port: MidiInputPort = midi_input_port_factory(
            self._midi_input_event_relay,
            client.resolved_config.midi_input,
        )
        self._midi_input_port.start()
        self._osc_input_port: OscInputPort = osc_input_port_factory(
            self._osc_input_event_relay,
            client.resolved_config.osc_input,
        )
        self._osc_input_port.start()
        self._refresh_input_techs()
        self._input_tech_refresh_timer.start()

    def close(self) -> None:
        self._input_tech_refresh_timer.stop()
        self._input_tech_activity_timer.stop()
        self._midi_input_closed = True
        self._osc_input_closed = True
        self._pending_midi_input_events.clear()
        self._pending_osc_input_events.clear()
        self.owner.resetExternalChordInput()
        self._osc_input_port.close()
        self._midi_input_port.close()
        self.engine.close()

    @Property(int, notify=stateChanged)
    def stateVersion(self) -> int:
        return self._state_version

    @Property(int, notify=stateChanged)
    def chordInputChannel(self) -> int:
        return self._chord_input_channel

    @Property(int, notify=bindingStateChanged)
    def bindingVersion(self) -> int:
        return self._binding_version

    @Property(str, notify=bindingStateChanged)
    def omniControlLedState(self) -> str:
        with self._midi_control_lock:
            return self._midi_control_state.omni_led_state()

    @Property(list, constant=True)
    def synthNames(self) -> list[str]:
        return [definition.label for definition in self.definitions]

    @Slot(int, result=str)
    def synthKind(self, row: int) -> str:
        if not self._valid_row(row) or self._is_drum(row):
            return "drum"
        return self._runtime(row).selected_kind

    @Slot(int, result=list)
    def synthBrowserNames(self, row: int) -> list[str]:
        if not self._valid_row(row):
            return []
        if self._is_drum(row):
            return [kit.label for kit in DRUM_KITS]
        return self._runtime(row).browser_names()

    @Slot(int, result=int)
    def synthBrowserIndex(self, row: int) -> int:
        if not self._valid_row(row):
            return 0
        if self._is_drum(row):
            return self._drum_kit_index
        return self._runtime(row).browser_index()

    @Slot(int, result=list)
    def sampleChoiceColumns(self, row: int) -> list[dict[str, Any]]:
        if not self._valid_row(row) or self._is_drum(row):
            return []
        return self._runtime(row).sample_choice_columns()

    @Slot(int, result=bool)
    def sampleSustainAvailable(self, row: int) -> bool:
        if not self._valid_row(row) or self._is_drum(row):
            return False
        runtime = self._runtime(row)
        return (
            runtime.selected_kind == "sample"
            and runtime.selected_browser_group == "Piano"
        )

    @Slot(int, result=bool)
    def sustainEnabled(self, row: int) -> bool:
        return self._valid_row(row) and self.engine.sustain_enabled(int(row))

    @Slot(int)
    def toggleSustain(self, row: int) -> None:
        if not self.sampleSustainAvailable(row):
            return
        selected = int(row)
        self.engine.set_sustain(selected, not self.engine.sustain_enabled(selected))
        self._emit_state()

    @Property(int, constant=True)
    def presetCount(self) -> int:
        return MIDI_PRESET_COUNT

    @Property(int, notify=presetChanged)
    def selectedPreset(self) -> int:
        return self._selected_preset

    @Property(bool, notify=tuningChanged)
    def tuningCoupled(self) -> bool:
        return self._tuning_coupled

    @Property(int, notify=tuningChanged)
    def tuningModeIndex(self) -> int:
        return int(self._tuning_mode_index)

    @Property(int, notify=tuningChanged)
    def tuningReference(self) -> int:
        return int(round(self._tuning_reference))

    @Property(float, notify=reverbLevelChanged)
    def reverbLevel(self) -> float:
        return self._reverb_level

    @Property(float, notify=reverbLivenessChanged)
    def reverbLiveness(self) -> float:
        return self._reverb_liveness

    @Property(float, notify=reverbLivenessChanged)
    def reverbRoom(self) -> float:
        return self._reverb_liveness

    @Property(float, notify=reverbDampingChanged)
    def reverbDamping(self) -> float:
        return self._reverb_damping

    @Property(bool, notify=reverbDrumsIncludedChanged)
    def reverbDrumsIncluded(self) -> bool:
        return self._reverb_drums

    @Property(list, constant=True)
    def drumKitNames(self) -> list[str]:
        return [kit.label for kit in DRUM_KITS]

    @Property(int, notify=drumKitChanged)
    def selectedDrumKitIndex(self) -> int:
        return self._drum_kit_index

    @Slot(int)
    def setDrumKitIndex(self, index: int) -> None:
        selected = int(index)
        if not 0 <= selected < len(DRUM_KITS) or selected == self._drum_kit_index:
            return
        self._drum_kit_index = selected
        self.engine.drum_kit_id = DRUM_KITS[selected].kit_id
        self.drumKitChanged.emit()
        self._emit_state()

    @Property(float, notify=masterVolumeChanged)
    def masterVolume(self) -> float:
        return self._master_volume

    @Property(bool, notify=masterMutedChanged)
    def masterMuted(self) -> bool:
        return self._master_muted

    @Property(list, notify=midiInputTechsChanged)
    def midiInputTechs(self) -> list[dict[str, Any]]:
        """Return the shared input-tech row under its compatibility name."""

        return list(self._input_tech_snapshot)

    @Property(str, constant=True)
    def oscInputState(self) -> str:
        return str(self._osc_input_port.lifecycle)

    @Property(str, constant=True)
    def oscInputFailureReason(self) -> str:
        return str(self._osc_input_port.failure_reason)

    @Slot(str)
    def _mark_midi_tech_activity(self, key: str) -> None:
        self._midi_input_activity_until[str(key)] = time.monotonic() + MIDI_INPUT_ACTIVITY_SECONDS
        self._refresh_input_techs()
        if not self._input_tech_activity_timer.isActive():
            self._input_tech_activity_timer.start()

    def _mark_osc_input_activity(self) -> None:
        self._osc_input_activity_until = (
            time.monotonic() + OSC_INPUT_ACTIVITY_SECONDS
        )
        self._refresh_input_techs()
        if not self._input_tech_activity_timer.isActive():
            self._input_tech_activity_timer.start()

    def _refresh_input_techs(self) -> None:
        snapshot = [
            status.presentation()
            for status in self._midi_input_port.status_snapshot(self._midi_input_activity_until)
        ]
        osc_address = self.client.resolved_config.osc_input.listen_address
        network_available = bool(
            osc_address is not None
            and qt_listener_network_available(osc_address)
        )
        osc_status = self._osc_input_port.status_snapshot(
            self._osc_input_activity_until,
            network_available,
        )
        if osc_status is not None:
            snapshot.append(osc_status.presentation())
        if snapshot != self._input_tech_snapshot:
            self._input_tech_snapshot = snapshot
            self.midiInputTechsChanged.emit()
        active = any(item.get("state") == "activity" for item in snapshot)
        if not active:
            self._input_tech_activity_timer.stop()

    @Slot(object)
    def _accept_midi_input_event(self, event: object) -> None:
        """Drain the one ordered native-to-Qt MIDI event stream."""

        if self._midi_input_closed or not isinstance(event, MidiInputEvent):
            return
        if event.sequence <= self._last_midi_input_sequence:
            return
        self._pending_midi_input_events[event.sequence] = event
        sequence = self._last_midi_input_sequence + 1
        while sequence in self._pending_midi_input_events:
            current = self._pending_midi_input_events.pop(sequence)
            self._dispatch_midi_input_event(current)
            self._last_midi_input_sequence = sequence
            sequence += 1

    def _dispatch_midi_input_event(self, event: MidiInputEvent) -> None:
        if event.kind == "activity":
            self._mark_midi_tech_activity(event.technology)
            return
        channel = max(1, min(16, int(event.channel)))
        if event.kind == "note":
            self.process_midi_note(
                channel,
                max(0, min(127, int(event.data))),
                max(0, min(127, int(event.value))),
                bool(event.is_on),
            )
            return
        if event.kind == "button":
            self.process_midi_button(
                channel,
                max(0, min(127, int(event.data))),
                max(0, min(127, int(event.value))) if event.is_on else 0,
            )
            return
        key = self._midi_control_state.key(channel, int(event.data))
        self.process_midi_control(
            channel,
            key[1],
            max(
                0,
                min(
                    self._midi_control_state.value_max_for_key(key),
                    int(event.value),
                ),
            ),
        )

    @Slot(object)
    def _accept_osc_input_event(self, event: object) -> None:
        """Drain the one ordered OSC-worker-to-Qt event stream."""

        if self._osc_input_closed or not isinstance(event, OscInputEvent):
            return
        if event.sequence <= self._last_osc_input_sequence:
            return
        self._mark_osc_input_activity()
        self._pending_osc_input_events[event.sequence] = event
        sequence = self._last_osc_input_sequence + 1
        while sequence in self._pending_osc_input_events:
            current = self._pending_osc_input_events.pop(sequence)
            self.process_osc_control(
                current.address,
                current.argument,
                current.value,
                current.value_type,
            )
            self._last_osc_input_sequence = sequence
            sequence += 1

    def process_osc_control(
        self,
        address: str,
        argument: int,
        value: float,
        value_type: str,
    ) -> None:
        with self._midi_control_lock:
            control_key = self._midi_control_state.osc_key(
                address,
                argument,
                value_type,
            )
            was_blue = control_key in self._midi_control_state.blue_since
            was_bound = control_key in self._midi_control_state.bindings
            changed, target, key = self._midi_control_state.observe_osc(
                address,
                argument,
                value,
                value_type,
                now=time.monotonic(),
            )
            if not changed or key is None:
                return
            blue_cleared = (
                was_blue and control_key not in self._midi_control_state.blue_since
            )
            preset_binding_restored = (
                not was_bound and control_key in self._midi_control_state.bindings
            )
        if blue_cleared or preset_binding_restored:
            self._sync_blue_timer()
            self._bump_binding_state()
        scaled_value = int(
            round(
                max(0.0, min(1.0, float(value)))
                * self._midi_control_state.value_max_for_key(key)
            )
        )
        if target is not None:
            if self._is_button_target(target):
                self._apply_button_target(target, scaled_value > 0)
            else:
                self._apply_control_target(target, scaled_value, key)
        self._emit_binding_location_feedback(key, target)

    @Slot(int, int, int)
    def process_midi_control(self, channel: int, controller: int, value: int) -> None:
        if int(controller) == MIDI_SUSTAIN_CONTROLLER:
            for row, row_channel in enumerate(self.channels):
                if int(row_channel) == int(channel) and not self._is_drum(row):
                    self.engine.set_sustain(row, int(value) >= 64)
        control_key = self._midi_control_state.key(channel, controller)
        with self._midi_control_lock:
            was_blue = control_key in self._midi_control_state.blue_since
            was_bound = control_key in self._midi_control_state.bindings
            changed, target, key = self._midi_control_state.observe(
                channel,
                controller,
                value,
                now=time.monotonic(),
            )
            if not changed or key is None:
                return
            blue_cleared = was_blue and control_key not in self._midi_control_state.blue_since
            preset_binding_restored = (
                not was_bound and control_key in self._midi_control_state.bindings
            )
        if blue_cleared or preset_binding_restored:
            self._sync_blue_timer()
            self._bump_binding_state()
        if target is not None:
            if self._is_button_target(target):
                self._apply_button_target(target, int(value) > 0)
            else:
                self._apply_control_target(target, int(value), control_key)
        self._emit_binding_location_feedback(key, target)

    @Slot(int, int, int)
    def process_midi_button(self, channel: int, note: int, velocity: int) -> None:
        controller = NOTE_BUTTON_OFFSET + max(0, min(127, int(note)))
        control_key = self._midi_control_state.key(channel, controller)
        with self._midi_control_lock:
            was_blue = control_key in self._midi_control_state.blue_since
            was_bound = control_key in self._midi_control_state.bindings
            changed, target, key = self._midi_control_state.observe(
                channel,
                controller,
                max(0, min(127, int(velocity))),
                now=time.monotonic(),
            )
            if not changed or key is None:
                return
            blue_cleared = was_blue and control_key not in self._midi_control_state.blue_since
            preset_binding_restored = (
                not was_bound and control_key in self._midi_control_state.bindings
            )
        if blue_cleared or preset_binding_restored:
            self._sync_blue_timer()
            self._bump_binding_state()
        if target is not None:
            if self._is_button_target(target):
                self._apply_button_target(target, int(velocity) > 0)
            else:
                self._apply_control_target(target, int(velocity), key)
        self._emit_binding_location_feedback(key, target)

    @Slot(int)
    def setControlIndicatorCapacity(self, capacity: int) -> None:
        """Match the LRU pool to the number of indicators visible in QML."""
        capacity = max(1, int(capacity))
        with self._midi_control_lock:
            self._midi_control_state.set_capacity(capacity)

    def _bump_binding_state(self) -> None:
        self._binding_version += 1
        self.bindingStateChanged.emit()

    def _sync_blue_timer(self) -> None:
        with self._midi_control_lock:
            active = bool(self._midi_control_state.blue_since)
        if active and not self._blue_expiry_timer.isActive():
            self._blue_expiry_timer.start()
        elif not active:
            self._blue_expiry_timer.stop()

    def _expire_blue_controls(self) -> None:
        with self._midi_control_lock:
            changed = self._midi_control_state.expire_blue()
        self._sync_blue_timer()
        if changed:
            self._bump_binding_state()

    def _sync_preset_feedback_timer(self) -> None:
        with self._midi_control_lock:
            active = self._midi_control_state.has_preset_feedback()
        if active and not self._preset_feedback_timer.isActive():
            self._preset_feedback_timer.start()
        elif not active:
            self._preset_feedback_timer.stop()

    def _expire_preset_feedback(self) -> None:
        with self._midi_control_lock:
            changed = self._midi_control_state.expire_preset_feedback()
        self._sync_preset_feedback_timer()
        if changed:
            self._bump_binding_state()

    def _definition_for_target(
        self,
        screen: str,
        instrument: str,
    ) -> Any | None:
        definitions = self.definitions if screen == "midi" else tuple(self.owner._synths)
        return next(
            (definition for definition in definitions if str(definition.key) == str(instrument)),
            None,
        )

    def _normalize_control_target(
        self,
        raw: Any,
    ) -> dict[str, Any] | None:
        if not isinstance(raw, dict):
            return None
        screen = str(raw.get("screen", ""))
        kind = str(raw.get("kind", ""))
        if screen not in ("midi", "omni"):
            return None

        target: dict[str, Any] = {"screen": screen, "kind": kind}
        if kind == "synth_control":
            control = str(raw.get("control", ""))
            if not control:
                return None
            if screen == "midi":
                row = int(raw.get("row", -1))
                if not self._valid_row(row):
                    return None
                instrument = str(
                    raw.get(
                        "instrument",
                        self._runtime(row).selected_definition.key,
                    )
                )
                target["row"] = row
                location = str(row)
            else:
                role = str(raw.get("role", ""))
                if role not in ("chord", "strum", "bass"):
                    return None
                instrument = str(
                    raw.get(
                        "instrument",
                        self.owner._runtime(role).selected_definition.key,
                    )
                )
                target["role"] = role
                location = role
            definition = self._definition_for_target(screen, instrument)
            if definition is None or not any(
                str(item.key) == control for item in definition.controls
            ):
                return None
            target.update({"instrument": instrument, "control": control})
            target["id"] = f"{screen}:synth_control:{location}:{instrument}:{control}"
            return target

        if kind == "volume":
            if screen == "midi":
                row = int(raw.get("row", -1))
                if not self._valid_row(row):
                    return None
                target["row"] = row
                location = str(row)
            else:
                role = str(raw.get("role", ""))
                if role not in ("chord", "strum", "bass", "percussion"):
                    return None
                target["role"] = role
                location = role
            target["id"] = f"{screen}:volume:{location}"
            return target

        if kind in (
            "reverb_level",
            "reverb_liveness",
            "reverb_damping",
            "tuning_reference",
            "master_volume",
        ):
            target["id"] = f"{screen}:{kind}"
            return target
        if screen == "omni" and kind == "pitch_bend":
            target["id"] = "omni:pitch_bend"
            return target

        if screen == "omni" and kind in (
            "rhythm_tempo",
            "rhythm_fill_density",
            "bass_voicing",
            "bass_riff_selector",
            "strum_position",
        ):
            target["id"] = f"omni:{kind}"
            return target
        if screen == "omni" and kind == "chord_type":
            row = int(raw.get("row", -1))
            if not 0 <= row < app_core.ROW_COUNT:
                return None
            target["row"] = row
            target["id"] = f"omni:chord_type:{row}"
            return target
        if kind == "button":
            action = str(raw.get("action", ""))
            if not action:
                return None
            target["action"] = action
            for field in ("preset", "row", "level", "fill", "rate"):
                if field in raw:
                    try:
                        target[field] = int(raw[field])
                    except (TypeError, ValueError):
                        return None
            target["id"] = ":".join(
                [screen, "button", action]
                + [
                    str(target[field])
                    for field in ("preset", "row", "level", "fill", "rate")
                    if field in target
                ]
            )
            return target
        return None

    def _target_range(
        self,
        target: dict[str, Any],
    ) -> tuple[float, float, float, str] | None:
        kind = str(target["kind"])
        screen = str(target["screen"])
        if kind == "synth_control":
            definition = self._definition_for_target(
                screen,
                str(target["instrument"]),
            )
            if definition is None:
                return None
            control = next(
                (item for item in definition.controls if str(item.key) == str(target["control"])),
                None,
            )
            if control is None:
                return None
            return (
                float(control.minimum),
                float(control.maximum),
                float(control.step),
                str(getattr(control, "scale", "linear")),
            )
        if kind == "volume":
            return 0.0, 1.0, 0.01, "linear"
        if kind == "master_volume":
            return 0.0, 1.0, 0.01, "linear"
        if kind == "reverb_level":
            return 0.0, MIDI_REVERB_MAX, 0.01, "linear"
        if kind in ("reverb_liveness", "reverb_damping"):
            return 0.0, 1.0, 0.01, "linear"
        if kind == "tuning_reference":
            return 415.0, 466.0, 1.0, "linear"
        if kind == "rhythm_tempo":
            return 40.0, 200.0, 1.0, "linear"
        if kind == "rhythm_fill_density":
            return 0.0, 7.0, 1.0, "linear"
        if kind == "bass_voicing":
            return -6.0, 6.0, 1.0, "linear"
        if kind == "bass_riff_selector":
            return (
                1.0,
                float(self.owner.bassRiffSelectorMaximum),
                1.0,
                "linear",
            )
        if kind == "strum_position":
            return 0.0, 1.0, 0.0, "linear"
        if kind == "chord_type":
            return 0.0, float(len(self.owner._chords) - 1), 1.0, "linear"
        return None

    def _mapped_target_value(
        self,
        target: dict[str, Any],
        midi_value: int,
        source_key: tuple[int, int] | None = None,
    ) -> float | None:
        target_range = self._target_range(target)
        if target_range is None:
            return None
        minimum, maximum, step, scale = target_range
        value_max = (
            self._midi_control_state.value_max_for_key(source_key)
            if source_key is not None
            else 127
        )
        position = max(0.0, min(1.0, float(midi_value) / float(value_max)))
        if scale == "log" and minimum > 0.0:
            value = math.exp(math.log(minimum) + position * (math.log(maximum) - math.log(minimum)))
        else:
            value = minimum + position * (maximum - minimum)
        if step > 0.0:
            value = minimum + round((value - minimum) / step) * step
        return max(minimum, min(maximum, value))

    def manual_change_blocked(self, raw: dict[str, Any]) -> bool:
        """Whether a user/API edit must yield to a live MIDI binding."""
        if self._applying_midi_control:
            return False
        target = self._normalize_control_target(raw)
        if target is None:
            return False
        targets = [target]
        if str(target.get("kind", "")) == "tuning_reference" and self._tuning_coupled:
            other_screen = "omni" if str(target.get("screen", "")) == "midi" else "midi"
            other = self._normalize_control_target(
                {"screen": other_screen, "kind": "tuning_reference"}
            )
            if other is not None:
                targets.append(other)
        with self._midi_control_lock:
            return any(
                self._midi_control_state.is_target_bound(item)
                or self._midi_control_state.target_visual_state(item) == "preset-displaced"
                for item in targets
            )

    @Slot("QVariantMap", result=bool)
    def midiButtonTargetBlocked(self, raw: dict[str, Any]) -> bool:
        if self._applying_midi_control:
            return False
        target = self._normalize_control_target(raw)
        if target is None or not self._is_button_target(target):
            return False
        group = self._button_takeover_group(target)
        if group is None:
            return False
        with self._midi_control_lock:
            return group in self._held_midi_button_targets

    def _apply_midi_setter(self, setter: Any, *args: Any) -> None:
        self._applying_midi_control += 1
        try:
            setter(*args)
        finally:
            self._applying_midi_control -= 1

    def _apply_control_target(
        self,
        target: dict[str, Any],
        midi_value: int,
        source_key: tuple[int, int] | None = None,
    ) -> None:
        if str(target.get("kind", "")) == "pitch_bend":
            self._apply_midi_setter(
                self.owner.setMidiPitchBend,
                int(midi_value),
            )
            return
        value = self._mapped_target_value(target, midi_value, source_key)
        if value is None:
            return
        screen = str(target["screen"])
        kind = str(target["kind"])

        if kind == "synth_control":
            definition = self._definition_for_target(
                screen,
                str(target["instrument"]),
            )
            if definition is None:
                return
            definitions = self.definitions if screen == "midi" else tuple(self.owner._synths)
            index = next(
                (
                    item_index
                    for item_index, item in enumerate(definitions)
                    if str(item.key) == str(target["instrument"])
                ),
                None,
            )
            if index is None:
                return
            if screen == "midi":
                row = int(target["row"])
                self._apply_midi_setter(self.setSynthIndex, row, index)
                self._apply_midi_setter(
                    self.setControl,
                    row,
                    str(target["control"]),
                    value,
                )
            else:
                role = str(target["role"])
                if role == "chord":
                    self._apply_midi_setter(self.owner.setChordSynthIndex, index)
                    self._apply_midi_setter(
                        self.owner.setChordSynthControl,
                        str(target["control"]),
                        value,
                    )
                elif role == "strum":
                    self._apply_midi_setter(self.owner.setStrumSynthIndex, index)
                    self._apply_midi_setter(
                        self.owner.setStrumSynthControl,
                        str(target["control"]),
                        value,
                    )
                else:
                    self._apply_midi_setter(self.owner.setBassSynthIndex, index)
                    self._apply_midi_setter(
                        self.owner.setBassSynthControl,
                        str(target["control"]),
                        value,
                    )
        elif kind == "volume":
            if screen == "midi":
                self._apply_midi_setter(
                    self.setVolume,
                    int(target["row"]),
                    value,
                )
            else:
                setter = {
                    "chord": self.owner.setChordVolume,
                    "strum": self.owner.setStrumVolume,
                    "bass": self.owner.setBassVolume,
                    "percussion": self.owner.setPercussionVolume,
                }[str(target["role"])]
                self._apply_midi_setter(setter, value)
        elif kind == "master_volume":
            controller = self if screen == "midi" else self.owner
            self._apply_midi_setter(controller.setMasterVolume, value)
        elif kind.startswith("reverb_"):
            controller = self if screen == "midi" else self.owner
            setter = {
                "reverb_level": controller.setReverbLevel,
                "reverb_liveness": controller.setReverbLiveness,
                "reverb_damping": controller.setReverbDamping,
            }[kind]
            self._apply_midi_setter(setter, value)
        elif kind == "tuning_reference":
            if screen == "midi":
                self._apply_midi_setter(
                    self.setTuningReference,
                    round(value),
                )
            else:
                self._apply_midi_setter(
                    self.owner.setTuningReference,
                    round(value),
                )
        elif kind == "rhythm_tempo":
            self._apply_midi_setter(self.owner.setRhythmTempo, value)
        elif kind == "rhythm_fill_density":
            self._apply_midi_setter(self.owner.setRhythmFillDensity, value)
        elif kind == "bass_voicing":
            self._apply_midi_setter(self.owner.setBassVoicingShift, value)
        elif kind == "bass_riff_selector":
            self._apply_midi_setter(self.owner.setBassRiffSelector, value)
        elif kind == "strum_position":
            # Conventional MIDI controls increase bottom-to-top; the screen
            # strum coordinate increases top-to-bottom.
            self._apply_midi_setter(self.owner.strumControlPosition, 1.0 - value)
        elif kind == "chord_type":
            self._apply_midi_setter(
                self.owner.setRowChordType,
                int(target["row"]),
                int(round(value)),
            )

    @staticmethod
    def _is_button_target(target: dict[str, Any]) -> bool:
        return str(target.get("kind", "")) == "button"

    @staticmethod
    def _button_takeover_group(target: dict[str, Any]) -> str | None:
        screen = str(target.get("screen", ""))
        action = str(target.get("action", ""))
        if not screen or not action:
            return None

        # Pure tap actions must not own later screen interaction while the
        # hardware contact is still held. They trigger once on MIDI press.
        if action in ("panic", "store_preset", "cycle_channel"):
            return None

        # Choice groups are held as a group: while one external control owns
        # the selection, screen taps for the other choices in the same group
        # are ignored, but unrelated app buttons remain usable.
        if action in (
            "select_preset",
            "rhythm_busyness",
            "rhythm_chord_activity",
            "rhythm_bass_activity",
            "chord_arpeggio_rate",
        ):
            return f"{screen}:button:{action}"

        # Independent toggle buttons only block their own screen target.
        return str(target["id"])

    def _apply_button_target(
        self,
        target: dict[str, Any],
        pressed: bool,
    ) -> None:
        takeover_group = self._button_takeover_group(target)
        with self._midi_control_lock:
            if takeover_group is not None:
                if pressed:
                    self._held_midi_button_targets.add(takeover_group)
                else:
                    self._held_midi_button_targets.discard(takeover_group)
        if not pressed:
            return

        action = str(target.get("action", ""))
        screen = str(target.get("screen", ""))

        if screen == "midi":
            if action == "store_preset":
                self._apply_midi_setter(self.storeSelectedPreset)
            elif action == "select_preset":
                self._apply_midi_setter(
                    self.selectPreset,
                    int(target.get("preset", self._selected_preset)),
                )
            elif action == "master_mute":
                self._apply_midi_setter(self.toggleMasterMuted)
            elif action == "reverb_drums":
                self._apply_midi_setter(self.toggleReverbDrums)
            elif action == "cycle_channel":
                self._apply_midi_setter(
                    self.cycleChannel,
                    int(target.get("row", 0)),
                )
        elif screen == "omni":
            if action == "store_preset":
                self._apply_midi_setter(self.owner.storeSelectedPreset)
            elif action == "select_preset":
                self._apply_midi_setter(
                    self.owner.selectPreset,
                    int(target.get("preset", self.owner.selectedPreset)),
                )
            elif action == "master_mute":
                self._apply_midi_setter(self.owner.toggleMasterMuted)
            elif action == "reverb_drums":
                self._apply_midi_setter(self.owner.toggleReverbDrums)
            elif action == "panic":
                self._apply_midi_setter(self.owner.panic)
            elif action == "rhythm_toggle":
                self._apply_midi_setter(self.owner.toggleRhythm)
            elif action == "rhythm_busyness":
                self._apply_midi_setter(
                    self.owner.setRhythmBusyness,
                    int(target.get("level", 0)),
                )
            elif action == "rhythm_chord_activity":
                self._apply_midi_setter(
                    self.owner.setRhythmChordActivity,
                    int(target.get("level", 0)),
                )
            elif action == "rhythm_bass_activity":
                self._apply_midi_setter(
                    self.owner.setRhythmBassActivity,
                    int(target.get("level", 1)),
                )
            elif action == "rhythm_fill":
                self._apply_midi_setter(
                    self.owner.toggleRhythmFill,
                    int(target.get("fill", 0)),
                )
            elif action == "strum_ladder":
                self._apply_midi_setter(self.owner.toggleStrumLadderMode)
            elif action == "chord_arpeggio":
                self._apply_midi_setter(self.owner.toggleChordArpeggio)
            elif action == "chord_arpeggio_rate":
                self._apply_midi_setter(
                    self.owner.setChordArpeggioRate,
                    int(target.get("rate", 1)),
                )
            elif action == "chord_arpeggio_direction":
                self._apply_midi_setter(self.owner.toggleChordArpeggioDirection)
            elif action == "chord_gate":
                self._apply_midi_setter(self.owner.toggleChordGate)

    @Slot(int, int)
    def clickControlIndicator(self, channel: int, controller: int) -> None:
        key = (int(channel), int(controller))
        with self._midi_control_lock:
            changed = self._midi_control_state.indicator_clicked(key)
        if changed:
            self._sync_blue_timer()
            self._bump_binding_state()

    @Slot("QVariantMap", result=bool)
    def activateControlTarget(self, raw: dict[str, Any]) -> bool:
        target = self._normalize_control_target(raw)
        if target is None:
            return False
        with self._midi_control_lock:
            learned_key = self._midi_control_state.learn_key
            learned = self._midi_control_state.bind_learned_target(target)
        if learned:
            if (
                learned_key is not None
                and self._midi_control_state.source_type(learned_key) == "pitch_bend"
                and not self._is_button_target(target)
            ):
                self._apply_control_target(
                    target,
                    self._midi_control_state.default_value_for_key(learned_key),
                    learned_key,
                )
            self._sync_blue_timer()
            self._bump_binding_state()
        return learned

    @Slot("QVariantMap", result=bool)
    def isControlTargetBound(self, raw: dict[str, Any]) -> bool:
        target = self._normalize_control_target(raw)
        if target is None:
            return False
        with self._midi_control_lock:
            return self._midi_control_state.is_target_bound(target)

    @Slot("QVariantMap", result=str)
    def controlTargetVisualState(self, raw: dict[str, Any]) -> str:
        target = self._normalize_control_target(raw)
        if target is None:
            return "idle"
        with self._midi_control_lock:
            return self._midi_control_state.target_visual_state(target)

    @Slot("QVariantMap")
    def releaseControlTargetForManualEdit(self, raw: dict[str, Any]) -> None:
        """Release MIDI ownership before QML applies a manual UI value."""
        target = self._normalize_control_target(raw)
        if target is None:
            return
        with self._midi_control_lock:
            changed = self._midi_control_state.release_target_for_manual_edit(target)
        if changed:
            self._sync_blue_timer()
            self._bump_binding_state()

    def control_bindings_snapshot(self, screen: str) -> list[dict[str, Any]]:
        result = self._binding_service().serialize(screen)
        for entry in result:
            target = entry.get("target")
            if isinstance(target, dict):
                target.pop("id", None)
        return result

    def _binding_service(self) -> MidiBindingService:
        service = getattr(self, "_midi_binding_service", None)
        if service is not None and service.state is self._midi_control_state:
            return service
        lock = getattr(self, "_midi_control_lock", None)
        if lock is None:
            lock = threading.Lock()
            self._midi_control_lock = lock
        service = MidiBindingService(self._midi_control_state, lock)
        self._midi_binding_service = service
        return service

    def _selected_preset_for_screen(self, screen: str) -> int:
        if str(screen) == "midi":
            return int(self._selected_preset)
        return int(self.owner.selectedPreset)

    def _binding_feedback_locations(
        self,
        key: tuple[int, int],
        active_target: dict[str, Any] | None,
    ) -> tuple[tuple[str, int], ...]:
        if active_target is not None:
            screen = str(active_target.get("screen", ""))
            if screen in ("omni", "midi"):
                return ((screen, self._selected_preset_for_screen(screen)),)
            return ()

        return tuple(
            (screen, preset_number)
            for screen, preset_number in self._preset_binding_locations.get(
                self._midi_control_state.key(*key),
                (),
            )
            if preset_number != self._selected_preset_for_screen(screen)
        )

    def _emit_binding_location_feedback(
        self,
        key: tuple[int, int],
        active_target: dict[str, Any] | None,
    ) -> None:
        for screen, preset_number in self._binding_feedback_locations(
            key,
            active_target,
        ):
            self.bindingLocationRequested.emit(screen, preset_number)

    def _refresh_preset_binding_locations(self) -> None:
        locations: dict[tuple[int, int], set[tuple[str, int]]] = {}
        banks = (
            ("omni", app_core.PRESET_COUNT, self.owner._preset_path),
            ("midi", MIDI_PRESET_COUNT, self._preset_path),
        )
        for screen, count, path_for_number in banks:
            for preset_number in range(1, count + 1):
                try:
                    data = json.loads(path_for_number(preset_number).read_text(encoding="utf-8"))
                    if not isinstance(data, dict):
                        continue
                    entries = self._normalized_binding_entries(
                        screen,
                        data.get("midi_control_bindings", []),
                    )
                except (
                    OSError,
                    TypeError,
                    ValueError,
                    KeyError,
                    json.JSONDecodeError,
                ):
                    continue
                for key, _target in entries:
                    locations.setdefault(key, set()).add((screen, preset_number))
        self._preset_binding_locations = {
            key: tuple(sorted(values)) for key, values in locations.items()
        }

    @Slot(int)
    def refreshPresetBindingLocations(self, _preset_number: int) -> None:
        self._refresh_preset_binding_locations()

    def _normalized_binding_entries(
        self,
        screen: str,
        data: Any,
        *,
        include_dormant: bool = True,
    ) -> list[tuple[tuple[int, int], dict[str, Any]]]:
        entries = self._binding_service().normalize_entries(
            screen,
            data,
            self._normalize_control_target,
        )
        if not include_dormant:
            entries = tuple(
                entry for entry in entries if not entry.activate_on_input
            )
        return MidiBindingService.as_state_entries(entries)

    def capture_bound_control_values(
        self,
        screen: str,
        *,
        incoming_bindings: Any = None,
        role: str | None = None,
        row: int | None = None,
    ) -> list[tuple[dict[str, Any], float]]:
        screen = str(screen)
        incoming_entries = (
            self._normalized_binding_entries(
                screen,
                incoming_bindings,
                include_dormant=False,
            )
            if incoming_bindings is not None
            else []
        )
        with self._midi_control_lock:
            targets = [
                dict(target)
                for target in self._midi_control_state.bindings.values()
                if str(target.get("screen", "")) == screen
            ]
            coupled_tuning_bound = self._tuning_coupled and any(
                str(target.get("kind", "")) == "tuning_reference"
                for target in self._midi_control_state.bindings.values()
            )
            preset_conflicts = (
                self._midi_control_state.preset_conflict_target_ids(incoming_entries)
                if incoming_entries
                else set()
            )
        if incoming_entries:
            targets.extend(dict(target) for _, target in incoming_entries)
        if self._tuning_coupled and (
            coupled_tuning_bound
            or any(str(target.get("kind", "")) == "tuning_reference" for target in targets)
        ):
            tuning_target = self._normalize_control_target(
                {"screen": screen, "kind": "tuning_reference"}
            )
            if tuning_target is not None:
                targets.append(tuning_target)

        unique = {str(target["id"]): target for target in targets}
        captured: list[tuple[dict[str, Any], float]] = []
        for target in unique.values():
            if str(target["id"]) in preset_conflicts:
                continue
            if role is not None and str(target.get("role", "")) != str(role):
                continue
            if row is not None and int(target.get("row", -1)) != int(row):
                continue
            value = self._control_target_value(target)
            if value is not None:
                captured.append((target, value))
        return captured

    def _control_target_value(self, target: dict[str, Any]) -> float | None:
        screen = str(target["screen"])
        kind = str(target["kind"])
        if kind == "synth_control":
            runtime = (
                self._runtime(int(target["row"]))
                if screen == "midi"
                else self.owner._runtime(str(target["role"]))
            )
            return runtime.control_value(
                str(target["instrument"]),
                str(target["control"]),
            )
        if kind == "volume":
            if screen == "midi":
                return float(self.volumes[int(target["row"])])
            return float(
                {
                    "chord": self.owner._chord_volume,
                    "strum": self.owner._strum_volume,
                    "bass": self.owner._bass_volume,
                    "percussion": self.owner._percussion_volume,
                }[str(target["role"])]
            )
        controller = self if screen == "midi" else self.owner
        if kind == "master_volume":
            return float(controller._master_volume)
        if kind == "reverb_level":
            return float(controller._reverb_level)
        if kind == "reverb_liveness":
            return float(controller._reverb_liveness)
        if kind == "reverb_damping":
            return float(controller._reverb_damping)
        if kind == "tuning_reference":
            return float(controller._tuning_reference)
        if kind == "rhythm_tempo":
            return float(self.owner.rhythmTempo)
        if kind == "rhythm_fill_density":
            return float(self.owner.rhythmFillDensityIndex)
        if kind == "bass_voicing":
            return float(self.owner._bass_voicing_shift)
        if kind == "bass_riff_selector":
            return float(self.owner.bassRiffSelector)
        if kind == "chord_type":
            return float(self.owner.chordIndexForRow(int(target["row"])))
        return None

    def restore_control_values(
        self,
        captured: list[tuple[dict[str, Any], float]],
    ) -> None:
        for target, value in captured:
            screen = str(target["screen"])
            kind = str(target["kind"])
            if kind == "synth_control":
                runtime = (
                    self._runtime(int(target["row"]))
                    if screen == "midi"
                    else self.owner._runtime(str(target["role"]))
                )
                runtime.set_instrument_control(
                    str(target["instrument"]),
                    str(target["control"]),
                    value,
                )
            elif kind == "volume":
                if screen == "midi":
                    self.volumes[int(target["row"])] = value
                else:
                    setattr(
                        self.owner,
                        {
                            "chord": "_chord_volume",
                            "strum": "_strum_volume",
                            "bass": "_bass_volume",
                            "percussion": "_percussion_volume",
                        }[str(target["role"])],
                        value,
                    )
            else:
                controller = self if screen == "midi" else self.owner
                if kind == "reverb_level":
                    controller._reverb_level = value
                elif kind == "master_volume":
                    controller._master_volume = value
                elif kind == "reverb_liveness":
                    controller._reverb_liveness = value
                elif kind == "reverb_damping":
                    controller._reverb_damping = value
                elif kind == "tuning_reference":
                    controller._tuning_reference = value
                elif kind == "rhythm_tempo":
                    rhythm = self.owner._rhythm
                    rhythm.tempo_by_rhythm[rhythm.selected_index] = value
                    if self.owner._rhythm_running:
                        self.owner._running_tempo = value
                elif kind == "rhythm_fill_density":
                    rhythm = self.owner._rhythm
                    rhythm.fill_density_index_by_rhythm[rhythm.selected_index] = int(round(value))
                elif kind == "bass_voicing":
                    self.owner._bass_voicing_shift = int(round(value))
                elif kind == "bass_riff_selector":
                    self.owner._choose_bass_riff(
                        fallback_selector=int(round(value)),
                    )
                elif kind == "chord_type":
                    self.owner._row_chord_indexes[int(target["row"])] = int(
                        round(value)
                    )

    def replace_control_bindings(self, screen: str, data: Any) -> None:
        service = self._binding_service()
        entries = service.normalize_entries(
            screen,
            data,
            self._normalize_control_target,
        )
        service.replace_screen(screen, entries)
        self._sync_blue_timer()
        self._sync_preset_feedback_timer()
        self._bump_binding_state()

    def remember_active_bindings_as_preset(self, screen: str) -> None:
        with self._midi_control_lock:
            self._midi_control_state.remember_active_bindings_as_preset(screen)

    def _emit_state(self) -> None:
        self._state_version += 1
        self.stateChanged.emit()

    @staticmethod
    def _valid_row(row: int) -> bool:
        return 0 <= int(row) < MIDI_ROW_COUNT

    def _runtime(self, row: int) -> SynthState:
        return self.rows[int(row)]

    @Slot(int, result=int)
    def synthIndex(self, row: int) -> int:
        if not self._valid_row(row):
            return 0
        return self._runtime(row).selected_index

    @Slot(int, result=int)
    def channel(self, row: int) -> int:
        if not self._valid_row(row):
            return 1
        return self.channels[int(row)]

    @Slot(int, result=float)
    def volume(self, row: int) -> float:
        if not self._valid_row(row):
            return 0.5
        return self.volumes[int(row)]

    @Slot(int, result="QVariantList")
    def commonControls(self, row: int) -> list[dict[str, Any]]:
        if int(row) == -1:
            return self._binding_service().presentation().qml_model()
        if not self._valid_row(row):
            return []
        return self._runtime(row).control_model("common")

    @Slot(int, result="QVariantList")
    def extraControls(self, row: int) -> list[dict[str, Any]]:
        if not self._valid_row(row):
            return []
        return self._runtime(row).control_model("extra")

    def _is_drum(self, row: int) -> bool:
        # The lower purple row is the dedicated percussion input.  Its role
        # does not silently change when an old MIDI preset contains a former
        # pitched-program selection at this position.
        return int(row) == MIDI_ROW_COUNT - 1

    def _configure_row(self, row: int) -> None:
        if self._is_drum(row):
            self.engine.silence_row(row)
            return
        runtime = self._runtime(row)
        payload = runtime.transport_payload()
        arguments = list(payload["params"])
        params = {
            str(arguments[index]): float(arguments[index + 1])
            for index in range(0, len(arguments), 2)
        }
        self.engine.configure_row(
            row,
            str(runtime.selected_definition.key),
            params,
            self.volumes[row],
        )
        self._apply_reverb()

    @Slot(int, int)
    def setSynthIndex(self, row: int, synth_index: int) -> None:
        if not self._valid_row(row):
            return
        if self._runtime(row).select(synth_index):
            self._configure_row(int(row))
            self._emit_state()

    @Slot(int)
    def toggleSynthKind(self, row: int) -> None:
        if not self._valid_row(row) or self._is_drum(row):
            return
        runtime = self._runtime(row)
        requested = "sample" if runtime.selected_kind == "synth" else "synth"
        if runtime.select_kind(requested):
            self._configure_row(int(row))
            self._emit_state()

    @Slot(int, int)
    def setSynthBrowserIndex(self, row: int, browser_index: int) -> None:
        if not self._valid_row(row):
            return
        if self._is_drum(row):
            self.setDrumKitIndex(browser_index)
            return
        if self._runtime(row).select_browser_index(browser_index):
            self._configure_row(int(row))
            self._emit_state()

    @Slot(int, int)
    def selectSampleChoice(self, row: int, synth_index: int) -> None:
        self.setSynthIndex(row, synth_index)

    @Slot(int, str, float)
    def setControl(self, row: int, key: str, value: float) -> None:
        self._set_control(row, key, value, emit_state=True)

    @Slot(int, str, float)
    def editControl(self, row: int, key: str, value: float) -> None:
        self._set_control(row, key, value, emit_state=False)

    def _set_control(
        self,
        row: int,
        key: str,
        value: float,
        *,
        emit_state: bool,
    ) -> None:
        if not self._valid_row(row):
            return
        runtime = self._runtime(row)
        if self.manual_change_blocked(
            {
                "screen": "midi",
                "kind": "synth_control",
                "row": int(row),
                "instrument": str(runtime.selected_definition.key),
                "control": str(key),
            }
        ):
            return
        if runtime.set_control(key, value):
            self._configure_row(int(row))
            if emit_state:
                self._emit_state()

    @Slot(int, float)
    def setVolume(self, row: int, value: float) -> None:
        if not self._valid_row(row):
            return
        row = int(row)
        if self.manual_change_blocked({"screen": "midi", "kind": "volume", "row": row}):
            return
        value = max(0.0, min(1.0, float(value)))
        if math.isclose(value, self.volumes[row], abs_tol=1e-4):
            return
        self.volumes[row] = value
        if not self._is_drum(row):
            key = str(self._runtime(row).selected_definition.key)
            self.engine.set_row_volume(
                row,
                self.engine.pitched_row_level(key, value),
            )
        self._emit_state()

    @Slot(int)
    def cycleChannel(self, row: int) -> None:
        if not self._valid_row(row):
            return
        row = int(row)
        current = self.channels[row]
        self.channels[row] = 1 if current == 0 else (0 if current == 16 else current + 1)
        self._emit_state()

    @Slot()
    def cycleChordInputChannel(self) -> None:
        self.owner.resetExternalChordInput()
        current = self._chord_input_channel
        self._chord_input_channel = (
            1 if current == 0 else (0 if current == 16 else current + 1)
        )
        self._emit_state()

    def _preset_path(self, number: int) -> Path:
        return MIDI_PRESET_DIR / f"m{number}.json"

    def _ensure_preset_storage(self) -> None:
        MIDI_PRESET_DIR.mkdir(parents=True, exist_ok=True)
        for number in range(1, MIDI_PRESET_COUNT + 1):
            target = self._preset_path(number)
            factory = MIDI_FACTORY_DIR / f"m{number}.json"
            if not factory.exists():
                continue
            factory_data = json.loads(factory.read_text(encoding="utf-8"))
            if not target.exists():
                _write_json_atomic(target, factory_data)
                continue
            try:
                stored_data = json.loads(target.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(stored_data, dict):
                continue
            migrated = _migrated_factory_channel_defaults(
                stored_data,
                factory_data,
            )
            if migrated is not None:
                _write_json_atomic(target, migrated)
        last = MIDI_PRESET_DIR / MIDI_LAST_PRESET_FILE
        if not last.exists():
            _write_json_atomic(last, {"preset": 1})

    def _load_startup_preset(self) -> None:
        number = 1
        try:
            data = json.loads((MIDI_PRESET_DIR / MIDI_LAST_PRESET_FILE).read_text(encoding="utf-8"))
            number = max(
                1,
                min(MIDI_PRESET_COUNT, int(data.get("preset", 1))),
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            number = 1
        self._load_preset(number, emit=False)

    def _snapshot(self) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        for index, runtime in enumerate(self.rows):
            rows.append(
                {
                    "selected": str(runtime.selected_definition.key),
                    "channel": int(self.channels[index]),
                    "volume": float(self.volumes[index]),
                    "parameters": runtime.sparse_overrides(),
                }
            )
        return {
            "version": 1,
            "drum_kit": DRUM_KITS[self._drum_kit_index].kit_id,
            "rows": rows,
            "tuning": {
                "mode": app_core.TUNING_MODE_NAMES[self._tuning_mode_index],
                "reference_hz": int(round(self._tuning_reference)),
            },
            "effects": {
                "reverb_level": self._reverb_level,
                "reverb_liveness": self._reverb_liveness,
                "reverb_damping": self._reverb_damping,
                "reverb_drums": self._reverb_drums,
            },
            "midi_control_bindings": self.control_bindings_snapshot("midi"),
        }

    def _apply_data(self, data: dict[str, Any]) -> None:
        rows = data.get("rows", [])
        key_to_index = {
            str(definition.key): index for index, definition in enumerate(self.definitions)
        }
        if not isinstance(rows, list) or len(rows) != MIDI_ROW_COUNT:
            raise ValueError("MIDI preset must contain six rows")

        selected_drum_kit = str(data.get("drum_kit", DEFAULT_DRUM_KIT_ID))
        self._drum_kit_index = next(
            (index for index, kit in enumerate(DRUM_KITS) if kit.kit_id == selected_drum_kit),
            0,
        )
        self.engine.drum_kit_id = DRUM_KITS[self._drum_kit_index].kit_id

        for index, row_data in enumerate(rows):
            if not isinstance(row_data, dict):
                raise ValueError("invalid MIDI preset row")
            selected = str(row_data.get("selected", self.definitions[0].key))
            selected_index = key_to_index.get(selected, 0)
            runtime = SynthState(self.definitions, selected_index)
            runtime.load_preset(
                {
                    "selected": selected,
                    "parameters": row_data.get("parameters", {}),
                }
            )
            self.rows[index] = runtime
            channel = int(row_data.get("channel", DEFAULT_MIDI_CHANNELS[index]))
            self.channels[index] = max(0, min(16, channel))
            self.volumes[index] = max(
                0.0,
                min(1.0, float(row_data.get("volume", 0.5))),
            )

        tuning = data.get("tuning", {})
        if isinstance(tuning, dict):
            mode = str(tuning.get("mode", "EQ"))
            if mode in app_core.TUNING_MODE_NAMES:
                self._tuning_mode_index = app_core.TUNING_MODE_NAMES.index(mode)
            self._tuning_reference = float(
                max(
                    415,
                    min(466, int(tuning.get("reference_hz", 440))),
                )
            )

        effects = data.get("effects", {})
        if isinstance(effects, dict):
            self._reverb_level = max(
                0.0,
                min(
                    MIDI_REVERB_MAX,
                    float(effects.get("reverb_level", 0.0)),
                ),
            )
            self._reverb_liveness = max(
                0.0,
                min(
                    1.0,
                    float(effects.get("reverb_liveness", 0.5)),
                ),
            )
            self._reverb_damping = max(
                0.0,
                min(
                    1.0,
                    float(effects.get("reverb_damping", 0.5)),
                ),
            )
            self._reverb_drums = bool(effects.get("reverb_drums", False))
        self.replace_control_bindings(
            "midi",
            data.get("midi_control_bindings", []),
        )

    def _load_preset(self, number: int, *, emit: bool) -> None:
        path = self._preset_path(number)
        data = json.loads(path.read_text(encoding="utf-8"))
        protected = (
            self.capture_bound_control_values(
                "midi",
                incoming_bindings=data.get("midi_control_bindings", []),
            )
            if emit
            else []
        )
        self.engine.all_notes_off()
        self._apply_data(data)
        self.restore_control_values(protected)
        self._selected_preset = int(number)
        self._preset_reference = json.loads(json.dumps(data))
        _write_json_atomic(
            MIDI_PRESET_DIR / MIDI_LAST_PRESET_FILE,
            {"preset": self._selected_preset},
        )
        if emit:
            self._apply_all_to_engine()
            self._emit_state()
            self.tuningChanged.emit()
            self._emit_reverb()
            self.drumKitChanged.emit()
            self.presetChanged.emit()

    @Slot(int)
    def selectPreset(self, number: int) -> None:
        if 1 <= int(number) <= MIDI_PRESET_COUNT:
            self._load_preset(int(number), emit=True)

    @Slot()
    def storeSelectedPreset(self) -> None:
        snapshot = self._snapshot()
        _write_json_atomic(
            self._preset_path(self._selected_preset),
            snapshot,
        )
        self._preset_reference = json.loads(json.dumps(snapshot))
        self.remember_active_bindings_as_preset("midi")
        self._refresh_preset_binding_locations()
        self.presetStored.emit(self._selected_preset)

    @Slot(int)
    def resetRow(self, row: int) -> None:
        if not self._valid_row(row):
            return
        row = int(row)
        protected = self.capture_bound_control_values("midi", row=row)
        rows = self._preset_reference.get("rows", [])
        if not isinstance(rows, list) or len(rows) != MIDI_ROW_COUNT:
            return
        stored = rows[row]
        if not isinstance(stored, dict):
            return
        key_to_index = {
            str(definition.key): index for index, definition in enumerate(self.definitions)
        }
        selected = str(stored.get("selected", self.definitions[0].key))
        runtime = SynthState(
            self.definitions,
            key_to_index.get(selected, 0),
        )
        runtime.load_preset(
            {
                "selected": selected,
                "parameters": stored.get("parameters", {}),
            }
        )
        self.rows[row] = runtime
        self.channels[row] = max(
            0,
            min(16, int(stored.get("channel", DEFAULT_MIDI_CHANNELS[row]))),
        )
        self.volumes[row] = max(
            0.0,
            min(1.0, float(stored.get("volume", 0.5))),
        )
        if self._is_drum(row):
            selected_kit = str(
                self._preset_reference.get("drum_kit", DEFAULT_DRUM_KIT_ID)
            )
            self._drum_kit_index = next(
                (
                    index
                    for index, kit in enumerate(DRUM_KITS)
                    if kit.kit_id == selected_kit
                ),
                0,
            )
            self.engine.drum_kit_id = DRUM_KITS[self._drum_kit_index].kit_id
            self.drumKitChanged.emit()
        self.restore_control_values(protected)
        self._configure_row(row)
        self._emit_state()

    @Slot(bool)
    def setTuningCoupled(self, coupled: bool) -> None:
        coupled = bool(coupled)
        if coupled == self._tuning_coupled:
            return
        self._tuning_coupled = coupled
        self.tuningChanged.emit()

    def syncFromOmni(self) -> None:
        mode_index = int(self.owner.selectedTuningModeIndex)
        reference = float(self.owner.tuningReference)
        reference_blocked = self.manual_change_blocked(
            {"screen": "midi", "kind": "tuning_reference"}
        )
        changed = mode_index != self._tuning_mode_index or (
            not reference_blocked
            and not math.isclose(
                reference,
                self._tuning_reference,
                abs_tol=1e-9,
            )
        )
        self._tuning_mode_index = mode_index
        if not reference_blocked:
            self._tuning_reference = reference
        if changed:
            self.tuningChanged.emit()

    @Slot(int)
    def setTuningModeIndex(self, index: int) -> None:
        index = max(
            0,
            min(len(app_core.TUNING_MODE_NAMES) - 1, int(index)),
        )
        if index != self._tuning_mode_index:
            self._tuning_mode_index = index
            self.tuningChanged.emit()

    @Slot(int)
    def setTuningReference(self, value: int) -> None:
        if self.manual_change_blocked({"screen": "midi", "kind": "tuning_reference"}):
            return
        value = max(415, min(466, int(value)))
        if math.isclose(
            self._tuning_reference,
            float(value),
            abs_tol=1e-9,
        ):
            self.tuningChanged.emit()
            return
        self._tuning_reference = float(value)
        self.tuningChanged.emit()

    @Slot(int)
    def beginPitchBend(self, direction: int) -> None:
        self.owner.beginPitchBend(direction)

    @Slot()
    def endPitchBend(self) -> None:
        self.owner.endPitchBend()

    def _chord_context(self) -> tuple[int, set[int]]:
        chord = self.owner.performance_snapshot().chord
        return chord.root_semitone, set(chord.pitch_classes)

    def _tune(self, note: int | float, root: int) -> float:
        owner_tuning = self.owner.performance_snapshot().tuning
        tuning = (
            owner_tuning
            if self._tuning_coupled
            else TuningSnapshot(
                mode=app_core.TUNING_MODE_NAMES[self._tuning_mode_index],
                reference_hz=self._tuning_reference,
                intonation_tables=owner_tuning.intonation_tables,
            )
        )
        return tune_note(tuning, note, root)

    def process_midi_note(
        self,
        channel: int,
        note: int,
        velocity: int,
        is_on: bool,
    ) -> None:
        if self._chord_input_channel in (0, int(channel)):
            self.owner.processExternalChordInput(
                int(channel),
                int(note),
                bool(is_on),
            )

        root: int | None = None
        for row in range(MIDI_ROW_COUNT):
            configured = self.channels[row]
            if configured not in (0, int(channel)):
                continue
            if self._is_drum(row):
                if is_on:
                    self.engine.drum_hit(
                        note,
                        velocity,
                        self.volumes[row],
                    )
                continue
            if is_on:
                if root is None:
                    root, _ = self._chord_context()
                self.engine.note_on(
                    row,
                    int(channel),
                    int(note),
                    self._tune(note, root),
                    int(velocity),
                )
            else:
                self.engine.note_off(
                    row,
                    int(channel),
                    int(note),
                )

    def _preview_notes(self) -> tuple[list[int], int]:
        root, pitch_classes = self._chord_context()
        notes = [
            note
            for note in range(MIDI_PREVIEW_LOW, MIDI_PREVIEW_HIGH + 1)
            if note % 12 in pitch_classes
        ]
        return notes, root

    @staticmethod
    def _index(normalized_y: float, count: int) -> int:
        y = max(0.0, min(1.0, float(normalized_y)))
        return round((1.0 - y) * (count - 1))

    def _preview_at(self, row: int, normalized_y: float) -> int | None:
        if self._is_drum(row):
            index = self._index(
                normalized_y,
                len(PREVIEW_DRUM_NOTES),
            )
            self.engine.drum_hit(
                PREVIEW_DRUM_NOTES[index],
                105,
                self.volumes[row],
            )
            return index
        notes, root = self._preview_notes()
        if not notes:
            return None
        index = self._index(normalized_y, len(notes))
        self.engine.preview_note(
            row,
            self._tune(notes[index], root),
        )
        return index

    @Slot(int, float)
    def previewStart(self, row: int, normalized_y: float) -> None:
        if not self._valid_row(row):
            return
        self._preview_row = int(row)
        self._preview_last_index = self._preview_at(
            int(row),
            normalized_y,
        )

    @Slot(int, float)
    def previewMove(self, row: int, normalized_y: float) -> None:
        if not self._valid_row(row) or int(row) != self._preview_row:
            return
        row = int(row)
        if self._is_drum(row):
            new = self._index(
                normalized_y,
                len(PREVIEW_DRUM_NOTES),
            )
        else:
            notes, _ = self._preview_notes()
            if not notes:
                return
            new = self._index(normalized_y, len(notes))
        old = self._preview_last_index
        if old is None:
            self._preview_last_index = self._preview_at(
                row,
                normalized_y,
            )
            return
        if new == old:
            return
        direction = 1 if new > old else -1
        for index in range(old + direction, new + direction, direction):
            if self._is_drum(row):
                self.engine.drum_hit(
                    PREVIEW_DRUM_NOTES[index],
                    105,
                    self.volumes[row],
                )
            else:
                notes, root = self._preview_notes()
                self.engine.preview_note(
                    row,
                    self._tune(notes[index], root),
                )
        self._preview_last_index = new

    @Slot()
    def previewEnd(self) -> None:
        self._preview_row = -1
        self._preview_last_index = None

    def _apply_reverb(self) -> None:
        self.engine.set_reverb(
            self._reverb_level,
            self._reverb_liveness,
            self._reverb_damping,
            self._reverb_drums,
        )

    def _emit_reverb(self) -> None:
        self.reverbLevelChanged.emit()
        self.reverbLivenessChanged.emit()
        self.reverbDampingChanged.emit()
        self.reverbDrumsIncludedChanged.emit()

    @Slot(float)
    def setReverbLevel(self, value: float) -> None:
        if self.manual_change_blocked({"screen": "midi", "kind": "reverb_level"}):
            return
        value = max(0.0, min(MIDI_REVERB_MAX, float(value)))
        if math.isclose(value, self._reverb_level, abs_tol=1e-4):
            return
        self._reverb_level = value
        self.reverbLevelChanged.emit()
        self._apply_reverb()

    @Slot(float)
    def setReverbLiveness(self, value: float) -> None:
        if self.manual_change_blocked({"screen": "midi", "kind": "reverb_liveness"}):
            return
        value = max(0.0, min(1.0, float(value)))
        if math.isclose(value, self._reverb_liveness, abs_tol=1e-4):
            return
        self._reverb_liveness = value
        self.reverbLivenessChanged.emit()
        self._apply_reverb()

    @Slot(float)
    def setReverbRoom(self, value: float) -> None:
        self.setReverbLiveness(value)

    @Slot(float)
    def setReverbDamping(self, value: float) -> None:
        if self.manual_change_blocked({"screen": "midi", "kind": "reverb_damping"}):
            return
        value = max(0.0, min(1.0, float(value)))
        if math.isclose(value, self._reverb_damping, abs_tol=1e-4):
            return
        self._reverb_damping = value
        self.reverbDampingChanged.emit()
        self._apply_reverb()

    @Slot()
    def toggleReverbDrums(self) -> None:
        self._reverb_drums = not self._reverb_drums
        self.reverbDrumsIncludedChanged.emit()
        self._apply_reverb()

    def _effective_master_volume(self) -> float:
        return 0.0 if self._master_muted else self._master_volume

    @Slot(float)
    def setMasterVolume(self, value: float) -> None:
        if self.manual_change_blocked({"screen": "midi", "kind": "master_volume"}):
            return
        value = max(0.0, min(1.0, float(value)))
        if math.isclose(value, self._master_volume, abs_tol=1e-4):
            return
        self._master_volume = value
        self.masterVolumeChanged.emit()
        self.engine.set_master_volume(self._effective_master_volume())
        self._emit_state()

    @Slot()
    def toggleMasterMuted(self) -> None:
        self._master_muted = not self._master_muted
        self.masterMutedChanged.emit()
        self.engine.set_master_volume(self._effective_master_volume())
        self._emit_state()

    def _apply_all_to_engine(self) -> None:
        for row in range(MIDI_ROW_COUNT):
            self._configure_row(row)
        self._apply_reverb()
        self.engine.set_master_volume(self._effective_master_volume())

    def send_initial_state(self) -> None:
        self._apply_all_to_engine()

    def rebuild_after_panic(self) -> None:
        self.engine.rebuild()
        self._apply_all_to_engine()
