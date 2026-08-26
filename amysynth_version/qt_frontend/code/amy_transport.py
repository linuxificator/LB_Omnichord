from __future__ import annotations

import json
import math
import queue
import socket
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import serial

from control_limits import clamp_control_value


AMY_PPQ = 48
RESET_SEQUENCER = 4096
RESET_ALL_OSCS = 8192
RESET_TIMEBASE = 16384
RESET_ALL_NOTES = 131072


DEFAULT_CONFIG: dict[str, Any] = {'serial': {'port': '/dev/serial0', 'baud': 1000000, 'write_timeout': 0.5},
 'synth_ids': {'drums': 0, 'bass': 1, 'strum': 2, 'manual_chord': 3, 'rhythm_chord': 4},
 'voices': {'drums': 4, 'bass': 1, 'strum': 2, 'manual_chord': 7, 'rhythm_chord': 4},
 'default_synths': {'chord': 'juno_004', 'strum': 'juno_028', 'bass': 'dx7_143'},
 'buses': {'main': 0, 'percussion': 1},
 'drums': {'velocity_gain': 5.0,
           'sample_map': {'bd_haus': {'preset': 1, 'note': 39},
                          'drum_bass_hard': {'preset': 1, 'note': 39},
                          'drum_bass_soft': {'preset': 1, 'note': 39},
                          'drum_snare_hard': {'preset': 2, 'note': 45},
                          'drum_snare_soft': {'preset': 5, 'note': 41},
                          'drum_cymbal_closed': {'preset': 6, 'note': 53},
                          'drum_cymbal_pedal': {'preset': 7, 'note': 61},
                          'drum_cymbal_open': {'preset': 7, 'note': 56},
                          'drum_tom_hi_soft': {'preset': 8, 'note': 73},
                          'drum_tom_mid_soft': {'preset': 8, 'note': 63},
                          'drum_tom_lo_soft': {'preset': 8, 'note': 61},
                          'elec_tick': {'preset': 4, 'note': 51},
                          'perc_bell': {'preset': 10, 'note': 69},
                          'perc_snap': {'preset': 9, 'note': 94}}},
 'rhythm': {'chord_gate_beats': 0.72,
            'bass_gate_beats': 0.3,
            'max_rhythm_chord_notes': 4,
            'max_sequencer_items': 256,
            'sequencer_reset_guard_ms': 10.0},
 'performance': {'strum_gate_ms': 800, 'one_shot_chord_gate_ms': 650, 'strum_tail_ms': 450},
 'synth_patches': {'juno_000': 0,
                   'juno_001': 1,
                   'juno_002': 2,
                   'juno_003': 3,
                   'juno_004': 4,
                   'juno_005': 5,
                   'juno_006': 6,
                   'juno_007': 7,
                   'juno_008': 8,
                   'juno_009': 9,
                   'juno_010': 10,
                   'juno_011': 11,
                   'juno_012': 12,
                   'juno_013': 13,
                   'juno_014': 14,
                   'juno_015': 15,
                   'juno_016': 16,
                   'juno_017': 17,
                   'juno_018': 18,
                   'juno_019': 19,
                   'juno_020': 20,
                   'juno_021': 21,
                   'juno_022': 22,
                   'juno_023': 23,
                   'juno_024': 24,
                   'juno_025': 25,
                   'juno_026': 26,
                   'juno_027': 27,
                   'juno_028': 28,
                   'juno_029': 29,
                   'juno_030': 30,
                   'juno_031': 31,
                   'juno_032': 32,
                   'juno_033': 33,
                   'juno_034': 34,
                   'juno_035': 35,
                   'juno_036': 36,
                   'juno_037': 37,
                   'juno_038': 38,
                   'juno_040': 40,
                   'juno_041': 41,
                   'juno_042': 42,
                   'juno_047': 47,
                   'juno_048': 48,
                   'juno_049': 49,
                   'juno_050': 50,
                   'juno_051': 51,
                   'juno_052': 52,
                   'juno_053': 53,
                   'juno_054': 54,
                   'juno_055': 55,
                   'juno_056': 56,
                   'juno_064': 64,
                   'juno_065': 65,
                   'juno_066': 66,
                   'juno_067': 67,
                   'juno_068': 68,
                   'juno_069': 69,
                   'juno_070': 70,
                   'juno_072': 72,
                   'juno_073': 73,
                   'juno_074': 74,
                   'juno_075': 75,
                   'juno_076': 76,
                   'juno_077': 77,
                   'juno_080': 80,
                   'juno_082': 82,
                   'juno_083': 83,
                   'juno_086': 86,
                   'juno_087': 87,
                   'juno_088': 88,
                   'juno_089': 89,
                   'juno_090': 90,
                   'juno_091': 91,
                   'juno_093': 93,
                   'juno_094': 94,
                   'juno_095': 95,
                   'juno_096': 96,
                   'juno_097': 97,
                   'juno_098': 98,
                   'juno_100': 100,
                   'juno_101': 101,
                   'juno_102': 102,
                   'juno_104': 104,
                   'juno_105': 105,
                   'juno_107': 107,
                   'juno_108': 108,
                   'juno_109': 109,
                   'juno_111': 111,
                   'juno_112': 112,
                   'juno_113': 113,
                   'juno_114': 114,
                   'juno_115': 115,
                   'juno_116': 116,
                   'juno_118': 118,
                   'juno_119': 119,
                   'juno_120': 120,
                   'juno_121': 121,
                   'juno_122': 122,
                   'juno_123': 123,
                   'juno_125': 125,
                   'juno_127': 127,
                   'dx7_128': 128,
                   'dx7_133': 133,
                   'dx7_138': 138,
                   'dx7_143': 143,
                   'dx7_148': 148,
                   'dx7_154': 154,
                   'dx7_160': 160,
                   'dx7_166': 166,
                   'dx7_172': 172,
                   'dx7_178': 178,
                   'dx7_184': 184,
                   'dx7_190': 190,
                   'dx7_196': 196,
                   'dx7_202': 202,
                   'dx7_213': 213,
                   'dx7_214': 214,
                   'dx7_215': 215,
                   'dx7_216': 216,
                   'dx7_244': 244,
                   'dx7_246': 246,
                   'juno_057': 57},
 'amy_max_oscs': 120,
 'debug': {'log_amy_commands': True,
           'amy_command_log': '~/.omnichord/amy_debug.log',
           'log_logical_events': True},
 'patch_compatibility': {'57': {'label': 'Juno A82 Resonance Funk',
                                'reason': 'All Juno sound-source amplitudes are zero; add a small '
                                          'noise excitation so the resonant VCF has input.',
                                'juno_noise_amp': 0.05},
                         '68': {'label': 'Juno B15 Harpsichord 1',
                                'reason': 'Factory patch requests 71265 Hz cutoff and Q 11.2; '
                                          'constrain the P4 fixed-point filter to a stable bright '
                                          'range.',
                                'juno_filter_hz': 6000.0,
                                'juno_resonance': 4.0},
                         '89': {'label': 'Juno B26 Harpsichord 2',
                                'reason': 'Factory filter base is at the unsafe top edge; keep the P4 filter stable.',
                                'juno_filter_hz': 6000.0},
                         '48': {'label': 'Juno A71 Sweep I',
                                'reason': 'Factory filter base is at the previous 18 kHz UI limit; keep below safety ceiling.',
                                'juno_filter_hz': 9000.0},
                         '74': {'label': 'Juno B23 Orchestral Pad',
                                'reason': 'Factory patch sets gather/output osc amp const to zero; '
                                          'AMY skips rendering when amp const is zero.',
                                'juno_output_amp': 1.0}}}


