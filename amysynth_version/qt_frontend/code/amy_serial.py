from __future__ import annotations

import json
import math
import queue
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import serial


AMY_PPQ = 48
RESET_SEQUENCER = 4096
RESET_ALL_OSCS = 8192
RESET_TIMEBASE = 16384
RESET_ALL_NOTES = 131072


DEFAULT_CONFIG: dict[str, Any] = {'serial': {'port': '/dev/serial0', 'baud': 1000000, 'write_timeout': 0.5},
 'synth_ids': {'drums': 0, 'bass': 1, 'strum': 2, 'manual_chord': 3, 'rhythm_chord': 4},
 'voices': {'drums': 4, 'bass': 1, 'strum': 2, 'manual_chord': 7, 'rhythm_chord': 4},
 'default_synths': {'chord': 'juno_004', 'strum': 'juno_028', 'bass': 'dx7_143'},
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
                                'juno_filter_hz': 16000.0,
                                'juno_resonance': 4.0},
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
    """Priority UART writer with generation-cancelled sequencer traffic.

    High-priority performance commands always win over low-priority pattern
    definitions.  A barrier can postpone low-priority traffic until a fixed
    interval after earlier high-priority reset commands have actually been
    transmitted; this is used because AMY reset commands execute on an audio
    block boundary rather than synchronously in the UART parser.
    """

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
        self._generation = 0
        self._low_ready_at: dict[int, float] = {0: 0.0}
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

    def new_low_generation(self) -> int:
        with self._condition:
            self._generation += 1
            self._low_ready_at[self._generation] = 0.0
            # Old entries need not be physically removed here; the worker
            # discards them without UART I/O when it encounters them.
            self._condition.notify_all()
            return self._generation

    def high(self, command: str) -> None:
        with self._condition:
            if self._closed:
                return
            self._high.append(("command", command, None, 0.0))
            self._condition.notify()

    def barrier(self, generation: int, delay_seconds: float) -> None:
        """After earlier high commands, hold this generation's low queue.

        The barrier itself performs no UART I/O.  Because it lives in the
        high FIFO, its delay starts only after all earlier reset commands have
        actually been written to the serial device.
        """
        with self._condition:
            if self._closed:
                return
            self._high.append((
                "barrier",
                None,
                int(generation),
                max(0.0, float(delay_seconds)),
            ))
            self._condition.notify()

    def delay(self, delay_seconds: float) -> None:
        """Insert a host-side guard before later high-priority commands."""
        with self._condition:
            if self._closed:
                return
            self._high.append((
                "delay",
                None,
                None,
                max(0.0, float(delay_seconds)),
            ))
            self._condition.notify()

    def low(self, generation: int, command: str) -> None:
        with self._condition:
            if self._closed:
                return
            self._low.append((generation, command))
            self._condition.notify()

    def _write(self, command: str, lane: str) -> None:
        if self.debug_log is not None:
            self.debug_log.write(f"TX-{lane}", command.strip())
        self.serial.write(self._line(command))

    def _run(self) -> None:
        while True:
            item_kind: str | None = None
            command: str | None = None
            barrier_generation: int | None = None
            barrier_delay = 0.0
            lane = "HIGH"

            with self._condition:
                while True:
                    if self._closed and not self._high and not self._low:
                        return

                    if self._high:
                        (
                            item_kind,
                            command,
                            barrier_generation,
                            barrier_delay,
                        ) = self._high.popleft()
                        break

                    # Discard stale low-priority generations immediately.
                    while self._low and self._low[0][0] != self._generation:
                        self._low.popleft()

                    if not self._low:
                        self._condition.wait()
                        continue

                    generation, low_command = self._low[0]
                    ready_at = self._low_ready_at.get(generation, 0.0)
                    now = time.monotonic()
                    if ready_at > now:
                        # A new high-priority performance command notifies the
                        # condition and therefore interrupts this wait.
                        self._condition.wait(timeout=ready_at - now)
                        continue

                    self._low.popleft()
                    item_kind = "command"
                    command = low_command
                    lane = "LOW"
                    break

            if item_kind == "barrier":
                with self._condition:
                    if barrier_generation == self._generation:
                        self._low_ready_at[barrier_generation] = (
                            time.monotonic() + barrier_delay
                        )
                    self._condition.notify_all()
                continue

            if item_kind == "delay":
                if self.debug_log is not None:
                    self.debug_log.write(
                        "GUARD", f"sleep {barrier_delay * 1000.0:.1f} ms"
                    )
                time.sleep(barrier_delay)
                continue

            if item_kind == "command" and command is not None:
                self._write(command, lane)

    def close(self) -> None:
        with self._condition:
            if self._closed:
                return
            # Invalidate all queued sequencer-definition messages. High
            # priority panic/note-off commands queued before close are kept.
            self._generation += 1
            self._low.clear()
            self._closed = True
            self._condition.notify_all()

        self._thread.join(timeout=1.0)
        self.serial.close()


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
    ) -> None:
        self.config = config
        self.addr = addresses

        self.debug_log = _DebugLog(config)
        if self.debug_log.path is not None:
            print(
                f"AMY command log: {self.debug_log.path}",
                flush=True,
            )
        serial_cfg = config["serial"]
        self.writer = _SerialWriter(
            str(serial_cfg["port"]),
            int(serial_cfg["baud"]),
            float(serial_cfg.get("write_timeout", 0.5)),
            self.debug_log,
        )

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

        self.chord_notes: list[float] = []
        self.bass_notes: list[float] = []
        self.rhythm_config: dict[str, Any] | None = None
        self.rhythm_running = False
        self.rhythm_chord_enabled = False
        self.bass_running = True
        self._scheduled_rhythm_id: str | None = None
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

    def _wire(self, command: str, *, low_generation: int | None = None) -> None:
        if low_generation is None:
            self.writer.high(command)
        else:
            self.writer.low(low_generation, command)

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
            out.append(f"v0F{self._f(float(raw['juno_filter_hz']))}i{synth}Z")
        if "juno_resonance" in raw:
            out.append(f"v0R{self._f(float(raw['juno_resonance']))}i{synth}Z")
        if "juno_output_amp" in raw:
            out.append(f"v0a{self._f(float(raw['juno_output_amp']))}i{synth}Z")
        return out

    def _apply_patch_compatibility(self, patch: int, synth: int) -> None:
        for command in self._patch_compatibility_commands(patch, synth):
            self._wire(command)

    def _configure_one_synth(self, role: str, synth: int) -> None:
        self._bump_synth_generation(synth)
        patch = self._patch(role)
        if synth in self._configured_synths:
            # Hot-swapping a patch on an existing synth retains num_voices.
            self._wire(f"l0i{synth}Z")
            self._wire(f"K{patch}i{synth}Z")
        else:
            voices = self._voice_count_for_synth(synth)
            self._wire(f"K{patch}i{synth}iv{voices}Z")
            self._configured_synths.add(synth)
        self._apply_patch_compatibility(patch, synth)
        self._wire(f"i{synth}iV{self._f(self.volume[role])}Z")

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
        self._wire(f"i{drums}iV{self._f(self.volume['drums'])}Z")
        self._configured_synths.add(drums)

        self._configure_synth("bass")
        self._configure_synth("strum")
        self._configure_synth("chord")

    @staticmethod
    def _params_from_list(values: Any) -> dict[str, float]:
        if not isinstance(values, (list, tuple)):
            return {}
        result: dict[str, float] = {}
        for index in range(0, len(values) - 1, 2):
            try:
                result[str(values[index])] = float(values[index + 1])
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
            return float(value)

        lfo_hz = nonneg("lfo_hz")
        portamento = nonneg("portamento_ms")

        if 0 <= patch <= 127:  # Juno
            cutoff = nonneg("filter_hz")
            if cutoff is not None:
                cutoff = max(20.0, min(18000.0, cutoff))
                commands.append(f"v0F{self._f(cutoff)}i{synth}Z")

            resonance = nonneg("resonance")
            if resonance is not None:
                resonance = max(0.51, min(12.0, resonance))
                commands.append(f"v0R{self._f(resonance)}i{synth}Z")

            if lfo_hz is not None:
                commands.append(
                    f"v1f{self._f(max(0.01, min(20.0, lfo_hz)))}i{synth}Z"
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
                depth = max(0.0, min(4.0, vcf_lfo))
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
                    f"v1f{self._f(max(0.01, min(20.0, lfo_hz)))}i{synth}Z"
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
                    return float(value)

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

        rhythm_generation: int | None = None
        rhythm_config: dict[str, Any] | None = None
        if role == "chord" and patch_required and self.rhythm_running:
            rhythm_generation, rhythm_config = self._prepare_rhythm_rebuild(
                reset_phase=False
            )

        self.selected_synth[role] = name
        self.synth_params[role] = new_params
        now_active = self._adsr_is_active(role)
        self._adsr_override_active[role] = now_active
        patch_required = patch_required or (was_active and not now_active)

        if patch_required:
            self._configure_synth(role)
        elif changed_keys:
            self._apply_supported_params(role, changed_keys)

        if rhythm_generation is not None and rhythm_config is not None:
            self.writer.delay(self._rhythm_guard_seconds())
            self._install_rhythm_schedule(rhythm_generation, rhythm_config)

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
        for synth in self._role_synth_ids(role):
            self._wire(f"i{synth}iV{self._f(level)}Z")

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

    def _chord_state(self, payload_text: str) -> None:
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            return
        self.chord_notes = [float(x) for x in payload.get("notes", [])]
        self.bass_notes = [float(x) for x in payload.get("bass_notes", [])]

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

        # Both accompaniment chords AND bass derive their pitch from this
        # chord state.  Rebuild if either lane is active.
        if self.rhythm_running and (
            self.rhythm_chord_enabled or self.bass_running
        ):
            self._rebuild_rhythm(reset_phase=False)

    # ------------------------------------------------------------------
    # AMY sequencer
    # ------------------------------------------------------------------

    def _schedule(
        self,
        generation: int,
        tick: int,
        period: int,
        body: str,
    ) -> None:
        tick = max(0, int(tick))
        period = max(1, int(period))
        body = body[:-1] if body.endswith("Z") else body
        self._wire(
            f"H{tick},{period}{body}Z",
            low_generation=generation,
        )

    def _rhythm_commands(self, generation: int) -> None:
        config = self.rhythm_config
        if not config:
            return

        period = max(1, round(float(config["length_beats"]) * AMY_PPQ))
        rhythm_cfg = self.config["rhythm"]
        budget = int(rhythm_cfg.get("max_sequencer_items", 256))
        scheduled = 0
        dropped = 0

        def room(items: int) -> bool:
            nonlocal scheduled, dropped
            if scheduled + items <= budget:
                scheduled += items
                return True
            dropped += items
            return False

        drum_synth = self.synth_id["drums"]
        sample_map = self.config["drums"]["sample_map"]
        drum_gain = max(0.0, float(self.config["drums"].get("velocity_gain", 5.0)))
        for event in config.get("percussion_events", []):
            sample = str(event.get("sample", ""))
            if sample not in sample_map or not room(1):
                continue
            tick = round(float(event.get("time", 0.0)) * AMY_PPQ)
            velocity = max(0.0, min(1.0, float(event.get("amp", 1.0))))
            hit = sample_map[sample]
            preset = int(hit["preset"])
            native_note = float(hit["note"])
            # The legacy patch-258 mapping scales incoming GM velocity to a
            # 0..5 range.  Apply the same gain directly, while synth_level is
            # still the user's overall percussion-volume control.
            hit_velocity = velocity * drum_gain
            self._schedule(
                generation,
                tick,
                period,
                f"p{preset}n{self._f(native_note)}l{self._f(hit_velocity)}i{drum_synth}",
            )

        if self.bass_running and self.bass_notes:
            bass_synth = self.synth_id["bass"]
            gate = max(
                1,
                round(float(rhythm_cfg["bass_gate_beats"]) * AMY_PPQ),
            )
            for event in config.get("bass_events", []):
                if not room(2):
                    continue
                degree = int(event.get("degree", 0))
                note = self.bass_notes[degree % len(self.bass_notes)]
                tick = round(float(event.get("time", 0.0)) * AMY_PPQ)
                velocity = max(0.0, min(1.0, float(event.get("amp", 1.0))))
                self._schedule(
                    generation,
                    tick,
                    period,
                    f"n{self._f(note)}l{self._f(velocity)}i{bass_synth}",
                )
                self._schedule(
                    generation,
                    tick + gate,
                    period,
                    f"n{self._f(note)}l0i{bass_synth}",
                )

        if self.rhythm_chord_enabled and self.chord_notes:
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
            items_per_hit = len(rhythm_notes) + 1
            for event in config.get("chord_events", []):
                if not room(items_per_hit):
                    continue
                tick = round(float(event.get("time", 0.0)) * AMY_PPQ)
                velocity = max(0.0, min(1.0, float(event.get("amp", 1.0))))
                for note in rhythm_notes:
                    self._schedule(
                        generation,
                        tick,
                        period,
                        f"n{self._f(note)}l{self._f(velocity)}i{chord_synth}",
                    )
                self._schedule(
                    generation,
                    tick + gate,
                    period,
                    f"l0i{chord_synth}",
                )

        if dropped:
            print(
                f"AMY rhythm warning: sequencer budget {budget} reached; "
                f"dropped {dropped} scheduled item(s)",
                flush=True,
            )

    def _silence_accompaniment(self) -> None:
        # Critical: RESET_SEQUENCER deletes future note-offs too.  Explicitly
        # terminate any currently sounding accompaniment before clearing it.
        self._wire(f"l0i{self.synth_id['bass']}Z")
        self._wire(f"l0i{self.synth_id['rhythm_chord']}Z")

    def _rhythm_guard_seconds(self) -> float:
        guard_ms = float(
            self.config["rhythm"].get("sequencer_reset_guard_ms", 10.0)
        )
        return max(0.0, guard_ms / 1000.0)

    def _prepare_rhythm_rebuild(
        self, *, reset_phase: bool
    ) -> tuple[int | None, dict[str, Any] | None]:
        """Stop/clear old rhythm state before any replacement is installed."""
        generation = self.writer.new_low_generation()

        # Stop transport first. Under AMY's internal clock zY0/zY1 preserves
        # sequencer_tick_count; zY1 merely re-anchors the next tick to 'now'.
        self._wire("zY0Z")
        self._silence_accompaniment()
        self._wire(f"S{RESET_SEQUENCER}Z")

        if not self.rhythm_running:
            return None, None

        config = self.rhythm_config
        if not config:
            return None, None

        rhythm_id = str(config.get("id", ""))
        if self._scheduled_rhythm_id != rhythm_id:
            reset_phase = True
        self._scheduled_rhythm_id = rhythm_id

        if reset_phase:
            self._wire(f"S{RESET_TIMEBASE}Z")

        # RESET_SEQUENCER executes on an AMY block boundary.  This delay is in
        # the UART writer thread and orders later high-priority patch commands
        # after the reset has had time to execute on the P4.
        self.writer.delay(self._rhythm_guard_seconds())
        return generation, config

    def _install_rhythm_schedule(
        self, generation: int, config: dict[str, Any]
    ) -> None:
        self._wire(f"j{self._f(float(config.get('tempo', 108.0)))}Z")
        self._rhythm_commands(generation)
        self._wire("zY1Z", low_generation=generation)

    def _rebuild_rhythm(
        self,
        *,
        reset_phase: bool,
        resync_chord: bool = False,
    ) -> None:
        generation, config = self._prepare_rhythm_rebuild(
            reset_phase=reset_phase
        )
        if generation is None or config is None:
            return

        # Before the first automatic chord, reapply only actual engine
        # overrides. Native AMY patch values are deliberately omitted: a Juno
        # filter such as Chorus Vibes has a 27.365 Hz base coefficient plus note
        # and envelope coefficients, and rewriting the base term is unnecessary.
        if resync_chord and self.rhythm_chord_enabled:
            self._sync_synth_params(
                "chord",
                (self.synth_id["rhythm_chord"],),
            )

        self._install_rhythm_schedule(generation, config)

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
        self.writer.new_low_generation()
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
            self.bass_running = bool(int(value))
            if not self.bass_running:
                self._wire(f"l0i{self.synth_id['bass']}Z")
            if self.rhythm_running:
                self._rebuild_rhythm(reset_phase=False)
        elif address == a["rhythm_config"]:
            try:
                self.rhythm_config = json.loads(str(value))
            except json.JSONDecodeError:
                return
            if self.rhythm_running:
                self._rebuild_rhythm(reset_phase=False)
            else:
                tempo = float(self.rhythm_config.get("tempo", 108.0))
                self._wire(f"j{self._f(tempo)}Z")
        elif address == a["rhythm_chord_enabled"]:
            enabled = bool(int(value))
            if self.rhythm_chord_enabled == enabled:
                return
            self.rhythm_chord_enabled = enabled
            if not enabled:
                self._wire(f"l0i{self.synth_id['rhythm_chord']}Z")
            if self.rhythm_running:
                self._rebuild_rhythm(
                    reset_phase=False,
                    resync_chord=enabled,
                )
        elif address == a["rhythm_running"]:
            new_state = bool(int(value))
            if new_state:
                self.rhythm_running = True
                self._rebuild_rhythm(
                    reset_phase=True,
                    resync_chord=True,
                )
            else:
                self.rhythm_running = False
                self.writer.new_low_generation()
                self._silence_accompaniment()
                self._wire("zY0Z")
                self._wire(f"S{RESET_SEQUENCER}Z")
        elif address == a["panic"]:
            self._panic()

    def close(self) -> None:
        try:
            self.writer.new_low_generation()
            self._cancel_strum_tail()
            self._wire("zY0Z")
            for synth in self.synth_id.values():
                self._wire(f"l0i{synth}Z")
            self._wire(f"S{RESET_SEQUENCER}Z")
        finally:
            self.writer.close()
            self.debug_log.close()
