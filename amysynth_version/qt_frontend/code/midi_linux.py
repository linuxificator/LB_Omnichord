from __future__ import annotations

import ctypes
import glob
import os
import select
import threading
import time
from dataclasses import dataclass
from typing import Any, Literal

from midi_input import (
    MidiByteStreamParser,
    MidiByteStreamState,
    MidiInputEventSink,
    MidiInputLifecycle,
    MidiInputTechnology,
    MidiInputTechnologyStatus,
    OrderedMidiInputEmitter,
)
from resolved_config import MidiInputConfig


@dataclass(frozen=True, slots=True)
class _LinuxTechnology:
    key: str
    label: str
    backend: Literal["byte-stream", "alsa-sequencer"]
    globs: tuple[str, ...] = ()
    device: str = ""


def linux_technologies(config: MidiInputConfig) -> tuple[_LinuxTechnology, ...]:
    raw_globs = config.alsa_raw_globs
    if config.device_glob and config.device_glob not in raw_globs:
        raw_globs = (config.device_glob, *raw_globs)
    return (
        _LinuxTechnology("alsa_raw", "ALSA raw", "byte-stream", raw_globs),
        _LinuxTechnology(
            "alsa_seq",
            "ALSA seq",
            "alsa-sequencer",
            device="/dev/snd/seq",
        ),
        _LinuxTechnology(
            "oss_midi",
            "OSS MIDI",
            "byte-stream",
            config.oss_midi_globs,
        ),
    )


class LinuxRawMidiReader:
    """Dependency-free raw MIDI byte-stream reader for Linux."""

    def __init__(
        self,
        emitter: OrderedMidiInputEmitter,
        technology: _LinuxTechnology,
    ) -> None:
        self._emitter = emitter
        self._technology = technology
        self._parser = MidiByteStreamParser(emitter, technology.key)
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name=f"omnichord-midi-{technology.key}",
            daemon=True,
        )
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            paths = sorted(
                {
                    path
                    for pattern in self._technology.globs
                    for path in glob.glob(pattern)
                }
            )
            if not paths:
                self._stop.wait(0.5)
                continue

            streams: dict[int, MidiByteStreamState] = {}
            try:
                for path in paths:
                    try:
                        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
                    except OSError:
                        continue
                    streams[descriptor] = MidiByteStreamState()
                if not streams:
                    self._stop.wait(0.5)
                    continue

                while not self._stop.is_set():
                    readable, _, _ = select.select(list(streams), [], [], 0.25)
                    for descriptor in readable:
                        try:
                            data = os.read(descriptor, 1024)
                        except OSError:
                            data = b""
                        if not data:
                            try:
                                os.close(descriptor)
                            except OSError:
                                pass
                            streams.pop(descriptor, None)
                            continue
                        self._emitter.activity(self._technology.key)
                        self._parser.feed(data, streams[descriptor])
                    if not streams:
                        break
            finally:
                for descriptor in list(streams):
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=1.0)


