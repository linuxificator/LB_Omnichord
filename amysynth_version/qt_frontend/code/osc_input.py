from __future__ import annotations

import math
import socket
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

from pythonosc.osc_packet import OscPacket, ParseError

from resolved_config import OscInputConfig


OscValueType = Literal["continuous", "button"]
OscInputLifecycle = Literal[
    "constructed",
    "starting",
    "ready",
    "failed",
    "closing",
    "closed",
]


@dataclass(frozen=True, slots=True)
class OscInputEvent:
    """One normalized OSC argument crossing the UDP-reader boundary."""

    sequence: int
    address: str
    argument: int
    value: float
    value_type: OscValueType


OscInputEventSink = Callable[[OscInputEvent], None]


class OscInputPort(Protocol):
    @property
    def lifecycle(self) -> OscInputLifecycle: ...

    @property
    def failure_reason(self) -> str: ...

    def start(self) -> None: ...

    def close(self) -> None: ...


class OscInputPortFactory(Protocol):
    def __call__(self, event_sink: OscInputEventSink, config: object) -> OscInputPort: ...


class OrderedOscInputEmitter:
    """Serialize immutable events and reject callbacks once shutdown begins."""

    def __init__(self, sink: OscInputEventSink) -> None:
        self._sink = sink
        self._lock = threading.Lock()
        self._sequence = 0
        self._closed = False

    def emit(
        self,
        address: str,
        argument: int,
        value: float,
        value_type: OscValueType,
    ) -> None:
        with self._lock:
            if self._closed:
                return
            self._sequence += 1
            self._sink(
                OscInputEvent(
                    sequence=self._sequence,
                    address=str(address),
                    argument=int(argument),
                    value=float(value),
                    value_type=value_type,
                )
            )

    def close(self) -> None:
        with self._lock:
            self._closed = True


def decode_osc_packet(packet: bytes) -> tuple[tuple[str, int, float, OscValueType], ...]:
    """Decode the numeric control arguments in one OSC message or bundle."""

    try:
        timed_messages = OscPacket(packet).messages
    except ParseError:
        return ()

    decoded: list[tuple[str, int, float, OscValueType]] = []
    for timed in timed_messages:
        message = timed.message
        address = str(message.address)
        for argument, raw in enumerate(message.params):
            if isinstance(raw, bool):
                decoded.append(
                    (address, argument, 1.0 if raw else 0.0, "button")
                )
                continue
            if not isinstance(raw, (int, float)):
                continue
            value = float(raw)
            if not math.isfinite(value):
                continue
            normalized = max(0.0, min(1.0, value))
            value_type: OscValueType = (
                "button" if normalized in (0.0, 1.0) else "continuous"
            )
            decoded.append((address, argument, normalized, value_type))
    return tuple(decoded)


class PythonOscUdpInputPort:
    """Portable single-worker UDP adapter around python-osc packet parsing."""

    def __init__(self, event_sink: OscInputEventSink, config: OscInputConfig) -> None:
        self._config = config
        self._emitter = OrderedOscInputEmitter(event_sink)
        self._state_lock = threading.Lock()
        self._lifecycle: OscInputLifecycle = "constructed"
        self._failure_reason = ""
        self._socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._closing = threading.Event()

    @property
    def lifecycle(self) -> OscInputLifecycle:
        with self._state_lock:
            return self._lifecycle

    @property
    def failure_reason(self) -> str:
        with self._state_lock:
            return self._failure_reason

    def _set_state(
        self,
        lifecycle: OscInputLifecycle,
        reason: str = "",
    ) -> None:
        with self._state_lock:
            self._lifecycle = lifecycle
            self._failure_reason = str(reason)

    def start(self) -> None:
        with self._state_lock:
            if self._lifecycle != "constructed":
                return
            self._lifecycle = "starting"
        if not self._config.enabled:
            self._set_state("ready")
            return

        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            udp_socket.bind(
                (self._config.listen_address, self._config.listen_port)
            )
            udp_socket.settimeout(0.1)
        except OSError as exc:
            udp_socket.close()
            self._set_state("failed", str(exc))
            return

        self._socket = udp_socket
        self._thread = threading.Thread(
            target=self._read_loop,
            name="osc-udp-input",
            daemon=True,
        )
        self._thread.start()
        self._set_state("ready")

    def _read_loop(self) -> None:
        udp_socket = self._socket
        if udp_socket is None:
            return
        while not self._closing.is_set():
            try:
                packet, _peer = udp_socket.recvfrom(65535)
            except TimeoutError:
                continue
            except OSError as exc:
                if not self._closing.is_set():
                    self._set_state("failed", str(exc))
                return
            for address, argument, value, value_type in decode_osc_packet(packet):
                self._emitter.emit(address, argument, value, value_type)

    def close(self) -> None:
        with self._state_lock:
            if self._lifecycle == "closed":
                return
            self._lifecycle = "closing"
        self._closing.set()
        self._emitter.close()
        udp_socket = self._socket
        self._socket = None
        if udp_socket is not None:
            udp_socket.close()
        thread = self._thread
        self._thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.0)
        self._set_state("closed")


def production_osc_input_port(
    event_sink: OscInputEventSink,
    config: object,
) -> OscInputPort:
    if not isinstance(config, OscInputConfig):
        raise TypeError("OSC input port requires resolved OscInputConfig")
    return PythonOscUdpInputPort(event_sink, config)
