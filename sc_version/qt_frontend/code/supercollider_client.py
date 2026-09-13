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

from config_loader import ResolvedAmyConfig
from engine_protocol import NoteOff, NoteOn, PROTOCOL_VERSION, VoiceSet
from supercollider_config import (
    SuperColliderRuntimeConfig,
    load_supercollider_config,
)


class SuperColliderUnavailable(RuntimeError):
    """The separately supervised language/audio service is not ready."""


class SuperColliderClient:
    """Typed OSC adapter to a separately supervised headless SC service.

    The public ``send_message`` method intentionally preserves the existing
    UI-facing semantic addresses during the migration.  It does not parse or
    produce AMY wire commands.  New MIDI code uses the typed methods directly.
    """

    def __init__(
        self,
        config: dict[str, Any] | None,
        addresses: dict[str, str],
        *,
        resolved_config: ResolvedAmyConfig | None = None,
        runtime_config_path: Path,
        **_transport_arguments: Any,
    ) -> None:
        if resolved_config is None:
            raise ValueError("resolved_config is required")
        self.resolved_config = resolved_config
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
        self._closed = False

        dispatcher = Dispatcher()
        dispatcher.map("/omni/v1/ready", self._accept_ready)
        dispatcher.map("/omni/v1/ack", self._accept_ack)
        language = self.runtime_config.language
        self._reply_server = ThreadingOSCUDPServer((language.host, 0), dispatcher)
        self.reply_port = int(self._reply_server.server_address[1])
        self._reply_thread = threading.Thread(
            target=self._reply_server.serve_forever,
            name="supercollider-osc-replies",
            daemon=True,
        )
        self._reply_thread.start()
        self._osc = SimpleUDPClient(language.host, language.port)

        self._selected_program = {
            "chord": resolved_config.synth_defaults.chord,
            "strum": resolved_config.synth_defaults.strum,
            "bass": resolved_config.synth_defaults.bass,
        }
        self._program_revision = {"chord": 1, "strum": 1, "bass": 1}
        self._program_params: dict[str, dict[str, float]] = {
            "chord": {},
            "strum": {},
            "bass": {},
        }
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
        self.rhythm_config: dict[str, Any] | None = None
        self.rhythm_running = False
        self.rhythm_chord_enabled = False
        self.bass_running = True

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
        # ACK state is expanded with definition transactions in M2/M3.  The
        # receiver exists now so protocol additions do not alter ownership.
        _ = arguments

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

    @staticmethod
    def note_to_frequency(note: float) -> float:
        value = float(note)
        if not math.isfinite(value):
            raise ValueError("note must be finite")
        return float(440.0 * (2.0 ** ((value - 69.0) / 12.0)))

    def note_on(self, event: NoteOn) -> None:
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

    def note_off(self, event: NoteOff) -> None:
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

    def configure_part(
        self,
        owner: str,
        program_id: str,
        revision: int,
        logical_bus: int,
        parameters: Mapping[str, float],
    ) -> None:
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
        logical_key: int,
        note: float,
        velocity: float,
        logical_bus: int,
        tail_seconds: float,
        voice_limit: int,
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
                max(1, int(voice_limit)),
            ],
        )

    def drum_hit(
        self,
        *,
        owner: str,
        logical_key: int,
        velocity: float,
        logical_bus: int,
    ) -> None:
        self._send_raw(
            "/omni/v1/drum/hit",
            [
                self.session,
                self._next_message_id(),
                str(owner),
                int(logical_key),
                max(0.0, min(1.0, float(velocity))),
                int(logical_bus),
            ],
        )

    def _role_bus(self, role: str) -> int:
        return int(dict(self.resolved_config.layout.role_buses)[role])

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
            name = str(value.get("name", self._selected_program[role]))
            raw = value.get("params", [])
            parameters: dict[str, float] = {}
            if isinstance(raw, list):
                for index in range(0, len(raw) - 1, 2):
                    parameters[str(raw[index])] = float(raw[index + 1])
        else:
            name = str(value)
            parameters = {}
        if name != self._selected_program[role] or parameters != self._program_params[role]:
            self._program_revision[role] += 1
        self._selected_program[role] = name
        self._program_params[role] = parameters
        logical_bus = self._role_bus("chord" if role == "chord" else role)
        owners = ("omni/manual", "omni/automatic") if role == "chord" else (f"omni/{role}",)
        for owner in owners:
            self.configure_part(
                owner,
                name,
                self._program_revision[role],
                logical_bus,
                parameters,
            )

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
        self.rhythm_chord_enabled = bool(payload.get("rhythm_chord_enabled", False))

    def _strum_note(self, note: float) -> None:
        self._strum_ordinal += 1
        voices = self.resolved_config.capacities.voices.strum
        self.gesture_note(
            owner="omni/strum",
            handle=f"strum/{self._strum_ordinal}",
            program_id=self._selected_program["strum"],
            logical_key=max(0, min(127, int(round(note)))),
            note=note,
            velocity=0.9,
            logical_bus=self._role_bus("strum"),
            tail_seconds=max(
                0.01,
                self.resolved_config.performance.strum_tail_ms / 1000.0,
            ),
            voice_limit=voices,
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
                self.release_owner("omni/bass")
        elif address == a["rhythm_config"]:
            payload = json.loads(str(value))
            if not isinstance(payload, dict):
                raise ValueError("rhythm config payload must be an object")
            self.rhythm_config = payload
        elif address == a["rhythm_chord_enabled"]:
            self.rhythm_chord_enabled = bool(int(value))
        elif address == a["pitch_bend"]:
            self._send_raw(
                "/omni/v1/global/pitch-bend",
                [self.session, self._next_message_id(), float(value)],
            )
        elif address == a["rhythm_running"]:
            self.rhythm_running = bool(int(value))
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
