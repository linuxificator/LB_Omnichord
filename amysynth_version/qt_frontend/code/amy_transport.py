from __future__ import annotations

import json
import math
import queue
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import serial

from control_limits import clamp_control_value
from amy_parameter_plan import compile_parameter_commands
from config_loader import DebugConfig, ResolvedAmyConfig, resolve_amy_config_data
from drum_patterns import (
    DrumFill,
    DrumPatternCatalog,
    load_drum_pattern_catalog,
)
from rhythm_command_plan import (
    compact_repeating_events,
    compile_bass_events,
    compile_chord_pattern_plan,
    compile_drum_activity_commands,
    compile_fill_definition,
    compile_fill_schedule_commands,
    compile_tagged_lane,
    drum_quantum,
    fill_occurrences,
)
from unix_wire_socket import connect_unix_wire_socket


AMY_PPQ = 48
RESET_SEQUENCER = 4096
RESET_ALL_OSCS = 8192
RESET_TIMEBASE = 16384
RESET_ALL_NOTES = 131072
SYNTH_FLAGS_NO_NOTE_WARNINGS = 8


def _resolve_drum_catalog_directory(
    module_file: Path = Path(__file__),
    packaged_root: Path | None = None,
) -> Path:
    """Resolve drum assets in source, frozen, and flat Android layouts."""

    if packaged_root is not None:
        return Path(packaged_root) / "music" / "drums"

    module_directory = Path(module_file).resolve().parent
    source_directory = module_directory.parent / "music" / "drums"
    if source_directory.is_dir():
        return source_directory
    return module_directory / "music" / "drums"


def _compact_repeating_events(
    occurrences: list[tuple[int, str]],
    bar_period: int,
) -> list[tuple[int, int, str]]:
    """Compatibility alias for tests and callers using the former location."""

    return compact_repeating_events(occurrences, bar_period)