class AlsaSequencerMidiReader:
    """ALSA sequencer input client visible in Linux graph tools."""

    _SND_SEQ_OPEN_INPUT = 2
    _SND_SEQ_NONBLOCK = 0x0001
    _SND_SEQ_PORT_CAP_WRITE = 1 << 1
    _SND_SEQ_PORT_CAP_SUBS_WRITE = 1 << 6
    _SND_SEQ_PORT_TYPE_MIDI_GENERIC = 1 << 1
    _SND_SEQ_PORT_TYPE_APPLICATION = 1 << 20

    def __init__(
        self,
        emitter: OrderedMidiInputEmitter,
        technology: _LinuxTechnology,
        client_name: str = "LB Omnichord",
        port_name: str = "MIDI In",
    ) -> None:
        self._emitter = emitter
        self._technology = technology
        self._parser = MidiByteStreamParser(emitter, technology.key)
        self._client_name = client_name.encode("utf-8")
        self._port_name = port_name.encode("utf-8")
        self._stop = threading.Event()
        self._available = False
        self._reason = "not started"
        self._client_id: int | None = None
        self._port_id: int | None = None
        self._thread = threading.Thread(
            target=self._run,
            name="omnichord-midi-alsa-seq",
            daemon=True,
        )
        self._thread.start()

    @staticmethod
    def _load_libasound() -> Any:
        library = ctypes.CDLL("libasound.so.2")
        void_pointer_pointer = ctypes.POINTER(ctypes.c_void_p)
        library.snd_seq_open.argtypes = [
            void_pointer_pointer,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_int,
        ]
        library.snd_seq_open.restype = ctypes.c_int
        library.snd_seq_close.argtypes = [ctypes.c_void_p]
        library.snd_seq_close.restype = ctypes.c_int
        library.snd_seq_set_client_name.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
        ]
        library.snd_seq_set_client_name.restype = ctypes.c_int
        library.snd_seq_client_id.argtypes = [ctypes.c_void_p]
        library.snd_seq_client_id.restype = ctypes.c_int
        library.snd_seq_create_simple_port.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_uint,
            ctypes.c_uint,
        ]
        library.snd_seq_create_simple_port.restype = ctypes.c_int
        library.snd_seq_event_input_pending.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
        ]
        library.snd_seq_event_input_pending.restype = ctypes.c_int
        library.snd_seq_event_input.argtypes = [
            ctypes.c_void_p,
            void_pointer_pointer,
        ]
        library.snd_seq_event_input.restype = ctypes.c_int
        library.snd_seq_free_event.argtypes = [ctypes.c_void_p]
        library.snd_seq_free_event.restype = ctypes.c_int
        library.snd_midi_event_new.argtypes = [
            ctypes.c_size_t,
            void_pointer_pointer,
        ]
        library.snd_midi_event_new.restype = ctypes.c_int
        library.snd_midi_event_free.argtypes = [ctypes.c_void_p]
        library.snd_midi_event_free.restype = None
        library.snd_midi_event_init.argtypes = [ctypes.c_void_p]
        library.snd_midi_event_init.restype = None
        library.snd_midi_event_decode.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_long,
            ctypes.c_void_p,
        ]
        library.snd_midi_event_decode.restype = ctypes.c_long
        library.snd_strerror.argtypes = [ctypes.c_int]
        library.snd_strerror.restype = ctypes.c_char_p
        return library

    @staticmethod
    def _error(library: Any, code: int) -> str:
        raw = library.snd_strerror(int(code))
        return raw.decode("utf-8", errors="replace") if raw else str(code)

    def _open_once(
        self,
        library: Any,
    ) -> tuple[ctypes.c_void_p, ctypes.c_void_p] | None:
        sequencer = ctypes.c_void_p()
        result = library.snd_seq_open(
            ctypes.byref(sequencer),
            b"default",
            self._SND_SEQ_OPEN_INPUT,
            self._SND_SEQ_NONBLOCK,
        )
        if result < 0:
            self._reason = self._error(library, result)
            return None
        try:
            library.snd_seq_set_client_name(sequencer, self._client_name)
            self._client_id = int(library.snd_seq_client_id(sequencer))
            self._port_id = int(
                library.snd_seq_create_simple_port(
                    sequencer,
                    self._port_name,
                    self._SND_SEQ_PORT_CAP_WRITE | self._SND_SEQ_PORT_CAP_SUBS_WRITE,
                    self._SND_SEQ_PORT_TYPE_MIDI_GENERIC
                    | self._SND_SEQ_PORT_TYPE_APPLICATION,
                )
            )
            if self._port_id < 0:
                self._reason = self._error(library, self._port_id)
                library.snd_seq_close(sequencer)
                return None

            decoder = ctypes.c_void_p()
            result = library.snd_midi_event_new(256, ctypes.byref(decoder))
            if result < 0:
                self._reason = self._error(library, result)
                library.snd_seq_close(sequencer)
                return None
            library.snd_midi_event_init(decoder)
            return sequencer, decoder
        except Exception as exc:
            self._reason = str(exc)
            library.snd_seq_close(sequencer)
            return None

    def _run_session(
        self,
        library: Any,
        sequencer: ctypes.c_void_p,
        decoder: ctypes.c_void_p,
    ) -> None:
        state = MidiByteStreamState()
        buffer = ctypes.create_string_buffer(256)
        self._available = True
        self._reason = (
            f"client {self._client_id}:{self._port_id}"
            if self._client_id is not None and self._port_id is not None
            else "listening"
        )
        try:
            while not self._stop.is_set():
                pending = int(library.snd_seq_event_input_pending(sequencer, 1))
                if pending <= 0:
                    self._stop.wait(0.01)
                    continue
                while pending > 0 and not self._stop.is_set():
                    event_pointer = ctypes.c_void_p()
                    result = int(
                        library.snd_seq_event_input(
                            sequencer,
                            ctypes.byref(event_pointer),
                        )
                    )
                    if result < 0 or not event_pointer:
                        break
                    try:
                        size = int(
                            library.snd_midi_event_decode(
                                decoder,
                                buffer,
                                len(buffer),
                                event_pointer,
                            )
                        )
                    finally:
                        library.snd_seq_free_event(event_pointer)
                    if size > 0:
                        self._emitter.activity(self._technology.key)
                        self._parser.feed(buffer.raw[:size], state)
                    pending -= 1
        finally:
            self._available = False
            self._reason = "closed"
            library.snd_midi_event_free(decoder)
            library.snd_seq_close(sequencer)

    def _run(self) -> None:
        try:
            library = self._load_libasound()
        except OSError as exc:
            self._reason = str(exc)
            return

        while not self._stop.is_set():
            opened = self._open_once(library)
            if opened is None:
                self._stop.wait(1.0)
                continue
            self._run_session(library, *opened)

    def status_snapshot(
        self,
        activity: bool,
    ) -> tuple[Literal["unavailable", "listening", "activity"], str]:
        state: Literal["unavailable", "listening", "activity"] = (
            "activity" if self._available and activity else "listening"
        )
        if not self._available:
            state = "unavailable"
        return state, self._reason

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=1.0)


