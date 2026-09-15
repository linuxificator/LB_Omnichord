from __future__ import annotations

from collections.abc import Mapping
import json
import math
from pathlib import Path
import threading
import time
from typing import Any
import uuid

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_message_builder import OscMessageBuilder
from pythonosc.osc_server import ThreadingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient

from frontend_config import FrontendConfig
from engine_protocol import NoteOff, NoteOn, PROTOCOL_VERSION, VoiceSet
from musical_sequence_plan import (
    LanePlan,
    compile_bass_lane,
    compile_chord_lane,
    compile_drum_lane,
)
from supercollider_config import (
    SuperColliderRuntimeConfig,
    load_supercollider_config,
)
from supercollider_programs import load_legacy_program_map
from sc_drum_kits import DEFAULT_DRUM_KIT_ID, DRUM_KITS, kit_by_id, midi_role, resolve_hit
from sc_music_catalog import load_sc_music_catalog


class SuperColliderUnavailable(RuntimeError):
    """The separately supervised language/audio service is not ready."""


TRANSACTION_ACK_TIMEOUT_SECONDS = 0.5
TRANSACTION_DELIVERY_ATTEMPTS = 3


class SuperColliderClient:
    """Typed OSC adapter to a separately supervised headless SC service.

    The public ``send_message`` method preserves the stable UI-facing semantic
    addresses. New code should use the typed methods directly.
    """

    def __init__(
        self,
        addresses: dict[str, str],
        *,
        frontend_config: FrontendConfig,
        runtime_config_path: Path,
        asset_root: Path | None = None,
    ) -> None:
        self.frontend_config = frontend_config
        self.runtime_config: SuperColliderRuntimeConfig = (
            load_supercollider_config(runtime_config_path)
        )
        self.addr = dict(addresses)
        self.session = f"qt-{uuid.uuid4().hex}"
        self.engine_session = ""
        self.catalog_digest = ""
        self._message_id = 0
        self._message_lock = threading.Lock()
        self._ready = threading.Event()
        self._ack_condition = threading.Condition()
        self._acknowledgements: dict[int, tuple[str, int, float, str]] = {}
        self._closed = False

        dispatcher = Dispatcher()
        dispatcher.map("/omni/v1/ready", self._accept_ready)
        dispatcher.map("/omni/v1/ack", self._accept_ack)
        dispatcher.map("/omni/v1/program/status", self._accept_program_status)
        language = self.runtime_config.language
        # Program-ready callbacks can synchronously publish a replacement lane
        # and wait for its acknowledgement. They therefore need an independent
        # reply handler while that callback is active.
        self._reply_server = ThreadingOSCUDPServer((language.host, 0), dispatcher)
        self.reply_port = int(self._reply_server.server_address[1])
        self._reply_thread = threading.Thread(
            target=self._reply_server.serve_forever,
            name="supercollider-osc-replies",
            daemon=True,
        )
        self._reply_thread.start()
        self._osc = SimpleUDPClient(language.host, language.port)

        root = Path(asset_root) if asset_root is not None else runtime_config_path.parent.parent
        self._legacy_program_map = load_legacy_program_map(
            root / "instruments" / "supercollider-legacy-map.json"
        )
        self._selected_program = {
            "chord": self._resolve_program(frontend_config.program_defaults.chord),
            "strum": self._resolve_program(frontend_config.program_defaults.strum),
            "bass": self._resolve_program(frontend_config.program_defaults.bass),
        }
        self._program_revision = {"chord": 1, "strum": 1, "bass": 1}
        self._configured_roles: set[str] = set()
        self._program_counter = 1
        self._program_params: dict[str, dict[str, float]] = {
            "chord": {},
            "strum": {},
            "bass": {},
        }
        self._pending_programs: dict[
            tuple[str, int], tuple[str, dict[str, float]]
        ] = {}
        self._program_errors: dict[str, str] = {}
        self._sample_state_lock = threading.Lock()
        self._sample_program_status: dict[tuple[str, int], str] = {}
        self._deferred_sample_notes: dict[str, NoteOn] = {}
        self._drum_program_status: dict[str, str] = {}
        self._requested_drum_programs: set[str] = set()
        self._deferred_drum_hits: list[tuple[str, str, str, int, float, int]] = []
        self._role_levels = {
            "chord": 0.5,
            "strum": 0.5,
            "bass": 0.5,
            "drums": 0.5,
        }
        self._omni_master = 1.0
        self._manual_active_id: str | None = None
        self._manual_handles: list[str] = []
        self._strum_ordinal = 0
        self._drum_ordinal = 0
        self.chord_notes: list[float] = []
        self.bass_notes: list[float] = []
        self.bass_riff: dict[str, Any] | None = None
        self.rhythm_config: dict[str, Any] | None = None
        self.rhythm_running = False
        self.rhythm_chord_enabled = False
        self.bass_running = True
        self._lane_generations = {"drums": 0, "bass": 0, "chords": 0}
        self._transaction_id = 0
        self._drum_catalog = load_sc_music_catalog(
            root
            / "music"
            / "sc_expansion"
            / "sc_kit_grooves_v1.json"
        )
        self._drum_kit = DEFAULT_DRUM_KIT_ID

        try:
            self._await_ready()
        except BaseException:
            self._close_reply_server()
            raise

    def _accept_ready(
        self,
        _address: str,
        engine_session: str,
        protocol_version: int,
        catalog_digest: str,
        status: str,
    ) -> None:
        if int(protocol_version) != PROTOCOL_VERSION:
            return
        if str(status) != "ready":
            return
        self.engine_session = str(engine_session)
        self.catalog_digest = str(catalog_digest)
        self._ready.set()

    def _accept_ack(self, _address: str, *arguments: Any) -> None:
        if len(arguments) != 6 or str(arguments[0]) != self.session:
            return
        transaction_id = int(arguments[1])
        acknowledgement = (
            str(arguments[2]),
            int(arguments[3]),
            float(arguments[4]),
            str(arguments[5]),
        )
        with self._ack_condition:
            self._acknowledgements[transaction_id] = acknowledgement
            self._ack_condition.notify_all()

    def _accept_program_status(self, _address: str, *arguments: Any) -> None:
        if len(arguments) != 5 or str(arguments[0]) != self.session:
            return
        program_id = str(arguments[1])
        revision = int(arguments[2])
        status = str(arguments[3])
        detail = str(arguments[4])
        program_key = (program_id, revision)
        deferred: list[NoteOn] = []
        deferred_drums: list[tuple[str, str, str, int, float, int]] = []
        with self._sample_state_lock:
            self._sample_program_status[program_key] = status
            if status == "ready":
                for handle, event in tuple(self._deferred_sample_notes.items()):
                    if (event.program_id, event.program_revision) == program_key:
                        pending_event = self._deferred_sample_notes.pop(handle, None)
                        if pending_event is not None:
                            deferred.append(pending_event)
            elif status == "error":
                for handle, event in tuple(self._deferred_sample_notes.items()):
                    if (event.program_id, event.program_revision) == program_key:
                        self._deferred_sample_notes.pop(handle, None)
            if any(program_id in kit.sample_programs for kit in DRUM_KITS):
                self._drum_program_status[program_id] = status
                if status == "ready":
                    deferred_drums = [
                        item for item in self._deferred_drum_hits if item[1] == program_id
                    ]
                    self._deferred_drum_hits = [
                        item for item in self._deferred_drum_hits if item[1] != program_id
                    ]
                elif status == "error":
                    self._deferred_drum_hits = [
                        item for item in self._deferred_drum_hits if item[1] != program_id
                    ]
        for event in deferred:
            self._send_note_on(event)
        for item in deferred_drums:
            self._send_drum_hit(*item)
        if status == "ready" and self.rhythm_config is not None:
            selected_kit = kit_by_id(
                str(self.rhythm_config.get("drum_kit", self._drum_kit))
            )
            if program_id in selected_kit.sample_programs:
                self._publish_drum_lane()
        pending = self._pending_programs.get((program_id, revision))
        if pending is None:
            return
        role, parameters = pending
        if status == "error":
            self._program_errors[role] = detail
            self._configured_roles.discard(role)
            self._pending_programs.pop((program_id, revision), None)
            self._release_program(program_id, revision)
            return
        if status != "ready":
            return
        self._pending_programs.pop((program_id, revision), None)
        self._activate_program(role, program_id, revision, parameters)

    def _release_program(self, program_id: str, revision: int) -> None:
        program_key = (str(program_id), int(revision))
        with self._sample_state_lock:
            self._sample_program_status.pop(program_key, None)
            for handle, event in tuple(self._deferred_sample_notes.items()):
                if (event.program_id, event.program_revision) == program_key:
                    self._deferred_sample_notes.pop(handle, None)
        self._send_raw(
            "/omni/v1/program/release",
            [
                self.session,
                self._next_message_id(),
                str(program_id),
                int(revision),
            ],
        )

    def release_program(self, program_id: str, revision: int) -> None:
        """Release a superseded revision after its part has released voices."""

        self._release_program(program_id, revision)

    def _await_ready(self) -> None:
        deadline = time.monotonic() + self.runtime_config.language.startup_timeout_seconds
        while not self._ready.is_set() and time.monotonic() < deadline:
            self._send_raw(
                "/omni/v1/hello",
                [self.session, PROTOCOL_VERSION, self.reply_port],
            )
            self._ready.wait(0.1)
        if not self._ready.is_set():
            language = self.runtime_config.language
            raise SuperColliderUnavailable(
                "SuperCollider service did not become ready at "
                f"{language.host}:{language.port} within "
                f"{language.startup_timeout_seconds:g} seconds"
            )

    def _send_raw(self, address: str, arguments: list[Any]) -> None:
        builder = OscMessageBuilder(address=address)
        for argument in arguments:
            builder.add_arg(argument)
        message = builder.build()
        size = len(message.dgram)
        ceiling = self.runtime_config.language.message_payload_bytes
        if size > ceiling:
            raise ValueError(
                f"OSC message {address} is {size} bytes; configured ceiling is {ceiling}"
            )
        self._osc.send(message)

    def _next_message_id(self) -> int:
        with self._message_lock:
            self._message_id += 1
            return self._message_id

    def _next_transaction_id(self) -> int:
        with self._message_lock:
            self._transaction_id += 1
            return self._transaction_id

    def allocate_program_revision(self) -> int:
        """Return a session-wide revision, unique across every musical part."""

        with self._message_lock:
            self._program_counter += 1
            return self._program_counter

    @staticmethod
    def _transaction_records(
        plan: LanePlan,
        transaction_id: int,
    ) -> list[tuple[str, list[Any]]]:
        records: list[tuple[str, list[Any]]] = []
        packet_index = 0
        for definition in plan.definitions:
            records.append(
                (
                    "/omni/v1/tx/def",
                    [
                        transaction_id,
                        packet_index,
                        definition.definition_id,
                        definition.revision,
                        definition.kind,
                        definition.period_ticks,
                        len(definition.events),
                    ],
                )
            )
            packet_index += 1
            for event in definition.events:
                records.append(
                    (
                        "/omni/v1/tx/event",
                        [
                            transaction_id,
                            packet_index,
                            definition.definition_id,
                            event.tick,
                            event.ordinal,
                            event.kind,
                            *event.atoms,
                        ],
                    )
                )
                packet_index += 1
        return records

    def publish_lane(self, plan: LanePlan) -> tuple[str, int, float, str]:
        """Reliably stage and atomically publish one immutable lane revision."""

        transaction_id = self._next_transaction_id()
        records = self._transaction_records(plan, transaction_id)
        begin = (
            "/omni/v1/tx/begin",
            [
                transaction_id,
                plan.lane,
                plan.generation,
                len(records),
                "replace",
                plan.alignment_ticks,
            ],
        )
        messages = [begin, *records, ("/omni/v1/tx/commit", [transaction_id])]
        for _attempt in range(TRANSACTION_DELIVERY_ATTEMPTS):
            for address, arguments in messages:
                self._send_raw(address, [self.session, *arguments])
            deadline = time.monotonic() + TRANSACTION_ACK_TIMEOUT_SECONDS
            with self._ack_condition:
                while transaction_id not in self._acknowledgements:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    self._ack_condition.wait(remaining)
                acknowledgement = self._acknowledgements.get(transaction_id)
            if acknowledgement is None:
                continue
            if acknowledgement[0] == "received" and acknowledgement[3] == "incomplete":
                with self._ack_condition:
                    self._acknowledgements.pop(transaction_id, None)
                continue
            if acknowledgement[0] == "rejected":
                with self._ack_condition:
                    self._acknowledgements.pop(transaction_id, None)
                raise SuperColliderUnavailable(
                    f"SuperCollider rejected {plan.lane} generation "
                    f"{plan.generation}: {acknowledgement[3]}"
                )
            with self._ack_condition:
                self._acknowledgements.pop(transaction_id, None)
            return acknowledgement
        raise SuperColliderUnavailable(
            f"SuperCollider did not acknowledge {plan.lane} generation "
            f"{plan.generation} after {TRANSACTION_DELIVERY_ATTEMPTS} "
            "delivery attempts"
        )

    @staticmethod
    def note_to_frequency(note: float) -> float:
        value = float(note)
        if not math.isfinite(value):
            raise ValueError("note must be finite")
        return float(440.0 * (2.0 ** ((value - 69.0) / 12.0)))

    def _send_note_on(self, event: NoteOn) -> None:
        self._send_raw(
            "/omni/v1/note/on",
            [
                self.session,
                self._next_message_id(),
                event.owner,
                event.handle,
                event.program_id,
                event.program_revision,
                event.logical_key,
                event.frequency_hz,
                event.velocity,
                event.logical_bus,
            ],
        )

    def note_on(self, event: NoteOn) -> None:
        if event.program_id.startswith("sample."):
            with self._sample_state_lock:
                status = self._sample_program_status.get(
                    (event.program_id, event.program_revision)
                )
                if status != "ready":
                    self._deferred_sample_notes[event.handle] = event
                    return
        self._send_note_on(event)

    def note_off(self, event: NoteOff) -> None:
        with self._sample_state_lock:
            if self._deferred_sample_notes.pop(event.handle, None) is not None:
                return
        self._send_raw(
            "/omni/v1/note/off",
            [
                self.session,
                self._next_message_id(),
                event.owner,
                event.handle,
                event.release_velocity,
            ],
        )

    def voice_set(self, event: VoiceSet) -> None:
        self._send_raw(
            "/omni/v1/voice/set",
            [
                self.session,
                self._next_message_id(),
                event.handle,
                event.parameter,
                event.value,
            ],
        )

    def release_owner(self, owner: str) -> None:
        self._send_raw(
            "/omni/v1/owner/release",
            [self.session, self._next_message_id(), str(owner)],
        )

    def set_owner_sustain(self, owner: str, enabled: bool) -> None:
        self._send_raw(
            "/omni/v1/owner/sustain",
            [
                self.session,
                self._next_message_id(),
                str(owner),
                int(bool(enabled)),
            ],
        )

    def configure_part(
        self,
        owner: str,
        program_id: str,
        revision: int,
        logical_bus: int,
        parameters: Mapping[str, float],
    ) -> None:
        if program_id.startswith("sample."):
            with self._sample_state_lock:
                self._sample_program_status.setdefault(
                    (str(program_id), int(revision)), "loading"
                )
        self._send_raw(
            "/omni/v1/program/prepare",
            [
                self.session,
                self._next_message_id(),
                str(owner),
                str(program_id),
                int(revision),
                int(logical_bus),
            ],
        )
        for key, value in sorted(parameters.items()):
            self._send_raw(
                "/omni/v1/program/value",
                [
                    self.session,
                    self._next_message_id(),
                    str(owner),
                    str(program_id),
                    int(revision),
                    str(key),
                    float(value),
                ],
            )

    def set_logical_bus_level(self, logical_bus: int, level: float) -> None:
        self._send_raw(
            "/omni/v1/mixer/bus-level",
            [
                self.session,
                self._next_message_id(),
                int(logical_bus),
                max(0.0, float(level)),
            ],
        )

    def set_room(
        self,
        room_index: int,
        level: float,
        liveness: float,
        damping: float,
    ) -> None:
        self._send_raw(
            "/omni/v1/mixer/room",
            [
                self.session,
                self._next_message_id(),
                int(room_index),
                max(0.0, float(level)),
                max(0.0, min(1.0, float(liveness))),
                max(0.0, min(1.0, float(damping))),
            ],
        )

    def set_room_send(self, logical_bus: int, level: float) -> None:
        self._send_raw(
            "/omni/v1/mixer/room-send",
            [
                self.session,
                self._next_message_id(),
                int(logical_bus),
                max(0.0, float(level)),
            ],
        )

    def gesture_note(
        self,
        *,
        owner: str,
        handle: str,
        program_id: str,
        program_revision: int,
        logical_key: int,
        note: float,
        velocity: float,
        logical_bus: int,
        tail_seconds: float,
    ) -> None:
        self._send_raw(
            "/omni/v1/gesture/note",
            [
                self.session,
                self._next_message_id(),
                owner,
                handle,
                program_id,
                int(logical_key),
                self.note_to_frequency(note),
                max(0.0, min(1.0, float(velocity))),
                int(logical_bus),
                max(0.01, float(tail_seconds)),
                max(1, int(program_revision)),
            ],
        )

    def drum_hit(
        self,
        *,
        owner: str,
        logical_key: int,
        velocity: float,
        logical_bus: int,
        kit_id: str | None = None,
    ) -> None:
        role = midi_role(logical_key)
        program, pad, gain = resolve_hit(
            str(kit_id or self._drum_kit), role
        )
        hit = (
            str(owner),
            program,
            pad,
            int(logical_key),
            max(0.0, min(1.0, float(velocity) * gain)),
            int(logical_bus),
        )
        if not self._drum_program_ready(program):
            with self._sample_state_lock:
                self._deferred_drum_hits.append(hit)
                if len(self._deferred_drum_hits) > 256:
                    self._deferred_drum_hits.pop(0)
            self._ensure_drum_kit(str(kit_id or self._drum_kit), logical_bus)
            return
        self._send_drum_hit(*hit)

    def _send_drum_hit(
        self,
        owner: str,
        program: str,
        pad: str,
        logical_key: int,
        velocity: float,
        logical_bus: int,
    ) -> None:
        self._send_raw(
            "/omni/v1/drum/hit",
            [
                self.session,
                self._next_message_id(),
                owner,
                program,
                1,
                pad,
                logical_key,
                velocity,
                logical_bus,
            ],
        )

    def _drum_program_ready(self, program: str) -> bool:
        if not str(program).startswith("sample."):
            return True
        with self._sample_state_lock:
            return self._drum_program_status.get(str(program)) == "ready"

    def _ensure_drum_kit(self, kit_id: str, logical_bus: int) -> bool:
        programs = kit_by_id(kit_id).sample_programs
        if not programs:
            return True
        all_ready = True
        for program in programs:
            should_prepare = False
            with self._sample_state_lock:
                if self._drum_program_status.get(program) != "ready":
                    all_ready = False
                    if program not in self._requested_drum_programs:
                        self._requested_drum_programs.add(program)
                        self._drum_program_status[program] = "loading"
                        should_prepare = True
            if should_prepare:
                self.configure_part(
                    f"drum-kit/{kit_id}",
                    program,
                    1,
                    int(logical_bus),
                    {},
                )
        return all_ready

    def _role_bus(self, role: str) -> int:
        return int(dict(self.frontend_config.layout.role_buses)[role])

    def _resolve_program(self, program_id: str) -> str:
        value = str(program_id)
        if value.startswith(("sc.", "sample.")):
            return value
        return self._legacy_program_map.get(value, "sc.sclork.defaultB")

    def _publish_role_level(self, role: str) -> None:
        self.set_logical_bus_level(
            self._role_bus(role),
            self._role_levels[role] * self._omni_master,
        )

    def _set_role_volume(self, role: str, value: Any) -> None:
        self._role_levels[role] = max(0.0, float(value))
        self._publish_role_level(role)

    def _set_program(self, role: str, value: Any) -> None:
        if isinstance(value, dict):
            name = self._resolve_program(
                str(value.get("name", self._selected_program[role]))
            )
            raw = value.get("params", [])
            parameters: dict[str, float] = {}
            if isinstance(raw, list):
                for index in range(0, len(raw) - 1, 2):
                    parameters[str(raw[index])] = float(raw[index + 1])
        else:
            name = self._resolve_program(str(value))
            parameters = {}
        if (
            role in self._configured_roles
            and name == self._selected_program[role]
            and parameters == self._program_params[role]
        ):
            return
        revision = self.allocate_program_revision()
        logical_bus = self._role_bus("chord" if role == "chord" else role)
        owners = {
            "chord": ("omni/manual", "rhythm/chords"),
            "strum": ("omni/strum",),
            "bass": ("rhythm/bass",),
        }[role]
        sample_program = name.startswith("sample.")
        if sample_program:
            superseded = [
                key
                for key, (pending_role, _parameters) in self._pending_programs.items()
                if pending_role == role
            ]
            for pending_program, pending_revision in superseded:
                self._pending_programs.pop(
                    (pending_program, pending_revision), None
                )
                self._release_program(pending_program, pending_revision)
            self._pending_programs[(name, revision)] = (role, parameters)
        for owner in owners:
            self.configure_part(
                owner,
                name,
                revision,
                logical_bus,
                parameters,
            )
        self._configured_roles.add(role)
        if not sample_program:
            self._activate_program(role, name, revision, parameters)

    def _activate_program(
        self,
        role: str,
        program_id: str,
        revision: int,
        parameters: dict[str, float],
    ) -> None:
        previous_program = self._selected_program[role]
        previous_revision = self._program_revision[role]
        if previous_program.startswith("sample.") and (
            previous_program != program_id or previous_revision != revision
        ):
            self._release_program(previous_program, previous_revision)
        self._selected_program[role] = program_id
        self._program_revision[role] = revision
        self._program_params[role] = dict(parameters)
        self._program_errors.pop(role, None)
        if role == "bass":
            self._publish_bass_lane()
        elif role == "chord":
            self._publish_chord_lane()

    def _manual_event(self, text: str) -> None:
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise ValueError("manual chord payload must be an object")
        action = str(payload.get("action", ""))
        voice_id = str(payload.get("id", ""))
        if action == "stop_all":
            for handle in self._manual_handles:
                self.note_off(NoteOff("omni/manual", handle))
            self._manual_handles.clear()
            self._manual_active_id = None
            return
        if action == "stop":
            if voice_id != self._manual_active_id:
                return
            for handle in self._manual_handles:
                self.note_off(NoteOff("omni/manual", handle))
            self._manual_handles.clear()
            self._manual_active_id = None
            return
        notes = payload.get("notes", [])
        if not isinstance(notes, list):
            raise ValueError("manual chord notes must be a list")
        tuned = [float(note) for note in notes]
        if action == "update" and voice_id == self._manual_active_id and len(tuned) == len(self._manual_handles):
            for handle, note in zip(self._manual_handles, tuned, strict=True):
                self.voice_set(VoiceSet(handle, "frequency_hz", self.note_to_frequency(note)))
            return
        if action not in ("start", "update"):
            return
        for handle in self._manual_handles:
            self.note_off(NoteOff("omni/manual", handle))
        self._manual_handles.clear()
        self._manual_active_id = voice_id
        for ordinal, note in enumerate(tuned):
            handle = f"manual/{voice_id}/{ordinal}"
            self.note_on(
                NoteOn(
                    owner="omni/manual",
                    handle=handle,
                    program_id=self._selected_program["chord"],
                    program_revision=self._program_revision["chord"],
                    logical_key=max(0, min(127, int(round(note)))),
                    frequency_hz=self.note_to_frequency(note),
                    velocity=0.8,
                    logical_bus=self._role_bus("chord"),
                )
            )
            self._manual_handles.append(handle)

    def _set_chord_state(self, text: str) -> None:
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise ValueError("chord state payload must be an object")
        self.chord_notes = [float(note) for note in payload.get("notes", [])]
        self.bass_notes = [float(note) for note in payload.get("bass_notes", [])]
        if "bass_riff" in payload:
            bass_riff = payload.get("bass_riff")
            self.bass_riff = dict(bass_riff) if isinstance(bass_riff, Mapping) else None
        self.rhythm_chord_enabled = bool(payload.get("rhythm_chord_enabled", False))
        self._publish_chord_lane()
        self._publish_bass_lane()

    def _next_lane_generation(self, lane: str) -> int:
        self._lane_generations[lane] += 1
        return self._lane_generations[lane]

    def _publish_chord_lane(self) -> None:
        generation = self._next_lane_generation("chords")
        rhythm = self.frontend_config.rhythm
        self.publish_lane(
            compile_chord_lane(
                config=self.rhythm_config,
                enabled=self.rhythm_chord_enabled,
                chord_notes=self.chord_notes,
                max_chord_notes=rhythm.max_chord_notes,
                chord_gate_beats=rhythm.chord_gate_beats,
                program_id=self._selected_program["chord"],
                program_revision=self._program_revision["chord"],
                logical_bus=self._role_bus("chord"),
                generation=generation,
            )
        )

    def _publish_drum_lane(self) -> None:
        selected_kit = (
            str(self.rhythm_config.get("drum_kit", self._drum_kit))
            if self.rhythm_config else self._drum_kit
        )
        if not self._ensure_drum_kit(selected_kit, self._role_bus("drums")):
            return
        generation = self._next_lane_generation("drums")
        self.publish_lane(
            compile_drum_lane(
                config=self.rhythm_config,
                catalog=self._drum_catalog,
                kit=selected_kit,
                logical_bus=self._role_bus("drums"),
                generation=generation,
                program_resolver=resolve_hit,
            )
        )

    def _publish_bass_lane(self) -> None:
        generation = self._next_lane_generation("bass")
        config = (
            {**self.rhythm_config, "bass_riff": self.bass_riff}
            if self.rhythm_config is not None
            else None
        )
        self.publish_lane(
            compile_bass_lane(
                config=config,
                running=self.bass_running,
                bass_notes=self.bass_notes,
                bass_gate_beats=self.frontend_config.rhythm.bass_gate_beats,
                program_id=self._selected_program["bass"],
                program_revision=self._program_revision["bass"],
                logical_bus=self._role_bus("bass"),
                generation=generation,
            )
        )

    def _strum_note(self, note: float) -> None:
        self._strum_ordinal += 1
        self.gesture_note(
            owner="omni/strum",
            handle=f"strum/{self._strum_ordinal}",
            program_id=self._selected_program["strum"],
            program_revision=self._program_revision["strum"],
            logical_key=max(0, min(127, int(round(note)))),
            note=note,
            velocity=0.9,
            logical_bus=self._role_bus("strum"),
            tail_seconds=max(
                0.01,
                self.frontend_config.performance.strum_tail_ms / 1000.0,
            ),
        )

    def send_message(self, address: str, value: Any) -> None:
        if self._closed:
            return
        a = self.addr
        if address == a["chord_amp"]:
            self._set_role_volume("chord", value)
        elif address == a["strum_amp"]:
            self._set_role_volume("strum", value)
        elif address == a["bass_amp"]:
            self._set_role_volume("bass", value)
        elif address == a["percussion_amp"]:
            self._set_role_volume("drums", value)
        elif address == a["master_volume"]:
            self._omni_master = max(0.0, min(1.0, float(value)))
            for role in self._role_levels:
                self._publish_role_level(role)
        elif address == a["reverb"]:
            if not isinstance(value, dict):
                raise ValueError("reverb payload must be an object")
            self.set_room(
                0,
                float(value.get("level", 0.0)),
                float(value.get("liveness", 0.5)),
                float(value.get("damping", 0.5)),
            )
            self.set_room_send(
                self._role_bus("drums"),
                1.0 if bool(value.get("drums", False)) else 0.0,
            )
        elif address == a["chord_synth"]:
            self._set_program("chord", value)
        elif address == a["strum_synth"]:
            self._set_program("strum", value)
        elif address == a["bass_synth"]:
            self._set_program("bass", value)
        elif address == a["manual_chord"]:
            self._manual_event(str(value))
        elif address == a["chord_state"]:
            self._set_chord_state(str(value))
        elif address == a["strum_note"]:
            self._strum_note(float(value))
        elif address == a["bass_running"]:
            self.bass_running = bool(int(value))
            if not self.bass_running:
                self.release_owner("rhythm/bass")
            self._publish_bass_lane()
        elif address == a["rhythm_config"]:
            payload = json.loads(str(value))
            if not isinstance(payload, dict):
                raise ValueError("rhythm config payload must be an object")
            self.rhythm_config = payload
            bass_riff = payload.get("bass_riff")
            self.bass_riff = dict(bass_riff) if isinstance(bass_riff, Mapping) else None
            self._publish_drum_lane()
            self._publish_chord_lane()
            self._publish_bass_lane()
        elif address == a["rhythm_chord_enabled"]:
            self.rhythm_chord_enabled = bool(int(value))
            self._publish_chord_lane()
        elif address == a["pitch_bend"]:
            self._send_raw(
                "/omni/v1/global/pitch-bend",
                [self.session, self._next_message_id(), float(value)],
            )
        elif address == a["rhythm_running"]:
            self.rhythm_running = bool(int(value))
            if self.rhythm_running:
                self._publish_drum_lane()
                self._publish_chord_lane()
                self._publish_bass_lane()
            self._send_raw(
                "/omni/v1/transport",
                [
                    self.session,
                    self._next_message_id(),
                    "start" if self.rhythm_running else "stop",
                    float((self.rhythm_config or {}).get("tempo", 108.0)),
                ],
            )
        elif address == a["panic"]:
            self._send_raw(
                "/omni/v1/panic",
                [self.session, self._next_message_id()],
            )
            self._manual_handles.clear()
            self._manual_active_id = None

    def _close_reply_server(self) -> None:
        self._reply_server.shutdown()
        self._reply_server.server_close()
        self._reply_thread.join(timeout=1.0)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._send_raw(
                "/omni/v1/panic",
                [self.session, self._next_message_id()],
            )
            self._send_raw(
                "/omni/v1/shutdown",
                [self.session, self._next_message_id()],
            )
        finally:
            self._close_reply_server()
            self._osc._sock.close()