class _DebugLog:
    """Asynchronous append-only AMY transport debug log.

    The UART writer must never wait on filesystem I/O just because debugging
    is enabled.  Producers only enqueue already-formatted text; a dedicated
    low-impact thread owns the file and writes the records.
    """

    def __init__(self, config: DebugConfig) -> None:
        self.enabled = config.log_amy_commands
        self.log_logical = config.log_logical_events
        self.path: Path | None = None
        self._queue: queue.SimpleQueue[str | None] | None = None
        self._thread: threading.Thread | None = None

        if self.enabled:
            path = Path(config.amy_command_log).expanduser()
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
        # Prefer packet-preserving local IPC and fall back to an LF-framed
        # stream when that socket mode is unavailable. The choice follows the
        # actual endpoint capability rather than an operating-system name.
        self.socket, self._stream_transport = connect_unix_wire_socket(
            str(socket_path),
            timeout=5.0,
        )
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
        plan = compile_tagged_lane(
            name=self.name,
            start=self.start,
            count=self.count,
            previous_high_water=self.high_water,
            events=events,
        )
        self.high_water = plan.high_water
        return list(plan.commands)

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
        config: dict[str, Any] | None,
        addresses: dict[str, str],
        *,
        writer_factory: Any | None = None,
        resolved_config: ResolvedAmyConfig | None = None,
    ) -> None:
        if resolved_config is None:
            if config is None:
                raise ValueError("config or resolved_config is required")
            resolved_config = resolve_amy_config_data(
                config,
                source_path=(
                    Path(__file__).resolve().parent.parent
                    / "config"
                    / "amy_config.json"
                ),
                source_kind="external",
            )
        self.resolved_config = resolved_config
        self.addr = addresses

        self.debug_log = _DebugLog(resolved_config.debug)
        if self.debug_log.path is not None:
            print(
                f"AMY command log: {self.debug_log.path}",
                flush=True,
            )
        if writer_factory is None:
            self.writer = _SerialWriter(
                resolved_config.transport.serial_port,
                resolved_config.transport.serial_baud,
                resolved_config.transport.serial_write_timeout,
                self.debug_log,
            )
        else:
            self.writer = writer_factory(self.debug_log)

        self.synth_id = dict(resolved_config.layout.role_synth_ids)
        voices = resolved_config.capacities.voices
        self.voice_count = {
            "drums": voices.drums,
            "bass": voices.bass,
            "strum": voices.strum,
            "manual_chord": voices.manual_chord,
            "rhythm_chord": voices.rhythm_chord,
        }

        self.selected_synth = {
            "chord": resolved_config.synth_defaults.chord,
            "strum": resolved_config.synth_defaults.strum,
            "bass": resolved_config.synth_defaults.bass,
        }
        self.patch_map = {
            str(key): int(value)
            for key, value in resolved_config.synth_patches
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
        self.bus_id = dict(resolved_config.layout.role_buses)
        bus_values = tuple(self.bus_id.values())
        if (
            len(set(bus_values)) != 4
            or any(bus < 0 or bus > 3 for bus in bus_values)
        ):
            raise ValueError(
                "drums, bass, strum and chord must use four distinct AMY buses 0..3"
            )
        self.master_volume = 1.0
        self.reverb = {
            "level": 0.0,
            "liveness": 0.5,
            "damping": 0.5,
            "drums": False,
        }

        self.chord_notes: list[float] = []
        self.bass_notes: list[float] = []
        self.bass_riff: dict[str, Any] | None = None
        self.rhythm_config: dict[str, Any] | None = None
        self.rhythm_running = False
        self.rhythm_chord_enabled = False
        self.bass_running = True
        self._scheduled_rhythm_id: str | None = None
        self.drum_catalog: DrumPatternCatalog = load_drum_pattern_catalog(
            _resolve_drum_catalog_directory(
                packaged_root=(
                    Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else None
                )
            )
        )
        self.drum_kit = resolved_config.drums.kit
        if self.drum_kit not in self.drum_catalog.kits:
            raise ValueError(
                f"unknown drums.kit {self.drum_kit!r}; expected "
                "tiny, gamma9001 or general_midi"
            )
        self._drum_roles = tuple(sorted({
            event.role
            for rhythm in self.drum_catalog.rhythms.values()
            for level in rhythm.levels
            for event in level
        }))
        self._pattern_ranges = {
            name: (start, count)
            for name, start, count in resolved_config.layout.sequencer_pattern_ranges
        }
        _, drum_pattern_count = self._pattern_ranges["drum_bases"]
        if len(self._drum_roles) > drum_pattern_count:
            raise ValueError("logical drum roles exceed reserved AMY pattern slots")
        self._drum_role_index = {
            role: index for index, role in enumerate(self._drum_roles)
        }

        tag_config = {
            name: (start, count)
            for name, start, count in resolved_config.layout.sequencer_tag_ranges
        }
        max_tags = resolved_config.rhythm.max_sequencer_tags
        self._sequencer_lanes: dict[str, _TaggedSequencerLane] = {}
        occupied: set[int] = set()
        for lane_name in ("drums", "bass", "chords"):
            start, count = tag_config[lane_name]
            lane = _TaggedSequencerLane(
                lane_name,
                start,
                count,
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
        max_oscs = resolved_config.capacities.max_oscs
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
        self._preload_drum_library()

    def _wire(self, command: str) -> None:
        self.writer.high(command)

    @staticmethod
    def _f(value: float) -> str:
        return f"{float(value):.9g}"

    def _drum_hit_body(
        self,
        rhythm_id: str,
        role: str,
        velocity: int,
        *,
        fill: bool,
    ) -> str:
        sound = self.drum_catalog.resolve(
            self.drum_kit,
            rhythm_id,
            role,
            fill=fill,
        )
        gain = max(0.0, self.resolved_config.drums.velocity_gain)
        level = max(0.0, min(1.0, float(velocity) / 127.0)) * gain
        preset = "" if sound.preset is None else f"p{sound.preset}"
        return (
            f"{preset}n{self._f(float(sound.note))}"
            f"l{self._f(level)}i{self.synth_id['drums']}"
        )

    def _fill_pattern_id(self, fill: DrumFill) -> int:
        start, count = self._pattern_ranges["fills"]
        pattern = start + int(fill.index) - 1
        if not start <= pattern < start + count:
            raise ValueError(
                f"fill {fill.fill_id!r} has unsupported index {fill.index}"
            )
        return pattern

    def _preload_drum_library(self) -> None:
        """Author every fill once; runtime changes only schedule definitions."""
        fills = {
            fill.index: (rhythm.rhythm_id, fill)
            for rhythm in self.drum_catalog.rhythms.values()
            for fill in rhythm.fills
        }
        for _, (rhythm_id, fill) in sorted(fills.items()):
            pattern = self._fill_pattern_id(fill)
            drum_base, _ = self._pattern_ranges["drum_bases"]
            commands = compile_fill_definition(
                rhythm_id=rhythm_id,
                fill=fill,
                pattern=pattern,
                roles=self._drum_roles,
                role_indexes=self._drum_role_index,
                drum_pattern_start=drum_base,
                hit_body=self._drum_hit_body,
            )
            tag_count = len(commands) - 2
            if tag_count > self.resolved_config.capacities.max_pattern_tags:
                raise ValueError(
                    f"fill {fill.fill_id!r} needs {tag_count} AMY pattern tags"
                )
            for command in commands:
                self._wire(command)

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

    def _synth_flag_fields(self, synth: int) -> str:
        """Return AMY policy fields which belong to one synth instance.

        The automatic chord lane deliberately retains repeating note-offs
        while its note-ons are drained. AMY flag 8 exists for exactly this
        sequencer-join/drain case: unmatched note-offs remain harmless but do
        not flood stderr (which may itself be a slow target UART). Keep the
        policy scoped to the automatic synth so unexpected manual, strum,
        bass and percussion note lifecycles remain visible.
        """
        if synth == self.synth_id["rhythm_chord"]:
            return f"if{SYNTH_FLAGS_NO_NOTE_WARNINGS}"
        return ""

    def _patch_compatibility_commands(
        self, patch: int, synth: int
    ) -> list[str]:
        """Small target-side corrections for known factory-patch edge cases.

        These do not replace the AMY patches.  They are sent immediately after
        the factory K command, so the original patch remains the source of all
        other settings.  Values live in amy_config.json for easy testing.
        """
        raw = self.resolved_config.patch_compatibility(patch)
        if raw is None:
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

    def _apply_master_bus(self, bus: int) -> None:
        self._wire(f"y{int(bus)}V{self._f(self.master_volume)}Z")

    def _apply_master_buses(self) -> None:
        for bus in self.bus_id.values():
            self._apply_master_bus(bus)

    def _set_master_volume(self, value: Any) -> None:
        updated = max(0.0, min(1.0, float(value)))
        if math.isclose(updated, self.master_volume, abs_tol=1e-4):
            return
        self.master_volume = updated
        self._apply_master_buses()

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
        flag_fields = self._synth_flag_fields(synth)
        already_configured = synth in self._configured_synths
        if already_configured:
            # The synth already owns its dedicated bus. Current AMY preserves
            # that bus across a repatch, so patch-level EQ/chorus remain local.
            self._wire(f"l0i{synth}Z")
            self._wire(f"K{patch}i{synth}{flag_fields}Z")
        else:
            voices = self._voice_count_for_synth(synth)
            # Put the bus in the allocation/patch event itself. Many Juno ROM
            # patches contain bus FX; without iy here those startup FX briefly
            # (and persistently) land on default bus 0 before a later route.
            self._wire(
                f"K{patch}i{synth}iv{voices}iy{bus}{flag_fields}Z"
            )
            self._configured_synths.add(synth)

            guard_ms = self.resolved_config.performance.synth_alloc_guard_ms
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
        self._apply_master_bus(bus)

        if already_configured:
            # A ROM repatch is not a cheap parameter edit in AMY: it releases,
            # resets and reallocates the voice's oscillator block.  Keep the
            # next patch transaction out of the same audio-block burst.  This
            # is especially important during startup/preset restore, where the
            # chord, strum and bass patches are otherwise queued back-to-back.
            guard_ms = self.resolved_config.performance.synth_alloc_guard_ms
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
        # Tiny and Gamma9001 resolve kit roles to direct PCM presets, allowing
        # one small polyphonic synth even when a Gamma rhythm mixes kit
        # families. General MIDI deliberately uses AMY's engine-side patch
        # 258 note map; it is still AMY audio and never opens a MIDI path.
        drums = self.synth_id["drums"]
        drum_voices = self.voice_count["drums"]
        self._bump_synth_generation(drums)
        if self.drum_kit == "general_midi":
            self._wire(f"K258i{drums}iy{self._bus_for_synth(drums)}Z")
        else:
            self._wire(f"i{drums}iv{drum_voices}in1Z")
            self._wire(f"v0w7i{drums}Z")
        self._route_synth_bus(drums)
        self._wire(f"i{drums}iV{self._f(self.volume['drums'])}Z")
        self._configured_synths.add(drums)

        self._configure_synth("bass")
        self._configure_synth("strum")
        self._configure_synth("chord")
        self._apply_reverb_buses()
        self._apply_master_buses()

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

        The pure compiler owns patch semantics and selective-update behavior;
        this adapter only supplies current application state.
        """
        return list(
            compile_parameter_commands(
                patch=self._patch(role),
                synth=synth,
                parameters=self.synth_params[role],
                selected_keys=parameter_keys,
            )
        )

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
        key = self.selected_synth.get(role, "")
        return max(0.0, self.resolved_config.instrument_level(key))

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

    def _set_rhythm_chord_enabled(
        self,
        enabled: bool,
    ) -> bool:
        """Apply an automatic-chord gate without truncating active children."""
        enabled = bool(enabled)
        if self.rhythm_chord_enabled == enabled:
            return False

        self.rhythm_chord_enabled = enabled
        if enabled:
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
        if "bass_riff" in payload:
            bass_riff = payload.get("bass_riff")
            self.bass_riff = bass_riff if isinstance(bass_riff, dict) else None
        if "rhythm_chord_enabled" in payload:
            self._set_rhythm_chord_enabled(
                payload.get("rhythm_chord_enabled"),
            )

        if payload.get("play_now") and self.chord_notes:
            synth = self.synth_id["manual_chord"]
            self._wire(f"l0i{synth}Z")
            for note in self.chord_notes:
                self._wire(f"n{self._f(note)}l1i{synth}Z")
            self._note_off_later(
                synth,
                None,
                self.resolved_config.performance.one_shot_chord_gate_ms,
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

    def _chord_pattern_plan(
        self,
    ) -> tuple[list[str], list[tuple[int, int, str]]]:
        """Build note-owner patterns and repeating root triggers.

        The pure planner keeps each note's matching release in its immutable
        one-shot pattern. Replacing a root schedule therefore cannot shorten
        an already-sounding arpeggio note.
        """
        rhythm_cfg = self.resolved_config.rhythm
        pattern_start, pattern_count = self._pattern_ranges["chords"]
        plan = compile_chord_pattern_plan(
            config=self.rhythm_config,
            enabled=self.rhythm_chord_enabled,
            chord_notes=self.chord_notes,
            max_chord_notes=rhythm_cfg.max_rhythm_chord_notes,
            chord_gate_beats=rhythm_cfg.chord_gate_beats,
            pattern_start=pattern_start,
            pattern_count=pattern_count,
            synth=self.synth_id["rhythm_chord"],
            ppq=AMY_PPQ,
        )
        return list(plan.definitions), list(plan.triggers)

    def _lane_events(self, lane_name: str) -> list[tuple[int, int, str]]:
        if lane_name == "drums":
            # Percussion uses nested patterns; this lane carries fill triggers.
            return []
        if lane_name == "bass":
            rhythm_cfg = self.resolved_config.rhythm
            return list(
                compile_bass_events(
                    config=self.rhythm_config,
                    running=self.bass_running,
                    bass_notes=self.bass_notes,
                    bass_riff=self.bass_riff,
                    synth=self.synth_id["bass"],
                    bass_gate_beats=rhythm_cfg.bass_gate_beats,
                    ppq=AMY_PPQ,
                )
            )
        if lane_name == "chords":
            return self._chord_pattern_plan()[1]
        raise KeyError(lane_name)

    def _drum_quantum(self) -> int:
        config = self.rhythm_config
        if not isinstance(config, dict):
            return 0
        return drum_quantum(
            self.drum_catalog.rhythm(str(config.get("id", "")))
        )

    def _drum_activity_commands(
        self,
        *,
        quantize_live: bool | None = None,
    ) -> list[str]:
        config = self.rhythm_config
        if not isinstance(config, dict):
            return []
        rhythm = self.drum_catalog.rhythm(str(config.get("id", "")))
        use_live_quantization = (
            self.rhythm_running
            if quantize_live is None
            else bool(quantize_live)
        )
        drum_base, _ = self._pattern_ranges["drum_bases"]
        return list(
            compile_drum_activity_commands(
                rhythm=rhythm,
                percussion_activity=int(
                    config.get("percussion_activity", 1)
                ),
                roles=self._drum_roles,
                pattern_start=drum_base,
                rhythm_running=self.rhythm_running,
                quantize_live=use_live_quantization,
                hit_body=self._drum_hit_body,
            )
        )

    @staticmethod
    def _fill_occurrences(
        order: list[int],
        fills: tuple[DrumFill, ...],
    ) -> list[tuple[DrumFill, int]]:
        return [
            (fill, start)
            for fill, start in fill_occurrences(order, fills)
        ]

    def _fill_schedule_commands(
        self,
        *,
        quantize_live: bool | None = None,
    ) -> list[str]:
        config = self.rhythm_config
        if not isinstance(config, dict):
            return []
        rhythm = self.drum_catalog.rhythm(str(config.get("id", "")))
        raw_order = config.get("fill_order", [])
        order = (
            list(
                dict.fromkeys(
                    int(value)
                    for value in raw_order
                    if 0 <= int(value) < len(rhythm.fills)
                )
            )
            if isinstance(raw_order, list)
            else []
        )
        lane = self._sequencer_lanes["drums"]
        use_live_quantization = (
            self.rhythm_running
            if quantize_live is None
            else bool(quantize_live)
        )
        plan = compile_fill_schedule_commands(
            fills=rhythm.fills,
            order=order,
            density_bars=int(config.get("fill_density_bars", 32)),
            bar_ticks=self._drum_quantum(),
            lane_start=lane.start,
            lane_count=lane.count,
            previous_high_water=lane.high_water,
            quantize_live=use_live_quantization,
            pattern_id=self._fill_pattern_id,
        )
        lane.high_water = plan.high_water
        return list(plan.commands)

    def _drum_commands(
        self,
        *,
        activity: bool = True,
        fills: bool = True,
        quantize_live: bool | None = None,
    ) -> list[str]:
        commands: list[str] = []
        if activity:
            commands.extend(self._drum_activity_commands(
                quantize_live=quantize_live,
            ))
        if fills:
            commands.extend(self._fill_schedule_commands(
                quantize_live=quantize_live,
            ))
        return commands

    @staticmethod
    def _only_bass_config_changed(
        old_config: dict[str, Any] | None,
        new_config: dict[str, Any],
    ) -> bool:
        if not isinstance(old_config, dict) or old_config == new_config:
            return False
        bass_fields = {
            "bass_activity",
            "bass_events",
            "bass_mode",
            "bass_riff",
        }
        old_shared = {
            key: value
            for key, value in old_config.items()
            if key not in bass_fields
        }
        new_shared = {
            key: value
            for key, value in new_config.items()
            if key not in bass_fields
        }
        return old_shared == new_shared

    @staticmethod
    def _only_chord_config_changed(
        old_config: dict[str, Any] | None,
        new_config: dict[str, Any],
    ) -> bool:
        if not isinstance(old_config, dict) or old_config == new_config:
            return False
        chord_fields = {
            "chord_activity",
            "chord_events",
            "chord_arpeggio",
        }
        old_shared = {
            key: value
            for key, value in old_config.items()
            if key not in chord_fields
        }
        new_shared = {
            key: value
            for key, value in new_config.items()
            if key not in chord_fields
        }
        return old_shared == new_shared

    @staticmethod
    def _only_drum_activity_changed(
        old_config: dict[str, Any] | None,
        new_config: dict[str, Any],
    ) -> bool:
        if not isinstance(old_config, dict) or old_config == new_config:
            return False
        fields = {"busyness", "percussion_activity"}
        return (
            {key: value for key, value in old_config.items() if key not in fields}
            == {key: value for key, value in new_config.items() if key not in fields}
        )

    @staticmethod
    def _only_fill_config_changed(
        old_config: dict[str, Any] | None,
        new_config: dict[str, Any],
    ) -> bool:
        if not isinstance(old_config, dict) or old_config == new_config:
            return False
        fields = {"fill_order", "fill_density_bars"}
        return (
            {key: value for key, value in old_config.items() if key not in fields}
            == {key: value for key, value in new_config.items() if key not in fields}
        )

    @staticmethod
    def _only_tempo_config_changed(
        old_config: dict[str, Any] | None,
        new_config: dict[str, Any],
    ) -> bool:
        if not isinstance(old_config, dict) or old_config == new_config:
            return False
        return (
            {key: value for key, value in old_config.items() if key != "tempo"}
            == {key: value for key, value in new_config.items() if key != "tempo"}
        )

    def _replace_lane(self, lane_name: str) -> None:
        lane = self._sequencer_lanes[lane_name]
        try:
            if lane_name == "drums":
                generation = self.writer.new_low_generation("drums")
                for command in self._drum_commands():
                    self.writer.low("drums", generation, command)
            elif lane_name == "chords":
                generation = self.writer.new_low_generation("chords")
                pattern_commands, events = self._chord_pattern_plan()
                for command in pattern_commands + lane.commands(events):
                    self.writer.low("chords", generation, command)
            else:
                lane.enqueue(self._lane_events(lane_name))
        except ValueError as exc:
            print(f"AMY rhythm warning: {exc}", flush=True)

    def _replace_drums(
        self,
        *,
        activity: bool,
        fills: bool,
    ) -> None:
        try:
            generation = self.writer.new_low_generation("drums")
            for command in self._drum_commands(
                activity=activity,
                fills=fills,
            ):
                self.writer.low("drums", generation, command)
        except ValueError as exc:
            print(f"AMY rhythm warning: {exc}", flush=True)

    def _replace_all_lanes(self, *, resume_transport: bool) -> None:
        for lane_name in self._sequencer_lanes:
            self.writer.new_low_generation(lane_name)
        generation = self.writer.new_low_generation("rhythm-full")

        commands: list[str] = []
        try:
            commands.extend(self._drum_commands(
                # Explicit Start has just reset the timebase and must begin at
                # tick zero. Only replacements on a running transport wait for
                # the next whole-bar boundary.
                quantize_live=False if resume_transport else None,
            ))
        except ValueError as exc:
            print(f"AMY rhythm warning: {exc}", flush=True)
            return
        for lane_name in ("bass", "chords"):
            lane = self._sequencer_lanes[lane_name]
            try:
                if lane_name == "chords":
                    pattern_commands, events = self._chord_pattern_plan()
                    commands.extend(pattern_commands)
                else:
                    events = self._lane_events(lane_name)
                commands.extend(lane.commands(events))
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

        old_config = self.rhythm_config
        bass_only_changed = self._only_bass_config_changed(
            old_config, new_config
        )
        chord_only_changed = self._only_chord_config_changed(
            old_config, new_config
        )
        drum_only_changed = self._only_drum_activity_changed(
            old_config, new_config
        )
        fill_only_changed = self._only_fill_config_changed(
            old_config, new_config
        )
        tempo_only_changed = self._only_tempo_config_changed(
            old_config, new_config
        )
        old_id = (
            str(self.rhythm_config.get("id", ""))
            if isinstance(self.rhythm_config, dict)
            else ""
        )
        new_id = str(new_config.get("id", ""))
        style_changed = bool(old_id) and old_id != new_id
        self.rhythm_config = new_config
        bass_riff = new_config.get("bass_riff")
        self.bass_riff = bass_riff if isinstance(bass_riff, dict) else None
        self._scheduled_rhythm_id = new_id
        self._wire(f"j{self._f(float(new_config.get('tempo', 108.0)))}Z")

        if tempo_only_changed:
            return
        if bass_only_changed:
            self._replace_lane("bass")
            return
        if chord_only_changed:
            self._replace_lane("chords")
            return
        if drum_only_changed:
            self._replace_drums(activity=True, fills=False)
            return
        if fill_only_changed:
            self._replace_drums(activity=False, fills=True)
            return

        if style_changed and self.rhythm_running:
            # The new drum loops and melodic root events take over on the
            # live clock. Do not stop transport, silence voices or reset time.
            self._replace_all_lanes(resume_transport=False)
        else:
            for lane_name in ("drums", "bass", "chords"):
                self._replace_lane(lane_name)

    def _start_rhythm(self) -> None:
        if self.rhythm_running:
            return
        self.rhythm_running = True
        # Stored pattern definitions survive RESET_SEQUENCER, while frozen
        # instances and old root H events do not. Starting is therefore a
        # clean transport boundary even after an earlier stop mid-pattern.
        self._wire(f"S{RESET_TIMEBASE | RESET_SEQUENCER}Z")
        # Reset is an ordinary AMY event and takes effect at the next audio
        # block boundary, whereas zQT is handled immediately on ingest. Keep
        # the new instances behind several 128-sample blocks so the reset can
        # never erase triggers that arrived in the same host burst.
        self.writer.delay(0.020)
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

        tail_ms = self.resolved_config.performance.strum_tail_ms

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
        elif address == a["master_volume"]:
            self._set_master_volume(value)
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
        config: dict[str, Any] | None,
        addresses: dict[str, str],
        socket_path: str,
        resolved_config: ResolvedAmyConfig | None = None,
    ) -> None:
        super().__init__(
            config=config,
            addresses=addresses,
            resolved_config=resolved_config,
            writer_factory=lambda debug_log: _UnixSocketWriter(
                socket_path,
                debug_log,
            ),
        )


class AmyLocalClient(AmySerialClient):
    """Send LF-framed wire requests through Qt's native local IPC."""

    def __init__(
        self,
        config: dict[str, Any] | None,
        addresses: dict[str, str],
        server_name: str,
        resolved_config: ResolvedAmyConfig | None = None,
    ) -> None:
        super().__init__(
            config=config,
            addresses=addresses,
            resolved_config=resolved_config,
            writer_factory=lambda debug_log: _QtLocalSocketWriter(
                server_name,
                debug_log,
            ),
        )
