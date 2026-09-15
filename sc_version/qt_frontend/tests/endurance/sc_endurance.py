#!/usr/bin/env python3
"""Drive the real SC edition indefinitely through its public Qt surface.

The driver, frontend, sclang/Supernova and PipeWire recorder are separate
processes. No synthetic-input endpoint is added to production code. With
``--gui`` the frontend also loads and continuously captures the production QML
scene through Qt's offscreen platform. Use Ctrl-C for a clean stop; a zero
``--cycles`` value means run forever.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
import math
import os
from pathlib import Path
import random
import signal
import socket
import subprocess
import sys
import threading
import time
from typing import Any, Iterator
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import wave


ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = ROOT.parents[1]
SC_ROOT = ROOT.parent / "supercollider"
CODE = ROOT / "code"
SUPPORT = ROOT / "tests" / "support"
HEADLESS_APP = ROOT / "tests" / "integration" / "headless_app.py"
SC_CONFIG = ROOT / "config" / "supercollider.json"
for module_path in (CODE, SUPPORT):
    sys.path.insert(0, str(module_path))

from catalog_extensions import load_synth_catalog  # noqa: E402
from sc_drum_kits import DRUM_KITS  # noqa: E402
from supercollider_config import load_supercollider_config  # noqa: E402
from supercollider_platform_adapter import (  # noqa: E402
    locate_supercollider_runtime,
    pipewire_jack_prefix,
    server_program_command,
)


FATAL_LOG_TEXT = (
    "FAILURE IN SERVER",
    "Binding loop detected",
    "No more buffer numbers",
    "Traceback (most recent call last)",
    "server 'localhost' disconnected",
    "Exception:",
    "SynthDef not found",
    "buffer overflow",
    "failed to get an audio bus allocated",
    "Message 'index' not understood",
    "exception in /s_new",
)


@dataclass(frozen=True, slots=True)
class Action:
    name: str
    args: tuple[Any, ...] = ()
    dwell: float = 0.08


@dataclass(frozen=True, slots=True)
class AudioWindow:
    duration_seconds: float
    rms: float
    peak: float
    clipped_fraction: float
    longest_silent_seconds: float


def free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def analyze_wave(path: Path, *, silence_threshold: int = 2) -> AudioWindow:
    with wave.open(str(path), "rb") as source:
        if source.getsampwidth() != 2 or source.getnchannels() != 2:
            raise RuntimeError("endurance capture must be 16-bit stereo PCM")
        sample_rate = source.getframerate()
        frames = source.getnframes()
        raw = source.readframes(frames)
    import array

    samples = array.array("h")
    samples.frombytes(raw)
    if sys.byteorder != "little":
        samples.byteswap()
    if not samples:
        raise RuntimeError("endurance capture contains no samples")
    squared = 0.0
    peak = 0
    clipped = 0
    silent_run = 0
    longest_silent_run = 0
    for left, right in zip(samples[0::2], samples[1::2], strict=True):
        magnitude = max(abs(int(left)), abs(int(right)))
        squared += (int(left) * int(left) + int(right) * int(right)) / 2.0
        peak = max(peak, magnitude)
        if magnitude >= 32767:
            clipped += 1
        if magnitude <= silence_threshold:
            silent_run += 1
            longest_silent_run = max(longest_silent_run, silent_run)
        else:
            silent_run = 0
    frame_count = len(samples) // 2
    return AudioWindow(
        duration_seconds=frame_count / float(sample_rate),
        rms=math.sqrt(squared / frame_count) / 32768.0,
        peak=peak / 32768.0,
        clipped_fraction=clipped / frame_count,
        longest_silent_seconds=longest_silent_run / float(sample_rate),
    )


def action_cycle(
    cycle: int,
    synths: list[Any],
    gui_artifact_dir: Path | None = None,
) -> Iterator[Action]:
    """Yield broad deterministic interaction coverage without musical timing."""

    synth_indexes = [index for index, synth in enumerate(synths) if synth.kind == "synth"]
    sample_indexes = [index for index, synth in enumerate(synths) if synth.kind == "sample"]
    rng = random.Random(0x4C42 + cycle)

    yield Action("setMasterVolume", (0.42,))
    yield Action("setChordVolume", (0.46,))
    yield Action("setStrumVolume", (0.40,))
    yield Action("setBassVolume", (0.43,))
    yield Action("setPercussionVolume", (0.42,))
    yield Action("ensureRhythmRunning", (True,), 0.2)
    yield Action("ensureBassRunning", (True,), 0.2)
    yield Action("ensureChordArpeggioRunning", (True,), 0.2)
    if gui_artifact_dir is not None:
        for midi_screen, name in ((False, "omni"), (True, "midi")):
            yield Action("setGuiScreen", (midi_screen,), 0.25)
            yield Action(
                "captureGui",
                (str(gui_artifact_dir / f"gui-{name}-cycle-{cycle:05d}.png"),),
                0.1,
            )

    for rhythm in range(18):
        yield Action("setRhythmIndex", (rhythm,), 0.16)
        yield Action("setRhythmBusyness", (float(1 + rhythm % 5),))
        yield Action("setRhythmChordActivity", (float(1 + (rhythm + 1) % 5),))
        yield Action("setRhythmBassActivity", (float(1 + (rhythm + 2) % 5),))
        yield Action("setRhythmFillDensity", (float(1 + rhythm % 8),))
        yield Action("toggleRhythmFill", (rhythm % 5,))
        yield Action("setChordArpeggioRate", (float(1 + rhythm % 4),))
        yield Action("setBassRiffSelector", (float(1 + rhythm % 5),))
        yield Action("setBassVoicingShift", (float((rhythm % 7) - 3),))
        drum_kit_index = rhythm % len(DRUM_KITS)
        yield Action("setDrumKitIndex", (drum_kit_index,), 0.12)
        yield Action("setMidiDrumKitIndex", (drum_kit_index,), 0.12)
        # The dedicated percussion row receives on MIDI channel 10. This
        # proves that every selected MIDI kit is not merely visible but can
        # prepare and play through the public physical-input path.
        drum_note = (36, 38, 42, 46, 49)[rhythm % 5]
        yield Action("injectMidiNote", (10, drum_note, 112, True), 0.08)
        yield Action("injectMidiNote", (10, drum_note, 0, False), 0.04)
        yield Action("pressChord", (rhythm % 6, rhythm % 12), 0.10)
        yield Action("strumStart", (0.08 + (rhythm % 4) * 0.2,))
        yield Action("strumMove", (0.88 - (rhythm % 4) * 0.18,))
        yield Action("strumEnd", dwell=0.14)
        yield Action("releaseChord", (rhythm % 6, rhythm % 12), 0.26)
        if rhythm % 3 == 0:
            yield Action("toggleChordArpeggioDirection")
            yield Action("toggleStrumLadderMode")
        if rhythm % 4 == 0:
            yield Action("setReverbLevel", (0.15 + 0.12 * (rhythm % 5),))
            yield Action("setReverbRoom", (0.25 + 0.1 * (rhythm % 6),))
            yield Action("setReverbDamping", (0.15 + 0.1 * (rhythm % 7),))
            yield Action("toggleReverbDrums")
        if rhythm == 9:
            # Cover the actual toggle actions while keeping the deliberately
            # silent interval shorter than the dropout qualification window.
            yield Action("toggleRhythm", dwell=0.15)
            yield Action("toggleRhythm", dwell=0.15)
            yield Action("toggleBassRunning", dwell=0.15)
            yield Action("toggleBassRunning", dwell=0.15)
            yield Action("toggleChordArpeggio", dwell=0.15)
            yield Action("toggleChordArpeggio", dwell=0.15)

    # Each cycle covers a rotating quarter of both catalogues for every OMNI
    # role and every pitched MIDI row. Four cycles exercise the full catalogue.
    for catalogue in (synth_indexes, sample_indexes):
        quarter = max(1, math.ceil(len(catalogue) / 4))
        start = (cycle % 4) * quarter
        selected = catalogue[start : start + quarter]
        for index in selected:
            for role in ("chord", "strum", "bass"):
                yield Action(f"set{role.title()}SynthIndex", (index,), 0.12)
            yield Action("pressChord", (cycle % 6, index % 12), 0.08)
            yield Action("strumTap", ((index % 17) / 16.0,), 0.10)
            yield Action("releaseChord", (cycle % 6, index % 12), 0.12)
            row = index % 5
            yield Action("setMidiSynthIndex", (row, index), 0.12)
            yield Action("setMidiVolume", (row, 0.36))
            yield Action("midiPreviewStart", (row, 0.15, bool(index % 2)), 0.07)
            yield Action("midiPreviewMove", (row, 0.82, bool(index % 2)), 0.07)
            yield Action("midiPreviewEnd", dwell=0.10)

    for row in range(5):
        yield Action("toggleMidiSustain", (row,))
        yield Action("injectMidiNote", (row, 48 + row, 88, True), 0.09)
        yield Action("injectMidiControl", (row, 64, 127), 0.08)
        yield Action("injectMidiNote", (row, 48 + row, 64, False), 0.08)
        yield Action("injectMidiControl", (row, 64, 0), 0.10)
        yield Action("toggleMidiSustain", (row,))
        yield Action("injectMidiButton", (row, 70 + row, 100), 0.04)
        yield Action("injectMidiButton", (row, 70 + row, 0), 0.06)

    for bend in (0, 4096, 8192, 12288, 16383, 8192):
        yield Action("injectMidiPitchBend", (0, bend), 0.06)
    for value in (0.0, 0.25, 0.75, 1.0, 0.5):
        yield Action("injectOscControl", ("/endurance/control", 0, value, "continuous"))
    for preset in rng.sample(range(18), 18):
        yield Action("selectPreset", (preset,), 0.12)
        yield Action("selectMidiPreset", (preset % 12,), 0.08)

    yield Action("panic", dwell=0.3)
    # Restore sustained activity before the next capture/cycle.
    yield Action("ensureRhythmRunning", (True,), 0.2)
    yield Action("ensureBassRunning", (True,), 0.2)
    yield Action("ensureChordArpeggioRunning", (True,), 0.2)


def pcm_chord_switch_cycle(synths: list[Any]) -> Iterator[Action]:
    """Stress prepared PCM revision handover while arpeggios keep running."""

    keys = (
        "sample.vsco.uprightpiano",
        "sample.vsco.flute-ks",
        "sample.vsco.marimba",
        "sample.vsco.flute-ks.art.c-2-sustain-vibrato",
        "sample.vsco.flute-ks",
    )
    indexes = {synth.key: index for index, synth in enumerate(synths)}
    missing = [key for key in keys if key not in indexes]
    if missing:
        raise RuntimeError(f"PCM chord-switch fixtures missing from catalogue: {missing}")
    yield Action("setMasterVolume", (0.36,))
    yield Action("setChordVolume", (0.46,))
    yield Action("ensureRhythmRunning", (True,), 0.2)
    yield Action("pressChord", (0, 0), 0.08)
    yield Action("releaseChord", (0, 0), 0.08)
    yield Action("ensureChordArpeggioRunning", (True,), 0.2)
    for _round in range(6):
        for key in keys:
            yield Action("setChordSynthIndex", (indexes[key],), 0.12)
    # Let the final prepared revision cross a complete arpeggio phrase and
    # allow delayed /n_end notifications to surface in the engine log.
    yield Action("setChordArpeggioRate", (4.0,), 2.0)


def vsco_drum_role_cycle() -> Iterator[Action]:
    """Exercise the legacy VSCO kit through several semantic drum roles."""

    yield Action("ensureRhythmRunning", (True,), 0.4)
    # Select away first so the VSCO selection is never a state-dependent no-op.
    yield Action("setDrumKitIndex", (1,), 0.2)
    # The complete legacy percussion program is roughly 281 MiB decoded, so
    # leave its asynchronous first-load enough time on ordinary storage.
    yield Action("setDrumKitIndex", (0,), 15.0)
    yield Action("setMasterVolume", (0.36,))
    yield Action("setPercussionVolume", (0.50,))
    yield Action("setRhythmIndex", (0,), 0.1)
    yield Action("setRhythmBusyness", (5.0,), 0.1)
    yield Action("ensureRhythmRunning", (True,), 5.0)
    yield Action("toggleRhythmFill", (4,), 3.0)


def startup_bass_riff_cycle() -> Iterator[Action]:
    """Reproduce P5 riff activation before the first chord exists."""

    yield Action("selectPreset", (4,), 0.2)
    yield Action("setRhythmBusyness", (2.0,))
    yield Action("setRhythmBassActivity", (5.0,))
    yield Action("setBassRiffSelector", (1.0,))
    yield Action("ensureBassRunning", (True,))
    yield Action("ensureRhythmRunning", (True,), 0.3)
    yield Action("pressChord", (0, 5), 4.0)
    yield Action("releaseChord", (0, 5), 0.3)


def strum_pressure_cycle(*, through_qml: bool = False) -> Iterator[Action]:
    """Hold the busiest accompaniment while increasing strum pressure."""

    # Trance Lift combines a comparatively expensive native strum voice,
    # supersaw accompaniment, acid bass and native percussion. It is a useful
    # upper-load production preset rather than a synthetic oscillator fixture.
    yield Action("selectPreset", (14,), 0.4)
    yield Action("setMasterVolume", (0.36,))
    yield Action("setChordVolume", (0.42,))
    yield Action("setStrumVolume", (0.38,))
    yield Action("setBassVolume", (0.40,))
    yield Action("setPercussionVolume", (0.42,))
    yield Action("setRhythmBusyness", (5.0,), 0.08)
    yield Action("setRhythmChordActivity", (5.0,), 0.08)
    yield Action("setRhythmBassActivity", (5.0,), 0.08)
    yield Action("setRhythmFillDensity", (1.0,), 0.08)
    yield Action("ensureRhythmRunning", (True,), 0.2)
    yield Action("ensureBassRunning", (True,), 0.2)
    yield Action("ensureChordArpeggioRunning", (True,), 0.2)
    yield Action("pressChord", (0, 0), 2.0)

    # Move across successive physical positions instead of jumping directly
    # between endpoints. This matches a real pointer trajectory: chord tones
    # are attacked across the duration of each sweep rather than in one burst.
    down = [0.96 - (index * 0.92 / 36) for index in range(37)]
    up = list(reversed(down))
    sweep_count = 200
    if through_qml:
        # One press crosses the full surface for nearly a minute. Releasing
        # between shorter batches failed to model the reported performance
        # problem and artificially allowed all strum voices to drain.
        yield Action(
            "strumContinuousSweeps",
            (sweep_count, len(down), 8),
            0.02,
        )
    else:
        yield Action("strumStart", (down[0],), 0.008)
        for sweep in range(sweep_count):
            path = down if sweep % 2 == 0 else up
            for position in path[1:]:
                yield Action("strumMove", (position,), 0.008)
        yield Action("strumEnd", dwell=0.1)
    yield Action("strumTap", (0.50,), 1.0)
    yield Action("releaseChord", (0, 0), 1.0)


class ApiClient:
    def __init__(self, port: int) -> None:
        self.port = port

    def health(self) -> bool:
        try:
            with urlopen(f"http://127.0.0.1:{self.port}/health", timeout=1) as reply:
                return bool(json.loads(reply.read()).get("ok"))
        except (URLError, TimeoutError, ConnectionError):
            return False

    def action(self, action: Action) -> None:
        payload = json.dumps(
            {"action": action.name, "args": list(action.args)}
        ).encode("utf-8")
        request = Request(
            f"http://127.0.0.1:{self.port}/action",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            # A production-QML pointer path deliberately holds the GUI event
            # loop while QTest delivers several seconds of real motion.
            with urlopen(request, timeout=125) as reply:
                result = json.loads(reply.read())
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{action.name}{action.args}: {detail}") from exc
        if not result.get("ok"):
            raise RuntimeError(f"{action.name}{action.args}: {result}")


def wait_for(predicate: Any, timeout: float, description: str) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise RuntimeError(f"timed out waiting for {description}")


def stop_process(process: subprocess.Popen[Any], timeout: float = 5.0) -> None:
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=2)


class AudioMonitor(threading.Thread):
    def __init__(self, artifact_dir: Path, chunk_seconds: float) -> None:
        super().__init__(name="sc-endurance-audio", daemon=True)
        self.artifact_dir = artifact_dir
        self.chunk_seconds = chunk_seconds
        self.stop_requested = threading.Event()
        self.failure: BaseException | None = None
        self.window_count = 0

    def stop(self) -> None:
        self.stop_requested.set()

    def _capture(self, path: Path) -> None:
        process = subprocess.Popen(
            [
                "pw-record", "--target", "0", "--rate", "48000",
                "--channels", "2", "--format", "s16", str(path),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            def recorder_ready() -> bool:
                ports = subprocess.run(
                    ["pw-link", "-i"], text=True, capture_output=True, check=False
                ).stdout
                return "pw-record:input_FL" in ports and "pw-record:input_FR" in ports

            wait_for(recorder_ready, 5, "PipeWire recorder ports")
            for source, target in (
                ("supernova:output_1", "pw-record:input_FL"),
                ("supernova:output_2", "pw-record:input_FR"),
            ):
                linked = subprocess.run(
                    ["pw-link", source, target], text=True, capture_output=True
                )
                if linked.returncode:
                    raise RuntimeError(linked.stderr.strip() or f"cannot link {source}")
            self.stop_requested.wait(self.chunk_seconds)
        finally:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
            try:
                _stdout, stderr = process.communicate(timeout=4)
            except subprocess.TimeoutExpired:
                stop_process(process)
                stderr = "pw-record did not stop cleanly"
            if process.returncode not in (0, 1, 130, -signal.SIGINT):
                raise RuntimeError(f"pw-record failed: {stderr}")

    def run(self) -> None:
        metrics_log = self.artifact_dir / "audio-windows.jsonl"
        try:
            while not self.stop_requested.is_set():
                wave_path = self.artifact_dir / f"audio-{self.window_count:05d}.wav"
                self._capture(wave_path)
                metrics = analyze_wave(wave_path)
                with metrics_log.open("a", encoding="utf-8") as target:
                    target.write(json.dumps(asdict(metrics), sort_keys=True) + "\n")
                self.window_count += 1
                if metrics.rms < 1e-5:
                    raise RuntimeError(f"live audio became silent: {metrics}")
                if metrics.clipped_fraction > 0.01:
                    raise RuntimeError(f"live audio clips persistently: {metrics}")
                if metrics.longest_silent_seconds > 3.0:
                    raise RuntimeError(f"live audio dropout exceeds 3 s: {metrics}")
                wave_path.unlink(missing_ok=True)
        except BaseException as exc:
            self.failure = exc
            self.stop_requested.set()


def log_has_failure(path: Path) -> str | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    return next((needle for needle in FATAL_LOG_TEXT if needle in text), None)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=0, help="0 runs indefinitely")
    parser.add_argument(
        "--start-cycle",
        type=int,
        default=0,
        help="catalogue rotation cycle used first (diagnostic reproduction)",
    )
    parser.add_argument("--chunk-seconds", type=float, default=60.0)
    parser.add_argument(
        "--startup-idle-seconds",
        type=float,
        default=0.0,
        help="leave the real frontend and engine idle before driving actions",
    )
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument(
        "--gui",
        action="store_true",
        help="load and capture the real production QML scene offscreen",
    )
    parser.add_argument(
        "--gui-platform",
        choices=("offscreen", "native"),
        default="offscreen",
        help="use deterministic offscreen QML or the current desktop compositor",
    )
    parser.add_argument(
        "--scenario",
        choices=(
            "broad",
            "pcm-chord-switch",
            "vsco-drum-roles",
            "startup-bass-riff",
            "strum-pressure",
        ),
        default="broad",
        help="run broad coverage or one focused playback regression",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    artifact_dir = (args.artifact_dir or ROOT / "test-artifacts" / f"sc-endurance-{stamp}").resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    sc_log = artifact_dir / "supercollider.log"
    frontend_log = artifact_dir / "frontend.log"
    debug_log = artifact_dir / "frontend-debug.jsonl"
    action_log = artifact_dir / "actions.jsonl"
    config = load_supercollider_config(SC_CONFIG)
    runtime = locate_supercollider_runtime()
    synths, _chord, _strum, _bass = load_synth_catalog(
        ROOT / "instruments" / "supercollider-legacy-map.json"
    )
    api_port = free_tcp_port()
    runtime_home = artifact_dir / "home"
    runtime_home.mkdir()

    environment = os.environ.copy()
    environment.update(
        {
            "OMNICHORD_SC_PORT": str(config.language.port),
            "OMNICHORD_SC_SAMPLE_RATE": str(config.server.sample_rate),
            "OMNICHORD_SC_BLOCK_SIZE": str(config.server.block_size),
            "OMNICHORD_SC_MAX_NODES": str(config.server.max_nodes),
            "OMNICHORD_SC_MAX_BUFFERS": str(config.server.max_buffers),
            "OMNICHORD_SC_MAX_GESTURE_VOICES": str(
                config.server.gesture_voice_limit
            ),
            "OMNICHORD_SC_MEM_KIB": str(config.server.realtime_memory_kib),
            "OMNICHORD_SC_VSCO_ROOT": str(config.samples.vsco_root),
            "OMNICHORD_SC_SAMPLE_RAM_MIB": str(config.samples.ram_budget_mib),
            "OMNICHORD_SC_SYNTH_PROGRAM": server_program_command(
                runtime.supernova
            ),
        }
    )
    sc_stream = sc_log.open("w", encoding="utf-8")
    frontend_stream = frontend_log.open("w", encoding="utf-8")
    sc_process: subprocess.Popen[Any] | None = None
    frontend_process: subprocess.Popen[Any] | None = None
    audio_monitor: AudioMonitor | None = None
    started = time.monotonic()
    try:
        command = [*pipewire_jack_prefix(environment=environment), "sclang", "-D", str(SC_ROOT / "bootstrap.scd")]
        sc_process = subprocess.Popen(
            command, cwd=SC_ROOT, env=environment, stdout=sc_stream,
            stderr=subprocess.STDOUT, start_new_session=True,
        )
        wait_for(
            lambda: "LB_OMNICHORD_SC_READY" in sc_log.read_text(encoding="utf-8", errors="replace"),
            45,
            "SuperCollider readiness",
        )

        frontend_environment = environment.copy()
        frontend_environment.update(
            {
                "HOME": str(runtime_home),
                "OMNICHORD_SC_CONFIG": str(SC_CONFIG),
                "OMNICHORD_TEST_API_PORT": str(api_port),
                "PYTHONUNBUFFERED": "1",
            }
        )
        if args.gui:
            frontend_environment["OMNICHORD_TEST_LOAD_QML"] = "1"
            if args.gui_platform == "offscreen":
                frontend_environment.update(
                    {
                        "QT_QPA_PLATFORM": "offscreen",
                        "QT_QUICK_BACKEND": "software",
                        "QSG_INFO": "0",
                    }
                )
        frontend_process = subprocess.Popen(
            [sys.executable, str(HEADLESS_APP), "--debug-file", str(debug_log)],
            cwd=ROOT, env=frontend_environment, stdout=frontend_stream,
            stderr=subprocess.STDOUT, start_new_session=True,
        )
        api = ApiClient(api_port)
        wait_for(api.health, 20, "frontend control process")

        idle_deadline = time.monotonic() + max(0.0, args.startup_idle_seconds)
        while time.monotonic() < idle_deadline:
            for process, label in (
                (sc_process, "SuperCollider"),
                (frontend_process, "frontend"),
            ):
                if process.poll() is not None:
                    raise RuntimeError(f"{label} exited with {process.returncode}")
            for path, label in (
                (sc_log, "SuperCollider"),
                (frontend_log, "frontend"),
            ):
                failure = log_has_failure(path)
                if failure is not None:
                    raise RuntimeError(f"{label} log contains {failure!r}")
            time.sleep(min(0.1, max(0.0, idle_deadline - time.monotonic())))
        if args.startup_idle_seconds > 0:
            print(
                f"SC_ENDURANCE_IDLE_COMPLETE seconds={args.startup_idle_seconds:.1f}",
                flush=True,
            )

        audio_monitor = AudioMonitor(artifact_dir, args.chunk_seconds)
        audio_monitor.start()
        cycle = max(0, args.start_cycle)
        completed_cycles = 0
        action_count = 0
        while args.cycles == 0 or completed_cycles < args.cycles:
            if args.scenario == "pcm-chord-switch":
                actions = pcm_chord_switch_cycle(synths)
            elif args.scenario == "vsco-drum-roles":
                actions = vsco_drum_role_cycle()
            elif args.scenario == "startup-bass-riff":
                actions = startup_bass_riff_cycle()
            elif args.scenario == "strum-pressure":
                actions = strum_pressure_cycle(through_qml=args.gui)
            else:
                actions = action_cycle(
                    cycle,
                    synths,
                    artifact_dir if args.gui else None,
                )
            for action in actions:
                for process, label in ((sc_process, "SuperCollider"), (frontend_process, "frontend")):
                    if process.poll() is not None:
                        raise RuntimeError(f"{label} exited with {process.returncode}")
                if audio_monitor.failure is not None:
                    raise RuntimeError(f"audio monitor failed: {audio_monitor.failure}")
                for path, label in ((sc_log, "SuperCollider"), (frontend_log, "frontend")):
                    failure = log_has_failure(path)
                    if failure is not None:
                        raise RuntimeError(f"{label} log contains {failure!r}")
                api.action(action)
                action_count += 1
                with action_log.open("a", encoding="utf-8") as target:
                    target.write(
                        json.dumps(
                            {
                                "elapsed_seconds": round(time.monotonic() - started, 6),
                                "cycle": cycle,
                                "action": action.name,
                                "args": action.args,
                            },
                            separators=(",", ":"),
                        )
                        + "\n"
                    )
                time.sleep(action.dwell)
            cycle += 1
            completed_cycles += 1
            with (artifact_dir / "progress.json").open("w", encoding="utf-8") as target:
                json.dump(
                    {
                        "started_utc": stamp,
                        "elapsed_seconds": round(time.monotonic() - started, 3),
                        "cycles": completed_cycles,
                        "next_cycle": cycle,
                        "actions": action_count,
                        "audio_windows": audio_monitor.window_count,
                    },
                    target,
                    indent=2,
                )
                target.write("\n")
        return 0
    except KeyboardInterrupt:
        return 0
    except BaseException as exc:
        (artifact_dir / "FAILURE.txt").write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
        print(f"SC_ENDURANCE_FAILURE {type(exc).__name__}: {exc}", flush=True)
        return 1
    finally:
        if audio_monitor is not None:
            audio_monitor.stop()
            audio_monitor.join(timeout=8)
        if frontend_process is not None:
            stop_process(frontend_process)
        if sc_process is not None:
            stop_process(sc_process)
        frontend_stream.close()
        sc_stream.close()
        print(
            f"SC_ENDURANCE_STOP elapsed={time.monotonic() - started:.1f}s "
            f"artifacts={artifact_dir}",
            flush=True,
        )


if __name__ == "__main__":
    raise SystemExit(main())
