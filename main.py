from __future__ import annotations

import argparse
import copy
import csv
import json
import math
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from PySide6.QtCore import QObject, Property, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from pythonosc.udp_client import SimpleUDPClient


APP_DIR = Path(__file__).resolve().parent

NOTE_DEFINITIONS = (
    {"label": "D♭", "semitone": 1, "accidental": True},
    {"label": "A♭", "semitone": 8, "accidental": True},
    {"label": "E♭", "semitone": 3, "accidental": True},
    {"label": "B♭", "semitone": 10, "accidental": True},
    {"label": "F", "semitone": 5, "accidental": False},
    {"label": "C", "semitone": 0, "accidental": False},
    {"label": "G", "semitone": 7, "accidental": False},
    {"label": "D", "semitone": 2, "accidental": False},
    {"label": "A", "semitone": 9, "accidental": False},
    {"label": "E", "semitone": 4, "accidental": False},
    {"label": "B", "semitone": 11, "accidental": False},
    {"label": "F♯", "semitone": 6, "accidental": True},
)

NOTE_NAMES_BY_SEMITONE = {
    item["semitone"]: item["label"]
    for item in NOTE_DEFINITIONS
}

# Stable ASCII identifiers used by the intonation JSON files.
INTONATION_NOTE_IDS = (
    "c",
    "db",
    "d",
    "eb",
    "e",
    "f",
    "fs",
    "g",
    "ab",
    "a",
    "bb",
    "b",
)

OCTAVE_NAMES = ("O1", "O2", "O3", "O4", "O5", "O6")
OCTAVE_BASES = (24, 36, 48, 60, 72, 84)

ROW_COUNT = 4

TUNING_MODE_NAMES = ("HARM", "EQ", "JV")
DEFAULT_TUNING_MODE_INDEX = 1
DEFAULT_TUNING_REFERENCE = 440

PRESET_COUNT = 18
PRESET_DIRECTORY = Path.home() / ".omnichord"
LAST_PRESET_FILE = "last_preset.json"

# Chord-touch dropout filter, derived from the captured Pi touchscreen trace.
CHORD_QUICK_TAP_MAX_MS = 160
CHORD_INITIAL_RELEASE_GRACE_MS = 450
CHORD_BOUNCE_RELEASE_GRACE_MS = 1300
CHORD_STABLE_HOLD_MS = 800

# Four visible activity states map onto the original five pattern levels.
# State 4 selects the complete arrangement, including both the stylistic
# colour layer and the final fill layer.
ACTIVITY_SOURCE_INDEXES = (0, 1, 2, 4)

# Fixed seven-octave strum window.
#
# MIDI 24 = C1
# MIDI 107 = B7
#
# The strum uses only pitch classes belonging to the active chord, but this
# absolute range is independent of the row octave and inversion controls.
STRUM_LOW_MIDI = 24
STRUM_HIGH_MIDI = 107

SynthRole = Literal["chord", "strum", "bass"]


def source_activity_to_ui(source_level: int) -> int:
    """Convert a catalogue level 0..4 to one visible level 1..4."""
    if source_level <= 0:
        return 1
    if source_level == 1:
        return 2
    if source_level == 2:
        return 3
    return 4


def ui_activity_to_source(ui_level: int) -> int:
    """Convert a visible level 1..4 to the selected catalogue level."""
    clamped = max(1, min(4, int(ui_level)))
    return ACTIVITY_SOURCE_INDEXES[clamped - 1]


@dataclass(frozen=True)
class ChordType:
    suffix: str
    label: str
    intervals: tuple[int, ...]
    inversions: tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class SynthControl:
    key: str
    label: str
    group: str
    default: float
    minimum: float
    maximum: float
    step: float
    decimals: int


@dataclass(frozen=True)
class SynthDefinition:
    key: str
    label: str
    controls: tuple[SynthControl, ...]


@dataclass
class SynthRuntime:
    selected_index: int
    values_by_synth: list[dict[str, float]]


@dataclass(frozen=True)
class RhythmDefinition:
    key: str
    label: str
    meter: str
    length_beats: float
    tempo_min: float
    tempo_max: float
    tempo_default: float
    default_busyness: int
    default_chord_activity: int
    default_bass_activity: int
    percussion_layers: tuple[dict[str, Any], ...]
    chord_levels: tuple[tuple[dict[str, Any], ...], ...]
    bass_levels: tuple[tuple[dict[str, Any], ...], ...]


@dataclass
class RhythmRuntime:
    selected_index: int
    tempo_by_rhythm: list[float]
    busyness_by_rhythm: list[int]
    chord_activity_by_rhythm: list[int]
    bass_activity_by_rhythm: list[int]


def display_label(suffix: str) -> str:
    text = suffix.replace("_", " ")
    text = re.sub(r"(?<=[A-Za-z])(?=\d)", " ", text)
    abbreviations = {
        "major": "maj",
        "minor": "min",
        "augmented": "aug",
        "diminished": "dim",
        "dominant": "dom",
    }
    return " ".join(
        abbreviations.get(word, word)
        for word in text.split()
    )


def inverted_intervals(
    intervals: tuple[int, ...],
    inversion_index: int,
) -> tuple[int, ...]:
    note_count = len(intervals)

    if note_count == 0:
        return ()

    inversion_index %= note_count

    if inversion_index == 0:
        return intervals

    rotated = (
        list(enumerate(
            intervals[inversion_index:],
            start=inversion_index,
        ))
        + list(enumerate(intervals[:inversion_index]))
    )

    ascending: list[tuple[int, int]] = []
    previous_pitch: int | None = None

    for original_index, pitch in rotated:
        if previous_pitch is not None:
            while pitch <= previous_pitch:
                pitch += 12

        ascending.append((original_index, pitch))
        previous_pitch = pitch

    root_pitch = next(
        pitch
        for original_index, pitch in ascending
        if original_index == 0
    )

    return tuple(
        pitch - root_pitch
        for _, pitch in ascending
    )


def make_inversions(
    intervals: tuple[int, ...],
) -> tuple[tuple[int, ...], ...]:
    return tuple(
        inverted_intervals(intervals, index)
        for index in range(len(intervals))
    )


def load_chords(path: Path) -> tuple[ChordType, ...]:
    chords: list[ChordType] = []

    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.reader(csv_file)
        header = next(reader, None)

        if not header or header[:2] != ["chord_suffix", "intervals"]:
            raise ValueError(
                f"{path} must begin with: chord_suffix,intervals"
            )

        for line_number, row in enumerate(reader, start=2):
            if not row or not row[0].strip():
                continue

            suffix = row[0].strip()

            try:
                intervals = tuple(
                    int(value.strip())
                    for value in row[1:]
                    if value.strip()
                )
            except ValueError as exc:
                raise ValueError(
                    f"Invalid interval on line {line_number} of {path}"
                ) from exc

            if not intervals or intervals[0] != 0:
                raise ValueError(
                    f"Chord {suffix!r} must start with interval 0"
                )

            if tuple(sorted(intervals)) != intervals:
                raise ValueError(
                    f"Intervals for {suffix!r} must be ascending"
                )

            chords.append(
                ChordType(
                    suffix=suffix,
                    label=display_label(suffix),
                    intervals=intervals,
                    inversions=make_inversions(intervals),
                )
            )

    if not chords:
        raise ValueError(f"No chord definitions found in {path}")

    return tuple(chords)



def load_defaults(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))

    rows = raw.get("chord_rows")
    if not isinstance(rows, list) or len(rows) != ROW_COUNT:
        raise ValueError(
            f"{path} must define exactly {ROW_COUNT} chord_rows"
        )

    required_sections = (
        "synths",
        "volumes",
        "transport",
        "rhythm",
    )
    for section in required_sections:
        if section not in raw:
            raise ValueError(
                f"{path} is missing section {section!r}"
            )

    return raw


def load_intonation_table(
    path: Path,
) -> tuple[tuple[float, ...], ...]:
    raw = json.loads(
        path.read_text(encoding="utf-8")
    )

    rows: list[tuple[float, ...]] = []

    for root_name in INTONATION_NOTE_IDS:
        key_name = f"key_{root_name}"
        row_raw = raw.get(key_name)

        if not isinstance(row_raw, dict):
            raise ValueError(
                f"{path} is missing {key_name!r}"
            )

        row: list[float] = []

        for note_name in INTONATION_NOTE_IDS:
            value_name = f"note_{note_name}"

            if value_name not in row_raw:
                raise ValueError(
                    f"{path}: {key_name!r} is missing "
                    f"{value_name!r}"
                )

            factor = float(
                row_raw[value_name]
            )

            if (
                not math.isfinite(factor)
                or factor <= 0.0
            ):
                raise ValueError(
                    f"{path}: invalid factor "
                    f"{key_name}.{value_name}={factor!r}"
                )

            row.append(factor)

        rows.append(tuple(row))

    return tuple(rows)


