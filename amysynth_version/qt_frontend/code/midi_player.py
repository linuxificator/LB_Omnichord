from __future__ import annotations

import glob
import json
import math
import os
import select
import threading
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot

import app_core
from control_limits import clamp_control_value
from synth_programs import resolve_program
from synth_state import SynthState


MIDI_ROW_COUNT = 6
MIDI_PRESET_COUNT = 18
MIDI_DRUM_KEY = "drum_kit_0"
MIDI_PRESET_DIR = Path.home() / ".omnichord" / "midi"
MIDI_FACTORY_DIR = app_core.INSTRUMENT_DIR / "midi_default_presets"
MIDI_LAST_PRESET_FILE = "last_preset.json"
MIDI_PREVIEW_LOW = app_core.STRUM_LOW_MIDI
MIDI_PREVIEW_HIGH = app_core.STRUM_HIGH_MIDI
MIDI_REVERB_MAX = 2.0

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


class _LinuxRawMidiReader:
    """Dependency-free ALSA raw-MIDI reader for Raspberry Pi/Linux."""

    def __init__(
        self,
        callback: Callable[[int, int, int, bool], None],
        device_glob: str,
        enabled: bool,
    ) -> None:
        self._callback = callback
        self._glob = str(device_glob)
        self._enabled = bool(enabled)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        if self._enabled:
            self._thread = threading.Thread(
                target=self._run,
                name="omnichord-usb-midi",
                daemon=True,
            )
            self._thread.start()

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

        state["running"] = running
        state["pending"] = pending
        state["sysex"] = sysex

    def _run(self) -> None:
        while not self._stop.is_set():
            paths = sorted(glob.glob(self._glob))
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
        self.configure_drum_synth()

    def _wire(self, command: str) -> None:
        self.client._wire(command)

    def _f(self, value: float) -> str:
        return self.client._f(value)

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
        self._drum_configured = True

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
        self.set_row_volume(row, volume)

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
        self._wire(
            f"n{self._f(note)}l{self._f(level)}i{synth}Z"
        )

        def release() -> None:
            self._wire(f"n{self._f(note)}l0i{synth}Z")

        timer = threading.Timer(0.45, release)
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

        self.engine = MidiAmyEngine(client)
        self._preview_row = -1
        self._preview_last_index: int | None = None

        self._ensure_preset_storage()
        self._load_startup_preset()
        self.syncFromOmni()
        self._apply_all_to_engine()

        midi_cfg = client.config.get("midi_input", {})
        self._reader = _LinuxRawMidiReader(
            self.process_midi_note,
            str(
                midi_cfg.get(
                    "device_glob",
                    "/dev/snd/midiC*D*",
                )
            ),
            bool(midi_cfg.get("enabled", True)),
        )

    def close(self) -> None:
        self._reader.close()

    @Property(int, notify=stateChanged)
    def stateVersion(self) -> int:
        return self._state_version

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
        if not self._valid_row(row):
            return
        if self._runtime(row).set_control(key, value):
            self._configure_row(int(row))
            self._emit_state()

    @Slot(int, float)
    def setVolume(self, row: int, value: float) -> None:
        if not self._valid_row(row):
            return
        row = int(row)
        value = max(0.0, min(1.0, float(value)))
        if math.isclose(value, self.volumes[row], abs_tol=1e-4):
            return
        self.volumes[row] = value
        if not self._is_drum(row):
            self.engine.set_row_volume(row, value)
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

    def _load_preset(self, number: int, *, emit: bool) -> None:
        path = self._preset_path(number)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.engine.all_notes_off()
        self._apply_data(data)
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
        self.presetStored.emit(self._selected_preset)

    @Slot(int)
    def resetRow(self, row: int) -> None:
        if not self._valid_row(row):
            return
        row = int(row)
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
        changed = (
            mode_index != self._tuning_mode_index
            or not math.isclose(
                reference,
                self._tuning_reference,
                abs_tol=1e-9,
            )
            or not math.isclose(self._bend_offset, 0.0, abs_tol=1e-9)
        )
        self._tuning_mode_index = mode_index
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
        self._bend_direction = 1 if int(direction) > 0 else -1
        self._bend_returning = False
        if not self._bend_timer.isActive():
            self._bend_timer.start()

    @Slot()
    def endPitchBend(self) -> None:
        if self._tuning_coupled:
            self.owner.endPitchBend()
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
        value = max(0.0, min(MIDI_REVERB_MAX, float(value)))
        if math.isclose(value, self._reverb_level, abs_tol=1e-4):
            return
        self._reverb_level = value
        self.reverbLevelChanged.emit()
        self._apply_reverb()

    @Slot(float)
    def setReverbLiveness(self, value: float) -> None:
        value = max(0.0, min(1.0, float(value)))
        if math.isclose(value, self._reverb_liveness, abs_tol=1e-4):
            return
        self._reverb_liveness = value
        self.reverbLivenessChanged.emit()
        self._apply_reverb()

    @Slot(float)
    def setReverbDamping(self, value: float) -> None:
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

    def _apply_all_to_engine(self) -> None:
        for row in range(MIDI_ROW_COUNT):
            self._configure_row(row)
        self._apply_reverb()

    def send_initial_state(self) -> None:
        self._apply_all_to_engine()

    def rebuild_after_panic(self) -> None:
        self.engine.rebuild()
        self._apply_all_to_engine()
