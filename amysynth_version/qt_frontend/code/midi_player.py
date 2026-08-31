from __future__ import annotations

import glob
import ctypes
import json
import math
import os
import select
import threading
import time
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication

import app_core
from control_limits import clamp_control_value
from midi_control import (
    NOTE_BUTTON_OFFSET,
    PITCH_BEND_CONTROLLER,
    MidiControlState,
)
from synth_programs import resolve_program
from synth_state import SynthState
from user_data import MIDI_PRESET_DIR


MIDI_ROW_COUNT = 6
MIDI_PRESET_COUNT = 18
MIDI_DRUM_KEY = "drum_kit_0"
MIDI_FACTORY_DIR = app_core.INSTRUMENT_DIR / "midi_default_presets"
MIDI_LAST_PRESET_FILE = "last_preset.json"
MIDI_PREVIEW_LOW = app_core.STRUM_LOW_MIDI
MIDI_PREVIEW_HIGH = app_core.STRUM_HIGH_MIDI
MIDI_REVERB_MAX = app_core.REVERB_LEVEL_MAX

GM_DRUM_SAMPLE = {
    35: "bd_haus",
    36: "drum_bass_hard",
    38: "drum_snare_hard",
    40: "drum_snare_soft",
    41: "drum_tom_lo_soft",
    45: "drum_tom_mid_soft",
    48: "drum_tom_hi_soft",
    39: "perc_snap",
    42: "drum_cymbal_closed",
    44: "drum_cymbal_pedal",
    46: "drum_cymbal_open",
    51: "perc_bell",
}
PREVIEW_DRUM_NOTES = (36, 38, 42, 46, 41, 45, 48, 51)


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


class _MidiByteStreamParser:
    """Parse raw MIDI bytes into the small event set the app consumes."""

    def __init__(
        self,
        callback: Callable[[int, int, int, bool], None],
        control_callback: Callable[[int, int, int], None],
    ) -> None:
        self._callback = callback
        self._control_callback = control_callback

    @staticmethod
    def _data_length(status: int) -> int:
        hi = status & 0xF0
        if hi in (0xC0, 0xD0):
            return 1
        if 0x80 <= hi <= 0xE0:
            return 2
        return 0

    def _parse_stream(self, data: bytes, state: dict[str, Any]) -> None:
        running = int(state.get("running", 0))
        pending = list(state.get("pending", []))
        sysex = bool(state.get("sysex", False))

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
            hi = running & 0xF0
            channel = (running & 0x0F) + 1
            if hi == 0x90:
                note, velocity = payload
                self._callback(channel, note, velocity, velocity > 0)
            elif hi == 0x80:
                note, velocity = payload
                self._callback(channel, note, velocity, False)
            elif hi == 0xB0:
                controller, value = payload
                self._control_callback(channel, controller, value)
            elif hi == 0xE0:
                lsb, msb = payload
                value = int(lsb) | (int(msb) << 7)
                self._control_callback(channel, PITCH_BEND_CONTROLLER, value)

        state["running"] = running
        state["pending"] = pending
        state["sysex"] = sysex


class _LinuxRawMidiReader(_MidiByteStreamParser):
    """Dependency-free raw MIDI byte-stream reader for Raspberry Pi/Linux."""

    def __init__(
        self,
        callback: Callable[[int, int, int, bool], None],
        control_callback: Callable[[int, int, int], None],
        device_glob: str | list[str],
        enabled: bool,
        activity_callback: Callable[[], None] | None = None,
        thread_name: str = "omnichord-usb-midi",
    ) -> None:
        super().__init__(callback, control_callback)
        if isinstance(device_glob, list):
            self._globs = [str(item) for item in device_glob]
        else:
            self._globs = [str(device_glob)]
        self._enabled = bool(enabled)
        self._activity_callback = activity_callback
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        if self._enabled:
            self._thread = threading.Thread(
                target=self._run,
                name=thread_name,
                daemon=True,
            )
            self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            paths = sorted({
                path
                for pattern in self._globs
                for path in glob.glob(pattern)
            })
            if not paths:
                self._stop.wait(0.5)
                continue

            fds: dict[int, tuple[str, dict[str, Any]]] = {}
            try:
                for path in paths:
                    try:
                        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
                    except OSError:
                        continue
                    fds[fd] = (
                        path,
                        {"running": 0, "pending": [], "sysex": False},
                    )
                if not fds:
                    self._stop.wait(0.5)
                    continue

                while not self._stop.is_set():
                    readable, _, _ = select.select(list(fds), [], [], 0.25)
                    for fd in readable:
                        try:
                            data = os.read(fd, 1024)
                        except OSError:
                            data = b""
                        if not data:
                            try:
                                os.close(fd)
                            except OSError:
                                pass
                            fds.pop(fd, None)
                            continue
                        if self._activity_callback is not None:
                            self._activity_callback()
                        self._parse_stream(data, fds[fd][1])
                    if not fds:
                        break
            finally:
                for fd in list(fds):
                    try:
                        os.close(fd)
                    except OSError:
                        pass

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)


