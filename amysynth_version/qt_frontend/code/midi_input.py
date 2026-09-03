from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

from input_technology import InputTechnologyStatus
from midi_control import PITCH_BEND_CONTROLLER


MidiInputEventKind = Literal["note", "control", "button", "activity"]
MIDI_INPUT_ACTIVITY_SECONDS = 0.45
MidiInputLifecycle = Literal[
    "constructed",
    "starting",
    "ready",
    "failed",
    "closing",
    "closed",
]


@dataclass(frozen=True, slots=True)
class MidiInputEvent:
    """One normalized, immutable event crossing the native-reader boundary."""

    sequence: int
    kind: MidiInputEventKind
    technology: str
    channel: int = 0
    data: int = 0
    value: int = 0
    is_on: bool = False


@dataclass(frozen=True, slots=True)
class MidiInputTechnology:
    key: str
    label: str


MidiInputTechnologyStatus = InputTechnologyStatus


MidiInputEventSink = Callable[[MidiInputEvent], None]


class MidiInputPort(Protocol):
    @property
    def lifecycle(self) -> MidiInputLifecycle: ...

    @property
    def technologies(self) -> tuple[MidiInputTechnology, ...]: ...

    def start(self) -> None: ...

    def status_snapshot(
        self,
        activity_until: dict[str, float] | None = None,
        now: float | None = None,
    ) -> tuple[MidiInputTechnologyStatus, ...]: ...

    def close(self) -> None: ...


class MidiInputPortFactory(Protocol):
    def __call__(self, event_sink: MidiInputEventSink, config: object) -> MidiInputPort: ...


class OrderedMidiInputEmitter:
    """Serialize events from one or more native reader threads."""

    def __init__(self, sink: MidiInputEventSink) -> None:
        self._sink = sink
        self._lock = threading.Lock()
        self._sequence = 0
        self._closed = False

    def _emit(
        self,
        kind: MidiInputEventKind,
        technology: str,
        *,
        channel: int = 0,
        data: int = 0,
        value: int = 0,
        is_on: bool = False,
    ) -> None:
        # Keep Signal.emit inside the lock: Qt then receives one serialized
        # stream even when two native reader threads become readable together.
        with self._lock:
            if self._closed:
                return
            self._sequence += 1
            self._sink(
                MidiInputEvent(
                    sequence=self._sequence,
                    kind=kind,
                    technology=str(technology),
                    channel=int(channel),
                    data=int(data),
                    value=int(value),
                    is_on=bool(is_on),
                )
            )

    def note(
        self,
        technology: str,
        channel: int,
        note: int,
        velocity: int,
        is_on: bool,
    ) -> None:
        self._emit(
            "note",
            technology,
            channel=channel,
            data=note,
            value=velocity,
            is_on=is_on,
        )

    def control(
        self,
        technology: str,
        channel: int,
        controller: int,
        value: int,
    ) -> None:
        self._emit(
            "control",
            technology,
            channel=channel,
            data=controller,
            value=value,
        )

    def button(
        self,
        technology: str,
        channel: int,
        note: int,
        velocity: int,
        is_on: bool,
    ) -> None:
        self._emit(
            "button",
            technology,
            channel=channel,
            data=note,
            value=velocity,
            is_on=is_on,
        )

    def activity(self, technology: str) -> None:
        self._emit("activity", technology)

    def close(self) -> None:
        with self._lock:
            self._closed = True


@dataclass(slots=True)
class MidiByteStreamState:
    running_status: int = 0
    pending: bytes = b""
    in_sysex: bool = False


class MidiByteStreamParser:
    """Normalize a raw MIDI byte stream without knowing its native transport."""

    def __init__(self, emitter: OrderedMidiInputEmitter, technology: str) -> None:
        self._emitter = emitter
        self._technology = technology

    @staticmethod
    def _data_length(status: int) -> int:
        high = status & 0xF0
        if high in (0xC0, 0xD0):
            return 1
        if 0x80 <= high <= 0xE0:
            return 2
        return 0

    def feed(self, data: bytes, state: MidiByteStreamState) -> None:
        running = state.running_status
        pending = list(state.pending)
        sysex = state.in_sysex

        for byte in data:
            if byte >= 0xF8:
                continue
            if sysex:
                if byte == 0xF7:
                    sysex = False
                continue
            if byte == 0xF0:
                sysex = True
                running = 0
                pending = []
                continue
            if byte & 0x80:
                if byte >= 0xF0:
                    running = 0
                    pending = []
                    continue
                running = byte
                pending = []
                continue
            if running == 0:
                continue
            pending.append(byte)
            needed = self._data_length(running)
            if needed == 0 or len(pending) < needed:
                continue
            payload = pending[:needed]
            pending = pending[needed:]
            high = running & 0xF0
            channel = (running & 0x0F) + 1
            if high == 0x90:
                note, velocity = payload
                self._emitter.note(
                    self._technology,
                    channel,
                    note,
                    velocity,
                    velocity > 0,
                )
            elif high == 0x80:
                note, velocity = payload
                self._emitter.note(
                    self._technology,
                    channel,
                    note,
                    velocity,
                    False,
                )
            elif high == 0xB0:
                controller, value = payload
                self._emitter.control(
                    self._technology,
                    channel,
                    controller,
                    value,
                )
            elif high == 0xE0:
                lsb, msb = payload
                self._emitter.control(
                    self._technology,
                    channel,
                    PITCH_BEND_CONTROLLER,
                    int(lsb) | (int(msb) << 7),
                )

        state.running_status = running
        state.pending = bytes(pending)
        state.in_sysex = sysex