def _deep_merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in base.items():
        if isinstance(value, dict):
            result[key] = _deep_merge(value, {})
        elif isinstance(value, list):
            result[key] = list(value)
        else:
            result[key] = value

    for key, value in extra.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_amy_config(path: Path) -> dict[str, Any]:
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            user = json.load(handle)
        if not isinstance(user, dict):
            raise ValueError(f"{path} must contain a JSON object")
    else:
        user = {}
    return _deep_merge(DEFAULT_CONFIG, user)


class _DebugLog:
    """Asynchronous append-only AMY transport debug log.

    The UART writer must never wait on filesystem I/O just because debugging
    is enabled.  Producers only enqueue already-formatted text; a dedicated
    low-impact thread owns the file and writes the records.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        debug = config.get("debug", {})
        self.enabled = bool(debug.get("log_amy_commands", False))
        self.log_logical = bool(debug.get("log_logical_events", False))
        self.path: Path | None = None
        self._queue: queue.SimpleQueue[str | None] | None = None
        self._thread: threading.Thread | None = None

        if self.enabled:
            path = Path(str(debug.get(
                "amy_command_log",
                "~/.omnichord/amy_debug.log",
            ))).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)
            self.path = path
            self._queue = queue.SimpleQueue()
            self._thread = threading.Thread(
                target=self._run,
                name="amy-debug-log",
                daemon=True,
            )
            self._thread.start()
            self.write("SESSION", "--- AMY Omnichord start ---")

    def _run(self) -> None:
        if self.path is None or self._queue is None:
            return
        with self.path.open("a", encoding="utf-8", buffering=1) as handle:
            while True:
                line = self._queue.get()
                if line is None:
                    break
                handle.write(line)
            handle.flush()

    def write(self, kind: str, text: str) -> None:
        if not self.enabled or self._queue is None:
            return
        stamp = datetime.now().astimezone().isoformat(timespec="milliseconds")
        self._queue.put(f"{stamp} {kind:<12} {text}\n")

    def close(self) -> None:
        if self._queue is None or self._thread is None:
            return
        self._queue.put(None)
        self._thread.join(timeout=1.0)
        self._queue = None
        self._thread = None


class _SerialWriter:
    """Priority UART writer with independently cancelable low-priority lanes."""

    def __init__(self, port: str, baud: int, write_timeout: float, debug_log: _DebugLog | None = None) -> None:
        from collections import deque

        self.debug_log = debug_log
        self.serial = serial.Serial(
            port=port,
            baudrate=int(baud),
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0,
            write_timeout=float(write_timeout),
        )
        self._high = deque()
        self._low = deque()
        self._lane_generation: dict[str, int] = {}
        self._closed = False
        self._condition = threading.Condition()
        self._thread = threading.Thread(
            target=self._run,
            name="amy-uart-writer",
            daemon=True,
        )
        self._thread.start()

    @staticmethod
    def _line(command: str) -> bytes:
        command = command.strip()
        if not command.endswith("Z"):
            command += "Z"
        return (command + "\n").encode("ascii")

    def new_low_generation(self, lane: str) -> int:
        lane = str(lane)
        with self._condition:
            generation = self._lane_generation.get(lane, 0) + 1
            self._lane_generation[lane] = generation
            self._condition.notify_all()
            return generation

    def invalidate_all_low(self) -> None:
        with self._condition:
            for lane in list(self._lane_generation):
                self._lane_generation[lane] += 1
            self._low.clear()
            self._condition.notify_all()

    def high(self, command: str) -> None:
        with self._condition:
            if self._closed:
                return
            self._high.append(("command", command, 0.0))
            self._condition.notify()

    def delay(self, delay_seconds: float) -> None:
        """Insert a host-side guard before later high-priority commands."""
        with self._condition:
            if self._closed:
                return
            self._high.append((
                "delay",
                None,
                max(0.0, float(delay_seconds)),
            ))
            self._condition.notify()

    def low(self, lane: str, generation: int, command: str) -> None:
        with self._condition:
            if self._closed:
                return
            self._low.append((str(lane), int(generation), command))
            self._condition.notify()

    def _write(self, command: str, lane: str) -> None:
        if self.debug_log is not None:
            self.debug_log.write(f"TX-{lane}", command.strip())
        self.serial.write(self._line(command))

    def _run(self) -> None:
        while True:
            item_kind: str | None = None
            command: str | None = None
            delay_seconds = 0.0
            output_lane = "HIGH"

            with self._condition:
                while True:
                    if self._closed and not self._high and not self._low:
                        return

                    if self._high:
                        item_kind, command, delay_seconds = self._high.popleft()
                        break

                    # Drop stale lane generations without touching UART. This
                    # scan is intentionally cheap: there are only three rhythm
                    # lanes plus the occasional full-rhythm transaction lane.
                    while self._low:
                        low_lane, generation, low_command = self._low.popleft()
                        if generation != self._lane_generation.get(low_lane, 0):
                            continue
                        item_kind = "command"
                        command = low_command
                        output_lane = "LOW"
                        break

                    if item_kind is not None:
                        break

                    self._condition.wait()

            if item_kind == "delay":
                if self.debug_log is not None:
                    self.debug_log.write(
                        "GUARD", f"sleep {delay_seconds * 1000.0:.1f} ms"
                    )
                time.sleep(delay_seconds)
                continue

            if item_kind == "command" and command is not None:
                self._write(command, output_lane)

    def close(self) -> None:
        with self._condition:
            if self._closed:
                return
            # Do not call invalidate_all_low() while already holding this
            # non-reentrant Condition lock.
            for lane in list(self._lane_generation):
                self._lane_generation[lane] += 1
            self._low.clear()
            self._closed = True
            self._condition.notify_all()

        self._thread.join(timeout=1.0)
        self.serial.close()


class _UnixSocketWriter(_SerialWriter):
    """Priority writer for a separately managed local AMY service."""

    def __init__(
        self,
        socket_path: str,
        debug_log: _DebugLog | None = None,
    ) -> None:
        from collections import deque

        self.debug_log = debug_log
        # Linux supports packet-preserving SOCK_SEQPACKET. macOS exposes a
        # stream socket, so delimit each wire request with LF there.
        self._stream_transport = sys.platform == "darwin"
        socket_type = (
            socket.SOCK_STREAM
            if self._stream_transport
            else socket.SOCK_SEQPACKET
        )
        self.socket = socket.socket(socket.AF_UNIX, socket_type)
        try:
            # A missing or incompatible local service must not freeze the UI
            # process indefinitely.  Restore blocking mode after connecting;
            # normal AMY command delivery remains synchronous at the writer.
            self.socket.settimeout(5.0)
            self.socket.connect(str(socket_path))
            self.socket.settimeout(None)
        except BaseException:
            self.socket.close()
            raise
        self.serial = self.socket
        self._high = deque()
        self._low = deque()
        self._lane_generation: dict[str, int] = {}
        self._closed = False
        self._condition = threading.Condition()
        self._thread = threading.Thread(
            target=self._run,
            name="amy-socket-writer",
            daemon=True,
        )
        self._thread.start()

    def _write(self, command: str, lane: str) -> None:
        command = command.strip()
        if not command.endswith("Z"):
            command += "Z"
        if self.debug_log is not None:
            self.debug_log.write(f"TX-{lane}", command)
        framing = "\n" if self._stream_transport else ""
        self.socket.sendall((command + framing).encode("ascii"))

    def close(self) -> None:
        super().close()


class _QtLocalSocketWriter(_SerialWriter):
    """LF-framed Qt local IPC writer used by the native Windows package.

    QLocalSocket maps this name to a Windows named pipe.  The object is
    created, connected, written and closed on the existing dedicated writer
    thread so its QObject thread affinity is never crossed.
    """

    def __init__(
        self,
        server_name: str,
        debug_log: _DebugLog | None = None,
    ) -> None:
        from collections import deque

        self.debug_log = debug_log
        self.server_name = str(server_name)
        self._high = deque()
        self._low = deque()
        self._lane_generation: dict[str, int] = {}
        self._closed = False
        self._condition = threading.Condition()
        self._connect_complete = threading.Event()
        self._connect_error: BaseException | None = None
        self._local_socket: Any | None = None
        self._thread = threading.Thread(
            target=self._run,
            name="amy-local-writer",
            daemon=True,
        )
        self._thread.start()

        if not self._connect_complete.wait(5.5):
            with self._condition:
                self._closed = True
                self._condition.notify_all()
            self._thread.join(timeout=1.0)
            raise TimeoutError(
                f"timed out connecting to local AMY service {self.server_name!r}"
            )
        if self._connect_error is not None:
            raise ConnectionError(str(self._connect_error)) from self._connect_error

    def _run(self) -> None:
        from PySide6.QtNetwork import QLocalSocket

        local_socket = QLocalSocket()
        self._local_socket = local_socket
        try:
            local_socket.connectToServer(self.server_name)
            if not local_socket.waitForConnected(5000):
                raise ConnectionError(local_socket.errorString())
            self._connect_complete.set()
            super()._run()
        except BaseException as exc:
            self._connect_error = exc
            with self._condition:
                self._closed = True
                self._high.clear()
                self._low.clear()
                self._condition.notify_all()
        finally:
            local_socket.close()
            self._connect_complete.set()

    def _write(self, command: str, lane: str) -> None:
        command = command.strip()
        if not command.endswith("Z"):
            command += "Z"
        if self.debug_log is not None:
            self.debug_log.write(f"TX-{lane}", command)
        payload = (command + "\n").encode("ascii")
        local_socket = self._local_socket
        if local_socket is None:
            raise ConnectionError("local AMY socket is not connected")
        if local_socket.write(payload) != len(payload):
            raise OSError(local_socket.errorString())
        deadline = time.monotonic() + 5.0
        while local_socket.bytesToWrite() > 0:
            remaining_ms = max(1, int((deadline - time.monotonic()) * 1000))
            if time.monotonic() >= deadline or not local_socket.waitForBytesWritten(
                remaining_ms
            ):
                raise TimeoutError(local_socket.errorString())

    def close(self) -> None:
        with self._condition:
            if not self._closed:
                for lane in list(self._lane_generation):
                    self._lane_generation[lane] += 1
                self._low.clear()
                self._closed = True
                self._condition.notify_all()
        self._thread.join(timeout=1.0)


class _TaggedSequencerLane:
    """One logical AMY sequencer lane backed by a reserved user-tag range.

    AMY tags are one-to-one with stored events. Reusing a tag replaces the
    previous event; H0,0,<tag> clears exactly that event. A lane therefore owns
    a contiguous range and assigns one deterministic tag to every scheduled
    event. The high-water mark is intentionally monotonic: if a queued update
    is superseded halfway through, the next update still clears every tag that
    could contain an older definition.
    """

    def __init__(
        self,
        name: str,
        start: int,
        count: int,
        writer: _SerialWriter,
    ) -> None:
        self.name = str(name)
        self.start = int(start)
        self.count = int(count)
        self.writer = writer
        self.high_water = 0
        if self.start < 0 or self.count <= 0:
            raise ValueError(f"invalid sequencer tag range for {self.name}")

    @property
    def end(self) -> int:
        return self.start + self.count

    def commands(
        self,
        events: list[tuple[int, int, str]],
    ) -> list[str]:
        if len(events) > self.count:
            raise ValueError(
                f"sequencer lane {self.name} requires {len(events)} tags; "
                f"range capacity is {self.count}"
            )

        previous_high_water = self.high_water
        self.high_water = max(self.high_water, len(events))
        commands: list[str] = []

        for index, (tick, period, body) in enumerate(events):
            tag = self.start + index
            period_value = max(1, int(period))
            tick_value = max(0, int(tick)) % period_value
            body = str(body)
            if body.endswith("Z"):
                body = body[:-1]
            commands.append(
                f"H{tick_value},{period_value},{tag}{body}Z"
            )

        # Clear tags no longer used by the new pattern. Keep using the maximum
        # ever occupied slot so an interrupted earlier update cannot leave a
        # stale event beyond the current event count.
        for index in range(len(events), max(previous_high_water, self.high_water)):
            commands.append(f"H0,0,{self.start + index}Z")

        return commands

    def enqueue(self, events: list[tuple[int, int, str]]) -> None:
        generation = self.writer.new_low_generation(self.name)
        for command in self.commands(events):
            self.writer.low(self.name, generation, command)

    def clear(self) -> None:
        self.enqueue([])


class AmySerialClient:
    """Translate the Omnichord's logical events to native AMY wire commands.

    Five AMY synth instances are kept allocated for the lifetime of the app:

        0 drums
        1 bass
        2 strum
        3 manual chords
        4 rhythm chords

    Manual and rhythm chords always use the same patch/settings, but their
    voice pools and note lifetimes are independent.
    """

    def __init__(
        self,
        config: dict[str, Any],
        addresses: dict[str, str],
        *,
        writer_factory: Any | None = None,
    ) -> None:
        self.config = config
        self.addr = addresses

        self.debug_log = _DebugLog(config)
        if self.debug_log.path is not None:
            print(
                f"AMY command log: {self.debug_log.path}",
                flush=True,
            )
        if writer_factory is None:
            serial_cfg = config["serial"]
            self.writer = _SerialWriter(
                str(serial_cfg["port"]),
                int(serial_cfg["baud"]),
                float(serial_cfg.get("write_timeout", 0.5)),
                self.debug_log,
            )
        else:
            self.writer = writer_factory(self.debug_log)

        ids = config["synth_ids"]
        self.synth_id = {
            "drums": int(ids["drums"]),
            "bass": int(ids["bass"]),
            "strum": int(ids["strum"]),
            "manual_chord": int(ids["manual_chord"]),
            "rhythm_chord": int(ids["rhythm_chord"]),
        }
        voices = config["voices"]
        self.voice_count = {
            "drums": int(voices["drums"]),
            "bass": int(voices["bass"]),
            "strum": int(voices["strum"]),
            "manual_chord": int(voices["manual_chord"]),
            "rhythm_chord": int(voices["rhythm_chord"]),
        }

        defaults = config.get("default_synths", {})
        self.selected_synth = {
            "chord": str(defaults.get("chord", "juno_004")),
            "strum": str(defaults.get("strum", "juno_028")),
            "bass": str(defaults.get("bass", "dx7_143")),
        }
        self.patch_map = {
            str(key): int(value)
            for key, value in config["synth_patches"].items()
        }
        self.synth_params: dict[str, dict[str, float]] = {
            "chord": {}, "strum": {}, "bass": {}
        }
        self._adsr_override_active = {
            "chord": False, "strum": False, "bass": False
        }
        self.volume = {
            "chord": 0.5,
            "strum": 0.5,
            "bass": 0.5,
            "drums": 0.5,
        }
        buses = config.get("buses", {})
        self.bus_id = {
            "drums": int(buses.get("drums", 0)),
            "bass": int(buses.get("bass", 1)),
            "strum": int(buses.get("strum", 2)),
            "chord": int(buses.get("chord", 3)),
        }
        bus_values = tuple(self.bus_id.values())
        if (
            len(set(bus_values)) != 4
            or any(bus < 0 or bus > 3 for bus in bus_values)
        ):
            raise ValueError(
                "drums, bass, strum and chord must use four distinct AMY buses 0..3"
            )
        self.reverb = {
            "level": 0.0,
            "liveness": 0.5,
            "damping": 0.5,
            "drums": False,
        }

        self.chord_notes: list[float] = []
        self.bass_notes: list[float] = []
        self.rhythm_config: dict[str, Any] | None = None
        self.rhythm_running = False
        self.rhythm_chord_enabled = False
        self.bass_running = True
        self._scheduled_rhythm_id: str | None = None

        tag_config = config.get("rhythm", {}).get("tag_ranges", {})
        max_tags = int(config.get("rhythm", {}).get("max_sequencer_tags", 256))
        self._sequencer_lanes: dict[str, _TaggedSequencerLane] = {}
        occupied: set[int] = set()
        for lane_name in ("drums", "bass", "chords"):
            raw_range = tag_config.get(lane_name, {})
            lane = _TaggedSequencerLane(
                lane_name,
                int(raw_range.get("start", -1)),
                int(raw_range.get("count", 0)),
                self.writer,
            )
            if lane.end > max_tags:
                raise ValueError(
                    f"sequencer lane {lane_name} ends at tag {lane.end - 1}, "
                    f"but max_sequencer_tags is {max_tags}"
                )
            tags = set(range(lane.start, lane.end))
            overlap = tags & occupied
            if overlap:
                raise ValueError(
                    f"sequencer tag ranges overlap at {min(overlap)}"
                )
            occupied |= tags
            self._sequencer_lanes[lane_name] = lane

        self._configured_synths: set[int] = set()
        self._synth_generation: dict[int, int] = {
            synth: 0 for synth in self.synth_id.values()
        }

        # Conservative oscillator-budget guard.  Every synth in the shipped
        # catalogue is Juno (6 oscs/voice) or DX7 (8 oscs/voice).  Drums use
        # one PCM osc per voice in v3.2.
        worst_case_oscs = (
            self.voice_count["drums"]
            + 8 * (
                self.voice_count["bass"]
                + self.voice_count["strum"]
                + self.voice_count["manual_chord"]
                + self.voice_count["rhythm_chord"]
            )
        )
        max_oscs = int(config.get("amy_max_oscs", 120))
        if worst_case_oscs > max_oscs:
            raise ValueError(
                f"AMY voice configuration can require {worst_case_oscs} "
                f"oscillators, but amy_max_oscs is {max_oscs}"
            )

        # One physical manual-chord synth.  The logical id is retained so a
        # delayed release from an older touch can never silence a newer chord.
        self._manual_active_id: str | None = None
        self._manual_active_notes: list[float] = []

        # Strum is deliberately host-voice-managed.  AMY's synth voice manager
        # keeps only a small fixed bookkeeping pool for stolen notes; a fast
        # seven-octave sweep can otherwise overflow it before delayed note-offs
        # arrive.  Keep at most the configured synth-2 voice count active and
        # use one inactivity tail release for the entire strum synth.
        self._strum_active_notes: list[float] = []
        self._strum_tail_token = 0
        self._strum_lock = threading.Lock()

        # Start from a known AMY allocation state.  This is intentionally
        # RESET_ALL_OSCS, not RESET_AMY: the latter stops/restarts the whole
        # engine inside the parser.  RESET_ALL_OSCS clears oscillators and the
        # synth/instrument table at an audio-block boundary while keeping the
        # running audio engine and UART path alive.
        self._wire("zY0Z")
        self._wire(f"S{RESET_SEQUENCER | RESET_ALL_OSCS}Z")
        self.writer.delay(0.020)
        self._configured_synths.clear()
        self._configure_fixed_synths()

    def _wire(self, command: str) -> None:
        self.writer.high(command)

    @staticmethod
    def _f(value: float) -> str:
        return f"{float(value):.9g}"

    def _bump_synth_generation(self, synth: int) -> None:
        self._synth_generation[synth] = self._synth_generation.get(synth, 0) + 1

    def _note_off_later(
        self,
        synth: int,
        note: float | None,
        delay_ms: float,
    ) -> None:
        generation = self._synth_generation.get(synth, 0)

        def note_off() -> None:
            # A panic or patch reload invalidates delayed releases that belong
            # to the old synth state.  Otherwise an old strum release could
            # silence a newly-triggered note of the same pitch.
            if self._synth_generation.get(synth, 0) != generation:
                return
            if note is None:
                self._wire(f"l0i{synth}Z")
            else:
                self._wire(f"n{self._f(note)}l0i{synth}Z")

        timer = threading.Timer(
            max(0.001, float(delay_ms) / 1000.0),
            note_off,
        )
        timer.daemon = True
        timer.start()

    def _patch(self, role: str) -> int:
        name = self.selected_synth[role]
        if name not in self.patch_map:
            print(
                f"AMY warning: unknown synth key {name!r}; using patch 0",
                flush=True,
            )
        return int(self.patch_map.get(name, 0))

    def _role_synth_ids(self, role: str) -> tuple[int, ...]:
        if role == "chord":
            return (
                self.synth_id["manual_chord"],
                self.synth_id["rhythm_chord"],
            )
        return (self.synth_id[role],)

    def _voice_count_for_synth(self, synth: int) -> int:
        for role, synth_id in self.synth_id.items():
            if synth_id == synth:
                return self.voice_count[role]
        raise KeyError(synth)

    def _patch_compatibility_commands(
        self, patch: int, synth: int
    ) -> list[str]:
        """Small target-side corrections for known factory-patch edge cases.

        These do not replace the AMY patches.  They are sent immediately after
        the factory K command, so the original patch remains the source of all
        other settings.  Values live in amy_config.json for easy testing.
        """
        raw = self.config.get("patch_compatibility", {}).get(str(patch), {})
        if not isinstance(raw, dict):
            return []
        out: list[str] = []
        if "juno_noise_amp" in raw:
            out.append(f"v5a{self._f(float(raw['juno_noise_amp']))}i{synth}Z")
        if "juno_filter_hz" in raw:
            value = clamp_control_value("filter_hz", float(raw["juno_filter_hz"]))
            out.append(f"v0F{self._f(value)}i{synth}Z")
        if "juno_resonance" in raw:
            value = clamp_control_value("resonance", float(raw["juno_resonance"]))
            out.append(f"v0R{self._f(value)}i{synth}Z")
        if "juno_output_amp" in raw:
            out.append(f"v0a{self._f(float(raw['juno_output_amp']))}i{synth}Z")
        return out

    def _apply_patch_compatibility(self, patch: int, synth: int) -> None:
        for command in self._patch_compatibility_commands(patch, synth):
            self._wire(command)

    def _bus_for_synth(self, synth: int) -> int:
        if synth == self.synth_id["drums"]:
            return self.bus_id["drums"]
        if synth == self.synth_id["bass"]:
            return self.bus_id["bass"]
        if synth == self.synth_id["strum"]:
            return self.bus_id["strum"]
        if synth in (
            self.synth_id["manual_chord"],
            self.synth_id["rhythm_chord"],
        ):
            return self.bus_id["chord"]
        raise KeyError(f"no AMY bus assigned for synth {synth}")

    def _route_synth_bus(self, synth: int) -> None:
        self._wire(f"i{synth}iy{self._bus_for_synth(synth)}Z")

    def _reverb_command(self, bus: int, *, enabled: bool) -> str:
        level = self.reverb["level"] if enabled else 0.0
        return (
            f"y{int(bus)}h{self._f(level)},"
            f"{self._f(self.reverb['liveness'])},"
            f"{self._f(self.reverb['damping'])}Z"
        )

    def _reverb_enabled_for_bus(self, bus: int) -> bool:
        if int(bus) == self.bus_id["drums"]:
            return bool(self.reverb["drums"])
        return True

    def _apply_reverb_bus(self, bus: int) -> None:
        self._wire(
            self._reverb_command(
                int(bus),
                enabled=self._reverb_enabled_for_bus(int(bus)),
            )
        )

    def _apply_reverb_buses(self) -> None:
        # Every musical role owns its own bus so loading a Juno patch cannot
        # leak the patch's bus-level EQ/chorus/reverb into another role.
        # The user reverb is intentionally shared across the three melodic
        # buses; drums receive the same room only when DRM is enabled.
        for bus in (
            self.bus_id["drums"],
            self.bus_id["bass"],
            self.bus_id["strum"],
            self.bus_id["chord"],
        ):
            self._apply_reverb_bus(bus)

    def _set_reverb(self, value: Any) -> None:
        if not isinstance(value, dict):
            return
        updated = {
            "level": max(0.0, min(1.0, float(value.get("level", self.reverb["level"])))),
            "liveness": max(0.0, min(1.0, float(value.get("liveness", self.reverb["liveness"])))),
            "damping": max(0.0, min(1.0, float(value.get("damping", self.reverb["damping"])))),
            "drums": bool(value.get("drums", self.reverb["drums"])),
        }
        if updated == self.reverb:
            return
        self.reverb = updated
        self._apply_reverb_buses()

    def _configure_one_synth(self, role: str, synth: int) -> None:
        self._bump_synth_generation(synth)
        patch = self._patch(role)
        bus = self._bus_for_synth(synth)
        already_configured = synth in self._configured_synths
        if already_configured:
            # The synth already owns its dedicated bus. Current AMY preserves
            # that bus across a repatch, so patch-level EQ/chorus remain local.
            self._wire(f"l0i{synth}Z")
            self._wire(f"K{patch}i{synth}Z")
        else:
            voices = self._voice_count_for_synth(synth)
            # Put the bus in the allocation/patch event itself. Many Juno ROM
            # patches contain bus FX; without iy here those startup FX briefly
            # (and persistently) land on default bus 0 before a later route.
            self._wire(f"K{patch}i{synth}iv{voices}iy{bus}Z")
            self._configured_synths.add(synth)

            guard_ms = float(
                self.config.get("performance", {}).get(
                    "synth_alloc_guard_ms", 10.0
                )
            )
            self.writer.delay(max(0.0, guard_ms) / 1000.0)
        self._apply_patch_compatibility(patch, synth)
        self._route_synth_bus(synth)
        level = self.volume[role] * self._instrument_level(role)
        self._wire(f"i{synth}iV{self._f(level)}Z")
        # A patch may carry its own reverb setting for this bus. The Omnichord
        # reverb controls are the application-level authority, so restore only
        # this role's room after the patch is loaded. Other role buses are not
        # touched.
        self._apply_reverb_bus(bus)

        if already_configured:
            # A ROM repatch is not a cheap parameter edit in AMY: it releases,
            # resets and reallocates the voice's oscillator block.  Keep the
            # next patch transaction out of the same audio-block burst.  This
            # is especially important during startup/preset restore, where the
            # chord, strum and bass patches are otherwise queued back-to-back.
            guard_ms = float(
                self.config.get("performance", {}).get(
                    "synth_alloc_guard_ms", 10.0
                )
            )
            self.writer.delay(max(0.0, guard_ms) / 1000.0)

    def _configure_synth(self, role: str) -> None:
        # Keep each patch load and its complete parameter restore adjacent in
        # the AMY command stream.  This is especially important for chord,
        # which owns both the manual and rhythm synth instances.
        for synth in self._role_synth_ids(role):
            self._configure_one_synth(role, synth)
            for command in self._param_commands_for_synth(role, synth):
                self._wire(command)

    def _configure_fixed_synths(self) -> None:
        # Drums deliberately do NOT use legacy patch 258 here.  That patch
        # reserves 32 oscillators merely to implement the complete GM-note
        # lookup table.  The Omnichord needs only a handful of simultaneous
        # hits, so synth 0 is a small polyphonic PCM synth: one oscillator per
        # voice, preconfigured as PCM.  Each hit supplies preset+native note.
        drums = self.synth_id["drums"]
        drum_voices = self.voice_count["drums"]
        self._bump_synth_generation(drums)
        self._wire(f"i{drums}iv{drum_voices}in1Z")
        self._wire(f"v0w7i{drums}Z")
        self._route_synth_bus(drums)
        self._wire(f"i{drums}iV{self._f(self.volume['drums'])}Z")
        self._configured_synths.add(drums)

        self._configure_synth("bass")
        self._configure_synth("strum")
        self._configure_synth("chord")
        self._apply_reverb_buses()

    @staticmethod
    def _params_from_list(values: Any) -> dict[str, float]:
        if not isinstance(values, (list, tuple)):
            return {}
        result: dict[str, float] = {}
        for index in range(0, len(values) - 1, 2):
            try:
                key = str(values[index])
                result[key] = clamp_control_value(key, float(values[index + 1]))
            except (TypeError, ValueError):
                pass
        return result

    def _param_commands_for_synth(
        self,
        role: str,
        synth: int,
        parameter_keys: set[str] | None = None,
    ) -> list[str]:
        """Build engine-relevant control commands for one synth.

        Missing controls leave the current patch value alone.  Negative values
        are accepted only as a legacy "unset" sentinel and are never exposed
        by the current UI.  When parameter_keys is provided, emit commands
        only for those controls so moving one slider cannot resend unrelated
        filter/LFO/envelope settings.

        Juno: osc0 is VCF/VCA gather, osc1 is the LFO, osc2 pulse,
        osc3 saw, osc4 sub.  DX7: osc0 is ALGO output, osc1 is its LFO.
        """
        patch = self._patch(role)
        params = self.synth_params[role]
        commands: list[str] = []

        def nonneg(name: str) -> float | None:
            if parameter_keys is not None and name not in parameter_keys:
                return None
            value = params.get(name)
            if value is None or value < 0:
                return None
            return clamp_control_value(name, float(value))

        lfo_hz = nonneg("lfo_hz")
        portamento = nonneg("portamento_ms")

        if 0 <= patch <= 127:  # Juno
            cutoff = nonneg("filter_hz")
            if cutoff is not None:
                cutoff = clamp_control_value("filter_hz", cutoff)
                commands.append(f"v0F{self._f(cutoff)}i{synth}Z")

            resonance = nonneg("resonance")
            if resonance is not None:
                resonance = clamp_control_value("resonance", resonance)
                commands.append(f"v0R{self._f(resonance)}i{synth}Z")

            if lfo_hz is not None:
                commands.append(
                    f"v1f{self._f(clamp_control_value('lfo_hz', lfo_hz))}i{synth}Z"
                )

            # Merely changing LFO frequency is inaudible when the patch has
            # zero modulation depth.  These controls explicitly route osc1
            # into the parameters the Juno architecture actually uses.
            vibrato = nonneg("vibrato_depth")
            if vibrato is not None:
                depth = max(0.0, min(0.05, vibrato))
                for osc in (2, 3, 4):
                    commands.append(f"v{osc}f,,,,,{self._f(depth)}i{synth}Z")

            vcf_lfo = nonneg("filter_lfo_depth")
            if vcf_lfo is not None:
                depth = clamp_control_value("filter_lfo_depth", vcf_lfo)
                commands.append(f"v0F,,,,,{self._f(depth)}i{synth}Z")

            pulse_width = nonneg("pulse_width")
            if pulse_width is not None:
                duty = max(0.05, min(0.95, pulse_width))
                commands.append(f"v2d{self._f(duty)}i{synth}Z")

            pwm_depth = nonneg("pwm_depth")
            if pwm_depth is not None:
                depth = max(0.0, min(0.45, pwm_depth))
                commands.append(f"v2d,,,,,{self._f(depth)}i{synth}Z")

            if portamento is not None:
                ms = max(0, int(round(portamento)))
                for osc in (2, 3, 4):
                    commands.append(f"v{osc}m{ms}i{synth}Z")

            attack = nonneg("attack_ms")
            decay = nonneg("decay_ms")
            sustain = nonneg("sustain")
            release = nonneg("release_ms")
            if any(v is not None for v in (attack, decay, sustain, release)):
                fields = [
                    self._f(attack) if attack is not None else "",
                    "",
                    self._f(decay) if decay is not None else "",
                    self._f(max(0.0, min(1.0, sustain)))
                    if sustain is not None else "",
                    self._f(release) if release is not None else "",
                    "",
                ]
                commands.append(f"v0A{','.join(fields)}i{synth}Z")

        elif 128 <= patch <= 255:  # DX7 / ALGO
            algorithm = nonneg("algorithm")
            if algorithm is not None:
                algorithm_i = max(1, min(32, int(round(algorithm))))
                commands.append(f"v0o{algorithm_i}i{synth}Z")

            feedback = nonneg("feedback")
            if feedback is not None:
                commands.append(
                    f"v0b{self._f(max(0.0, min(1.0, feedback)))}i{synth}Z"
                )

            if lfo_hz is not None:
                commands.append(
                    f"v1f{self._f(clamp_control_value('lfo_hz', lfo_hz))}i{synth}Z"
                )

            vibrato = nonneg("vibrato_depth")
            if vibrato is not None:
                depth = max(0.0, min(0.05, vibrato))
                commands.append(f"v0f,,,,,{self._f(depth)}i{synth}Z")

            if portamento is not None:
                commands.append(
                    f"v0m{max(0, int(round(portamento)))}i{synth}Z"
                )

            # This is a global ALGO-output ADSR layered on top of the DX7
            # operators' native envelopes.  The native operator envelopes are
            # intentionally left intact.  If any ADSR member changed, resend
            # the complete global envelope because it belongs to us rather than
            # to the factory DX7 operator patch.
            adsr_keys = {
                "attack_ms", "decay_ms", "sustain", "release_ms"
            }
            if (
                parameter_keys is None
                or bool(parameter_keys & adsr_keys)
            ):
                def current_nonneg(name: str) -> float | None:
                    value = params.get(name)
                    if value is None or value < 0:
                        return None
                    return clamp_control_value(name, float(value))

                attack = current_nonneg("attack_ms")
                decay = current_nonneg("decay_ms")
                sustain = current_nonneg("sustain")
                release = current_nonneg("release_ms")
                if any(
                    v is not None
                    for v in (attack, decay, sustain, release)
                ):
                    a = 0.0 if attack is None else max(0.0, attack)
                    d = 0.0 if decay is None else max(0.0, decay)
                    sus = (
                        1.0
                        if sustain is None
                        else max(0.0, min(1.0, sustain))
                    )
                    r = 60000.0 if release is None else max(0.0, release)
                    commands.append(
                        f"v0a,,,1A{self._f(a)},1,{self._f(d)},{self._f(sus)},"
                        f"{self._f(r)},0i{synth}Z"
                    )

        return commands

    def _adsr_is_active(self, role: str) -> bool:
        params = self.synth_params[role]
        return any(
            params.get(key, -1.0) >= 0
            for key in ("attack_ms", "decay_ms", "sustain", "release_ms")
        )

    def _sync_synth_params(
        self,
        role: str,
        synth_ids: tuple[int, ...] | None = None,
        parameter_keys: set[str] | None = None,
    ) -> None:
        targets = self._role_synth_ids(role) if synth_ids is None else synth_ids
        for synth in targets:
            for command in self._param_commands_for_synth(
                role, synth, parameter_keys
            ):
                self._wire(command)

    def _apply_supported_params(
        self,
        role: str,
        parameter_keys: set[str] | None = None,
    ) -> None:
        self._sync_synth_params(role, parameter_keys=parameter_keys)

    def _restore_manual_chord_after_patch(self) -> None:
        if self._manual_active_id is None:
            return
        synth = self.synth_id["manual_chord"]
        for note in self._manual_active_notes:
            self._wire(f"n{self._f(note)}l1i{synth}Z")

    @staticmethod
    def _changed_param_keys(
        old_params: dict[str, float],
        new_params: dict[str, float],
    ) -> set[str]:
        changed: set[str] = set()
        for key in set(old_params) | set(new_params):
            old_value = old_params.get(key)
            new_value = new_params.get(key)
            if old_value is None or new_value is None:
                if old_value != new_value:
                    changed.add(key)
                continue
            if not math.isclose(
                float(old_value),
                float(new_value),
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                changed.add(key)
        return changed

    def _apply_synth_state(
        self,
        role: str,
        name: str,
        params: dict[str, float],
        *,
        force_patch: bool = False,
    ) -> None:
        """Converge one logical synth role onto the supplied complete state.

        This is the only normal synth-state mutation path on the AMY side.
        Startup/preset messages, instrument switches and slider edits all arrive
        here as the same complete state. A same-instrument update is diffed and
        changes only affected parameters; an instrument change performs the
        ordered patch transaction.
        """
        name = str(name)
        if name not in self.patch_map:
            print(f"AMY warning: refusing unknown synth {name!r}", flush=True)
            return

        old_params = dict(self.synth_params[role])
        new_params = dict(params)
        changed_keys = self._changed_param_keys(old_params, new_params)
        removed_keys = set(old_params) - set(new_params)
        name_changed = force_patch or self.selected_synth[role] != name
        was_active = self._adsr_override_active.get(role, False)

        if role == "strum" and name_changed:
            self._cancel_strum_tail()
            self._wire(f"l0i{self.synth_id['strum']}Z")

        # Missing keys mean "return this control to the native patch".
        # AMY has no generic per-control undo operation, so convergence in that
        # case is a deliberate patch reload followed by the remaining sparse
        # overrides. This keeps defaults, preset loads, UI edits and switch-back
        # restoration on one transaction path.
        patch_required = name_changed or bool(removed_keys)

        if role == "chord" and patch_required:
            # Silence only the currently sounding automatic chord. Tagged
            # synth-4 events remain scheduled and use the new patch when they
            # next fire; drums, bass and transport are untouched.
            self._wire(f"l0i{self.synth_id['rhythm_chord']}Z")

        self.selected_synth[role] = name
        self.synth_params[role] = new_params
        now_active = self._adsr_is_active(role)
        self._adsr_override_active[role] = now_active
        patch_required = patch_required or (was_active and not now_active)

        if patch_required:
            self._configure_synth(role)
        elif changed_keys:
            self._apply_supported_params(role, changed_keys)

        if role == "chord" and patch_required:
            self._restore_manual_chord_after_patch()

    def _set_synth_state(self, role: str, state: Any) -> None:
        if not isinstance(state, dict):
            self._set_synth_name(role, str(state))
            return
        self._apply_synth_state(
            role,
            str(state.get("name", "")),
            self._params_from_list(state.get("params", [])),
        )

    def _set_synth_name(self, role: str, name: str) -> None:
        # Compatibility for old senders. New frontend code always sends the
        # complete state object.
        self._apply_synth_state(role, str(name), {}, force_patch=True)

    def _set_params(self, role: str, values: Any) -> None:
        # Compatibility for old senders: feed the parameter-only packet back
        # through the same complete-state convergence method.
        self._apply_synth_state(
            role,
            self.selected_synth[role],
            self._params_from_list(values),
        )

    def _set_volume(self, role: str, value: Any) -> None:
        level = max(0.0, min(1.0, float(value)))
        self.volume[role] = level
        output_level = level * self._instrument_level(role)
        for synth in self._role_synth_ids(role):
            self._wire(f"i{synth}iV{self._f(output_level)}Z")

    def _instrument_level(self, role: str) -> float:
        levels = self.config.get("instrument_levels", {})
        if not isinstance(levels, dict):
            return 1.0
        key = self.selected_synth.get(role, "")
        return max(0.0, float(levels.get(key, 1.0)))

    # ------------------------------------------------------------------
    # Manual chord voice (synth 3)
    # ------------------------------------------------------------------

    def _start_manual(self, voice_id: str, notes: list[float]) -> None:
        synth = self.synth_id["manual_chord"]
        self._wire(f"l0i{synth}Z")
        self._manual_active_id = voice_id
        self._manual_active_notes = list(notes)
        for note in notes:
            self._wire(f"n{self._f(note)}l1i{synth}Z")

    def _stop_manual(self, voice_id: str) -> None:
        # Ignore stale delayed releases belonging to an older chord touch.
        if self._manual_active_id != voice_id:
            return
        self._wire(f"l0i{self.synth_id['manual_chord']}Z")
        self._manual_active_id = None
        self._manual_active_notes = []

    def _stop_all_manual(self) -> None:
        self._wire(f"l0i{self.synth_id['manual_chord']}Z")
        self._manual_active_id = None
        self._manual_active_notes = []

    def _manual_event(self, payload_text: str) -> None:
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            return
        action = str(payload.get("action", ""))
        voice_id = str(payload.get("id", ""))
        notes = [float(x) for x in payload.get("notes", [])]
        if action in ("start", "update") and voice_id:
            if action == "update" and self._manual_active_id != voice_id:
                return
            self._start_manual(voice_id, notes)
        elif action == "stop" and voice_id:
            self._stop_manual(voice_id)
        elif action == "stop_all":
            self._stop_all_manual()

    def _set_rhythm_chord_enabled(self, enabled: bool) -> bool:
        """Apply an automatic-chord gate transition and its audio edge."""
        enabled = bool(enabled)
        if self.rhythm_chord_enabled == enabled:
            return False

        self.rhythm_chord_enabled = enabled
        if not enabled:
            # Clearing tagged events removes their future note-offs too.  A
            # velocity-zero event without a note releases every active voice
            # of synth 4 through the patch's normal envelope; it is not an
            # oscillator reset and deliberately leaves the rhythm transport,
            # drums, bass and effect tails alone.
            self._wire(f"l0i{self.synth_id['rhythm_chord']}Z")
        else:
            self._sync_synth_params(
                "chord",
                (self.synth_id["rhythm_chord"],),
            )
        return True

    def _chord_state(self, payload_text: str) -> None:
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            return
        self.chord_notes = [float(x) for x in payload.get("notes", [])]
        self.bass_notes = [float(x) for x in payload.get("bass_notes", [])]
        if "rhythm_chord_enabled" in payload:
            self._set_rhythm_chord_enabled(
                payload.get("rhythm_chord_enabled")
            )

        if payload.get("play_now") and self.chord_notes:
            synth = self.synth_id["manual_chord"]
            self._wire(f"l0i{synth}Z")
            for note in self.chord_notes:
                self._wire(f"n{self._f(note)}l1i{synth}Z")
            self._note_off_later(
                synth,
                None,
                float(self.config["performance"]["one_shot_chord_gate_ms"]),
            )

        # Chord and bass are independent tagged sequencer lanes. Updating
        # tuning/chord pitch replaces only those ranges; percussion and
        # sequencer transport remain untouched.
        if self.bass_running:
            self._replace_lane("bass")
        self._replace_lane("chords")

    # ------------------------------------------------------------------
    # AMY tagged sequencer lanes
    # ------------------------------------------------------------------

    def _rhythm_period_ticks(self) -> int:
        config = self.rhythm_config
        if not config:
            return AMY_PPQ
        return max(1, round(float(config["length_beats"]) * AMY_PPQ))

    def _lane_events(self, lane_name: str) -> list[tuple[int, int, str]]:
        config = self.rhythm_config
        if not config:
            return []

        period = self._rhythm_period_ticks()
        rhythm_cfg = self.config["rhythm"]
        events: list[tuple[int, int, str]] = []

        if lane_name == "drums":
            drum_synth = self.synth_id["drums"]
            sample_map = self.config["drums"]["sample_map"]
            drum_gain = max(
                0.0,
                float(self.config["drums"].get("velocity_gain", 5.0)),
            )
            for event in config.get("percussion_events", []):
                sample = str(event.get("sample", ""))
                if sample not in sample_map:
                    continue
                tick = round(float(event.get("time", 0.0)) * AMY_PPQ)
                velocity = max(0.0, min(1.0, float(event.get("amp", 1.0))))
                hit = sample_map[sample]
                events.append((
                    tick,
                    period,
                    f"p{int(hit['preset'])}n{self._f(float(hit['note']))}"
                    f"l{self._f(velocity * drum_gain)}i{drum_synth}",
                ))
            return events

        if lane_name == "bass":
            if not self.bass_running or not self.bass_notes:
                return []
            bass_synth = self.synth_id["bass"]
            gate = max(
                1,
                round(float(rhythm_cfg["bass_gate_beats"]) * AMY_PPQ),
            )
            for event in config.get("bass_events", []):
                degree = int(event.get("degree", 0))
                note = self.bass_notes[degree % len(self.bass_notes)]
                tick = round(float(event.get("time", 0.0)) * AMY_PPQ)
                velocity = max(0.0, min(1.0, float(event.get("amp", 1.0))))
                events.append((
                    tick,
                    period,
                    f"n{self._f(note)}l{self._f(velocity)}i{bass_synth}",
                ))
                events.append((
                    tick + gate,
                    period,
                    f"n{self._f(note)}l0i{bass_synth}",
                ))
            return events

        if lane_name == "chords":
            if not self.rhythm_chord_enabled or not self.chord_notes:
                return []
            chord_synth = self.synth_id["rhythm_chord"]
            max_notes = max(
                1,
                int(rhythm_cfg.get("max_rhythm_chord_notes", 4)),
            )
            rhythm_notes = self.chord_notes[:max_notes]
            gate = max(
                1,
                round(float(rhythm_cfg["chord_gate_beats"]) * AMY_PPQ),
            )
            for event in config.get("chord_events", []):
                tick = round(float(event.get("time", 0.0)) * AMY_PPQ)
                velocity = max(0.0, min(1.0, float(event.get("amp", 1.0))))
                for note in rhythm_notes:
                    events.append((
                        tick,
                        period,
                        f"n{self._f(note)}l{self._f(velocity)}i{chord_synth}",
                    ))
                events.append((tick + gate, period, f"l0i{chord_synth}"))
            return events

        raise KeyError(lane_name)

    def _replace_lane(self, lane_name: str) -> None:
        lane = self._sequencer_lanes[lane_name]
        try:
            lane.enqueue(self._lane_events(lane_name))
        except ValueError as exc:
            print(f"AMY rhythm warning: {exc}", flush=True)

    def _replace_all_lanes(self, *, resume_transport: bool) -> None:
        for lane_name in self._sequencer_lanes:
            self.writer.new_low_generation(lane_name)
        generation = self.writer.new_low_generation("rhythm-full")

        commands: list[str] = []
        for lane_name in ("drums", "bass", "chords"):
            lane = self._sequencer_lanes[lane_name]
            try:
                commands.extend(lane.commands(self._lane_events(lane_name)))
            except ValueError as exc:
                print(f"AMY rhythm warning: {exc}", flush=True)
                return

        if resume_transport:
            commands.append("zY1Z")
        for command in commands:
            self.writer.low("rhythm-full", generation, command)

    def _cancel_queued_rhythm_updates(self) -> None:
        self.writer.new_low_generation("rhythm-full")
        for lane_name in self._sequencer_lanes:
            self.writer.new_low_generation(lane_name)

    def _silence_accompaniment(self) -> None:
        """Immediately release every voice owned by the rhythm transport.

        Stopping AMY's sequencer freezes future tagged events.  If transport is
        stopped between a scheduled note-on and note-off, that note-off can no
        longer fire.  Explicit all-off messages are therefore part of the stop
        transaction.  Manual chord synth 3 and strum synth 2 are intentionally
        excluded because they are controlled by the player's fingers, not by
        rhythm transport.
        """
        for key in ("drums", "bass", "rhythm_chord"):
            self._wire(f"l0i{self.synth_id[key]}Z")

    def _set_rhythm_config(self, payload_text: str) -> None:
        try:
            new_config = json.loads(str(payload_text))
        except json.JSONDecodeError:
            return
        if not isinstance(new_config, dict):
            return

        old_id = (
            str(self.rhythm_config.get("id", ""))
            if isinstance(self.rhythm_config, dict)
            else ""
        )
        new_id = str(new_config.get("id", ""))
        style_changed = bool(old_id) and old_id != new_id
        self.rhythm_config = new_config
        self._scheduled_rhythm_id = new_id
        self._wire(f"j{self._f(float(new_config.get('tempo', 108.0)))}Z")

        if style_changed and self.rhythm_running:
            self._cancel_queued_rhythm_updates()
            self._wire("zY0Z")
            self._silence_accompaniment()
            self._wire(f"S{RESET_TIMEBASE}Z")
            self._replace_all_lanes(resume_transport=True)
        else:
            for lane_name in ("drums", "bass", "chords"):
                self._replace_lane(lane_name)

    def _start_rhythm(self) -> None:
        if self.rhythm_running:
            return
        self.rhythm_running = True
        self._wire(f"S{RESET_TIMEBASE}Z")
        self._replace_all_lanes(resume_transport=True)

    def _stop_rhythm(self) -> None:
        if not self.rhythm_running:
            return
        self.rhythm_running = False
        self._cancel_queued_rhythm_updates()
        self._wire("zY0Z")
        self._silence_accompaniment()

    def _cancel_strum_tail(self) -> None:
        with self._strum_lock:
            self._strum_tail_token += 1
            self._strum_active_notes.clear()

    def _strum_note_on(self, note: float) -> None:
        """Play one strum note without invoking AMY voice stealing."""
        synth = self.synth_id["strum"]
        midi_key = int(round(note))

        with self._strum_lock:
            self._strum_tail_token += 1
            token = self._strum_tail_token

            # AMY matches stolen/forgotten notes by rounded MIDI note.  If the
            # same pitch is re-entered, explicitly release the old instance.
            duplicate_index = next(
                (i for i, n in enumerate(self._strum_active_notes)
                 if int(round(n)) == midi_key),
                None,
            )
            if duplicate_index is not None:
                old = self._strum_active_notes.pop(duplicate_index)
                self._wire(f"n{self._f(old)}l0i{synth}Z")

            # Never present AMY with more live notes than synth2 has voices.
            # Releasing before the next onset prevents its forgotten-note pool
            # from being used during fast seven-octave sweeps.
            max_live = max(1, self.voice_count["strum"])
            while len(self._strum_active_notes) >= max_live:
                old = self._strum_active_notes.pop(0)
                self._wire(f"n{self._f(old)}l0i{synth}Z")

            self._wire(f"n{self._f(note)}l1i{synth}Z")
            self._strum_active_notes.append(note)

        tail_ms = float(
            self.config.get("performance", {}).get("strum_tail_ms", 450)
        )

        def tail_release() -> None:
            with self._strum_lock:
                if token != self._strum_tail_token:
                    return
                self._strum_tail_token += 1
                self._strum_active_notes.clear()
            self._wire(f"l0i{synth}Z")

        timer = threading.Timer(max(0.01, tail_ms / 1000.0), tail_release)
        timer.daemon = True
        timer.start()

    def _panic(self) -> None:
        """Return AMY and the five Omnichord synths to a known-good state.

        RESET_ALL_OSCS is an ordinary AMY reset delta: it frees oscillator
        state and resets the synth/instrument table without stopping the AMY
        engine itself.  After several audio blocks we therefore know synths
        0..4 no longer exist and can define them from scratch.
        """
        self.writer.invalidate_all_low()
        for synth in self.synth_id.values():
            self._bump_synth_generation(synth)
        self._cancel_strum_tail()

        self.rhythm_running = False
        self.rhythm_chord_enabled = False
        self.bass_running = False
        self._manual_active_id = None
        self._manual_active_notes = []
        self._scheduled_rhythm_id = None

        # Stop transport first, then reset both sequencer and complete
        # oscillator/instrument allocation.  RESET_ALL_OSCS also guarantees
        # that a synth which had failed or disappeared is genuinely gone.
        self._wire("zY0Z")
        self._wire(f"S{RESET_SEQUENCER | RESET_ALL_OSCS}Z")

        # 128 samples / 48 kHz = 2.667 ms.  20 ms crosses more than seven
        # render boundaries before definitions are recreated.  This delay is
        # in the dedicated serial writer, never the Qt/UI thread.
        self.writer.delay(0.020)

        self._configured_synths.clear()
        self._configure_fixed_synths()

        if self.rhythm_config is not None:
            tempo = float(self.rhythm_config.get("tempo", 108.0))
            self._wire(f"j{self._f(tempo)}Z")

    def send_message(self, address: str, value: Any) -> None:
        if self.debug_log.log_logical:
            self.debug_log.write("EVENT", f"{address} {value!r}")
        a = self.addr
        if address == a["chord_amp"]:
            self._set_volume("chord", value)
        elif address == a["strum_amp"]:
            self._set_volume("strum", value)
        elif address == a["bass_amp"]:
            self._set_volume("bass", value)
        elif address == a["percussion_amp"]:
            self._set_volume("drums", value)
        elif address == a["reverb"]:
            self._set_reverb(value)
        elif address == a["chord_synth"]:
            if isinstance(value, dict):
                self._set_synth_state("chord", value)
            else:
                self._set_synth_name("chord", str(value))
        elif address == a["strum_synth"]:
            if isinstance(value, dict):
                self._set_synth_state("strum", value)
            else:
                self._set_synth_name("strum", str(value))
        elif address == a["bass_synth"]:
            if isinstance(value, dict):
                self._set_synth_state("bass", value)
            else:
                self._set_synth_name("bass", str(value))
        elif address == a["chord_params"]:
            self._set_params("chord", value)
        elif address == a["strum_params"]:
            self._set_params("strum", value)
        elif address == a["bass_params"]:
            self._set_params("bass", value)
        elif address == a["manual_chord"]:
            self._manual_event(str(value))
        elif address == a["chord_state"]:
            self._chord_state(str(value))
        elif address == a["strum_note"]:
            self._strum_note_on(float(value))
        elif address == a["bass_running"]:
            enabled = bool(int(value))
            if self.bass_running == enabled:
                return
            self.bass_running = enabled
            if not enabled:
                self._wire(f"l0i{self.synth_id['bass']}Z")
            self._replace_lane("bass")
        elif address == a["rhythm_config"]:
            self._set_rhythm_config(str(value))
        elif address == a["rhythm_chord_enabled"]:
            enabled = bool(int(value))
            if not self._set_rhythm_chord_enabled(enabled):
                return
            self._replace_lane("chords")
        elif address == a["rhythm_running"]:
            new_state = bool(int(value))
            if new_state:
                self._start_rhythm()
            else:
                self._stop_rhythm()
        elif address == a["panic"]:
            self._panic()

    def close(self) -> None:
        try:
            self.writer.invalidate_all_low()
            self._cancel_strum_tail()
            self._wire("zY0Z")
            for synth in self.synth_id.values():
                self._wire(f"l0i{synth}Z")
        finally:
            self.writer.close()
            self.debug_log.close()


class AmySocketClient(AmySerialClient):
    """Send wire packets to an external AMY process without AMY API calls."""

    def __init__(
        self,
        config: dict[str, Any],
        addresses: dict[str, str],
        socket_path: str,
    ) -> None:
        super().__init__(
            config=config,
            addresses=addresses,
            writer_factory=lambda debug_log: _UnixSocketWriter(
                socket_path,
                debug_log,
            ),
        )


class AmyLocalClient(AmySerialClient):
    """Send LF-framed wire requests through Qt's native local IPC."""

    def __init__(
        self,
        config: dict[str, Any],
        addresses: dict[str, str],
        server_name: str,
    ) -> None:
        super().__init__(
            config=config,
            addresses=addresses,
            writer_factory=lambda debug_log: _QtLocalSocketWriter(
                server_name,
                debug_log,
            ),
        )