class _AlsaSequencerMidiReader(_MidiByteStreamParser):
    """ALSA sequencer MIDI input client visible in graph tools."""

    _SND_SEQ_OPEN_INPUT = 2
    _SND_SEQ_NONBLOCK = 0x0001
    _SND_SEQ_PORT_CAP_WRITE = 1 << 1
    _SND_SEQ_PORT_CAP_SUBS_WRITE = 1 << 6
    _SND_SEQ_PORT_TYPE_MIDI_GENERIC = 1 << 1
    _SND_SEQ_PORT_TYPE_APPLICATION = 1 << 20

    def __init__(
        self,
        callback: Callable[[int, int, int, bool], None],
        control_callback: Callable[[int, int, int], None],
        activity_callback: Callable[[], None],
        enabled: bool,
        client_name: str = "LB Omnichord",
        port_name: str = "MIDI In",
    ) -> None:
        super().__init__(callback, control_callback)
        self._activity_callback = activity_callback
        self._enabled = bool(enabled)
        self._client_name = client_name.encode("utf-8")
        self._port_name = port_name.encode("utf-8")
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._available = False
        self._reason = "not started"
        self._client_id: int | None = None
        self._port_id: int | None = None
        if self._enabled:
            self._thread = threading.Thread(
                target=self._run,
                name="omnichord-midi-alsa-seq",
                daemon=True,
            )
            self._thread.start()

    @staticmethod
    def _load_libasound() -> ctypes.CDLL:
        lib = ctypes.CDLL("libasound.so.2")
        c_void_pp = ctypes.POINTER(ctypes.c_void_p)

        lib.snd_seq_open.argtypes = [
            c_void_pp,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_int,
        ]
        lib.snd_seq_open.restype = ctypes.c_int
        lib.snd_seq_close.argtypes = [ctypes.c_void_p]
        lib.snd_seq_close.restype = ctypes.c_int
        lib.snd_seq_set_client_name.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
        ]
        lib.snd_seq_set_client_name.restype = ctypes.c_int
        lib.snd_seq_client_id.argtypes = [ctypes.c_void_p]
        lib.snd_seq_client_id.restype = ctypes.c_int
        lib.snd_seq_create_simple_port.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_uint,
            ctypes.c_uint,
        ]
        lib.snd_seq_create_simple_port.restype = ctypes.c_int
        lib.snd_seq_event_input_pending.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
        ]
        lib.snd_seq_event_input_pending.restype = ctypes.c_int
        lib.snd_seq_event_input.argtypes = [
            ctypes.c_void_p,
            c_void_pp,
        ]
        lib.snd_seq_event_input.restype = ctypes.c_int
        lib.snd_seq_free_event.argtypes = [ctypes.c_void_p]
        lib.snd_seq_free_event.restype = ctypes.c_int
        lib.snd_midi_event_new.argtypes = [
            ctypes.c_size_t,
            c_void_pp,
        ]
        lib.snd_midi_event_new.restype = ctypes.c_int
        lib.snd_midi_event_free.argtypes = [ctypes.c_void_p]
        lib.snd_midi_event_free.restype = None
        lib.snd_midi_event_init.argtypes = [ctypes.c_void_p]
        lib.snd_midi_event_init.restype = None
        lib.snd_midi_event_decode.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_long,
            ctypes.c_void_p,
        ]
        lib.snd_midi_event_decode.restype = ctypes.c_long
        lib.snd_strerror.argtypes = [ctypes.c_int]
        lib.snd_strerror.restype = ctypes.c_char_p
        return lib

    @staticmethod
    def _error(lib: ctypes.CDLL, code: int) -> str:
        raw = lib.snd_strerror(int(code))
        return raw.decode("utf-8", errors="replace") if raw else str(code)

    def _open_once(
        self,
        lib: ctypes.CDLL,
    ) -> tuple[ctypes.c_void_p, ctypes.c_void_p] | None:
        seq = ctypes.c_void_p()
        rc = lib.snd_seq_open(
            ctypes.byref(seq),
            b"default",
            self._SND_SEQ_OPEN_INPUT,
            self._SND_SEQ_NONBLOCK,
        )
        if rc < 0:
            self._reason = self._error(lib, rc)
            return None
        try:
            lib.snd_seq_set_client_name(seq, self._client_name)
            self._client_id = int(lib.snd_seq_client_id(seq))
            self._port_id = int(
                lib.snd_seq_create_simple_port(
                    seq,
                    self._port_name,
                    self._SND_SEQ_PORT_CAP_WRITE
                    | self._SND_SEQ_PORT_CAP_SUBS_WRITE,
                    self._SND_SEQ_PORT_TYPE_MIDI_GENERIC
                    | self._SND_SEQ_PORT_TYPE_APPLICATION,
                )
            )
            if self._port_id < 0:
                self._reason = self._error(lib, self._port_id)
                lib.snd_seq_close(seq)
                return None

            decoder = ctypes.c_void_p()
            rc = lib.snd_midi_event_new(256, ctypes.byref(decoder))
            if rc < 0:
                self._reason = self._error(lib, rc)
                lib.snd_seq_close(seq)
                return None
            lib.snd_midi_event_init(decoder)
            return seq, decoder
        except Exception as exc:
            self._reason = str(exc)
            lib.snd_seq_close(seq)
            return None

    def _run_session(
        self,
        lib: ctypes.CDLL,
        seq: ctypes.c_void_p,
        decoder: ctypes.c_void_p,
    ) -> None:
        stream_state: dict[str, Any] = {}
        buffer = ctypes.create_string_buffer(256)
        self._available = True
        self._reason = (
            f"client {self._client_id}:{self._port_id}"
            if self._client_id is not None and self._port_id is not None
            else "listening"
        )
        try:
            while not self._stop.is_set():
                pending = int(lib.snd_seq_event_input_pending(seq, 1))
                if pending <= 0:
                    self._stop.wait(0.01)
                    continue
                while pending > 0 and not self._stop.is_set():
                    event_ptr = ctypes.c_void_p()
                    rc = int(lib.snd_seq_event_input(seq, ctypes.byref(event_ptr)))
                    if rc < 0 or not event_ptr:
                        break
                    try:
                        size = int(
                            lib.snd_midi_event_decode(
                                decoder,
                                buffer,
                                len(buffer),
                                event_ptr,
                            )
                        )
                    finally:
                        lib.snd_seq_free_event(event_ptr)
                    if size > 0:
                        self._activity_callback()
                        self._parse_stream(buffer.raw[:size], stream_state)
                    pending -= 1
        finally:
            self._available = False
            self._reason = "closed"
            lib.snd_midi_event_free(decoder)
            lib.snd_seq_close(seq)

    def _run(self) -> None:
        try:
            lib = self._load_libasound()
        except OSError as exc:
            self._reason = str(exc)
            return

        while not self._stop.is_set():
            opened = self._open_once(lib)
            if opened is None:
                self._stop.wait(1.0)
                continue
            self._run_session(lib, *opened)

    def status_snapshot(
        self,
        activity: bool,
    ) -> dict[str, Any]:
        state = "activity" if self._available and activity else "listening"
        if not self._available:
            state = "unavailable"
        return {
            "state": state,
            "available": self._available,
            "reason": self._reason,
        }

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)