def load_title_config(
    path: Path,
) -> dict[str, object]:
    default = {
        "text": "Luciel's Birthday Omnichord",
        "height": 74,
        "font": "URW Chancery L",
    }

    try:
        raw = json.loads(
            path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return default

    if not isinstance(raw, dict):
        return default

    text = str(
        raw.get("text", default["text"])
    )
    font = str(
        raw.get("font", default["font"])
    ).strip()

    try:
        height = int(
            raw.get("height", default["height"])
        )
    except (TypeError, ValueError):
        height = int(default["height"])

    # Keep pathological JSON values from destroying the layout.
    height = max(0, min(240, height))

    if not font:
        font = str(default["font"])

    return {
        "text": text,
        "height": height,
        "font": font,
    }


def load_synth_catalog(
    path: Path,
) -> tuple[
    tuple[SynthDefinition, ...],
    int,
    int,
    int,
]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    synths: list[SynthDefinition] = []

    for raw_synth in raw["synths"]:
        controls = tuple(
            SynthControl(
                key=str(control["key"]),
                label=str(control["label"]),
                group=str(control["group"]),
                default=float(control["default"]),
                minimum=float(control["minimum"]),
                maximum=float(control["maximum"]),
                step=float(control["step"]),
                decimals=int(control["decimals"]),
            )
            for control in raw_synth["controls"]
        )

        synths.append(
            SynthDefinition(
                key=str(raw_synth["key"]),
                label=str(raw_synth["label"]),
                controls=controls,
            )
        )

    def index_for(key: str) -> int:
        return next(
            index
            for index, synth in enumerate(synths)
            if synth.key == key
        )

    return (
        tuple(synths),
        index_for(str(raw["default_chord_synth"])),
        index_for(str(raw["default_strum_synth"])),
        index_for(str(raw["default_bass_synth"])),
    )


def load_rhythm_catalog(
    path: Path,
) -> tuple[RhythmDefinition, ...]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    rhythms: list[RhythmDefinition] = []

    for item in raw["rhythms"]:
        tempo = item["tempo"]

        rhythms.append(
            RhythmDefinition(
                key=str(item["id"]),
                label=str(item["label"]),
                meter=str(item["meter"]),
                length_beats=float(item["length_beats"]),
                tempo_min=float(tempo["min"]),
                tempo_max=float(tempo["max"]),
                tempo_default=float(tempo["default"]),
                default_busyness=int(item["default_busyness"]),
                default_chord_activity=int(
                    item["default_chord_activity"]
                ),
                default_bass_activity=int(
                    item["default_bass_activity"]
                ),
                percussion_layers=tuple(
                    dict(layer)
                    for layer in item["percussion_layers"]
                ),
                chord_levels=tuple(
                    tuple(dict(event) for event in level)
                    for level in item["chord_levels"]
                ),
                bass_levels=tuple(
                    tuple(dict(event) for event in level)
                    for level in item["bass_levels"]
                ),
            )
        )

    if not rhythms:
        raise ValueError("No rhythm definitions found")

    for rhythm in rhythms:
        if len(rhythm.percussion_layers) != 5:
            raise ValueError(
                f"Rhythm {rhythm.key!r} must have five percussion layers"
            )
        if len(rhythm.chord_levels) != 5:
            raise ValueError(
                f"Rhythm {rhythm.key!r} must have five chord levels"
            )
        if len(rhythm.bass_levels) != 5:
            raise ValueError(
                f"Rhythm {rhythm.key!r} must have five bass levels"
            )

    return tuple(rhythms)


class InstrumentBackend(QObject):
    stateChanged = Signal()

    chordVolumeChanged = Signal()
    strumVolumeChanged = Signal()
    bassVolumeChanged = Signal()
    percussionVolumeChanged = Signal()
    bassRunningChanged = Signal()

    chordSynthStateChanged = Signal()
    chordSynthControlsChanged = Signal()
    strumSynthStateChanged = Signal()
    strumSynthControlsChanged = Signal()
    bassSynthStateChanged = Signal()
    bassSynthControlsChanged = Signal()

    rhythmStateChanged = Signal()
    rhythmControlsChanged = Signal()

    tuningChanged = Signal()
    presetChanged = Signal()
    presetStored = Signal(int)

    def __init__(
        self,
        chords: tuple[ChordType, ...],
        synths: tuple[SynthDefinition, ...],
        rhythms: tuple[RhythmDefinition, ...],
        intonation_eq: tuple[tuple[float, ...], ...],
        intonation_harm: tuple[tuple[float, ...], ...],
        intonation_jv: tuple[tuple[float, ...], ...],
        default_chord_synth_index: int,
        default_strum_synth_index: int,
        default_bass_synth_index: int,
        defaults: dict[str, Any],
        osc_host: str,
        osc_port: int,
        chord_state_address: str,
        chord_manual_address: str,
        chord_amp_address: str,
        strum_amp_address: str,
        bass_amp_address: str,
        percussion_amp_address: str,
        chord_synth_address: str,
        chord_params_address: str,
        strum_synth_address: str,
        strum_params_address: str,
        bass_synth_address: str,
        bass_params_address: str,
        bass_running_address: str,
        strum_note_address: str,
        rhythm_config_address: str,
        rhythm_running_address: str,
        rhythm_chord_enabled_address: str,
        panic_address: str,
        debug_enabled: bool,
        debug_file: Path | None,
    ) -> None:
        super().__init__()

        self._chords = chords
        self._synths = synths
        self._rhythms = rhythms
        self._intonation_tables = {
            "EQ": intonation_eq,
            "HARM": intonation_harm,
            "JV": intonation_jv,
        }
        self._client = SimpleUDPClient(osc_host, osc_port)

        self._chord_state_address = chord_state_address
        self._chord_manual_address = chord_manual_address
        self._chord_amp_address = chord_amp_address
        self._strum_amp_address = strum_amp_address
        self._bass_amp_address = bass_amp_address
        self._percussion_amp_address = percussion_amp_address
        self._chord_synth_address = chord_synth_address
        self._chord_params_address = chord_params_address
        self._strum_synth_address = strum_synth_address
        self._strum_params_address = strum_params_address
        self._bass_synth_address = bass_synth_address
        self._bass_params_address = bass_params_address
        self._bass_running_address = bass_running_address
        self._strum_note_address = strum_note_address
        self._rhythm_config_address = rhythm_config_address
        self._rhythm_running_address = rhythm_running_address
        self._rhythm_chord_enabled_address = (
            rhythm_chord_enabled_address
        )
        self._panic_address = panic_address

        self._preset_dir = PRESET_DIRECTORY

        self._debug_enabled = bool(debug_enabled)
        self._debug_started = time.monotonic()
        self._debug_sequence = 0
        self._debug_file: Path | None = None

        if self._debug_enabled:
            self._preset_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            if debug_file is None:
                debug_file = (
                    self._preset_dir
                    / (
                        "debug-"
                        + time.strftime(
                            "%Y%m%d-%H%M%S"
                        )
                        + ".jsonl"
                    )
                )
            else:
                debug_file = (
                    Path(debug_file)
                    .expanduser()
                    .resolve()
                )
                debug_file.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

            self._debug_file = debug_file
            self._debug_file.write_text(
                "",
                encoding="utf-8",
            )

            print(
                "Omnichord debug log: "
                f"{self._debug_file}",
                file=sys.stderr,
                flush=True,
            )

        self._selected_preset = 1
        self._tuning_mode_index = (
            DEFAULT_TUNING_MODE_INDEX
        )
        self._tuning_reference = (
            DEFAULT_TUNING_REFERENCE
        )

        suffix_to_index = {
            chord.suffix: index
            for index, chord in enumerate(chords)
        }
        octave_to_index = {
            name: index
            for index, name in enumerate(OCTAVE_NAMES)
        }

        row_defaults = defaults["chord_rows"]

        try:
            self._row_chord_indexes = [
                suffix_to_index[str(row["chord"])]
                for row in row_defaults
            ]
            self._row_octave_indexes = [
                octave_to_index[str(row["octave"])]
                for row in row_defaults
            ]
            self._row_inversion_indexes = [
                int(row.get("inversion", 0))
                for row in row_defaults
            ]
        except KeyError as exc:
            raise ValueError(
                f"Unknown chord or octave in defaults.json: {exc}"
            ) from exc

        for row_index, chord_index in enumerate(
            self._row_chord_indexes
        ):
            inversion_count = len(
                self._chords[chord_index].inversions
            )
            self._row_inversion_indexes[row_index] %= (
                inversion_count
            )

        self._active_row = -1
        self._active_root_semitone = -1
        self._state_version = 0

        volumes = defaults["volumes"]
        transport = defaults["transport"]

        self._chord_volume = float(volumes["chord"])
        self._strum_volume = float(volumes["strum"])
        self._bass_volume = float(volumes["bass"])
        self._percussion_volume = float(
            volumes["percussion"]
        )
        self._bass_running = bool(
            transport["bass_running"]
        )

        self._chord_synth = self._make_synth_runtime(
            default_chord_synth_index
        )
        self._strum_synth = self._make_synth_runtime(
            default_strum_synth_index
        )
        self._bass_synth = self._make_synth_runtime(
            default_bass_synth_index
        )

        rhythm_key_to_index = {
            rhythm.key: index
            for index, rhythm in enumerate(rhythms)
        }
        selected_rhythm_key = str(
            defaults["rhythm"]["selected"]
        )

        if selected_rhythm_key not in rhythm_key_to_index:
            raise ValueError(
                "Unknown rhythm in defaults.json: "
                f"{selected_rhythm_key!r}"
            )

        self._rhythm = RhythmRuntime(
            selected_index=rhythm_key_to_index[
                selected_rhythm_key
            ],
            tempo_by_rhythm=[
                rhythm.tempo_default for rhythm in rhythms
            ],
            busyness_by_rhythm=[
                source_activity_to_ui(rhythm.default_busyness)
                for rhythm in rhythms
            ],
            chord_activity_by_rhythm=[
                source_activity_to_ui(rhythm.default_chord_activity)
                for rhythm in rhythms
            ],
            bass_activity_by_rhythm=[
                source_activity_to_ui(rhythm.default_bass_activity)
                for rhythm in rhythms
            ],
        )
        self._rhythm_running = bool(
            defaults["transport"]["rhythm_running"]
        )

        self._strum_last_index: int | None = None

        # A held chord temporarily suppresses automatic rhythmic chords
        # without altering the user's stored activity setting.
        self._pressed_chords: set[tuple[int, int]] = set()
        self._pressed_chord_order: list[tuple[int, int]] = []
        self._promoted_chords: set[tuple[int, int]] = set()
        self._chord_activity_hold_override = False

        self._chord_press_started: dict[
            tuple[int, int],
            float,
        ] = {}
        self._pending_chord_releases: dict[
            tuple[int, int],
            QTimer,
        ] = {}
        self._chord_bounce_mode: set[
            tuple[int, int]
        ] = set()

        self._ensure_preset_storage()
        self._load_startup_preset()

    def _debug(
        self,
        event: str,
        **fields: Any,
    ) -> None:
        if (
            not self._debug_enabled
            or self._debug_file is None
        ):
            return

        self._debug_sequence += 1

        record = {
            "seq": self._debug_sequence,
            "t_ms": round(
                (
                    time.monotonic()
                    - self._debug_started
                )
                * 1000.0,
                3,
            ),
            "event": event,
            **fields,
        }

        with self._debug_file.open(
            "a",
            encoding="utf-8",
        ) as handle:
            handle.write(
                json.dumps(
                    record,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
                + "\n"
            )

    def _debug_chord_state(
        self,
    ) -> dict[str, Any]:
        return {
            "pressed": [
                list(key)
                for key in sorted(
                    self._pressed_chords
                )
            ],
            "promoted": [
                list(key)
                for key in sorted(
                    self._promoted_chords
                )
            ],
            "override": (
                self._chord_activity_hold_override
            ),
            "effective_activity": (
                self._effective_chord_activity()
            ),
            "stored_activity": (
                self._rhythm
                .chord_activity_by_rhythm[
                    self._rhythm.selected_index
                ]
            ),
            "rhythm_running": (
                self._rhythm_running
            ),
            "pending_release": [
                list(key)
                for key in sorted(
                    self._pending_chord_releases
                )
            ],
            "bounce_mode": [
                list(key)
                for key in sorted(
                    self._chord_bounce_mode
                )
            ],
        }

    @Slot(str, int, int, float, float)
    def debugChordTouch(
        self,
        action: str,
        row_index: int,
        root_semitone: int,
        x: float,
        y: float,
    ) -> None:
        self._debug(
            "qml_chord_touch",
            action=str(action),
            row=int(row_index),
            root=int(root_semitone),
            x=round(float(x), 3),
            y=round(float(y), 3),
            **self._debug_chord_state(),
        )

    def _make_synth_runtime(
        self,
        selected_index: int,
    ) -> SynthRuntime:
        return SynthRuntime(
            selected_index=selected_index,
            values_by_synth=[
                {
                    control.key: control.default
                    for control in synth.controls
                }
                for synth in self._synths
            ],
        )

    def _runtime(self, role: SynthRole) -> SynthRuntime:
        if role == "chord":
            return self._chord_synth
        if role == "strum":
            return self._strum_synth
        return self._bass_synth

    def _emit_state_changed(self) -> None:
        self._state_version += 1
        self.stateChanged.emit()

    @Property(int, notify=stateChanged)
    def stateVersion(self) -> int:
        return self._state_version

    @Property(int, notify=stateChanged)
    def activeRowIndex(self) -> int:
        return self._active_row

    @Property(int, notify=stateChanged)
    def activeRootSemitone(self) -> int:
        return self._active_root_semitone

    @Property(bool, notify=stateChanged)
    def isOff(self) -> bool:
        return self._active_row < 0

    @Property(float, notify=chordVolumeChanged)
    def chordVolume(self) -> float:
        return self._chord_volume

    @Property(float, notify=strumVolumeChanged)
    def strumVolume(self) -> float:
        return self._strum_volume

    @Property(float, notify=bassVolumeChanged)
    def bassVolume(self) -> float:
        return self._bass_volume

    @Property(bool, notify=bassRunningChanged)
    def bassRunning(self) -> bool:
        return self._bass_running

    @Property(float, notify=percussionVolumeChanged)
    def percussionVolume(self) -> float:
        return self._percussion_volume

    @Property(int, notify=chordSynthStateChanged)
    def selectedChordSynthIndex(self) -> int:
        return self._chord_synth.selected_index

    @Property(int, notify=strumSynthStateChanged)
    def selectedStrumSynthIndex(self) -> int:
        return self._strum_synth.selected_index

    @Property(int, notify=bassSynthStateChanged)
    def selectedBassSynthIndex(self) -> int:
        return self._bass_synth.selected_index

    @Property("QVariantList", notify=chordSynthControlsChanged)
    def chordCommonControls(self) -> list[dict[str, Any]]:
        return self._control_model("chord", "common")

    @Property("QVariantList", notify=chordSynthControlsChanged)
    def chordExtraControls(self) -> list[dict[str, Any]]:
        return self._control_model("chord", "extra")

    @Property("QVariantList", notify=strumSynthControlsChanged)
    def strumCommonControls(self) -> list[dict[str, Any]]:
        return self._control_model("strum", "common")

    @Property("QVariantList", notify=strumSynthControlsChanged)
    def strumExtraControls(self) -> list[dict[str, Any]]:
        return self._control_model("strum", "extra")

    @Property("QVariantList", notify=bassSynthControlsChanged)
    def bassCommonControls(self) -> list[dict[str, Any]]:
        return self._control_model("bass", "common")

    @Property("QVariantList", notify=bassSynthControlsChanged)
    def bassExtraControls(self) -> list[dict[str, Any]]:
        return self._control_model("bass", "extra")

    @Property(int, notify=rhythmStateChanged)
    def selectedRhythmIndex(self) -> int:
        return self._rhythm.selected_index

    @Property(bool, notify=rhythmStateChanged)
    def rhythmRunning(self) -> bool:
        return self._rhythm_running

    @Property(float, notify=rhythmControlsChanged)
    def rhythmTempo(self) -> float:
        return self._rhythm.tempo_by_rhythm[
            self._rhythm.selected_index
        ]

    @Property(float, notify=rhythmStateChanged)
    def rhythmTempoMin(self) -> float:
        return 40.0

    @Property(float, notify=rhythmStateChanged)
    def rhythmTempoMax(self) -> float:
        return 200.0

    @Property(int, notify=rhythmControlsChanged)
    def rhythmBusyness(self) -> int:
        return self._rhythm.busyness_by_rhythm[
            self._rhythm.selected_index
        ]

    def _effective_chord_activity(self) -> int:
        if self._chord_activity_hold_override:
            return 0

        return self._rhythm.chord_activity_by_rhythm[
            self._rhythm.selected_index
        ]

    @Property(int, notify=rhythmControlsChanged)
    def rhythmChordActivity(self) -> int:
        return self._effective_chord_activity()

    @Property(int, notify=rhythmControlsChanged)
    def rhythmBassActivity(self) -> int:
        return self._rhythm.bass_activity_by_rhythm[
            self._rhythm.selected_index
        ]

    @Property(int, notify=tuningChanged)
    def selectedTuningModeIndex(self) -> int:
        return self._tuning_mode_index

    @Property(int, notify=tuningChanged)
    def tuningReference(self) -> int:
        return self._tuning_reference

    @Property(int, constant=True)
    def presetCount(self) -> int:
        return PRESET_COUNT

    @Property(int, notify=presetChanged)
    def selectedPreset(self) -> int:
        return self._selected_preset

    def _control_model(
        self,
        role: SynthRole,
        group: str,
    ) -> list[dict[str, Any]]:
        runtime = self._runtime(role)
        synth = self._synths[runtime.selected_index]
        values = runtime.values_by_synth[runtime.selected_index]

        return [
            {
                "key": control.key,
                "label": control.label,
                "value": values[control.key],
                "minimum": control.minimum,
                "maximum": control.maximum,
                "step": control.step,
                "decimals": control.decimals,
            }
            for control in synth.controls
            if control.group == group
        ]

    def _selected_rhythm(self) -> RhythmDefinition:
        return self._rhythms[self._rhythm.selected_index]

    @Slot(float)
    def setChordVolume(self, value: float) -> None:
        clamped = max(0.0, min(1.0, float(value)))

        if abs(clamped - self._chord_volume) < 0.0001:
            return

        self._chord_volume = clamped
        self.chordVolumeChanged.emit()
        self._client.send_message(
            self._chord_amp_address,
            clamped,
        )

    @Slot(float)
    def setStrumVolume(self, value: float) -> None:
        clamped = max(0.0, min(1.0, float(value)))

        if abs(clamped - self._strum_volume) < 0.0001:
            return

        self._strum_volume = clamped
        self.strumVolumeChanged.emit()
        self._client.send_message(
            self._strum_amp_address,
            clamped,
        )

    @Slot(float)
    def setBassVolume(self, value: float) -> None:
        clamped = max(0.0, min(1.0, float(value)))

        if abs(clamped - self._bass_volume) < 0.0001:
            return

        self._bass_volume = clamped
        self.bassVolumeChanged.emit()
        self._client.send_message(
            self._bass_amp_address,
            clamped,
        )

    @Slot()
    def toggleBassRunning(self) -> None:
        self._bass_running = not self._bass_running
        self._client.send_message(
            self._bass_running_address,
            1 if self._bass_running else 0,
        )
        self.bassRunningChanged.emit()

    @Slot(float)
    def setPercussionVolume(self, value: float) -> None:
        clamped = max(0.0, min(1.0, float(value)))

        if abs(clamped - self._percussion_volume) < 0.0001:
            return

        self._percussion_volume = clamped
        self.percussionVolumeChanged.emit()
        self._client.send_message(
            self._percussion_amp_address,
            clamped,
        )

    @Slot()
    def copyStrumToChord(self) -> None:
        self._chord_synth.selected_index = (
            self._strum_synth.selected_index
        )
        self._chord_synth.values_by_synth = copy.deepcopy(
            self._strum_synth.values_by_synth
        )
        self._chord_volume = self._strum_volume

        self.chordSynthStateChanged.emit()
        self.chordSynthControlsChanged.emit()
        self.chordVolumeChanged.emit()

        self._send_synth_state("chord")
        self._client.send_message(
            self._chord_amp_address,
            self._chord_volume,
        )

    @Slot(int)
    def setChordSynthIndex(self, synth_index: int) -> None:
        self._set_synth_index("chord", synth_index)

    @Slot(int)
    def setStrumSynthIndex(self, synth_index: int) -> None:
        self._set_synth_index("strum", synth_index)

    @Slot(int)
    def setBassSynthIndex(self, synth_index: int) -> None:
        self._set_synth_index("bass", synth_index)

    def _set_synth_index(
        self,
        role: SynthRole,
        synth_index: int,
    ) -> None:
        if not 0 <= synth_index < len(self._synths):
            return

        runtime = self._runtime(role)

        if runtime.selected_index == synth_index:
            return

        runtime.selected_index = synth_index

        if role == "chord":
            self.chordSynthStateChanged.emit()
            self.chordSynthControlsChanged.emit()
        elif role == "strum":
            self.strumSynthStateChanged.emit()
            self.strumSynthControlsChanged.emit()
        else:
            self.bassSynthStateChanged.emit()
            self.bassSynthControlsChanged.emit()

        self._send_synth_state(role)

    @Slot(str, float)
    def setChordSynthControl(
        self,
        key: str,
        value: float,
    ) -> None:
        self._set_synth_control("chord", key, value)

    @Slot(str, float)
    def setStrumSynthControl(
        self,
        key: str,
        value: float,
    ) -> None:
        self._set_synth_control("strum", key, value)

    @Slot(str, float)
    def setBassSynthControl(
        self,
        key: str,
        value: float,
    ) -> None:
        self._set_synth_control("bass", key, value)

    def _set_synth_control(
        self,
        role: SynthRole,
        key: str,
        value: float,
    ) -> None:
        runtime = self._runtime(role)
        synth = self._synths[runtime.selected_index]

        control = next(
            (
                item
                for item in synth.controls
                if item.key == key
            ),
            None,
        )

        if control is None:
            return

        clamped = max(
            control.minimum,
            min(control.maximum, float(value)),
        )

        values = runtime.values_by_synth[runtime.selected_index]

        if abs(clamped - values[key]) < 0.0001:
            return

        values[key] = clamped
        self._send_synth_params(role)

    def _tuning_note_offset(self) -> float:
        # A-reference tuning is global and remains exactly as before.
        return 12.0 * math.log2(
            float(self._tuning_reference) / 440.0
        )

    def _intonation_factor(
        self,
        root_semitone: int | None,
        note: int | float,
    ) -> float:
        # EQ is explicitly unity; HARM and JV are key-dependent tables.
        mode = TUNING_MODE_NAMES[
            self._tuning_mode_index
        ]

        if mode not in self._intonation_tables:
            return 1.0

        if root_semitone is None:
            return 1.0

        root_pc = int(root_semitone) % 12
        note_pc = int(
            math.floor(float(note) + 0.5)
        ) % 12

        return self._intonation_tables[
            mode
        ][root_pc][note_pc]

    def _intonation_note_offset(
        self,
        root_semitone: int | None,
        note: int | float,
    ) -> float:
        factor = self._intonation_factor(
            root_semitone,
            note,
        )

        # The JSON factor multiplies the equal-tempered frequency. Sonic Pi
        # accepts fractional MIDI-style note numbers, so a frequency factor
        # becomes an additive semitone offset.
        return 12.0 * math.log2(factor)

    def _tuned_note(
        self,
        note: int | float,
        root_semitone: int | None = None,
    ) -> float:
        return (
            float(note)
            + self._tuning_note_offset()
            + self._intonation_note_offset(
                root_semitone,
                note,
            )
        )

    def _tuned_notes(
        self,
        notes: list[int | float],
        root_semitone: int | None = None,
    ) -> list[float]:
        return [
            self._tuned_note(
                note,
                root_semitone,
            )
            for note in notes
        ]

    def _tuned_note_text(
        self,
        note: int | float,
        root_semitone: int | None = None,
    ) -> str:
        # Keep the high-precision text OSC path used by strum notes.
        return (
            f"{self._tuned_note(note, root_semitone):.12f}"
        )

    def _refresh_tuning_on_active_notes(self) -> None:
        # Retune every manually held chord in place.
        for key in sorted(self._pressed_chords):
            row_index, root_semitone = key

            self._send_manual_chord(
                "update",
                key=key,
                notes=self._notes_for_chord(
                    row_index,
                    root_semitone,
                ),
            )

        # This updates bass-note state as well and retunes a currently sounding
        # automatic rhythm chord without creating a new attack.
        if (
            self._active_row >= 0
            and self._active_root_semitone >= 0
        ):
            self._send_chord_state(
                play_now=False
            )

    @Slot(int)
    def setTuningModeIndex(self, index: int) -> None:
        clamped = max(
            0,
            min(
                len(TUNING_MODE_NAMES) - 1,
                int(index),
            ),
        )

        if clamped == self._tuning_mode_index:
            return

        self._tuning_mode_index = clamped
        self.tuningChanged.emit()
        self._refresh_tuning_on_active_notes()

    @Slot(int)
    def setTuningReference(self, value: int) -> None:
        clamped = max(415, min(466, int(value)))

        if clamped == self._tuning_reference:
            return

        self._tuning_reference = clamped
        self.tuningChanged.emit()
        self._refresh_tuning_on_active_notes()

    def _preset_path(self, preset_number: int) -> Path:
        return (
            self._preset_dir
            / f"p{preset_number}.json"
        )

    @staticmethod
    def _write_json_atomic(
        path: Path,
        data: dict[str, Any],
    ) -> None:
        temporary = path.with_suffix(
            path.suffix + ".tmp"
        )
        temporary.write_text(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    def _preset_snapshot(self) -> dict[str, Any]:
        synth_roles: dict[str, Any] = {}

        for role in ("chord", "strum", "bass"):
            runtime = self._runtime(role)

            synth_roles[role] = {
                "selected": self._synths[
                    runtime.selected_index
                ].key,
                "parameters": {
                    synth.key: copy.deepcopy(
                        runtime.values_by_synth[index]
                    )
                    for index, synth
                    in enumerate(self._synths)
                },
            }

        rhythm_settings = {}

        for index, rhythm in enumerate(
            self._rhythms
        ):
            rhythm_settings[rhythm.key] = {
                "tempo": (
                    self._rhythm
                    .tempo_by_rhythm[index]
                ),
                "percussion_activity": (
                    self._rhythm
                    .busyness_by_rhythm[index]
                ),
                "chord_activity": (
                    self._rhythm
                    .chord_activity_by_rhythm[index]
                ),
                "bass_activity": (
                    self._rhythm
                    .bass_activity_by_rhythm[index]
                ),
            }

        return {
            "version": 1,
            "chord_rows": [
                {
                    "chord": self._chords[
                        self._row_chord_indexes[
                            row_index
                        ]
                    ].suffix,
                    "octave": OCTAVE_NAMES[
                        self._row_octave_indexes[
                            row_index
                        ]
                    ],
                    "inversion": (
                        self._row_inversion_indexes[
                            row_index
                        ]
                    ),
                }
                for row_index in range(ROW_COUNT)
            ],
            "synths": synth_roles,
            "volumes": {
                "chord": self._chord_volume,
                "strum": self._strum_volume,
                "bass": self._bass_volume,
                "percussion": (
                    self._percussion_volume
                ),
            },
            "transport": {
                "rhythm_running": (
                    self._rhythm_running
                ),
                "bass_running": (
                    self._bass_running
                ),
            },
            "rhythm": {
                "selected": (
                    self._selected_rhythm().key
                ),
                "settings": rhythm_settings,
            },
            "tuning": {
                "mode": TUNING_MODE_NAMES[
                    self._tuning_mode_index
                ],
                "reference_hz": (
                    self._tuning_reference
                ),
            },
        }

    def _ensure_preset_storage(self) -> None:
        self._preset_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        factory_dir = (
            APP_DIR / "default_presets"
        )
        fallback = self._preset_snapshot()

        for preset_number in range(
            1,
            PRESET_COUNT + 1,
        ):
            path = self._preset_path(
                preset_number
            )

            # Never overwrite an existing user preset. A missing pN.json is
            # seeded from the corresponding factory pN.json.
            if path.exists():
                continue

            factory_path = (
                factory_dir
                / f"p{preset_number}.json"
            )

            if factory_path.exists():
                try:
                    factory_data = json.loads(
                        factory_path.read_text(
                            encoding="utf-8"
                        )
                    )

                    if not isinstance(
                        factory_data,
                        dict,
                    ):
                        raise ValueError(
                            "factory preset is not an object"
                        )

                    self._write_json_atomic(
                        path,
                        factory_data,
                    )
                    continue
                except (
                    OSError,
                    ValueError,
                    json.JSONDecodeError,
                ) as exc:
                    print(
                        "Could not seed "
                        f"P{preset_number} from "
                        f"{factory_path}: {exc}",
                        file=sys.stderr,
                    )

            # Last-resort compatibility fallback if installation files are
            # incomplete.
            self._write_json_atomic(
                path,
                fallback,
            )

        last_path = (
            self._preset_dir
            / LAST_PRESET_FILE
        )

        if not last_path.exists():
            self._write_json_atomic(
                last_path,
                {"preset": 1},
            )

    def _read_preset(
        self,
        preset_number: int,
    ) -> dict[str, Any]:
        path = self._preset_path(
            preset_number
        )

        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(data, dict):
            raise ValueError(
                f"{path} does not contain a JSON object"
            )

        return data

    def _load_startup_preset(self) -> None:
        last_path = (
            self._preset_dir
            / LAST_PRESET_FILE
        )

        preset_number = 1

        try:
            last_data = json.loads(
                last_path.read_text(
                    encoding="utf-8"
                )
            )
            preset_number = int(
                last_data.get("preset", 1)
            )
        except (
            OSError,
            ValueError,
            TypeError,
            json.JSONDecodeError,
        ):
            preset_number = 1

        if not 1 <= preset_number <= PRESET_COUNT:
            preset_number = 1

        try:
            data = self._read_preset(
                preset_number
            )
            self._apply_preset_data(data)
            self._selected_preset = (
                preset_number
            )
        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            json.JSONDecodeError,
        ) as exc:
            print(
                "Could not load startup preset "
                f"P{preset_number}: {exc}",
                file=sys.stderr,
            )
            self._selected_preset = 1

    def _fresh_synth_runtime(
        self,
        selected_index: int,
    ) -> SynthRuntime:
        return self._make_synth_runtime(
            selected_index
        )

    def _apply_synth_preset(
        self,
        role: SynthRole,
        data: dict[str, Any],
    ) -> SynthRuntime:
        selected_key = str(
            data.get(
                "selected",
                self._synths[
                    self._runtime(role)
                    .selected_index
                ].key,
            )
        )

        key_to_index = {
            synth.key: index
            for index, synth
            in enumerate(self._synths)
        }

        selected_index = key_to_index.get(
            selected_key,
            self._runtime(role).selected_index,
        )

        runtime = self._fresh_synth_runtime(
            selected_index
        )

        all_parameters = data.get(
            "parameters",
            {},
        )

        if isinstance(all_parameters, dict):
            for synth_index, synth in enumerate(
                self._synths
            ):
                stored_values = (
                    all_parameters.get(
                        synth.key,
                        {},
                    )
                )

                if not isinstance(
                    stored_values,
                    dict,
                ):
                    continue

                values = (
                    runtime.values_by_synth[
                        synth_index
                    ]
                )

                for control in synth.controls:
                    if control.key not in stored_values:
                        continue

                    value = float(
                        stored_values[
                            control.key
                        ]
                    )
                    values[control.key] = max(
                        control.minimum,
                        min(
                            control.maximum,
                            value,
                        ),
                    )

        return runtime

    def _apply_preset_data(
        self,
        data: dict[str, Any],
    ) -> None:
        suffix_to_index = {
            chord.suffix: index
            for index, chord
            in enumerate(self._chords)
        }
        octave_to_index = {
            name: index
            for index, name
            in enumerate(OCTAVE_NAMES)
        }

        rows = data.get("chord_rows", [])

        if (
            isinstance(rows, list)
            and len(rows) == ROW_COUNT
        ):
            for row_index, row in enumerate(
                rows
            ):
                if not isinstance(row, dict):
                    continue

                chord_key = str(
                    row.get(
                        "chord",
                        self._chords[
                            self._row_chord_indexes[
                                row_index
                            ]
                        ].suffix,
                    )
                )
                octave_key = str(
                    row.get(
                        "octave",
                        OCTAVE_NAMES[
                            self._row_octave_indexes[
                                row_index
                            ]
                        ],
                    )
                )

                if chord_key in suffix_to_index:
                    self._row_chord_indexes[
                        row_index
                    ] = suffix_to_index[
                        chord_key
                    ]

                if octave_key in octave_to_index:
                    self._row_octave_indexes[
                        row_index
                    ] = octave_to_index[
                        octave_key
                    ]

                chord = self._chords[
                    self._row_chord_indexes[
                        row_index
                    ]
                ]
                inversion_count = len(
                    chord.inversions
                )
                self._row_inversion_indexes[
                    row_index
                ] = int(
                    row.get("inversion", 0)
                ) % inversion_count

        synth_data = data.get("synths", {})

        if isinstance(synth_data, dict):
            for role in (
                "chord",
                "strum",
                "bass",
            ):
                role_data = synth_data.get(
                    role,
                    {},
                )

                if not isinstance(
                    role_data,
                    dict,
                ):
                    continue

                runtime = (
                    self._apply_synth_preset(
                        role,
                        role_data,
                    )
                )

                if role == "chord":
                    self._chord_synth = runtime
                elif role == "strum":
                    self._strum_synth = runtime
                else:
                    self._bass_synth = runtime

        volumes = data.get("volumes", {})

        if isinstance(volumes, dict):
            self._chord_volume = max(
                0.0,
                min(
                    1.0,
                    float(
                        volumes.get(
                            "chord",
                            self._chord_volume,
                        )
                    ),
                ),
            )
            self._strum_volume = max(
                0.0,
                min(
                    1.0,
                    float(
                        volumes.get(
                            "strum",
                            self._strum_volume,
                        )
                    ),
                ),
            )
            self._bass_volume = max(
                0.0,
                min(
                    1.0,
                    float(
                        volumes.get(
                            "bass",
                            self._bass_volume,
                        )
                    ),
                ),
            )
            self._percussion_volume = max(
                0.0,
                min(
                    1.0,
                    float(
                        volumes.get(
                            "percussion",
                            self._percussion_volume,
                        )
                    ),
                ),
            )

        transport = data.get(
            "transport",
            {},
        )

        if isinstance(transport, dict):
            self._rhythm_running = bool(
                transport.get(
                    "rhythm_running",
                    self._rhythm_running,
                )
            )
            self._bass_running = bool(
                transport.get(
                    "bass_running",
                    self._bass_running,
                )
            )

        rhythm_data = data.get(
            "rhythm",
            {},
        )

        if isinstance(rhythm_data, dict):
            rhythm_key_to_index = {
                rhythm.key: index
                for index, rhythm
                in enumerate(self._rhythms)
            }

            selected_key = str(
                rhythm_data.get(
                    "selected",
                    self._selected_rhythm().key,
                )
            )

            if selected_key in rhythm_key_to_index:
                self._rhythm.selected_index = (
                    rhythm_key_to_index[
                        selected_key
                    ]
                )

            settings = rhythm_data.get(
                "settings",
                {},
            )

            if isinstance(settings, dict):
                for index, rhythm in enumerate(
                    self._rhythms
                ):
                    stored = settings.get(
                        rhythm.key,
                        {},
                    )

                    if not isinstance(
                        stored,
                        dict,
                    ):
                        continue

                    self._rhythm.tempo_by_rhythm[
                        index
                    ] = max(
                        40.0,
                        min(
                            200.0,
                            float(
                                stored.get(
                                    "tempo",
                                    self._rhythm
                                    .tempo_by_rhythm[
                                        index
                                    ],
                                )
                            ),
                        ),
                    )
                    self._rhythm.busyness_by_rhythm[
                        index
                    ] = max(
                        1,
                        min(
                            4,
                            int(
                                stored.get(
                                    "percussion_activity",
                                    self._rhythm
                                    .busyness_by_rhythm[
                                        index
                                    ],
                                )
                            ),
                        ),
                    )
                    self._rhythm.chord_activity_by_rhythm[
                        index
                    ] = max(
                        0,
                        min(
                            4,
                            int(
                                stored.get(
                                    "chord_activity",
                                    self._rhythm
                                    .chord_activity_by_rhythm[
                                        index
                                    ],
                                )
                            ),
                        ),
                    )
                    self._rhythm.bass_activity_by_rhythm[
                        index
                    ] = max(
                        1,
                        min(
                            4,
                            int(
                                stored.get(
                                    "bass_activity",
                                    self._rhythm
                                    .bass_activity_by_rhythm[
                                        index
                                    ],
                                )
                            ),
                        ),
                    )

        tuning = data.get("tuning", {})

        if isinstance(tuning, dict):
            mode = str(
                tuning.get(
                    "mode",
                    TUNING_MODE_NAMES[
                        self._tuning_mode_index
                    ],
                )
            )

            if mode in TUNING_MODE_NAMES:
                self._tuning_mode_index = (
                    TUNING_MODE_NAMES.index(mode)
                )

            self._tuning_reference = max(
                415,
                min(
                    466,
                    int(
                        tuning.get(
                            "reference_hz",
                            self._tuning_reference,
                        )
                    ),
                ),
            )

        # Performance-state notes are deliberately never part of a preset.
        self._clear_touch_dropout_state()

        self._active_row = -1
        self._active_root_semitone = -1
        self._strum_last_index = None
        self._pressed_chords.clear()
        self._pressed_chord_order.clear()
        self._promoted_chords.clear()
        self._chord_activity_hold_override = False

    def _emit_full_preset_state(self) -> None:
        self._emit_state_changed()

        self.chordVolumeChanged.emit()
        self.strumVolumeChanged.emit()
        self.bassVolumeChanged.emit()
        self.percussionVolumeChanged.emit()
        self.bassRunningChanged.emit()

        self.chordSynthStateChanged.emit()
        self.chordSynthControlsChanged.emit()
        self.strumSynthStateChanged.emit()
        self.strumSynthControlsChanged.emit()
        self.bassSynthStateChanged.emit()
        self.bassSynthControlsChanged.emit()

        self.rhythmStateChanged.emit()
        self.rhythmControlsChanged.emit()
        self.tuningChanged.emit()

    def _write_last_preset(self) -> None:
        self._write_json_atomic(
            self._preset_dir
            / LAST_PRESET_FILE,
            {
                "preset": self._selected_preset,
            },
        )

    @Slot(int)
    def selectPreset(
        self,
        preset_number: int,
    ) -> None:
        if not 1 <= preset_number <= PRESET_COUNT:
            return

        try:
            data = self._read_preset(
                preset_number
            )
            self._apply_preset_data(data)
        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            json.JSONDecodeError,
        ) as exc:
            print(
                f"Could not load P{preset_number}: "
                f"{exc}",
                file=sys.stderr,
            )
            return

        self._selected_preset = preset_number
        self._write_last_preset()

        self._emit_full_preset_state()
        self.presetChanged.emit()

        self.send_initial_state()

    @Slot()
    def storeSelectedPreset(self) -> None:
        self._write_json_atomic(
            self._preset_path(
                self._selected_preset
            ),
            self._preset_snapshot(),
        )
        self._write_last_preset()
        self.presetChanged.emit()
        self.presetStored.emit(
            self._selected_preset
        )

    @Slot()
    def panic(self) -> None:
        # Stop and invalidate all performance state locally first.
        self._rhythm_running = False
        self._bass_running = False
        self._clear_touch_dropout_state()

        self._pressed_chords.clear()
        self._pressed_chord_order.clear()
        self._promoted_chords.clear()
        self._chord_activity_hold_override = False

        self._active_row = -1
        self._active_root_semitone = -1
        self._strum_last_index = None

        # Dedicated panic packet tells Sonic Pi to kill every node created by
        # this receiver, including notes whose ordinary release has not yet
        # elapsed.
        self._client.send_message(
            self._panic_address,
            1,
        )

        # Redundant explicit state packets make the UI and receiver converge
        # even if one UDP packet is lost.
        self._client.send_message(
            self._rhythm_chord_enabled_address,
            0,
        )
        self._client.send_message(
            self._rhythm_running_address,
            0,
        )
        self._client.send_message(
            self._bass_running_address,
            0,
        )
        self._send_manual_chord("stop_all")
        self._send_chord_state(
            play_now=False
        )

        self._emit_state_changed()
        self.rhythmStateChanged.emit()
        self.rhythmControlsChanged.emit()
        self.bassRunningChanged.emit()

    @Slot(int)
    def setRhythmIndex(self, rhythm_index: int) -> None:
        if not 0 <= rhythm_index < len(self._rhythms):
            return
        if rhythm_index == self._rhythm.selected_index:
            return

        self._rhythm.selected_index = rhythm_index
        self.rhythmStateChanged.emit()
        self.rhythmControlsChanged.emit()
        self._send_rhythm_config()

    @Slot(float)
    def setRhythmTempo(self, value: float) -> None:
        clamped = max(
            40.0,
            min(200.0, float(value)),
        )

        index = self._rhythm.selected_index
        if abs(
            clamped - self._rhythm.tempo_by_rhythm[index]
        ) < 0.0001:
            return

        self._rhythm.tempo_by_rhythm[index] = clamped
        self.rhythmControlsChanged.emit()
        self._send_rhythm_config()

    @Slot(float)
    def setRhythmBusyness(self, value: float) -> None:
        level = max(1, min(4, int(round(float(value)))))
        index = self._rhythm.selected_index

        if level == self._rhythm.busyness_by_rhythm[index]:
            return

        self._rhythm.busyness_by_rhythm[index] = level
        self.rhythmControlsChanged.emit()
        self._send_rhythm_config()

    @Slot(float)
    def setRhythmChordActivity(self, value: float) -> None:
        self._debug(
            "setRhythmChordActivity_called",
            requested=float(value),
            **self._debug_chord_state(),
        )

        if self._chord_activity_hold_override:
            self._debug(
                "setRhythmChordActivity_ignored_override",
                requested=float(value),
                **self._debug_chord_state(),
            )
            return

        level = max(0, min(4, int(round(float(value)))))
        index = self._rhythm.selected_index

        if level == self._rhythm.chord_activity_by_rhythm[index]:
            return

        self._rhythm.chord_activity_by_rhythm[index] = level
        self.rhythmControlsChanged.emit()

        # Disabling automatic chords should take effect immediately,
        # including inside the currently playing bar.
        self._send_rhythm_chord_enabled()
        self._send_rhythm_config()

    @Slot(float)
    def setRhythmBassActivity(self, value: float) -> None:
        level = max(1, min(4, int(round(float(value)))))
        index = self._rhythm.selected_index

        if level == self._rhythm.bass_activity_by_rhythm[index]:
            return

        self._rhythm.bass_activity_by_rhythm[index] = level
        self.rhythmControlsChanged.emit()
        self._send_rhythm_config()

    @Slot()
    def toggleRhythm(self) -> None:
        self._rhythm_running = not self._rhythm_running

        if self._rhythm_running:
            self._send_rhythm_config()

            # Start transport with the chord gate still closed, then publish
            # the current gate state. Either OSC receiver order is safe.
            self._client.send_message(
                self._rhythm_running_address,
                1,
            )
            self._send_rhythm_chord_enabled()
        else:
            # Close the automatic-chord path before stopping transport.
            self._send_rhythm_chord_enabled()
            self._client.send_message(
                self._rhythm_running_address,
                0,
            )

        self.rhythmStateChanged.emit()

    @Slot(int, result=int)
    def chordIndexForRow(self, row_index: int) -> int:
        if 0 <= row_index < ROW_COUNT:
            return self._row_chord_indexes[row_index]
        return 0

    @Slot(int, result=int)
    def octaveIndexForRow(self, row_index: int) -> int:
        if 0 <= row_index < ROW_COUNT:
            return self._row_octave_indexes[row_index]
        return 0

    @Slot(int, result=int)
    def inversionCountForRow(self, row_index: int) -> int:
        if not 0 <= row_index < ROW_COUNT:
            return 1

        chord = self._chords[
            self._row_chord_indexes[row_index]
        ]
        return len(chord.inversions)

    @Slot(int, result=str)
    def inversionLabelForRow(self, row_index: int) -> str:
        if not 0 <= row_index < ROW_COUNT:
            return "Root\n1/1"

        current = self._row_inversion_indexes[row_index]
        count = self.inversionCountForRow(row_index)
        name = "Root" if current == 0 else f"Inv {current}"
        return f"{name}\n{current + 1}/{count}"

    def _refresh_row_chord_notes(
        self,
        row_index: int,
    ) -> None:
        # Retune every currently held manual voice in this row.
        for key in sorted(self._pressed_chords):
            pressed_row, pressed_root = key

            if pressed_row != row_index:
                continue

            self._send_manual_chord(
                "update",
                key=key,
                notes=self._notes_for_chord(
                    pressed_row,
                    pressed_root,
                ),
            )

        # Update future rhythm events and retune the current rhythm chord,
        # but only if this row is the active chord row.
        if row_index == self._active_row:
            self._send_chord_state(play_now=False)

    @Slot(int, int)
    def setRowChordType(
        self,
        row_index: int,
        chord_index: int,
    ) -> None:
        if not 0 <= row_index < ROW_COUNT:
            return
        if not 0 <= chord_index < len(self._chords):
            return
        if chord_index == self._row_chord_indexes[row_index]:
            return

        self._row_chord_indexes[row_index] = chord_index
        self._row_inversion_indexes[row_index] = 0
        self._strum_last_index = None
        self._emit_state_changed()

        self._refresh_row_chord_notes(row_index)

    @Slot(int, int)
    def setRowOctave(
        self,
        row_index: int,
        octave_index: int,
    ) -> None:
        if not 0 <= row_index < ROW_COUNT:
            return
        if not 0 <= octave_index < len(OCTAVE_BASES):
            return
        if octave_index == self._row_octave_indexes[row_index]:
            return

        self._row_octave_indexes[row_index] = octave_index
        self._strum_last_index = None
        self._emit_state_changed()

        self._refresh_row_chord_notes(row_index)

    @Slot(int)
    def cycleRowInversion(self, row_index: int) -> None:
        if not 0 <= row_index < ROW_COUNT:
            return

        count = self.inversionCountForRow(row_index)
        self._row_inversion_indexes[row_index] = (
            self._row_inversion_indexes[row_index] + 1
        ) % count

        self._strum_last_index = None
        self._emit_state_changed()

        self._refresh_row_chord_notes(row_index)

    def _valid_chord_selection(
        self,
        row_index: int,
        root_semitone: int,
    ) -> bool:
        return (
            0 <= row_index < ROW_COUNT
            and root_semitone in NOTE_NAMES_BY_SEMITONE
        )

    def _set_active_chord(
        self,
        row_index: int,
        root_semitone: int,
    ) -> None:
        self._active_row = row_index
        self._active_root_semitone = root_semitone
        self._strum_last_index = None
        self._emit_state_changed()

    def _send_rhythm_chord_enabled(self) -> None:
        enabled = (
            self._rhythm_running
            and self._effective_chord_activity() > 0
        )

        self._debug(
            "osc_rhythm_chord_enabled",
            value=1 if enabled else 0,
            **self._debug_chord_state(),
        )

        self._client.send_message(
            self._rhythm_chord_enabled_address,
            1 if enabled else 0,
        )

    @staticmethod
    def _manual_voice_id(
        key: tuple[int, int],
    ) -> str:
        row_index, root_semitone = key
        return f"r{row_index}_n{root_semitone}"

    def _send_manual_chord(
        self,
        action: str,
        key: tuple[int, int] | None = None,
        notes: list[int] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "action": action,
        }

        if key is not None:
            payload["id"] = self._manual_voice_id(key)

        if notes is not None:
            root_semitone = (
                key[1]
                if key is not None
                else self._active_root_semitone
            )
            payload["notes"] = self._tuned_notes(
                notes,
                root_semitone,
            )

        if action == "start":
            payload["rhythm_running"] = bool(
                self._rhythm_running
            )

        self._debug(
            "osc_manual_chord",
            action=action,
            voice_id=payload.get("id"),
            notes=payload.get("notes"),
            packet_rhythm_running=(
                payload.get(
                    "rhythm_running"
                )
            ),
            **self._debug_chord_state(),
        )

        self._client.send_message(
            self._chord_manual_address,
            json.dumps(
                payload,
                separators=(",", ":"),
            ),
        )

    def _update_hold_override(self) -> None:
        should_override = bool(
            self._promoted_chords
        )

        self._debug(
            "hold_override_check",
            requested=should_override,
            **self._debug_chord_state(),
        )

        if (
            should_override
            == self._chord_activity_hold_override
        ):
            return

        old_value = (
            self._chord_activity_hold_override
        )
        self._chord_activity_hold_override = (
            should_override
        )

        self._debug(
            "hold_override_changed",
            old=old_value,
            new=should_override,
            **self._debug_chord_state(),
        )

        self.rhythmControlsChanged.emit()
        self._send_rhythm_chord_enabled()
        self._send_rhythm_config()

    def _clear_touch_dropout_state(self) -> None:
        for timer in list(
            self._pending_chord_releases.values()
        ):
            timer.stop()
            timer.deleteLater()

        self._pending_chord_releases.clear()
        self._chord_press_started.clear()
        self._chord_bounce_mode.clear()

    def _cancel_pending_chord_release(
        self,
        key: tuple[int, int],
    ) -> bool:
        timer = self._pending_chord_releases.pop(
            key,
            None,
        )

        if timer is None:
            return False

        timer.stop()
        timer.deleteLater()

        self._chord_bounce_mode.add(key)
        self._chord_press_started[key] = (
            time.monotonic()
        )

        self._debug(
            "touch_dropout_recovered",
            row=key[0],
            root=key[1],
            **self._debug_chord_state(),
        )
        return True

    def _finalize_chord_release(
        self,
        key: tuple[int, int],
        reason: str,
    ) -> None:
        timer = self._pending_chord_releases.pop(
            key,
            None,
        )

        if timer is not None:
            timer.stop()
            timer.deleteLater()

        if key not in self._pressed_chords:
            return

        row_index, root_semitone = key

        self._debug(
            "chord_release_finalized",
            row=row_index,
            root=root_semitone,
            reason=reason,
            **self._debug_chord_state(),
        )

        self._send_manual_chord(
            "stop",
            key=key,
        )

        self._pressed_chords.discard(key)
        self._promoted_chords.discard(key)
        self._chord_press_started.pop(
            key,
            None,
        )
        self._chord_bounce_mode.discard(
            key
        )

        try:
            self._pressed_chord_order.remove(key)
        except ValueError:
            pass

        if (
            self._active_row == row_index
            and self._active_root_semitone
            == root_semitone
            and self._pressed_chord_order
        ):
            next_row, next_root = (
                self._pressed_chord_order[-1]
            )
            self._set_active_chord(
                next_row,
                next_root,
            )
            self._send_chord_state(
                play_now=False
            )

        self._update_hold_override()

        self._debug(
            "releaseChord_exit",
            row=row_index,
            root=root_semitone,
            **self._debug_chord_state(),
        )

    def _schedule_chord_release(
        self,
        key: tuple[int, int],
        delay_ms: int,
        reason: str,
    ) -> None:
        old_timer = (
            self._pending_chord_releases.pop(
                key,
                None,
            )
        )

        if old_timer is not None:
            old_timer.stop()
            old_timer.deleteLater()

        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(int(delay_ms))

        def finish_release() -> None:
            if (
                self._pending_chord_releases.get(
                    key
                )
                is not timer
            ):
                return

            self._finalize_chord_release(
                key,
                reason=reason,
            )

        timer.timeout.connect(
            finish_release
        )
        self._pending_chord_releases[
            key
        ] = timer

        self._debug(
            "chord_release_delayed",
            row=key[0],
            root=key[1],
            delay_ms=int(delay_ms),
            reason=reason,
            **self._debug_chord_state(),
        )

        timer.start()

    def _release_all_pressed_chords(self) -> None:
        # stop_all is intentionally unconditional. It also clears a voice
        # left behind by a previous GUI run or an interrupted touch sequence.
        self._send_manual_chord("stop_all")
        self._clear_touch_dropout_state()

        self._pressed_chords.clear()
        self._pressed_chord_order.clear()
        self._promoted_chords.clear()
        self._update_hold_override()

    @Slot(int, int)
    def pressChord(
        self,
        row_index: int,
        root_semitone: int,
    ) -> None:
        if not self._valid_chord_selection(
            row_index,
            root_semitone,
        ):
            return

        key = (row_index, root_semitone)

        self._debug(
            "pressChord_enter",
            row=row_index,
            root=root_semitone,
            **self._debug_chord_state(),
        )

        if self._cancel_pending_chord_release(
            key
        ):
            self._debug(
                "pressChord_dropout_resume",
                row=row_index,
                root=root_semitone,
                **self._debug_chord_state(),
            )
            return

        if key in self._pressed_chords:
            self._debug(
                "pressChord_duplicate_ignored",
                row=row_index,
                root=root_semitone,
                **self._debug_chord_state(),
            )
            return

        self._pressed_chords.add(key)
        self._pressed_chord_order.append(key)
        self._chord_press_started[key] = (
            time.monotonic()
        )

        # Manual chord input takes precedence immediately on finger-down.
        # This emits chord activity 0 and closes the automatic chord gate
        # before sending the manual note-on.
        self._promoted_chords.add(key)
        self._update_hold_override()

        # Last pressed chord becomes the active chord used by strum/bass.
        # Other simultaneously pressed chord voices continue independently.
        self._set_active_chord(
            row_index,
            root_semitone,
        )
        self._send_chord_state(play_now=False)

        self._send_manual_chord(
            "start",
            key=key,
            notes=self._current_notes(),
        )

        self._debug(
            "pressChord_exit",
            row=row_index,
            root=root_semitone,
            **self._debug_chord_state(),
        )

    @Slot(int, int)
    def promoteChordHold(
        self,
        row_index: int,
        root_semitone: int,
    ) -> None:
        # Compatibility no-op for older QML. Current QML promotes directly
        # inside pressChord(), so there is no delayed hold transition.
        return

    @Slot(int, int)
    def releaseChord(
        self,
        row_index: int,
        root_semitone: int,
    ) -> None:
        key = (row_index, root_semitone)

        self._debug(
            "releaseChord_enter",
            row=row_index,
            root=root_semitone,
            **self._debug_chord_state(),
        )

        if key not in self._pressed_chords:
            self._debug(
                "releaseChord_unknown_ignored",
                row=row_index,
                root=root_semitone,
                **self._debug_chord_state(),
            )
            return

        started = self._chord_press_started.get(
            key,
            time.monotonic(),
        )
        held_ms = (
            time.monotonic() - started
        ) * 1000.0

        # A normal intentional tap should remain responsive. In the captured
        # failure traces, the *first* false release happened only after the
        # finger had been down for roughly 240-340 ms, so releases in this
        # short-tap region are finalized immediately.
        if (
            key not in self._chord_bounce_mode
            and held_ms <= CHORD_QUICK_TAP_MAX_MS
        ):
            self._finalize_chord_release(
                key,
                reason="quick_tap_release",
            )
            return

        if held_ms >= CHORD_STABLE_HOLD_MS:
            self._finalize_chord_release(
                key,
                reason="stable_physical_release",
            )
            return

        if key in self._chord_bounce_mode:
            self._schedule_chord_release(
                key,
                delay_ms=(
                    CHORD_BOUNCE_RELEASE_GRACE_MS
                ),
                reason="bounce_mode_timeout",
            )
        else:
            self._schedule_chord_release(
                key,
                delay_ms=(
                    CHORD_INITIAL_RELEASE_GRACE_MS
                ),
                reason="initial_release_timeout",
            )

    @Slot(int, int)
    def selectChord(
        self,
        row_index: int,
        root_semitone: int,
    ) -> None:
        # Programmatic one-shot helper retained for compatibility.
        if not self._valid_chord_selection(
            row_index,
            root_semitone,
        ):
            return

        self._set_active_chord(
            row_index,
            root_semitone,
        )
        self._send_chord_state(play_now=True)

    @Slot()
    def turnOff(self) -> None:
        self._release_all_pressed_chords()
        self._active_row = -1
        self._active_root_semitone = -1
        self._strum_last_index = None
        self._emit_state_changed()
        self._send_chord_state(play_now=False)

    def _notes_for_chord(
        self,
        row_index: int,
        root_semitone: int,
    ) -> list[int]:
        if not self._valid_chord_selection(
            row_index,
            root_semitone,
        ):
            return []

        chord = self._chords[
            self._row_chord_indexes[row_index]
        ]
        inversion_index = (
            self._row_inversion_indexes[row_index]
        )
        octave_base = OCTAVE_BASES[
            self._row_octave_indexes[row_index]
        ]
        root_midi = octave_base + root_semitone

        return [
            root_midi + interval
            for interval in chord.inversions[inversion_index]
        ]

    def _current_notes(self) -> list[int]:
        if (
            self._active_row < 0
            or self._active_root_semitone < 0
        ):
            return []

        return self._notes_for_chord(
            self._active_row,
            self._active_root_semitone,
        )

    def _current_bass_notes(self) -> list[int]:
        if (
            self._active_row < 0
            or self._active_root_semitone < 0
        ):
            return []

        chord = self._chords[
            self._row_chord_indexes[self._active_row]
        ]

        # One low-register octave of unique chord tones. The bass remains
        # rooted around octave 2 regardless of the selected chord octave.
        pitch_classes = sorted(
            {
                interval % 12
                for interval in chord.intervals
            }
        )
        bass_root = 36 + self._active_root_semitone

        return [
            bass_root + pitch_class
            for pitch_class in pitch_classes
        ]

    def _send_chord_state(self, play_now: bool) -> None:
        payload = {
            "notes": self._tuned_notes(
                self._current_notes(),
                self._active_root_semitone,
            ),
            "bass_notes": self._tuned_notes(
                self._current_bass_notes(),
                self._active_root_semitone,
            ),
            "play_now": bool(play_now),
            "rhythm_running": bool(
                self._rhythm_running
            ),
        }

        self._debug(
            "osc_chord_state",
            play_now=bool(play_now),
            notes=payload.get("notes"),
            bass_notes=payload.get(
                "bass_notes"
            ),
            packet_rhythm_running=(
                payload.get(
                    "rhythm_running"
                )
            ),
            **self._debug_chord_state(),
        )

        self._client.send_message(
            self._chord_state_address,
            json.dumps(payload, separators=(",", ":")),
        )

    def _arpeggio_notes(self) -> list[int]:
        if (
            self._active_row < 0
            or self._active_root_semitone < 0
        ):
            return []

        chord = self._chords[
            self._row_chord_indexes[self._active_row]
        ]

        # Convert the chord definition to pitch classes only. This deliberately
        # ignores both the row octave and the selected inversion.
        pitch_classes = {
            (
                self._active_root_semitone
                + interval
            ) % 12
            for interval in chord.intervals
        }

        return [
            midi_note
            for midi_note in range(
                STRUM_LOW_MIDI,
                STRUM_HIGH_MIDI + 1,
            )
            if midi_note % 12 in pitch_classes
        ]

    def _strum_index(self, normalized_y: float) -> int | None:
        notes = self._arpeggio_notes()

        if not notes:
            return None

        y = max(0.0, min(1.0, float(normalized_y)))
        return round((1.0 - y) * (len(notes) - 1))

    @Slot(float)
    def strumTap(self, normalized_y: float) -> None:
        notes = self._arpeggio_notes()
        index = self._strum_index(normalized_y)

        if index is None:
            return

        self._client.send_message(
            self._strum_note_address,
            self._tuned_note_text(
                notes[index],
                self._active_root_semitone,
            ),
        )

    @Slot(float)
    def strumStart(self, normalized_y: float) -> None:
        self._strum_last_index = self._strum_index(
            normalized_y
        )

    @Slot(float)
    def strumMove(self, normalized_y: float) -> None:
        notes = self._arpeggio_notes()
        new_index = self._strum_index(normalized_y)

        if new_index is None:
            self._strum_last_index = None
            return

        if self._strum_last_index is None:
            self._strum_last_index = new_index
            return

        old_index = self._strum_last_index

        if new_index == old_index:
            return

        direction = 1 if new_index > old_index else -1

        for index in range(
            old_index + direction,
            new_index + direction,
            direction,
        ):
            self._client.send_message(
                self._strum_note_address,
                self._tuned_note_text(
                    notes[index],
                    self._active_root_semitone,
                ),
            )

        self._strum_last_index = new_index

    @Slot()
    def strumEnd(self) -> None:
        self._strum_last_index = None

    def _selected_synth(
        self,
        role: SynthRole,
    ) -> SynthDefinition:
        runtime = self._runtime(role)
        return self._synths[runtime.selected_index]

    def _send_synth_name(self, role: SynthRole) -> None:
        synth = self._selected_synth(role)

        if role == "chord":
            address = self._chord_synth_address
        elif role == "strum":
            address = self._strum_synth_address
        else:
            address = self._bass_synth_address

        self._client.send_message(address, synth.key)

    def _send_synth_params(self, role: SynthRole) -> None:
        runtime = self._runtime(role)
        synth = self._selected_synth(role)
        values = runtime.values_by_synth[runtime.selected_index]

        arguments: list[str | float] = []

        for control in synth.controls:
            arguments.extend(
                [control.key, float(values[control.key])]
            )

        if role == "chord":
            address = self._chord_params_address
        elif role == "strum":
            address = self._strum_params_address
        else:
            address = self._bass_params_address

        self._client.send_message(address, arguments)

    def _send_synth_state(self, role: SynthRole) -> None:
        self._send_synth_name(role)
        self._send_synth_params(role)

    def _rhythm_payload(self) -> dict[str, Any]:
        rhythm = self._selected_rhythm()
        index = self._rhythm.selected_index
        busyness = self._rhythm.busyness_by_rhythm[index]
        chord_activity = self._effective_chord_activity()
        bass_activity = (
            self._rhythm.bass_activity_by_rhythm[index]
        )

        busyness_source = ui_activity_to_source(busyness)
        chord_source = (
            ui_activity_to_source(chord_activity)
            if chord_activity > 0
            else None
        )
        bass_source = ui_activity_to_source(bass_activity)

        percussion_events: list[dict[str, Any]] = []

        for layer_index in range(busyness_source + 1):
            percussion_events.extend(
                copy.deepcopy(
                    rhythm.percussion_layers[layer_index]["events"]
                )
            )

        percussion_events.sort(
            key=lambda event: float(event["time"])
        )

        return {
            "id": rhythm.key,
            "label": rhythm.label,
            "meter": rhythm.meter,
            "length_beats": rhythm.length_beats,
            "tempo": self._rhythm.tempo_by_rhythm[index],
            "busyness": busyness,
            "chord_activity": chord_activity,
            "bass_activity": bass_activity,
            "percussion_events": percussion_events,
            "chord_events": (
                [
                    copy.deepcopy(event)
                    for event in rhythm.chord_levels[chord_source]
                ]
                if chord_source is not None
                else []
            ),
            "bass_events": [
                copy.deepcopy(event)
                for event in rhythm.bass_levels[bass_source]
            ],
        }

    def _send_rhythm_config(self) -> None:
        rhythm_payload = self._rhythm_payload()

        self._debug(
            "osc_rhythm_config",
            rhythm=rhythm_payload.get("id"),
            tempo=rhythm_payload.get("tempo"),
            chord_event_count=len(
                rhythm_payload.get(
                    "chord_events",
                    [],
                )
            ),
            **self._debug_chord_state(),
        )

        payload = json.dumps(
            rhythm_payload,
            separators=(",", ":"),
        )
        self._client.send_message(
            self._rhythm_config_address,
            payload,
        )

    def send_initial_state(self) -> None:
        self._debug(
            "send_initial_state_enter",
            **self._debug_chord_state(),
        )

        # Hard-quiesce the receiver before replacing complete instrument state.
        # Do not derive the initial gate from self._rhythm_running here:
        # transport may be true in the preset we are about to start.
        self._client.send_message(
            self._rhythm_chord_enabled_address,
            0,
        )
        self._client.send_message(
            self._rhythm_running_address,
            0,
        )
        self._send_manual_chord("stop_all")

        self._active_row = -1
        self._active_root_semitone = -1
        self._strum_last_index = None
        self._clear_touch_dropout_state()
        self._pressed_chords.clear()
        self._pressed_chord_order.clear()
        self._promoted_chords.clear()
        self._chord_activity_hold_override = False
        self._send_chord_state(
            play_now=False
        )

        self._client.send_message(
            self._chord_amp_address,
            self._chord_volume,
        )
        self._client.send_message(
            self._strum_amp_address,
            self._strum_volume,
        )
        self._client.send_message(
            self._bass_amp_address,
            self._bass_volume,
        )
        self._client.send_message(
            self._percussion_amp_address,
            self._percussion_volume,
        )

        self._send_synth_state("chord")
        self._send_synth_state("strum")
        self._send_synth_state("bass")
        self._send_rhythm_config()

        self._client.send_message(
            self._bass_running_address,
            1 if self._bass_running else 0,
        )

        if self._rhythm_running:
            self._client.send_message(
                self._rhythm_running_address,
                1,
            )
            self._send_rhythm_chord_enabled()
        else:
            self._client.send_message(
                self._rhythm_chord_enabled_address,
                0,
            )
            self._client.send_message(
                self._rhythm_running_address,
                0,
            )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Qt Quick Omnichord with synchronized rhythm, chord and bass"
        )
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4560)

    window_group = parser.add_mutually_exclusive_group()
    window_group.add_argument(
        "--fullscreen",
        action="store_true",
        help="Start without a title bar and scale the complete UI to the screen.",
    )
    window_group.add_argument(
        "--windowed",
        action="store_true",
        help="Override defaults.json and start in a normal window.",
    )
    parser.add_argument(
        "--no-scale-to-fit",
        action="store_true",
        help="Disable automatic uniform scaling of the complete control surface.",
    )

    renderer_group = parser.add_mutually_exclusive_group()
    renderer_group.add_argument(
        "--software-renderer",
        action="store_true",
        help=(
            "Use Qt Quick's software scene-graph renderer. "
            "Useful for isolating GPU/Wayland display problems."
        ),
    )
    renderer_group.add_argument(
        "--opengl-renderer",
        action="store_true",
        help=(
            "Request the OpenGL Qt Quick RHI backend explicitly."
        ),
    )

    platform_group = parser.add_mutually_exclusive_group()
    platform_group.add_argument(
        "--x11",
        action="store_true",
        help=(
            "Run through XWayland/XCB instead of native Wayland "
            "(diagnostic option)."
        ),
    )
    platform_group.add_argument(
        "--wayland",
        action="store_true",
        help=(
            "Force the native Wayland Qt platform plugin "
            "(diagnostic option)."
        ),
    )
    parser.add_argument(
        "--chord-state-address",
        default="/chord/state",
    )
    parser.add_argument(
        "--chord-manual-address",
        default="/chord/manual",
    )
    parser.add_argument(
        "--chord-amp-address",
        default="/chord/amp",
    )
    parser.add_argument(
        "--strum-amp-address",
        default="/strum/amp",
    )
    parser.add_argument(
        "--bass-amp-address",
        default="/bass/amp",
    )
    parser.add_argument(
        "--percussion-amp-address",
        default="/rhythm/amp",
    )
    parser.add_argument(
        "--chord-synth-address",
        default="/chord/synth/name",
    )
    parser.add_argument(
        "--chord-params-address",
        default="/chord/synth/params",
    )
    parser.add_argument(
        "--strum-synth-address",
        default="/strum/synth/name",
    )
    parser.add_argument(
        "--strum-params-address",
        default="/strum/synth/params",
    )
    parser.add_argument(
        "--bass-synth-address",
        default="/bass/synth/name",
    )
    parser.add_argument(
        "--bass-params-address",
        default="/bass/synth/params",
    )
    parser.add_argument(
        "--bass-running-address",
        default="/bass/running",
    )
    parser.add_argument(
        "--strum-note-address",
        default="/strum/note",
    )
    parser.add_argument(
        "--rhythm-config-address",
        default="/rhythm/config",
    )
    parser.add_argument(
        "--rhythm-running-address",
        default="/rhythm/running",
    )
    parser.add_argument(
        "--rhythm-chord-enabled-address",
        default="/rhythm/chord/enabled",
    )
    parser.add_argument(
        "--panic-address",
        default="/panic",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help=(
            "Log detailed chord-touch and OSC state transitions "
            "to ~/.omnichord/debug-*.jsonl"
        ),
    )
    parser.add_argument(
        "--debug-file",
        type=Path,
        default=None,
        help=(
            "Write debug JSONL to this path; implies --debug."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    # These Qt choices must be made before the first application/window is
    # constructed.
    if args.software_renderer:
        os.environ["QT_QUICK_BACKEND"] = "software"
        os.environ.pop("QSG_RHI_BACKEND", None)
    elif args.opengl_renderer:
        os.environ.pop("QT_QUICK_BACKEND", None)
        os.environ["QSG_RHI_BACKEND"] = "opengl"

    if args.x11:
        os.environ["QT_QPA_PLATFORM"] = "xcb"
    elif args.wayland:
        os.environ["QT_QPA_PLATFORM"] = "wayland"

    # QSG_INFO prints the actual scene-graph backend chosen by Qt. It is kept
    # on for this diagnostic build; the output is only a few startup lines.
    os.environ.setdefault("QSG_INFO", "1")

    defaults = load_defaults(APP_DIR / "defaults.json")
    chords = load_chords(APP_DIR / "chords.csv")
    (
        synths,
        legacy_chord_synth_index,
        legacy_strum_synth_index,
        legacy_bass_synth_index,
    ) = load_synth_catalog(APP_DIR / "synths.json")
    rhythms = load_rhythm_catalog(APP_DIR / "rhythms.json")
    title_config = load_title_config(
        APP_DIR / "title.json"
    )
    intonation_eq = load_intonation_table(
        APP_DIR / "intonation_eq.json"
    )
    intonation_harm = load_intonation_table(
        APP_DIR / "intonation_harm.json"
    )
    intonation_jv = load_intonation_table(
        APP_DIR / "intonation_jv.json"
    )

    # Startup synth selections are controlled by defaults.json.
    # The legacy values in synths.json remain harmless and preserve
    # compatibility with the existing catalogue updater.
    synth_index_by_key = {
        synth.key: index
        for index, synth in enumerate(synths)
    }

    try:
        default_chord_synth_index = synth_index_by_key[
            str(defaults["synths"]["chord"])
        ]
        default_strum_synth_index = synth_index_by_key[
            str(defaults["synths"]["strum"])
        ]
        default_bass_synth_index = synth_index_by_key[
            str(defaults["synths"]["bass"])
        ]
    except KeyError as exc:
        raise ValueError(
            f"Unknown synth in defaults.json: {exc}"
        ) from exc

    QQuickStyle.setStyle("Basic")

    app = QGuiApplication(sys.argv)
    app.setApplicationName("Qt Omnichord")

    print(
        "Qt Omnichord display diagnostics:",
        file=sys.stderr,
        flush=True,
    )
    print(
        f"  QPA platform: {QGuiApplication.platformName()}",
        file=sys.stderr,
        flush=True,
    )
    print(
        f"  XDG_SESSION_TYPE: {os.environ.get('XDG_SESSION_TYPE', '<unset>')}",
        file=sys.stderr,
        flush=True,
    )
    print(
        f"  WAYLAND_DISPLAY: {os.environ.get('WAYLAND_DISPLAY', '<unset>')}",
        file=sys.stderr,
        flush=True,
    )
    print(
        f"  DISPLAY: {os.environ.get('DISPLAY', '<unset>')}",
        file=sys.stderr,
        flush=True,
    )
    print(
        f"  QT_QPA_PLATFORM: {os.environ.get('QT_QPA_PLATFORM', '<auto>')}",
        file=sys.stderr,
        flush=True,
    )
    print(
        f"  QT_QUICK_BACKEND: {os.environ.get('QT_QUICK_BACKEND', '<default>')}",
        file=sys.stderr,
        flush=True,
    )
    print(
        f"  QSG_RHI_BACKEND: {os.environ.get('QSG_RHI_BACKEND', '<default>')}",
        file=sys.stderr,
        flush=True,
    )

    backend = InstrumentBackend(
        chords=chords,
        synths=synths,
        rhythms=rhythms,
        intonation_eq=intonation_eq,
        intonation_harm=intonation_harm,
        intonation_jv=intonation_jv,
        default_chord_synth_index=(
            default_chord_synth_index
        ),
        default_strum_synth_index=(
            default_strum_synth_index
        ),
        default_bass_synth_index=(
            default_bass_synth_index
        ),
        defaults=defaults,
        osc_host=args.host,
        osc_port=args.port,
        chord_state_address=args.chord_state_address,
        chord_manual_address=args.chord_manual_address,
        chord_amp_address=args.chord_amp_address,
        strum_amp_address=args.strum_amp_address,
        bass_amp_address=args.bass_amp_address,
        percussion_amp_address=args.percussion_amp_address,
        chord_synth_address=args.chord_synth_address,
        chord_params_address=args.chord_params_address,
        strum_synth_address=args.strum_synth_address,
        strum_params_address=args.strum_params_address,
        bass_synth_address=args.bass_synth_address,
        bass_params_address=args.bass_params_address,
        bass_running_address=args.bass_running_address,
        strum_note_address=args.strum_note_address,
        rhythm_config_address=args.rhythm_config_address,
        rhythm_running_address=args.rhythm_running_address,
        rhythm_chord_enabled_address=(
            args.rhythm_chord_enabled_address
        ),
        panic_address=args.panic_address,
        debug_enabled=(
            args.debug
            or args.debug_file is not None
        ),
        debug_file=args.debug_file,
    )

    engine = QQmlApplicationEngine()
    context = engine.rootContext()

    context.setContextProperty("backend", backend)
    context.setContextProperty(
        "chordNames",
        [chord.label for chord in chords],
    )
    context.setContextProperty(
        "noteDefinitions",
        list(NOTE_DEFINITIONS),
    )
    context.setContextProperty(
        "octaveNames",
        list(OCTAVE_NAMES),
    )
    context.setContextProperty(
        "synthNames",
        [synth.label for synth in synths],
    )
    context.setContextProperty(
        "rhythmNames",
        [rhythm.label for rhythm in rhythms],
    )
    context.setContextProperty(
        "tuningModeNames",
        list(TUNING_MODE_NAMES),
    )
    context.setContextProperty(
        "headerTitleText",
        title_config["text"],
    )
    context.setContextProperty(
        "headerTitleHeight",
        title_config["height"],
    )
    context.setContextProperty(
        "headerTitleFont",
        title_config["font"],
    )

    window_defaults = defaults.get("window", {})
    start_fullscreen = bool(
        window_defaults.get("start_fullscreen", False)
    )
    if args.fullscreen:
        start_fullscreen = True
    elif args.windowed:
        start_fullscreen = False

    scale_to_fit = bool(
        window_defaults.get("scale_to_fit", True)
    ) and not args.no_scale_to_fit

    context.setContextProperty(
        "startFullscreen",
        start_fullscreen,
    )
    context.setContextProperty(
        "scaleToFit",
        scale_to_fit,
    )

    engine.load(
        QUrl.fromLocalFile(str(APP_DIR / "Main.qml"))
    )

    if not engine.rootObjects():
        return 1

    backend.send_initial_state()

    # Make teardown order explicit. QML must be destroyed while the Python
    # backend QObject is still alive; otherwise its context property becomes
    # null and dozens of bindings log TypeErrors during application shutdown.
    exit_code = app.exec()

    # Destroy the QML engine/root objects first.
    del engine

    # The backend can safely be released after QML no longer references it.
    del backend

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