class LinuxMidiInputPort:
    """Own Linux MIDI discovery/readers behind the portable input contract."""

    def __init__(self, event_sink: MidiInputEventSink, config: MidiInputConfig) -> None:
        self._config = config
        self._definitions = linux_technologies(config)
        self._emitter = OrderedMidiInputEmitter(event_sink)
        self._raw_readers: list[LinuxRawMidiReader] = []
        self._sequencer_readers: dict[str, AlsaSequencerMidiReader] = {}
        self._lifecycle: MidiInputLifecycle = "constructed"

    @property
    def lifecycle(self) -> MidiInputLifecycle:
        return self._lifecycle

    @property
    def technologies(self) -> tuple[MidiInputTechnology, ...]:
        return tuple(
            MidiInputTechnology(item.key, item.label) for item in self._definitions
        )

    def start(self) -> None:
        if self._lifecycle != "constructed":
            return
        self._lifecycle = "starting"
        if self._config.enabled:
            for definition in self._definitions:
                if definition.backend == "byte-stream":
                    self._raw_readers.append(
                        LinuxRawMidiReader(self._emitter, definition)
                    )
                else:
                    self._sequencer_readers[definition.key] = (
                        AlsaSequencerMidiReader(self._emitter, definition)
                    )
        self._lifecycle = "ready"

    @staticmethod
    def _glob_paths(definition: _LinuxTechnology) -> list[str]:
        return sorted(
            {
                path
                for pattern in definition.globs
                for path in glob.glob(pattern)
            }
        )

    def status_snapshot(
        self,
        activity_until: dict[str, float] | None = None,
        now: float | None = None,
    ) -> tuple[MidiInputTechnologyStatus, ...]:
        activity_until = activity_until or {}
        instant = time.monotonic() if now is None else float(now)
        statuses: list[MidiInputTechnologyStatus] = []
        for definition in self._definitions:
            state: Literal["unavailable", "listening", "activity"] = "unavailable"
            reason = ""
            if not self._config.enabled:
                reason = "MIDI input disabled in configuration"
            elif definition.backend == "byte-stream":
                paths = self._glob_paths(definition)
                readable = [path for path in paths if os.access(path, os.R_OK)]
                if readable:
                    state = (
                        "activity"
                        if activity_until.get(definition.key, 0.0) > instant
                        else "listening"
                    )
                    reason = ", ".join(readable[:3])
                    if len(readable) > 3:
                        reason += f" (+{len(readable) - 3})"
                elif paths:
                    reason = "device present but not readable"
                else:
                    reason = "no matching device"
            else:
                reader = self._sequencer_readers.get(definition.key)
                if reader is not None:
                    raw_state, reason = reader.status_snapshot(
                        activity_until.get(definition.key, 0.0) > instant
                    )
                    if raw_state in ("unavailable", "listening", "activity"):
                        state = raw_state
                elif definition.device and not os.path.exists(definition.device):
                    reason = f"{definition.device} not present"
                else:
                    reason = "ALSA sequencer listener not started"
            statuses.append(
                MidiInputTechnologyStatus(
                    definition.key,
                    definition.label,
                    state,
                    reason,
                )
            )
        return tuple(statuses)

    def close(self) -> None:
        if self._lifecycle in ("closing", "closed"):
            return
        self._lifecycle = "closing"
        self._emitter.close()
        for raw_reader in self._raw_readers:
            raw_reader.close()
        for sequencer_reader in self._sequencer_readers.values():
            sequencer_reader.close()
        self._lifecycle = "closed"