class _MidiInputTechManager:
    """Own platform MIDI input tech detection and byte-stream readers."""

    ACTIVITY_SECONDS = 0.45

    def __init__(
        self,
        callback: Callable[[int, int, int, bool], None],
        control_callback: Callable[[int, int, int], None],
        activity_callback: Callable[[str], None],
        midi_cfg: dict[str, Any],
        platform_name: str | None = None,
    ) -> None:
        self._callback = callback
        self._control_callback = control_callback
        self._activity_callback = activity_callback
        self._midi_cfg = midi_cfg
        self._enabled = bool(midi_cfg.get("enabled", True))
        self._techs = self.platform_techs(
            midi_cfg,
            platform_name or self.current_tech_profile(midi_cfg),
        )
        self._readers: list[_LinuxRawMidiReader] = []
        self._listener_readers: dict[str, _AlsaSequencerMidiReader] = {}

        if self._enabled:
            for tech in self._techs:
                key = str(tech["key"])
                if tech.get("backend") == "byte_stream":
                    self._readers.append(
                        _LinuxRawMidiReader(
                            callback,
                            control_callback,
                            list(tech.get("globs", [])),
                            True,
                            lambda key=key: self._activity_callback(key),
                            f"omnichord-midi-{key}",
                        )
                    )
                elif tech.get("backend") == "alsa_seq":
                    self._listener_readers[key] = _AlsaSequencerMidiReader(
                        callback,
                        control_callback,
                        lambda key=key: self._activity_callback(key),
                        True,
                    )

    @staticmethod
    def _cfg_list(
        midi_cfg: dict[str, Any],
        key: str,
        fallback: list[str],
    ) -> list[str]:
        value = midi_cfg.get(key)
        if isinstance(value, list):
            return [str(item) for item in value]
        if isinstance(value, str) and value:
            return [value]
        return list(fallback)

    @staticmethod
    def current_tech_profile(midi_cfg: dict[str, Any]) -> str:
        configured = str(midi_cfg.get("tech_profile", "")).strip()
        if configured:
            return configured
        app = QGuiApplication.instance()
        qpa = (
            str(QGuiApplication.platformName()).casefold()
            if app is not None
            else ""
        )
        if qpa == "cocoa":
            return "darwin"
        if qpa == "windows":
            return "win32"
        if qpa == "android":
            return "android"
        return "linux"

    @classmethod
    def platform_techs(
        cls,
        midi_cfg: dict[str, Any],
        platform_name: str,
    ) -> list[dict[str, Any]]:
        platform_name = str(platform_name).lower()
        if platform_name.startswith("linux"):
            legacy_raw_glob = str(
                midi_cfg.get("device_glob", "/dev/snd/midiC*D*")
            )
            alsa_raw_globs = cls._cfg_list(
                midi_cfg,
                "alsa_raw_globs",
                [legacy_raw_glob],
            )
            if legacy_raw_glob and legacy_raw_glob not in alsa_raw_globs:
                alsa_raw_globs = [legacy_raw_glob] + alsa_raw_globs
            return [
                {
                    "key": "alsa_raw",
                    "label": "ALSA raw",
                    "backend": "byte_stream",
                    "globs": alsa_raw_globs,
                },
                {
                    "key": "alsa_seq",
                    "label": "ALSA seq",
                    "backend": "alsa_seq",
                    "device": "/dev/snd/seq",
                },
                {
                    "key": "oss_midi",
                    "label": "OSS MIDI",
                    "backend": "byte_stream",
                    "globs": cls._cfg_list(
                        midi_cfg,
                        "oss_midi_globs",
                        [
                            "/dev/midi",
                            "/dev/midi[0-9]*",
                            "/dev/amidi[0-9]*",
                        ],
                    ),
                },
            ]
        if platform_name == "darwin":
            return [
                {
                    "key": "coremidi",
                    "label": "CoreMIDI",
                    "backend": "unsupported",
                    "unsupported_reason": (
                        "native CoreMIDI bridge is not bundled"
                    ),
                }
            ]
        if platform_name.startswith("win"):
            return [
                {
                    "key": "winmm",
                    "label": "WinMM MIDI",
                    "backend": "unsupported",
                    "unsupported_reason": (
                        "native WinMM MIDI bridge is not bundled"
                    ),
                }
            ]
        if platform_name.startswith("android"):
            return [
                {
                    "key": "android_midi",
                    "label": "Android MIDI",
                    "backend": "unsupported",
                    "unsupported_reason": (
                        "native Android MIDI bridge is not bundled"
                    ),
                }
            ]
        return []

    @staticmethod
    def _glob_paths(tech: dict[str, Any]) -> list[str]:
        return sorted({
            path
            for pattern in tech.get("globs", [])
            for path in glob.glob(str(pattern))
        })

    def status_snapshot(
        self,
        activity_until: dict[str, float] | None = None,
        now: float | None = None,
    ) -> list[dict[str, Any]]:
        activity_until = activity_until or {}
        now = time.monotonic() if now is None else float(now)
        items: list[dict[str, Any]] = []
        for tech in self._techs:
            key = str(tech["key"])
            state = "unavailable"
            reason = ""
            if not self._enabled:
                reason = "MIDI input disabled in configuration"
            elif tech.get("backend") == "byte_stream":
                paths = self._glob_paths(tech)
                readable = [path for path in paths if os.access(path, os.R_OK)]
                if readable:
                    state = (
                        "activity"
                        if activity_until.get(key, 0.0) > now
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
                listener = self._listener_readers.get(key)
                if listener is not None:
                    status = listener.status_snapshot(
                        activity_until.get(key, 0.0) > now
                    )
                    state = str(status["state"])
                    reason = str(status["reason"])
                elif tech.get("backend") == "alsa_seq":
                    device = tech.get("device")
                    if device and not os.path.exists(str(device)):
                        reason = f"{device} not present"
                    else:
                        reason = "ALSA sequencer listener not started"
                else:
                    reason = str(
                        tech.get("unsupported_reason", "not supported by this build")
                    )

            items.append(
                {
                    "key": key,
                    "label": str(tech["label"]),
                    "state": state,
                    "available": state in ("listening", "activity"),
                    "reason": reason,
                }
            )
        return items

    def close(self) -> None:
        for reader in self._readers:
            reader.close()
        for reader in self._listener_readers.values():
            reader.close()


class MidiAmyEngine:
    """Own only MIDI synths 5..11; Omnichord synths 0..4 are never touched."""

    def __init__(self, client: Any) -> None:
        self.client = client
        cfg = client.config
        midi_cfg = cfg.get("midi_player", {})
        buses = cfg.get("buses", {})
        self.row_synths = tuple(
            int(x)
            for x in midi_cfg.get("synth_ids", [5, 6, 7, 8, 9, 10])
        )
        if len(self.row_synths) != MIDI_ROW_COUNT:
            raise ValueError("midi_player.synth_ids must contain six synth IDs")
        self.drum_synth = int(midi_cfg.get("drum_synth_id", 11))
        self.voices = int(midi_cfg.get("voices_per_synth", 4))
        self.drum_voices = int(midi_cfg.get("drum_voices", 8))
        raw_row_buses = buses.get("midi_rows", [4, 5, 6, 7, 8, 9])
        self.row_buses = tuple(int(bus) for bus in raw_row_buses)
        self.drum_bus = int(buses.get("midi_drums", 10))
        if (
            len(self.row_buses) != MIDI_ROW_COUNT
            or len(set(self.row_buses)) != MIDI_ROW_COUNT
            or self.drum_bus in self.row_buses
            or any(bus < 4 for bus in (*self.row_buses, self.drum_bus))
        ):
            raise ValueError(
                "six MIDI row buses and the MIDI drum bus must be distinct "
                "buses >= 4"
            )
        self._configured_rows: set[int] = set()
        self._drum_configured = False
        self._active_notes: dict[tuple[int, int, int], float] = {}
        self._preview_lock = threading.Lock()
        self._preview_active_notes: dict[int, list[float]] = {
            row: [] for row in range(MIDI_ROW_COUNT)
        }
        self._preview_tail_tokens = [0] * MIDI_ROW_COUNT
        self.master_volume = 1.0
        self.configure_drum_synth()

    def _wire(self, command: str) -> None:
        self.client._wire(command)

    def _f(self, value: float) -> str:
        return self.client._f(value)

    def balanced_volume(self, key: str, volume: float) -> float:
        levels = self.client.config.get("instrument_levels", {})
        multiplier = (
            max(0.0, float(levels.get(str(key), 1.0)))
            if isinstance(levels, dict)
            else 1.0
        )
        return float(volume) * multiplier

    def _patch(self, key: str) -> int | None:
        patch_map = getattr(self.client, "patch_map", {})
        value = patch_map.get(str(key))
        return None if value is None else int(value)

    def _wait_for_synth_allocation(self) -> None:
        writer = getattr(self.client, "writer", None)
        delay = getattr(writer, "delay", None)
        if not callable(delay):
            return
        guard_ms = float(
            self.client.config.get("performance", {}).get(
                "synth_alloc_guard_ms",
                10.0,
            )
        )
        delay(max(0.0, guard_ms) / 1000.0)

    def _route(self, synth: int, bus: int) -> None:
        self._wire(f"i{synth}iy{bus}Z")

    def configure_drum_synth(self) -> None:
        if self._drum_configured:
            return
        synth = self.drum_synth
        self._wire(
            f"i{synth}iv{self.drum_voices}in1iy{self.drum_bus}Z"
        )
        self._wire(f"v0w7i{synth}Z")
        self._route(synth, self.drum_bus)
        self._apply_master_bus(self.drum_bus)
        self._drum_configured = True

    def _apply_master_bus(self, bus: int) -> None:
        self._wire(f"y{int(bus)}V{self._f(self.master_volume)}Z")

    def set_master_volume(self, volume: float) -> None:
        self.master_volume = max(0.0, min(1.0, float(volume)))
        for bus in (*self.row_buses, self.drum_bus):
            self._apply_master_bus(bus)

    def _compat_commands(self, patch: int, synth: int) -> list[str]:
        helper = getattr(self.client, "_patch_compatibility_commands", None)
        if callable(helper):
            return list(helper(patch, synth))
        return []

    def _param_commands(
        self,
        patch: int,
        synth: int,
        params: dict[str, float],
    ) -> list[str]:
        p = {str(k): float(v) for k, v in params.items()}
        out: list[str] = []

        def nonneg(name: str) -> float | None:
            value = p.get(name)
            if value is None or value < 0:
                return None
            return clamp_control_value(name, float(value))

        if 0 <= patch <= 127:
            cutoff = nonneg("filter_hz")
            resonance = nonneg("resonance")
            lfo = nonneg("lfo_hz")
            vibrato = nonneg("vibrato_depth")
            vcf_lfo = nonneg("filter_lfo_depth")
            pulse = nonneg("pulse_width")
            pwm = nonneg("pwm_depth")
            porta = nonneg("portamento_ms")
            attack = nonneg("attack_ms")
            decay = nonneg("decay_ms")
            sustain = nonneg("sustain")
            release = nonneg("release_ms")
            if cutoff is not None:
                out.append(f"v0F{self._f(cutoff)}i{synth}Z")
            if resonance is not None:
                out.append(f"v0R{self._f(resonance)}i{synth}Z")
            if lfo is not None:
                out.append(f"v1f{self._f(lfo)}i{synth}Z")
            if vibrato is not None:
                depth = max(0.0, min(0.05, vibrato))
                for osc in (2, 3, 4):
                    out.append(
                        f"v{osc}f,,,,,{self._f(depth)}i{synth}Z"
                    )
            if vcf_lfo is not None:
                out.append(f"v0F,,,,,{self._f(vcf_lfo)}i{synth}Z")
            if pulse is not None:
                duty = max(0.05, min(0.95, pulse))
                out.append(f"v2d{self._f(duty)}i{synth}Z")
            if pwm is not None:
                depth = max(0.0, min(0.45, pwm))
                out.append(f"v2d,,,,,{self._f(depth)}i{synth}Z")
            if porta is not None:
                ms = max(0, int(round(porta)))
                for osc in (2, 3, 4):
                    out.append(f"v{osc}m{ms}i{synth}Z")
            if any(v is not None for v in (attack, decay, sustain, release)):
                fields = [
                    self._f(attack) if attack is not None else "",
                    "",
                    self._f(decay) if decay is not None else "",
                    (
                        self._f(max(0.0, min(1.0, sustain)))
                        if sustain is not None
                        else ""
                    ),
                    self._f(release) if release is not None else "",
                    "",
                ]
                out.append(f"v0A{','.join(fields)}i{synth}Z")

        elif 128 <= patch <= 255:
            algorithm = nonneg("algorithm")
            feedback = nonneg("feedback")
            lfo = nonneg("lfo_hz")
            vibrato = nonneg("vibrato_depth")
            porta = nonneg("portamento_ms")
            if algorithm is not None:
                value = max(1, min(32, int(round(algorithm))))
                out.append(f"v0o{value}i{synth}Z")
            if feedback is not None:
                value = max(0.0, min(1.0, feedback))
                out.append(f"v0b{self._f(value)}i{synth}Z")
            if lfo is not None:
                out.append(f"v1f{self._f(lfo)}i{synth}Z")
            if vibrato is not None:
                value = max(0.0, min(0.05, vibrato))
                out.append(f"v0f,,,,,{self._f(value)}i{synth}Z")
            if porta is not None:
                out.append(
                    f"v0m{max(0, int(round(porta)))}i{synth}Z"
                )
            attack = nonneg("attack_ms")
            decay = nonneg("decay_ms")
            sustain = nonneg("sustain")
            release = nonneg("release_ms")
            if any(v is not None for v in (attack, decay, sustain, release)):
                a = 0.0 if attack is None else attack
                d = 0.0 if decay is None else decay
                s = (
                    1.0
                    if sustain is None
                    else max(0.0, min(1.0, sustain))
                )
                r = 60000.0 if release is None else release
                out.append(
                    f"v0a,,,1A{self._f(a)},1,{self._f(d)},"
                    f"{self._f(s)},{self._f(r)},0i{synth}Z"
                )
        return out

    def silence_row(self, row: int) -> None:
        if row not in self._configured_rows:
            return
        with self._preview_lock:
            self._preview_tail_tokens[row] += 1
            self._preview_active_notes[row].clear()
        synth = self.row_synths[row]
        self._wire(f"l0i{synth}Z")
        for key in [key for key in self._active_notes if key[0] == row]:
            self._active_notes.pop(key, None)

    def configure_row(
        self,
        row: int,
        key: str,
        params: dict[str, float],
        volume: float,
    ) -> None:
        synth = self.row_synths[row]
        bus = self.row_buses[row]
        self.silence_row(row)
        program = resolve_program(str(key), self.client.config)
        patch = self._patch(key)

        if program is not None and not program.is_rom_patch:
            if program.kind != "karplus_strong":
                raise ValueError(
                    f"unsupported MIDI synth program {program.kind!r}"
                )
            wave = 6 if program.wave is None else int(program.wave)
            feedback = (
                0.985 if program.feedback is None else float(program.feedback)
            )
            self._wire(
                f"i{synth}iv{self.voices}in1iy{bus}Z"
            )
            self._wire(
                f"v0w{wave}b{self._f(feedback)}i{synth}Z"
            )
            if "ks_feedback" in params:
                value = max(
                    0.0,
                    min(0.9999, float(params["ks_feedback"])),
                )
                self._wire(f"v0b{self._f(value)}i{synth}Z")
        elif patch is not None:
            if row in self._configured_rows:
                self._wire(f"K{patch}i{synth}Z")
            else:
                self._wire(
                    f"K{patch}i{synth}iv{self.voices}iy{bus}Z"
                )
            # Loading a ROM patch reallocates its oscillator block. Keep its
            # compatibility, parameter, routing and volume commands behind
            # the same allocation barrier used by the Omnichord synth path.
            self._wait_for_synth_allocation()
            for command in self._compat_commands(patch, synth):
                self._wire(command)
            for command in self._param_commands(patch, synth, params):
                self._wire(command)
        else:
            raise ValueError(f"unknown MIDI synth {key!r}")

        self._configured_rows.add(row)
        self._route(synth, bus)
        self.set_row_volume(row, self.balanced_volume(key, volume))
        self._apply_master_bus(bus)

    def set_row_volume(self, row: int, volume: float) -> None:
        value = max(0.0, min(1.0, float(volume)))
        self._wire(
            f"i{self.row_synths[row]}iV{self._f(value)}Z"
        )

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
        for bus in self.row_buses:
            self._wire(
                f"y{bus}h{self._f(level)},"
                f"{self._f(liveness)},{self._f(damping)}Z"
            )
        drum_level = level if drums else 0.0
        self._wire(
            f"y{self.drum_bus}h{self._f(drum_level)},"
            f"{self._f(liveness)},{self._f(damping)}Z"
        )

    def note_on(
        self,
        row: int,
        channel: int,
        source_note: int,
        note: float,
        velocity: int,
    ) -> None:
        synth = self.row_synths[row]
        key = (row, channel, source_note)
        old = self._active_notes.pop(key, None)
        if old is not None:
            self._wire(f"n{self._f(old)}l0i{synth}Z")
        level = max(0.0, min(1.0, int(velocity) / 127.0))
        self._wire(
            f"n{self._f(note)}l{self._f(level)}i{synth}Z"
        )
        self._active_notes[key] = float(note)

    def note_off(self, row: int, channel: int, source_note: int) -> None:
        key = (row, channel, source_note)
        note = self._active_notes.pop(key, None)
        if note is not None:
            self._wire(
                f"n{self._f(note)}l0i{self.row_synths[row]}Z"
            )

    def preview_note(
        self,
        row: int,
        note: float,
        velocity: int = 105,
    ) -> None:
        synth = self.row_synths[row]
        level = max(0.0, min(1.0, velocity / 127.0))
        midi_key = int(round(note))

        with self._preview_lock:
            self._preview_tail_tokens[row] += 1
            token = self._preview_tail_tokens[row]
            active = self._preview_active_notes[row]

            duplicate_index = next(
                (
                    index
                    for index, active_note in enumerate(active)
                    if int(round(active_note)) == midi_key
                ),
                None,
            )
            if duplicate_index is not None:
                old = active.pop(duplicate_index)
                self._wire(f"n{self._f(old)}l0i{synth}Z")

            while len(active) >= max(1, self.voices):
                old = active.pop(0)
                self._wire(f"n{self._f(old)}l0i{synth}Z")

            self._wire(
                f"n{self._f(note)}l{self._f(level)}i{synth}Z"
            )
            active.append(float(note))

        tail_ms = float(
            self.client.config.get("performance", {}).get(
                "strum_tail_ms",
                450.0,
            )
        )

        def release() -> None:
            with self._preview_lock:
                if token != self._preview_tail_tokens[row]:
                    return
                self._preview_tail_tokens[row] += 1
                notes = list(self._preview_active_notes[row])
                self._preview_active_notes[row].clear()
            for active_note in notes:
                self._wire(f"n{self._f(active_note)}l0i{synth}Z")

        timer = threading.Timer(max(0.01, tail_ms / 1000.0), release)
        timer.daemon = True
        timer.start()

    def drum_hit(
        self,
        midi_note: int,
        velocity: int,
        row_volume: float,
    ) -> None:
        sample_name = GM_DRUM_SAMPLE.get(int(midi_note))
        if sample_name is None:
            return
        hit = self.client.config["drums"]["sample_map"].get(sample_name)
        if not isinstance(hit, dict):
            return
        level = max(0.0, min(1.0, int(velocity) / 127.0))
        gain = float(
            self.client.config["drums"].get("velocity_gain", 5.0)
        )
        amp = (
            level
            * gain
            * max(0.0, min(1.0, float(row_volume)))
        )
        self._wire(
            f"p{int(hit['preset'])}n{self._f(float(hit['note']))}"
            f"l{self._f(amp)}i{self.drum_synth}Z"
        )

    def all_notes_off(self) -> None:
        with self._preview_lock:
            for row in range(MIDI_ROW_COUNT):
                self._preview_tail_tokens[row] += 1
                self._preview_active_notes[row].clear()
        for row in sorted(self._configured_rows):
            self._wire(f"l0i{self.row_synths[row]}Z")
        if self._drum_configured:
            self._wire(f"l0i{self.drum_synth}Z")
        self._active_notes.clear()

    def rebuild(self) -> None:
        self._configured_rows.clear()
        self._drum_configured = False
        self._active_notes.clear()
        self.configure_drum_synth()


class MidiPlayerBackend(QObject):
    """Independent MIDI-player state, presets, USB input and AMY routing."""

    stateChanged = Signal()
    tuningChanged = Signal()
    presetChanged = Signal()
    presetStored = Signal(int)
    reverbLevelChanged = Signal()
    reverbLivenessChanged = Signal()
    reverbDampingChanged = Signal()
    reverbDrumsIncludedChanged = Signal()
    masterVolumeChanged = Signal()
    masterMutedChanged = Signal()
    bindingStateChanged = Signal()
    bindingLocationRequested = Signal(str, int)
    _queuedControlChange = Signal(int, int, int)
    _queuedButtonChange = Signal(int, int, int)
    midiInputTechsChanged = Signal()
    _queuedMidiTechActivity = Signal(str)

    def __init__(
        self,
        owner: Any,
        synths: tuple[Any, ...],
        client: Any,
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
        self.rows = [
            SynthState(self.definitions, 0)
            for _ in range(MIDI_ROW_COUNT)
        ]
        self.channels = [1, 2, 3, 4, 5, 6]
        self.volumes = [0.5] * MIDI_ROW_COUNT
        self._state_version = 0
        self._selected_preset = 1
        self._preset_reference: dict[str, Any] = {}

        self._tuning_coupled = True
        self._tuning_mode_index = int(owner.selectedTuningModeIndex)
        self._tuning_reference = float(owner.tuningReference)
        self._bend_offset = 0.0
        self._bend_direction = 0
        self._bend_returning = False
        self._bend_timer = QTimer(self)
        self._bend_timer.setInterval(100)
        self._bend_timer.timeout.connect(self._bend_tick)

        self._reverb_level = 0.0
        self._reverb_liveness = 0.5
        self._reverb_damping = 0.5
        self._reverb_drums = False
        # MIDI master output is live state and is not replaced by presets.
        self._master_volume = 1.0
        self._master_muted = False
        self._midi_control_state = MidiControlState(capacity=17)
        self._preset_binding_locations: dict[
            tuple[int, int], tuple[tuple[str, int], ...]
        ] = {}
        self._binding_version = 0
        self._midi_control_lock = threading.Lock()
        self._applying_midi_control = 0
        self._held_midi_button_targets: set[str] = set()
        raw_cc_log = os.environ.get("OMNICHORD_TEST_MIDI_CC_LOG", "")
        self._midi_cc_test_log = Path(raw_cc_log) if raw_cc_log else None
        self._queuedControlChange.connect(self.process_midi_control)
        self._queuedButtonChange.connect(self.process_midi_button)
        self._queuedMidiTechActivity.connect(self._mark_midi_tech_activity)
        self._blue_expiry_timer = QTimer(self)
        self._blue_expiry_timer.setInterval(250)
        self._blue_expiry_timer.timeout.connect(self._expire_blue_controls)
        self._preset_feedback_timer = QTimer(self)
        self._preset_feedback_timer.setInterval(100)
        self._preset_feedback_timer.timeout.connect(
            self._expire_preset_feedback
        )
        self._midi_input_activity_until: dict[str, float] = {}
        self._midi_input_tech_snapshot: list[dict[str, Any]] = []
        self._midi_input_refresh_timer = QTimer(self)
        self._midi_input_refresh_timer.setInterval(1000)
        self._midi_input_refresh_timer.timeout.connect(
            self._refresh_midi_input_techs
        )
        self._midi_input_activity_timer = QTimer(self)
        self._midi_input_activity_timer.setInterval(120)
        self._midi_input_activity_timer.timeout.connect(
            self._refresh_midi_input_techs
        )

        self.engine = MidiAmyEngine(client)
        self._preview_row = -1
        self._preview_last_index: int | None = None

        self._ensure_preset_storage()
        self._load_startup_preset()
        self._refresh_preset_binding_locations()
        self.syncFromOmni()
        self._apply_all_to_engine()

        midi_cfg = client.config.get("midi_input", {})
        self._reader = _MidiInputTechManager(
            self.process_midi_note,
            self._queue_midi_control,
            self._queue_midi_tech_activity,
            midi_cfg if isinstance(midi_cfg, dict) else {},
        )
        self._refresh_midi_input_techs()
        self._midi_input_refresh_timer.start()

    def close(self) -> None:
        self._midi_input_refresh_timer.stop()
        self._midi_input_activity_timer.stop()
        self._reader.close()

    @Property(int, notify=stateChanged)
    def stateVersion(self) -> int:
        return self._state_version

    @Property(int, notify=bindingStateChanged)
    def bindingVersion(self) -> int:
        return self._binding_version

    @Property(str, notify=bindingStateChanged)
    def omniControlLedState(self) -> str:
        with self._midi_control_lock:
            return self._midi_control_state.omni_led_state()

    @Property(bool, constant=True)
    def testCcLogging(self) -> bool:
        return self._midi_cc_test_log is not None

    @Property("QVariantList", constant=True)
    def synthNames(self) -> list[str]:
        return [definition.label for definition in self.definitions]

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
        return int(round(self._effective_local_reference()))

    @Property(float, notify=reverbLevelChanged)
    def reverbLevel(self) -> float:
        return self._reverb_level

    @Property(float, notify=reverbLivenessChanged)
    def reverbLiveness(self) -> float:
        return self._reverb_liveness

    @Property(float, notify=reverbDampingChanged)
    def reverbDamping(self) -> float:
        return self._reverb_damping

    @Property(bool, notify=reverbDrumsIncludedChanged)
    def reverbDrumsIncluded(self) -> bool:
        return self._reverb_drums

    @Property(float, notify=masterVolumeChanged)
    def masterVolume(self) -> float:
        return self._master_volume

    @Property(bool, notify=masterMutedChanged)
    def masterMuted(self) -> bool:
        return self._master_muted

    @Property("QVariantList", notify=midiInputTechsChanged)
    def midiInputTechs(self) -> list[dict[str, Any]]:
        return list(self._midi_input_tech_snapshot)

    def _queue_midi_tech_activity(self, key: str) -> None:
        self._queuedMidiTechActivity.emit(str(key))

    @Slot(str)
    def _mark_midi_tech_activity(self, key: str) -> None:
        self._midi_input_activity_until[str(key)] = (
            time.monotonic() + _MidiInputTechManager.ACTIVITY_SECONDS
        )
        self._refresh_midi_input_techs()
        if not self._midi_input_activity_timer.isActive():
            self._midi_input_activity_timer.start()

    def _refresh_midi_input_techs(self) -> None:
        snapshot = self._reader.status_snapshot(
            self._midi_input_activity_until
        )
        if snapshot != self._midi_input_tech_snapshot:
            self._midi_input_tech_snapshot = snapshot
            self.midiInputTechsChanged.emit()
        active = any(
            item.get("state") == "activity"
            for item in snapshot
        )
        if not active:
            self._midi_input_activity_timer.stop()

    def _queue_midi_control(self, channel: int, controller: int, value: int) -> None:
        """Move raw-MIDI thread callbacks onto this QObject's Qt thread."""
        key = self._midi_control_state.key(channel, controller)
        self._queuedControlChange.emit(
            max(1, min(16, int(channel))),
            key[1],
            max(0, min(self._midi_control_state.value_max_for_key(key), int(value))),
        )

    def _queue_midi_button(
        self,
        channel: int,
        note: int,
        velocity: int,
        is_on: bool,
    ) -> None:
        self._queuedButtonChange.emit(
            max(1, min(16, int(channel))),
            max(0, min(127, int(note))),
            max(0, min(127, int(velocity))) if is_on else 0,
        )

    @Slot(int, int, int)
    def process_midi_control(self, channel: int, controller: int, value: int) -> None:
        control_key = self._midi_control_state.key(channel, controller)
        with self._midi_control_lock:
            was_blue = control_key in self._midi_control_state.blue_since
            before = {
                (item["channel"], item["controller"])
                for item in self._midi_control_state.controls
            }
            changed, target, key = self._midi_control_state.observe(
                channel,
                controller,
                value,
                now=time.monotonic(),
            )
            if not changed or key is None:
                return
            after = {
                (item["channel"], item["controller"])
                for item in self._midi_control_state.controls
            }
            evicted = next(iter(before - after), None)
            self._write_cc_test_log({
                "event": "change",
                "channel": key[0],
                "controller": key[1],
                "clock": self._midi_control_state.clock,
                "capacity": self._midi_control_state.capacity,
                "count": len(self._midi_control_state.controls),
                "evicted": list(evicted) if evicted else None,
                "mapped": target is not None,
            })
            blue_cleared = (
                was_blue
                and control_key not in self._midi_control_state.blue_since
            )
        if blue_cleared:
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
            changed, target, key = self._midi_control_state.observe(
                channel,
                controller,
                max(0, min(127, int(velocity))),
                now=time.monotonic(),
            )
            if not changed or key is None:
                return
            self._write_cc_test_log({
                "event": "button-change",
                "channel": key[0],
                "note": key[1] - NOTE_BUTTON_OFFSET,
                "clock": self._midi_control_state.clock,
                "mapped": target is not None,
            })
            blue_cleared = (
                was_blue
                and control_key not in self._midi_control_state.blue_since
            )
        if blue_cleared:
            self._sync_blue_timer()
            self._bump_binding_state()
        if target is not None:
            if self._is_button_target(target):
                self._apply_button_target(target, int(velocity) > 0)
            else:
                self._apply_control_target(target, int(velocity), key)
        self._emit_binding_location_feedback(key, target)

    def _write_cc_test_log(self, record: dict[str, Any]) -> None:
        if getattr(self, "_midi_cc_test_log", None) is None:
            return
        with self._midi_cc_test_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, separators=(",", ":")) + "\n")

    @Slot(float, float, int, float, int, float)
    def testLogControlIndicatorLayout(
        self,
        bar_x: float,
        bar_width: float,
        capacity: int,
        row_width: float,
        count: int,
        last_right: float,
    ) -> None:
        with self._midi_control_lock:
            self._write_cc_test_log({
                "event": "layout",
                "barX": float(bar_x),
                "barWidth": float(bar_width),
                "capacity": int(capacity),
                "rowWidth": float(row_width),
                "count": int(count),
                "lastRight": float(last_right),
            })

    @Slot("QVariantList")
    def testLogControlIndicatorState(self, items: list[dict[str, Any]]) -> None:
        if self._midi_cc_test_log is None:
            return
        self._write_cc_test_log(
            {
                "event": "indicator-state",
                "items": [
                    {
                        "channel": int(item.get("channel", 0)),
                        "controller": int(item.get("controller", -1)),
                        "state": str(item.get("state", "idle")),
                        "evicting": bool(item.get("evicting", False)),
                    }
                    for item in items
                    if isinstance(item, dict)
                ],
            }
        )

    @Slot(int)
    def setControlIndicatorCapacity(self, capacity: int) -> None:
        """Match the LRU pool to the number of indicators visible in QML."""
        capacity = max(1, int(capacity))
        with self._midi_control_lock:
            self._midi_control_state.set_capacity(capacity)

    def _bump_binding_state(self) -> None:
        self._binding_version += 1
        with self._midi_control_lock:
            led_state = self._midi_control_state.omni_led_state()
            bindings = len(self._midi_control_state.bindings)
        self._write_cc_test_log(
            {
                "event": "binding-state",
                "version": self._binding_version,
                "omniLed": led_state,
                "bindings": bindings,
            }
        )
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
            self._write_cc_test_log({"event": "blue-expired"})
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
            self._write_cc_test_log({"event": "preset-feedback-expired"})
            self._bump_binding_state()

    def _definition_for_target(
        self,
        screen: str,
        instrument: str,
    ) -> Any | None:
        definitions = (
            self.definitions if screen == "midi" else tuple(self.owner._synths)
        )
        return next(
            (
                definition
                for definition in definitions
                if str(definition.key) == str(instrument)
            ),
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
            target["id"] = (
                f"{screen}:synth_control:{location}:{instrument}:{control}"
            )
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

        if screen == "omni" and kind in (
            "rhythm_tempo",
            "rhythm_fill_density",
            "bass_voicing",
            "bass_riff_selector",
        ):
            target["id"] = f"omni:{kind}"
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
                    for field in ("preset", "row", "level", "fill")
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
                (
                    item
                    for item in definition.controls
                    if str(item.key) == str(target["control"])
                ),
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
            value = math.exp(
                math.log(minimum)
                + position * (math.log(maximum) - math.log(minimum))
            )
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
        if (
            str(target.get("kind", "")) == "tuning_reference"
            and self._tuning_coupled
        ):
            other_screen = (
                "omni" if str(target.get("screen", "")) == "midi" else "midi"
            )
            other = self._normalize_control_target(
                {"screen": other_screen, "kind": "tuning_reference"}
            )
            if other is not None:
                targets.append(other)
        with self._midi_control_lock:
            return any(
                self._midi_control_state.is_target_bound(item)
                or self._midi_control_state.target_visual_state(item)
                == "preset-displaced"
                for item in targets
            )

    @Slot("QVariantMap", result=bool)
    def midiButtonTargetBlocked(self, raw: dict[str, Any]) -> bool:
        if self._applying_midi_control:
            return False
        target = self._normalize_control_target(raw)
        if target is None or not self._is_button_target(target):
            return False
        target_id = str(target["id"])
        with self._midi_control_lock:
            return bool(
                self._held_midi_button_targets
                and target_id not in self._held_midi_button_targets
            )

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
            definitions = (
                self.definitions if screen == "midi" else tuple(self.owner._synths)
            )
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
            self._apply_midi_setter(
                self.owner.setRhythmFillDensity, value
            )
        elif kind == "bass_voicing":
            self._apply_midi_setter(self.owner.setBassVoicingShift, value)
        elif kind == "bass_riff_selector":
            self._apply_midi_setter(self.owner.setBassRiffSelector, value)

        self._write_cc_test_log(
            {
                "event": "apply",
                "target": target["id"],
                "midiValue": int(midi_value),
                "mappedValue": float(value),
            }
        )

    @staticmethod
    def _is_button_target(target: dict[str, Any]) -> bool:
        return str(target.get("kind", "")) == "button"

    def _apply_button_target(
        self,
        target: dict[str, Any],
        pressed: bool,
    ) -> None:
        target_id = str(target["id"])
        with self._midi_control_lock:
            if pressed:
                self._held_midi_button_targets.add(target_id)
            else:
                self._held_midi_button_targets.discard(target_id)
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
                self._apply_midi_setter(
                    self.owner.toggleChordArpeggioDirection
                )

    @Slot(int, int)
    def selectControlIndicator(self, channel: int, controller: int) -> None:
        with self._midi_control_lock:
            self._midi_control_state.select_control((channel, controller))
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
                and self._midi_control_state.source_type(learned_key)
                == "pitch_bend"
                and not self._is_button_target(target)
            ):
                self._apply_control_target(
                    target,
                    self._midi_control_state.default_value_for_key(learned_key),
                    learned_key,
                )
            self._write_cc_test_log(
                {"event": "bind", "target": target["id"]}
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
    def controlTargetDoubleTapped(self, raw: dict[str, Any]) -> None:
        target = self._normalize_control_target(raw)
        if target is None:
            return
        with self._midi_control_lock:
            changed = self._midi_control_state.target_double_tapped(target)
        if changed:
            self._write_cc_test_log(
                {"event": "unbind", "reason": "double-tap", "target": target["id"]}
            )
            self._sync_blue_timer()
            self._bump_binding_state()

    @Slot("QVariantMap")
    def controlTargetMoved(self, raw: dict[str, Any]) -> None:
        target = self._normalize_control_target(raw)
        if target is None:
            return
        with self._midi_control_lock:
            changed = self._midi_control_state.target_moved(target)
        if changed:
            self._write_cc_test_log(
                {"event": "unbind", "reason": "move", "target": target["id"]}
            )
            self._sync_blue_timer()
            self._bump_binding_state()

    @Slot(int, int, int)
    def injectControl(self, channel: int, controller: int, value: int) -> None:
        self.process_midi_control(channel, controller, value)

    @Slot(int, int)
    def injectPitchBend(self, channel: int, value: int) -> None:
        self.process_midi_control(channel, PITCH_BEND_CONTROLLER, value)

    @Slot(int, int, int)
    def injectButton(self, channel: int, note: int, velocity: int) -> None:
        self.process_midi_button(channel, note, velocity)

    def control_bindings_snapshot(self, screen: str) -> list[dict[str, Any]]:
        with self._midi_control_lock:
            result = self._midi_control_state.serialize_bindings(screen)
        for entry in result:
            target = entry.get("target")
            if isinstance(target, dict):
                target.pop("id", None)
        return result

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
            self._write_cc_test_log(
                {
                    "event": "binding-location",
                    "channel": int(key[0]),
                    "controller": int(key[1]),
                    "sourceType": self._midi_control_state.source_type(key),
                    "screen": screen,
                    "preset": preset_number,
                    "active": active_target is not None,
                }
            )
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
                    data = json.loads(
                        path_for_number(preset_number).read_text(
                            encoding="utf-8"
                        )
                    )
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
                    locations.setdefault(key, set()).add(
                        (screen, preset_number)
                    )
        self._preset_binding_locations = {
            key: tuple(sorted(values))
            for key, values in locations.items()
        }

    @Slot(int)
    def refreshPresetBindingLocations(self, _preset_number: int) -> None:
        self._refresh_preset_binding_locations()

    def _normalized_binding_entries(
        self,
        screen: str,
        data: Any,
    ) -> list[tuple[tuple[int, int], dict[str, Any]]]:
        entries: list[tuple[tuple[int, int], dict[str, Any]]] = []
        if isinstance(data, list):
            for raw in data:
                if not isinstance(raw, dict):
                    continue
                target_data = raw.get("target")
                if not isinstance(target_data, dict):
                    continue
                target_data = dict(target_data)
                target_data["screen"] = str(screen)
                target = self._normalize_control_target(target_data)
                if target is None:
                    continue
                try:
                    channel = int(raw.get("channel", 0))
                    source_type = str(raw.get("source_type", "cc"))
                    if source_type == "pitch_bend":
                        controller = PITCH_BEND_CONTROLLER
                    elif source_type == "note_button":
                        controller = NOTE_BUTTON_OFFSET + int(raw.get("note", -1))
                    else:
                        controller = int(raw.get("controller", -1))
                    key = self._midi_control_state.key(channel, controller)
                except (TypeError, ValueError):
                    continue
                if not 1 <= key[0] <= 16:
                    continue
                if source_type == "pitch_bend" and key[1] != PITCH_BEND_CONTROLLER:
                    continue
                if source_type == "note_button" and not (
                    NOTE_BUTTON_OFFSET <= key[1] <= NOTE_BUTTON_OFFSET + 127
                ):
                    continue
                if source_type not in ("cc", "pitch_bend", "note_button"):
                    continue
                if source_type == "cc" and not 0 <= key[1] <= 127:
                    continue
                entries.append((key, target))
        return entries

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
            self._normalized_binding_entries(screen, incoming_bindings)
            if incoming_bindings is not None
            else []
        )
        with self._midi_control_lock:
            targets = [
                dict(target)
                for target in self._midi_control_state.bindings.values()
                if str(target.get("screen", "")) == screen
            ]
            coupled_tuning_bound = (
                self._tuning_coupled
                and any(
                    str(target.get("kind", "")) == "tuning_reference"
                    for target in self._midi_control_state.bindings.values()
                )
            )
            preset_conflicts = (
                self._midi_control_state.preset_conflict_target_ids(
                    incoming_entries
                )
                if incoming_entries
                else set()
            )
        if incoming_entries:
            targets.extend(
                dict(target)
                for _, target in incoming_entries
            )
        if self._tuning_coupled and (
            coupled_tuning_bound
            or any(
                str(target.get("kind", "")) == "tuning_reference"
                for target in targets
            )
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
                    rhythm.fill_density_index_by_rhythm[
                        rhythm.selected_index
                    ] = int(round(value))
                elif kind == "bass_voicing":
                    self.owner._bass_voicing_shift = int(round(value))
                elif kind == "bass_riff_selector":
                    candidates = self.owner._available_bass_riffs()
                    if candidates:
                        selected = max(
                            1,
                            min(len(candidates), int(round(value))),
                        )
                        self.owner._bass_riff_selector = selected
                        self.owner._active_bass_riff_id = (
                            candidates[selected - 1].riff_id
                        )
                        self.owner._bass_riff_context = (
                            self.owner._current_bass_riff_context()
                        )

    def replace_control_bindings(self, screen: str, data: Any) -> None:
        entries = self._normalized_binding_entries(screen, data)
        with self._midi_control_lock:
            self._midi_control_state.replace_screen_bindings(
                str(screen),
                entries,
            )
        self._sync_blue_timer()
        self._sync_preset_feedback_timer()
        self._bump_binding_state()
        self._write_cc_test_log(
            {
                "event": "load-bindings",
                "screen": str(screen),
                "count": len(entries),
            }
        )

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
            with self._midi_control_lock:
                return self._midi_control_state.visible_model()
        if not self._valid_row(row):
            return []
        return self._runtime(row).control_model("common")

    @Slot(int, result="QVariantList")
    def extraControls(self, row: int) -> list[dict[str, Any]]:
        if not self._valid_row(row):
            return []
        return self._runtime(row).control_model("extra")

    def _is_drum(self, row: int) -> bool:
        return self._runtime(row).selected_definition.key == MIDI_DRUM_KEY

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
        if self.manual_change_blocked(
            {"screen": "midi", "kind": "volume", "row": row}
        ):
            return
        value = max(0.0, min(1.0, float(value)))
        if math.isclose(value, self.volumes[row], abs_tol=1e-4):
            return
        self.volumes[row] = value
        if not self._is_drum(row):
            key = str(self._runtime(row).selected_definition.key)
            self.engine.set_row_volume(
                row,
                self.engine.balanced_volume(key, value),
            )
        self._emit_state()

    @Slot(int)
    def cycleChannel(self, row: int) -> None:
        if not self._valid_row(row):
            return
        row = int(row)
        current = self.channels[row]
        self.channels[row] = (
            1 if current == 0 else (0 if current == 16 else current + 1)
        )
        self._emit_state()

    def _preset_path(self, number: int) -> Path:
        return MIDI_PRESET_DIR / f"m{number}.json"

    def _ensure_preset_storage(self) -> None:
        MIDI_PRESET_DIR.mkdir(parents=True, exist_ok=True)
        for number in range(1, MIDI_PRESET_COUNT + 1):
            target = self._preset_path(number)
            if target.exists():
                continue
            factory = MIDI_FACTORY_DIR / f"m{number}.json"
            if factory.exists():
                data = json.loads(factory.read_text(encoding="utf-8"))
                _write_json_atomic(target, data)
        last = MIDI_PRESET_DIR / MIDI_LAST_PRESET_FILE
        if not last.exists():
            _write_json_atomic(last, {"preset": 1})

    def _load_startup_preset(self) -> None:
        number = 1
        try:
            data = json.loads(
                (MIDI_PRESET_DIR / MIDI_LAST_PRESET_FILE).read_text(
                    encoding="utf-8"
                )
            )
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
            "rows": rows,
            "tuning": {
                "mode": app_core.TUNING_MODE_NAMES[
                    self._tuning_mode_index
                ],
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
            str(definition.key): index
            for index, definition in enumerate(self.definitions)
        }
        if not isinstance(rows, list) or len(rows) != MIDI_ROW_COUNT:
            raise ValueError("MIDI preset must contain six rows")

        for index, row_data in enumerate(rows):
            if not isinstance(row_data, dict):
                raise ValueError("invalid MIDI preset row")
            selected = str(
                row_data.get("selected", self.definitions[0].key)
            )
            selected_index = key_to_index.get(selected, 0)
            runtime = SynthState(self.definitions, selected_index)
            runtime.load_preset(
                {
                    "selected": selected,
                    "parameters": row_data.get("parameters", {}),
                }
            )
            self.rows[index] = runtime
            channel = int(row_data.get("channel", index + 1))
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
            self._reverb_drums = bool(
                effects.get("reverb_drums", False)
            )
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
            str(definition.key): index
            for index, definition in enumerate(self.definitions)
        }
        selected = str(
            stored.get("selected", self.definitions[0].key)
        )
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
            min(16, int(stored.get("channel", row + 1))),
        )
        self.volumes[row] = max(
            0.0,
            min(1.0, float(stored.get("volume", 0.5))),
        )
        self.restore_control_values(protected)
        self._configure_row(row)
        self._emit_state()

    @Slot(bool)
    def setTuningCoupled(self, coupled: bool) -> None:
        coupled = bool(coupled)
        if coupled == self._tuning_coupled:
            return
        self._tuning_coupled = coupled
        self._stop_bend()
        self._bend_offset = 0.0
        self.tuningChanged.emit()

    def syncFromOmni(self) -> None:
        mode_index = int(self.owner.selectedTuningModeIndex)
        reference = float(self.owner.tuningReference)
        reference_blocked = self.manual_change_blocked(
            {"screen": "midi", "kind": "tuning_reference"}
        )
        changed = (
            mode_index != self._tuning_mode_index
            or (
                not reference_blocked
                and (
                    not math.isclose(
                        reference,
                        self._tuning_reference,
                        abs_tol=1e-9,
                    )
                    or not math.isclose(
                        self._bend_offset,
                        0.0,
                        abs_tol=1e-9,
                    )
                )
            )
        )
        self._tuning_mode_index = mode_index
        if not reference_blocked:
            self._tuning_reference = reference
            self._stop_bend()
            self._bend_offset = 0.0
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
        if self.manual_change_blocked(
            {"screen": "midi", "kind": "tuning_reference"}
        ):
            return
        value = max(415, min(466, int(value)))
        self._stop_bend()
        self._bend_offset = 0.0
        if math.isclose(
            self._tuning_reference,
            float(value),
            abs_tol=1e-9,
        ):
            self.tuningChanged.emit()
            return
        self._tuning_reference = float(value)
        self.tuningChanged.emit()

    def _effective_local_reference(self) -> float:
        return max(
            415.0,
            min(466.0, self._tuning_reference + self._bend_offset),
        )

    def _stop_bend(self) -> None:
        self._bend_timer.stop()
        self._bend_direction = 0
        self._bend_returning = False

    def _bend_tick(self) -> None:
        old = self._bend_offset
        if self._bend_returning:
            if abs(old) <= 1.0:
                self._bend_offset = 0.0
                self._stop_bend()
            else:
                self._bend_offset = old - math.copysign(1.0, old)
        else:
            candidate = old + float(self._bend_direction)
            self._bend_offset = max(
                415.0 - self._tuning_reference,
                min(466.0 - self._tuning_reference, candidate),
            )
        if not math.isclose(old, self._bend_offset, abs_tol=1e-9):
            self.tuningChanged.emit()

    @Slot(int)
    def beginPitchBend(self, direction: int) -> None:
        if self._tuning_coupled:
            self.owner.beginPitchBend(direction)
            return
        if self.manual_change_blocked(
            {"screen": "midi", "kind": "tuning_reference"}
        ):
            self._stop_bend()
            self._bend_offset = 0.0
            return
        self._bend_direction = 1 if int(direction) > 0 else -1
        self._bend_returning = False
        if not self._bend_timer.isActive():
            self._bend_timer.start()

    @Slot()
    def endPitchBend(self) -> None:
        if self._tuning_coupled:
            self.owner.endPitchBend()
            return
        if self.manual_change_blocked(
            {"screen": "midi", "kind": "tuning_reference"}
        ):
            self._stop_bend()
            self._bend_offset = 0.0
            return
        self._bend_direction = 0
        if math.isclose(self._bend_offset, 0.0, abs_tol=1e-9):
            self._stop_bend()
        else:
            self._bend_returning = True
            if not self._bend_timer.isActive():
                self._bend_timer.start()

    def _chord_context(self) -> tuple[int, set[int]]:
        if (
            self.owner._active_row >= 0
            and self.owner._active_root_semitone >= 0
        ):
            root = int(self.owner._active_root_semitone)
            chord = self.owner._chords[
                self.owner._row_chord_indexes[self.owner._active_row]
            ]
            return root, {
                (root + interval) % 12
                for interval in chord.intervals
            }
        return 0, {0, 4, 7}

    def _tune(self, note: int | float, root: int) -> float:
        reference_offset = 12.0 * math.log2(
            self._effective_local_reference() / 440.0
        )
        mode = app_core.TUNING_MODE_NAMES[self._tuning_mode_index]
        factor = 1.0
        if mode in self.owner._intonation_tables:
            note_pc = int(math.floor(float(note) + 0.5)) % 12
            factor = self.owner._intonation_tables[mode][root % 12][note_pc]
        return (
            float(note)
            + reference_offset
            + 12.0 * math.log2(factor)
        )

    def process_midi_note(
        self,
        channel: int,
        note: int,
        velocity: int,
        is_on: bool,
    ) -> None:
        root, _ = self._chord_context()
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

    @Slot(int, int, int, bool)
    def injectNote(
        self,
        channel: int,
        note: int,
        velocity: int,
        is_on: bool,
    ) -> None:
        self.process_midi_note(channel, note, velocity, is_on)

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
        if (
            not self._valid_row(row)
            or int(row) != self._preview_row
        ):
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
        if self.manual_change_blocked(
            {"screen": "midi", "kind": "reverb_level"}
        ):
            return
        value = max(0.0, min(MIDI_REVERB_MAX, float(value)))
        if math.isclose(value, self._reverb_level, abs_tol=1e-4):
            return
        self._reverb_level = value
        self.reverbLevelChanged.emit()
        self._apply_reverb()

    @Slot(float)
    def setReverbLiveness(self, value: float) -> None:
        if self.manual_change_blocked(
            {"screen": "midi", "kind": "reverb_liveness"}
        ):
            return
        value = max(0.0, min(1.0, float(value)))
        if math.isclose(value, self._reverb_liveness, abs_tol=1e-4):
            return
        self._reverb_liveness = value
        self.reverbLivenessChanged.emit()
        self._apply_reverb()

    @Slot(float)
    def setReverbDamping(self, value: float) -> None:
        if self.manual_change_blocked(
            {"screen": "midi", "kind": "reverb_damping"}
        ):
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
        if self.manual_change_blocked(
            {"screen": "midi", "kind": "master_volume"}
        ):
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
