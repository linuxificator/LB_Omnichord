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
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Literal, cast

from PySide6.QtCore import (
    QObject,
    Property,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQuickControls2 import QQuickStyle
from application_composition import (
    ApplicationDependencies,
    ClientSelection,
    CommandClient,
    compose_application_graph,
    load_application_resources,
)
from bass_riffs import BassRiffCatalog
from control_limits import bounded_control_range, clamp_control_value
from config_loader import ResolvedAmyConfig
from drum_patterns import (
    DrumRhythm,
    FILL_DENSITY_BARS,
    load_drum_pattern_catalog,
)
from musical_state import (
    ChordSnapshot,
    OmniPerformanceSnapshot,
    TuningSnapshot,
    chord_snapshot,
    freeze_intonation_tables,
    intonation_factor,
    tune_note,
    tuning_note_offset,
)
from json_store import JsonStore
from preset_plan import (
    ChordRowPreset,
    EffectsPreset,
    RhythmSettingPreset,
    compile_omni_preset_plan,
)
from runtime_paths import production_frontend_asset_root
from screenshot_state import populate_screenshot_input_controls
from synth_state import SynthState
from user_data import OMNI_PRESET_DIR, ensure_user_configs, migrate_user_layout


CODE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = production_frontend_asset_root(CODE_DIR)
GUI_DIR = FRONTEND_DIR / "gui"
CONFIG_DIR = FRONTEND_DIR / "config"
INSTRUMENT_DIR = FRONTEND_DIR / "instruments"
MUSIC_DIR = FRONTEND_DIR / "music"

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

NOTE_NAMES_BY_SEMITONE = {item["semitone"]: item["label"] for item in NOTE_DEFINITIONS}

SHARP_NOTE_NAMES = (
    "C",
    "C♯",
    "D",
    "D♯",
    "E",
    "F",
    "F♯",
    "G",
    "G♯",
    "A",
    "A♯",
    "B",
)
FLAT_NOTE_NAMES = (
    "C",
    "D♭",
    "D",
    "E♭",
    "E",
    "F",
    "G♭",
    "G",
    "A♭",
    "A",
    "B♭",
    "B",
)
NATURAL_NOTE_LETTERS = ("C", "D", "E", "F", "G", "A", "B")
NATURAL_NOTE_SEMITONES = (0, 2, 4, 5, 7, 9, 11)

# The diatonic function of every interval used by music/chords.csv. Keeping
# the function as well as the pitch is what lets C minor display E-flat rather
# than the enharmonic but musically misleading D-sharp.
CHORD_DEGREE_BY_INTERVAL = {
    0: 0,
    1: 1,
    2: 1,
    3: 2,
    4: 2,
    5: 3,
    6: 4,
    7: 4,
    8: 4,
    9: 5,
    10: 6,
    11: 6,
    12: 0,
    13: 1,
    14: 1,
    15: 1,
    17: 3,
    18: 3,
    20: 5,
    21: 5,
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
REVERB_LEVEL_MAX = 3.0

PRESET_COUNT = 18
PRESET_DIRECTORY = OMNI_PRESET_DIR
LAST_PRESET_FILE = "last_preset.json"

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
    native_default: float | None
    minimum: float
    maximum: float
    step: float
    decimals: int
    unit: str
    scale: str


@dataclass(frozen=True)
class SynthDefinition:
    key: str
    label: str
    controls: tuple[SynthControl, ...]


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
    drum_pattern: DrumRhythm
    # Retained only for backwards-compatible catalogue diagnostics. Runtime
    # percussion uses drum_pattern's five complete logical-role patterns.
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
    fill_order_by_rhythm: list[list[int]]
    fill_density_index_by_rhythm: list[int]


@dataclass(frozen=True)
class RunningPresetState:
    """Live controls that a preset must not replace during playback."""

    attributes: dict[str, Any]
    rhythm_controls: tuple[int, int, int, list[int], int]
    active_row_octave: tuple[int, int] | None


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
    return " ".join(abbreviations.get(word, word) for word in text.split())


LadderPattern = tuple[tuple[int, ...], tuple[int, ...]]

# LDR plays every listed pitch rather than letting an improviser de-emphasize
# an avoid tone. These patterns therefore use common chord-scale relationships
# but omit avoid tones and unspecified alternative alterations where useful.
# Every pattern still contains every pitch class explicitly present in its
# chord definition.
_MAJOR_PENTATONIC: LadderPattern = (
    (0, 2, 4, 7, 9),
    (0, 1, 2, 4, 5),
)
_MINOR_PENTATONIC: LadderPattern = (
    (0, 3, 5, 7, 10),
    (0, 2, 3, 4, 6),
)
_SUSPENDED_PENTATONIC: LadderPattern = (
    (0, 2, 5, 7, 9),
    (0, 1, 3, 4, 5),
)
_MINOR_6_9_PENTATONIC: LadderPattern = (
    (0, 2, 3, 7, 9),
    (0, 1, 2, 4, 5),
)
_MINOR_ADD9_HEXATONIC: LadderPattern = (
    (0, 2, 3, 5, 7, 10),
    (0, 1, 2, 3, 4, 6),
)
_MAJOR7_HEXATONIC: LadderPattern = (
    (0, 2, 4, 7, 9, 11),
    (0, 1, 2, 4, 5, 6),
)
_DOMINANT_HEXATONIC: LadderPattern = (
    (0, 2, 4, 7, 9, 10),
    (0, 1, 2, 4, 5, 6),
)
_MELODIC_MINOR_HEXATONIC: LadderPattern = (
    (0, 2, 3, 7, 9, 11),
    (0, 1, 2, 4, 5, 6),
)
_DOMINANT_SUS_HEXATONIC: LadderPattern = (
    (0, 2, 5, 7, 9, 10),
    (0, 1, 3, 4, 5, 6),
)
_LOCRIAN_NATURAL2: LadderPattern = (
    (0, 2, 3, 5, 6, 8, 10),
    (0, 1, 2, 3, 4, 5, 6),
)
_WHOLE_HALF_DIMINISHED: LadderPattern = (
    (0, 2, 3, 5, 6, 8, 9, 11),
    # C D E-flat F G-flat A-flat A B is the conventional readable
    # mixed spelling; the repeated sixth letter is intentional.
    (0, 1, 2, 3, 4, 5, 5, 6),
)
_WHOLE_TONE: LadderPattern = (
    (0, 2, 4, 6, 8, 10),
    (0, 1, 2, 3, 4, 5),
)
_LYDIAN_AUGMENTED: LadderPattern = (
    (0, 2, 4, 6, 8, 9, 11),
    (0, 1, 2, 3, 4, 5, 6),
)
_MIXOLYDIAN: LadderPattern = (
    (0, 2, 4, 5, 7, 9, 10),
    (0, 1, 2, 3, 4, 5, 6),
)
_MAJOR: LadderPattern = (
    (0, 2, 4, 5, 7, 9, 11),
    (0, 1, 2, 3, 4, 5, 6),
)
_DORIAN: LadderPattern = (
    (0, 2, 3, 5, 7, 9, 10),
    (0, 1, 2, 3, 4, 5, 6),
)
_LYDIAN_DOMINANT: LadderPattern = (
    (0, 2, 4, 6, 7, 9, 10),
    (0, 1, 2, 3, 4, 5, 6),
)
_DOMINANT_FLAT5: LadderPattern = (
    (0, 2, 4, 6, 10),
    (0, 1, 2, 4, 6),
)
_DOMINANT_SHARP5: LadderPattern = (
    (0, 2, 4, 8, 10),
    (0, 1, 2, 4, 6),
)
_DOMINANT_FLAT9: LadderPattern = (
    (0, 1, 4, 7, 10),
    (0, 1, 2, 4, 6),
)
_DOMINANT_SHARP9: LadderPattern = (
    (0, 3, 4, 7, 10),
    (0, 1, 2, 4, 6),
)
_DOMINANT_FLAT13: LadderPattern = (
    (0, 2, 4, 7, 8, 10),
    (0, 1, 2, 4, 5, 6),
)

CHORD_LADDER_PATTERNS: dict[str, LadderPattern] = {
    "major": _MAJOR_PENTATONIC,
    "minor": _MINOR_PENTATONIC,
    "diminished": _WHOLE_HALF_DIMINISHED,
    "augmented": _WHOLE_TONE,
    "sus2": _SUSPENDED_PENTATONIC,
    "sus4": _SUSPENDED_PENTATONIC,
    "5": _MAJOR_PENTATONIC,
    "major6": _MAJOR_PENTATONIC,
    "minor6": _MINOR_6_9_PENTATONIC,
    "6_9": _MAJOR_PENTATONIC,
    "add9": _MAJOR_PENTATONIC,
    "minor_add9": _MINOR_ADD9_HEXATONIC,
    "dominant7": _DOMINANT_HEXATONIC,
    "major7": _MAJOR7_HEXATONIC,
    "minor7": _MINOR_PENTATONIC,
    "minor_major7": _MELODIC_MINOR_HEXATONIC,
    "minor7_flat5": _LOCRIAN_NATURAL2,
    "diminished7": _WHOLE_HALF_DIMINISHED,
    "augmented7": _DOMINANT_SHARP5,
    "augmented_major7": _LYDIAN_AUGMENTED,
    "7_sus4": _DOMINANT_SUS_HEXATONIC,
    "dominant9": _DOMINANT_HEXATONIC,
    "major9": _MAJOR7_HEXATONIC,
    "minor9": _MINOR_ADD9_HEXATONIC,
    "dominant11": _MIXOLYDIAN,
    "major11": _MAJOR,
    "minor11": _MINOR_ADD9_HEXATONIC,
    "dominant13": _MIXOLYDIAN,
    "major13": _MAJOR,
    "minor13": _DORIAN,
    "dominant7_flat5": _DOMINANT_FLAT5,
    "dominant7_sharp5": _DOMINANT_SHARP5,
    "dominant7_flat9": _DOMINANT_FLAT9,
    "dominant7_sharp9": _DOMINANT_SHARP9,
    "dominant7_sharp11": _LYDIAN_DOMINANT,
    "dominant7_flat13": _DOMINANT_FLAT13,
}


def ladder_pattern(chord_suffix: str) -> LadderPattern:
    """Return the audited LDR pitches and musical scale-degree spellings."""
    try:
        return CHORD_LADDER_PATTERNS[chord_suffix]
    except KeyError as exc:
        raise ValueError(f"No audited LDR pattern for chord {chord_suffix!r}") from exc


def _fallback_prefers_flats(root_label: str, chord_suffix: str) -> bool:
    """Choose a readable single-accidental fallback for rare double notes."""
    if "♭" in root_label:
        return True
    if "♯" in root_label:
        return False
    if "flat" in chord_suffix or "diminished" in chord_suffix:
        return True
    if "sharp" in chord_suffix or "augmented" in chord_suffix:
        return False

    root_semitone = NATURAL_NOTE_SEMITONES[NATURAL_NOTE_LETTERS.index(root_label)]
    if chord_suffix.startswith("minor"):
        return root_semitone in {0, 2, 5, 7}
    if "dominant" in chord_suffix or chord_suffix == "7_sus4":
        return root_semitone in {0, 5}
    return root_semitone == 5


def spell_strum_note_names(
    root_semitone: int,
    chord_suffix: str,
    intervals: tuple[int, ...],
    degree_offsets: tuple[int, ...],
) -> list[str]:
    """Spell root-relative pitch classes using their musical note function."""
    root_label = str(NOTE_NAMES_BY_SEMITONE[int(root_semitone) % 12])
    root_letter_index = NATURAL_NOTE_LETTERS.index(root_label[0])
    fallback_names = (
        FLAT_NOTE_NAMES if _fallback_prefers_flats(root_label, chord_suffix) else SHARP_NOTE_NAMES
    )

    names: list[str] = []
    seen_pitch_classes: set[int] = set()
    for interval, degree_offset in zip(intervals, degree_offsets):
        pitch_class = (int(root_semitone) + interval) % 12
        if pitch_class in seen_pitch_classes:
            continue
        seen_pitch_classes.add(pitch_class)

        letter_index = (root_letter_index + degree_offset) % 7
        letter = NATURAL_NOTE_LETTERS[letter_index]
        accidental = (pitch_class - NATURAL_NOTE_SEMITONES[letter_index]) % 12
        if accidental > 6:
            accidental -= 12

        if accidental == -1:
            names.append(f"{letter}♭")
        elif accidental == 0:
            names.append(letter)
        elif accidental == 1:
            names.append(f"{letter}♯")
        else:
            # Double accidentals are hard to scan in a 34-pixel marker. They
            # occur only in unusual altered/octatonic keys, where an explicit
            # readable enharmonic mix is preferable to an illegible glyph.
            names.append(fallback_names[pitch_class])

    return names


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

    rotated = list(
        enumerate(
            intervals[inversion_index:],
            start=inversion_index,
        )
    ) + list(enumerate(intervals[:inversion_index]))

    ascending: list[tuple[int, int]] = []
    previous_pitch: int | None = None

    for original_index, pitch in rotated:
        if previous_pitch is not None:
            while pitch <= previous_pitch:
                pitch += 12

        ascending.append((original_index, pitch))
        previous_pitch = pitch

    root_pitch = next(pitch for original_index, pitch in ascending if original_index == 0)

    return tuple(pitch - root_pitch for _, pitch in ascending)


def make_inversions(
    intervals: tuple[int, ...],
) -> tuple[tuple[int, ...], ...]:
    return tuple(inverted_intervals(intervals, index) for index in range(len(intervals)))


def load_chords(path: Path) -> tuple[ChordType, ...]:
    chords: list[ChordType] = []

    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.reader(csv_file)
        header = next(reader, None)

        if not header or header[:2] != ["chord_suffix", "intervals"]:
            raise ValueError(f"{path} must begin with: chord_suffix,intervals")

        for line_number, row in enumerate(reader, start=2):
            if not row or not row[0].strip():
                continue

            suffix = row[0].strip()

            try:
                intervals = tuple(int(value.strip()) for value in row[1:] if value.strip())
            except ValueError as exc:
                raise ValueError(f"Invalid interval on line {line_number} of {path}") from exc

            if not intervals or intervals[0] != 0:
                raise ValueError(f"Chord {suffix!r} must start with interval 0")

            if tuple(sorted(intervals)) != intervals:
                raise ValueError(f"Intervals for {suffix!r} must be ascending")

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
        raise ValueError(f"{path} must define exactly {ROW_COUNT} chord_rows")

    required_sections = (
        "synths",
        "volumes",
        "transport",
        "rhythm",
    )
    for section in required_sections:
        if section not in raw:
            raise ValueError(f"{path} is missing section {section!r}")

    return raw


def load_intonation_table(
    path: Path,
) -> tuple[tuple[float, ...], ...]:
    raw = json.loads(path.read_text(encoding="utf-8"))

    rows: list[tuple[float, ...]] = []

    for root_name in INTONATION_NOTE_IDS:
        key_name = f"key_{root_name}"
        row_raw = raw.get(key_name)

        if not isinstance(row_raw, dict):
            raise ValueError(f"{path} is missing {key_name!r}")

        row: list[float] = []

        for note_name in INTONATION_NOTE_IDS:
            value_name = f"note_{note_name}"

            if value_name not in row_raw:
                raise ValueError(f"{path}: {key_name!r} is missing {value_name!r}")

            factor = float(row_raw[value_name])

            if not math.isfinite(factor) or factor <= 0.0:
                raise ValueError(f"{path}: invalid factor {key_name}.{value_name}={factor!r}")

            row.append(factor)

        rows.append(tuple(row))

    return tuple(rows)


def load_title_config(
    path: Path,
) -> dict[str, object]:
    default_height = 74
    default: dict[str, object] = {
        "text": "Luciel's Birthday Omnichord",
        "height": default_height,
        "font": "URW Chancery L",
    }

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default

    if not isinstance(raw, dict):
        return default

    text = str(raw.get("text", default["text"]))
    font = str(raw.get("font", default["font"])).strip()

    try:
        height = int(raw.get("height", default_height))
    except (TypeError, ValueError):
        height = default_height

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
        controls_list: list[SynthControl] = []
        for control in raw_synth["controls"]:
            key = str(control["key"])
            minimum, maximum = bounded_control_range(
                key,
                float(control["minimum"]),
                float(control["maximum"]),
            )
            default = clamp_control_value(key, float(control["default"]))
            default = max(minimum, min(maximum, default))
            controls_list.append(
                SynthControl(
                    key=key,
                    label=str(control["label"]),
                    group=str(control["group"]),
                    default=default,
                    native_default=(
                        None
                        if control.get("native_default") is None
                        else float(control["native_default"])
                    ),
                    minimum=minimum,
                    maximum=maximum,
                    step=float(control["step"]),
                    decimals=int(control["decimals"]),
                    unit=str(control.get("unit", "")),
                    scale=str(control.get("scale", "linear")),
                )
            )
        controls = tuple(controls_list)

        synths.append(
            SynthDefinition(
                key=str(raw_synth["key"]),
                label=str(raw_synth["label"]),
                controls=controls,
            )
        )

    def index_for(key: str) -> int:
        return next(index for index, synth in enumerate(synths) if synth.key == key)

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
    drum_catalog = load_drum_pattern_catalog(path.parent / "drums")
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
                default_chord_activity=int(item["default_chord_activity"]),
                default_bass_activity=int(item["default_bass_activity"]),
                drum_pattern=drum_catalog.rhythm(str(item["id"])),
                percussion_layers=tuple(dict(layer) for layer in item["percussion_layers"]),
                chord_levels=tuple(
                    tuple(dict(event) for event in level) for level in item["chord_levels"]
                ),
                bass_levels=tuple(
                    tuple(dict(event) for event in level) for level in item["bass_levels"]
                ),
            )
        )

    if not rhythms:
        raise ValueError("No rhythm definitions found")

    for rhythm in rhythms:
        if len(rhythm.percussion_layers) != 5:
            raise ValueError(f"Rhythm {rhythm.key!r} must have five percussion layers")
        if rhythm.drum_pattern.meter != rhythm.meter:
            raise ValueError(f"Rhythm {rhythm.key!r} meter differs from drum catalogue")
        if len(rhythm.chord_levels) != 5:
            raise ValueError(f"Rhythm {rhythm.key!r} must have five chord levels")
        if len(rhythm.bass_levels) != 5:
            raise ValueError(f"Rhythm {rhythm.key!r} must have five bass levels")

    return tuple(rhythms)


class InstrumentBackend(QObject):
    # This is the single policy list for scalar state that stays live while a
    # preset changes during an active beat. Subclasses extend it instead of
    # adding per-control rhythm-running branches to their preset loaders.
    RUNNING_PRESET_PRESERVED_ATTRIBUTES: ClassVar[tuple[str, ...]] = (
        "_rhythm_running",
        "_running_tempo",
        "_reverb_level",
        "_reverb_liveness",
        "_reverb_damping",
        "_reverb_drums",
    )

    stateChanged = Signal()

    chordVolumeChanged = Signal()
    strumVolumeChanged = Signal()
    bassVolumeChanged = Signal()
    percussionVolumeChanged = Signal()
    reverbLevelChanged = Signal()
    reverbLivenessChanged = Signal()
    reverbDampingChanged = Signal()
    reverbDrumsIncludedChanged = Signal()
    masterVolumeChanged = Signal()
    masterMutedChanged = Signal()
    strumModeChanged = Signal()
    strumNoteNamesChanged = Signal()
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

    # These integration signals live in the base meta-object so PySide 6.8 on
    # aarch64 does not append subclass signals after inherited slots. Newer
    # PySide versions silently reorder them, but 6.8 rejects that meta-object.
    midiStateChanged = Signal()
    midiTuningChanged = Signal()
    midiPresetChanged = Signal()
    midiPresetStored = Signal(int)

    def __init__(
        self,
        chords: tuple[ChordType, ...],
        synths: tuple[SynthDefinition, ...],
        rhythms: tuple[RhythmDefinition, ...],
        bass_riffs: BassRiffCatalog,
        intonation_eq: tuple[tuple[float, ...], ...],
        intonation_harm: tuple[tuple[float, ...], ...],
        intonation_jv: tuple[tuple[float, ...], ...],
        default_chord_synth_index: int,
        default_strum_synth_index: int,
        default_bass_synth_index: int,
        defaults: dict[str, Any],
        client: CommandClient,
        chord_state_address: str,
        chord_manual_address: str,
        chord_amp_address: str,
        strum_amp_address: str,
        bass_amp_address: str,
        percussion_amp_address: str,
        reverb_address: str,
        master_volume_address: str,
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
        self._bass_riffs = bass_riffs
        self._intonation_tables = {
            "EQ": intonation_eq,
            "HARM": intonation_harm,
            "JV": intonation_jv,
        }
        self._frozen_intonation_tables = freeze_intonation_tables(self._intonation_tables)
        self._client = client

        self._chord_state_address = chord_state_address
        self._chord_manual_address = chord_manual_address
        self._chord_amp_address = chord_amp_address
        self._strum_amp_address = strum_amp_address
        self._bass_amp_address = bass_amp_address
        self._percussion_amp_address = percussion_amp_address
        self._reverb_address = reverb_address
        self._master_volume_address = master_volume_address
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
        self._rhythm_chord_enabled_address = rhythm_chord_enabled_address
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
                debug_file = self._preset_dir / (
                    "debug-" + time.strftime("%Y%m%d-%H%M%S") + ".jsonl"
                )
            else:
                debug_file = Path(debug_file).expanduser().resolve()
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
                f"Omnichord debug log: {self._debug_file}",
                file=sys.stderr,
                flush=True,
            )

        self._defaults = copy.deepcopy(defaults)
        self._preset_reference_data: dict[str, Any] = {}
        self._selected_preset = 1
        self._tuning_mode_index = DEFAULT_TUNING_MODE_INDEX
        self._tuning_reference = DEFAULT_TUNING_REFERENCE

        suffix_to_index = {chord.suffix: index for index, chord in enumerate(chords)}
        octave_to_index = {name: index for index, name in enumerate(OCTAVE_NAMES)}

        row_defaults = defaults["chord_rows"]

        try:
            self._row_chord_indexes = [suffix_to_index[str(row["chord"])] for row in row_defaults]
            self._row_octave_indexes = [octave_to_index[str(row["octave"])] for row in row_defaults]
            self._row_inversion_indexes = [int(row.get("inversion", 0)) for row in row_defaults]
        except KeyError as exc:
            raise ValueError(f"Unknown chord or octave in defaults.json: {exc}") from exc

        for row_index, chord_index in enumerate(self._row_chord_indexes):
            inversion_count = len(self._chords[chord_index].inversions)
            self._row_inversion_indexes[row_index] %= inversion_count

        self._active_row = -1
        self._active_root_semitone = -1
        self._state_version = 0

        volumes = defaults["volumes"]
        transport = defaults["transport"]

        self._chord_volume = float(volumes["chord"])
        self._strum_volume = float(volumes["strum"])
        self._bass_volume = float(volumes["bass"])
        self._percussion_volume = float(volumes["percussion"])
        effects = defaults.get("effects", {})
        self._reverb_level = max(
            0.0,
            min(REVERB_LEVEL_MAX, float(effects.get("reverb_level", 0.0))),
        )
        self._reverb_liveness = max(0.0, min(1.0, float(effects.get("reverb_liveness", 0.5))))
        self._reverb_damping = max(0.0, min(1.0, float(effects.get("reverb_damping", 0.5))))
        self._reverb_drums = bool(effects.get("reverb_drums", False))
        # Screen masters are live output state, independent of presets.
        self._master_volume = 1.0
        self._master_muted = False
        self._bass_running = bool(transport["bass_running"])

        self._chord_synth = InstrumentBackend._make_synth_runtime(
            self, default_chord_synth_index
        )
        self._strum_synth = InstrumentBackend._make_synth_runtime(
            self, default_strum_synth_index
        )
        self._bass_synth = InstrumentBackend._make_synth_runtime(
            self, default_bass_synth_index
        )

        rhythm_key_to_index = {rhythm.key: index for index, rhythm in enumerate(rhythms)}
        selected_rhythm_key = str(defaults["rhythm"]["selected"])

        if selected_rhythm_key not in rhythm_key_to_index:
            raise ValueError(f"Unknown rhythm in defaults.json: {selected_rhythm_key!r}")

        self._rhythm = RhythmRuntime(
            selected_index=rhythm_key_to_index[selected_rhythm_key],
            tempo_by_rhythm=[rhythm.tempo_default for rhythm in rhythms],
            busyness_by_rhythm=[max(1, min(5, rhythm.default_busyness + 1)) for rhythm in rhythms],
            chord_activity_by_rhythm=[
                source_activity_to_ui(rhythm.default_chord_activity) for rhythm in rhythms
            ],
            bass_activity_by_rhythm=[
                source_activity_to_ui(rhythm.default_bass_activity) for rhythm in rhythms
            ],
            fill_order_by_rhythm=[[] for _ in rhythms],
            fill_density_index_by_rhythm=[0 for _ in rhythms],
        )
        # Rhythm transport is live session state, never startup/preset state.
        self._rhythm_running = False
        self._running_tempo: float | None = None

        # Tempo nudge: 1 BPM every 100 ms = 10 BPM/s. A quick tap keeps
        # running to a 20 BPM total change; a held button keeps going.
        self._tempo_nudge_timer = QTimer(self)
        self._tempo_nudge_timer.setInterval(100)
        self._tempo_nudge_timer.timeout.connect(self._tempo_nudge_tick)
        self._tempo_nudge_direction = 0
        self._tempo_nudge_origin = self._rhythm.tempo_by_rhythm[
            self._rhythm.selected_index
        ]
        self._tempo_nudge_pressed = False

        # Pitch bend is deliberately transient. _tuning_reference remains the
        # stored/preset A-reference; this offset returns to zero on release.
        self._pitch_bend_timer = QTimer(self)
        self._pitch_bend_timer.setInterval(100)
        self._pitch_bend_timer.timeout.connect(self._pitch_bend_tick)
        self._pitch_bend_direction = 0
        self._pitch_bend_offset_hz = 0.0
        self._pitch_bend_returning = False

        self._strum_last_index: int | None = None
        self._strum_ladder_mode = False

        # A held chord temporarily suppresses automatic rhythmic chords
        # without altering the user's stored activity setting.
        self._pressed_chords: set[tuple[int, int]] = set()
        self._pressed_chord_order: list[tuple[int, int]] = []
        self._promoted_chords: set[tuple[int, int]] = set()
        self._chord_activity_hold_override = False

        self._initialized = False

    def initialize(self) -> None:
        """Perform preset I/O after the complete concrete facade is built."""
        if self._initialized:
            return
        self._ensure_preset_storage()
        self._load_startup_preset()
        self._initialized = True

    def _debug(
        self,
        event: str,
        **fields: Any,
    ) -> None:
        if not self._debug_enabled or self._debug_file is None:
            return

        self._debug_sequence += 1

        record = {
            "seq": self._debug_sequence,
            "t_ms": round(
                (time.monotonic() - self._debug_started) * 1000.0,
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
            "pressed": [list(key) for key in sorted(self._pressed_chords)],
            "promoted": [list(key) for key in sorted(self._promoted_chords)],
            "override": (self._chord_activity_hold_override),
            "effective_activity": (self._effective_chord_activity()),
            "stored_activity": (self._rhythm.chord_activity_by_rhythm[self._rhythm.selected_index]),
            "rhythm_running": (self._rhythm_running),
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
    ) -> SynthState:
        return SynthState(self._synths, selected_index)

    def _runtime(self, role: SynthRole) -> SynthState:
        if role == "chord":
            return self._chord_synth
        if role == "strum":
            return self._strum_synth
        return self._bass_synth

    def _emit_state_changed(self) -> None:
        self._state_version += 1
        self.stateChanged.emit()
        self.strumNoteNamesChanged.emit()

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

    @Property(bool, notify=strumModeChanged)
    def strumLadderMode(self) -> bool:
        return self._strum_ladder_mode

    @Property(list, notify=strumNoteNamesChanged)
    def strumNoteNames(self) -> list[str]:
        return self._strum_note_names()

    @Property(int, notify=chordSynthStateChanged)
    def selectedChordSynthIndex(self) -> int:
        return self._chord_synth.selected_index

    @Property(int, notify=strumSynthStateChanged)
    def selectedStrumSynthIndex(self) -> int:
        return self._strum_synth.selected_index

    @Property(int, notify=bassSynthStateChanged)
    def selectedBassSynthIndex(self) -> int:
        return self._bass_synth.selected_index

    @Property(list, notify=chordSynthControlsChanged)
    def chordCommonControls(self) -> list[dict[str, Any]]:
        return self._control_model("chord", "common")

    @Property(list, notify=chordSynthControlsChanged)
    def chordExtraControls(self) -> list[dict[str, Any]]:
        return self._control_model("chord", "extra")

    @Property(list, notify=strumSynthControlsChanged)
    def strumCommonControls(self) -> list[dict[str, Any]]:
        return self._control_model("strum", "common")

    @Property(list, notify=strumSynthControlsChanged)
    def strumExtraControls(self) -> list[dict[str, Any]]:
        return self._control_model("strum", "extra")

    @Property(list, notify=bassSynthControlsChanged)
    def bassCommonControls(self) -> list[dict[str, Any]]:
        return self._control_model("bass", "common")

    @Property(list, notify=bassSynthControlsChanged)
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
        return self._rhythm_tempo_value()

    def _rhythm_tempo_value(self) -> float:
        if self._rhythm_running and self._running_tempo is not None:
            return self._running_tempo
        return self._rhythm.tempo_by_rhythm[self._rhythm.selected_index]

    @Property(float, notify=rhythmStateChanged)
    def rhythmTempoMin(self) -> float:
        return 40.0

    @Property(float, notify=rhythmStateChanged)
    def rhythmTempoMax(self) -> float:
        return 200.0

    @Property(int, notify=rhythmControlsChanged)
    def rhythmBusyness(self) -> int:
        return self._rhythm.busyness_by_rhythm[self._rhythm.selected_index]

    @Property(list, notify=rhythmControlsChanged)
    def rhythmFillEnabled(self) -> list[bool]:
        enabled = set(self._rhythm.fill_order_by_rhythm[self._rhythm.selected_index])
        return [index in enabled for index in range(5)]

    @Property(int, notify=rhythmControlsChanged)
    def rhythmFillDensityIndex(self) -> int:
        return self._rhythm_fill_density_index_value()

    def _rhythm_fill_density_index_value(self) -> int:
        return self._rhythm.fill_density_index_by_rhythm[self._rhythm.selected_index]

    @Property(int, notify=rhythmControlsChanged)
    def rhythmFillDensityBars(self) -> int:
        return FILL_DENSITY_BARS[self._rhythm_fill_density_index_value()]

    @Property(list, constant=True)
    def rhythmFillDensityLabels(self) -> list[str]:
        return [f"/{bars}" for bars in FILL_DENSITY_BARS]

    def _effective_chord_activity(self) -> int:
        if self._chord_activity_hold_override:
            return 0

        return self._rhythm.chord_activity_by_rhythm[self._rhythm.selected_index]

    @Property(int, notify=rhythmControlsChanged)
    def rhythmChordActivity(self) -> int:
        return self._effective_chord_activity()

    @Property(int, notify=rhythmControlsChanged)
    def rhythmBassActivity(self) -> int:
        return self._rhythm.bass_activity_by_rhythm[self._rhythm.selected_index]

    @Property(int, notify=tuningChanged)
    def selectedTuningModeIndex(self) -> int:
        return self._tuning_mode_index

    @Property(int, notify=tuningChanged)
    def tuningReference(self) -> int:
        return int(round(self._effective_tuning_reference()))

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
        return self._runtime(role).control_model(group)

    def _selected_rhythm(self) -> RhythmDefinition:
        return self._rhythms[self._rhythm.selected_index]

    def _midi_control_blocks(self, target: dict[str, Any]) -> bool:
        """Return whether a live MIDI binding owns this numeric target.

        The base backend is usable without the MIDI integration layer.  The
        integrated backend overrides this hook and keeps the normal setters as
        the single state/transport convergence path for both UI and MIDI.
        """
        return False

    def _copy_strum_to_chord_state(self) -> None:
        """Copy logical state before the public operation emits/sends it."""
        self._chord_synth.copy_from(self._strum_synth)
        self._chord_volume = self._strum_volume

    @Slot(float)
    def setChordVolume(self, value: float) -> None:
        if self._midi_control_blocks({"screen": "omni", "kind": "volume", "role": "chord"}):
            return
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
        if self._midi_control_blocks({"screen": "omni", "kind": "volume", "role": "strum"}):
            return
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
        if self._midi_control_blocks({"screen": "omni", "kind": "volume", "role": "bass"}):
            return
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
        if self._midi_control_blocks({"screen": "omni", "kind": "volume", "role": "percussion"}):
            return
        clamped = max(0.0, min(1.0, float(value)))

        if abs(clamped - self._percussion_volume) < 0.0001:
            return

        self._percussion_volume = clamped
        self.percussionVolumeChanged.emit()
        self._client.send_message(
            self._percussion_amp_address,
            clamped,
        )

    def _reverb_payload(self) -> dict[str, Any]:
        return {
            "level": self._reverb_level,
            "liveness": self._reverb_liveness,
            "damping": self._reverb_damping,
            "drums": self._reverb_drums,
        }

    def _send_reverb_state(self) -> None:
        self._client.send_message(self._reverb_address, self._reverb_payload())

    def _send_master_volume(self) -> None:
        effective = 0.0 if self._master_muted else self._master_volume
        self._client.send_message(self._master_volume_address, effective)

    @Slot(float)
    def setMasterVolume(self, value: float) -> None:
        if self._midi_control_blocks({"screen": "omni", "kind": "master_volume"}):
            return
        clamped = max(0.0, min(1.0, float(value)))
        if math.isclose(clamped, self._master_volume, abs_tol=1e-4):
            return
        self._master_volume = clamped
        self.masterVolumeChanged.emit()
        self._send_master_volume()

    @Slot()
    def toggleMasterMuted(self) -> None:
        self._master_muted = not self._master_muted
        self.masterMutedChanged.emit()
        self._send_master_volume()

    @Slot(float)
    def setReverbLevel(self, value: float) -> None:
        if self._midi_control_blocks({"screen": "omni", "kind": "reverb_level"}):
            return
        clamped = max(0.0, min(REVERB_LEVEL_MAX, float(value)))
        if abs(clamped - self._reverb_level) < 0.0001:
            return
        self._reverb_level = clamped
        self.reverbLevelChanged.emit()
        self._send_reverb_state()

    @Slot(float)
    def setReverbLiveness(self, value: float) -> None:
        if self._midi_control_blocks({"screen": "omni", "kind": "reverb_liveness"}):
            return
        clamped = max(0.0, min(1.0, float(value)))
        if abs(clamped - self._reverb_liveness) < 0.0001:
            return
        self._reverb_liveness = clamped
        self.reverbLivenessChanged.emit()
        self._send_reverb_state()

    @Slot(float)
    def setReverbDamping(self, value: float) -> None:
        if self._midi_control_blocks({"screen": "omni", "kind": "reverb_damping"}):
            return
        clamped = max(0.0, min(1.0, float(value)))
        if abs(clamped - self._reverb_damping) < 0.0001:
            return
        self._reverb_damping = clamped
        self.reverbDampingChanged.emit()
        self._send_reverb_state()

    @Slot()
    def toggleReverbDrums(self) -> None:
        self._reverb_drums = not self._reverb_drums
        self.reverbDrumsIncludedChanged.emit()
        self._send_reverb_state()

    def _emit_synth_change(
        self,
        role: SynthRole,
        *,
        selection_changed: bool,
    ) -> None:
        if role == "chord":
            if selection_changed:
                self.chordSynthStateChanged.emit()
            self.chordSynthControlsChanged.emit()
        elif role == "strum":
            if selection_changed:
                self.strumSynthStateChanged.emit()
            self.strumSynthControlsChanged.emit()
        else:
            if selection_changed:
                self.bassSynthStateChanged.emit()
            self.bassSynthControlsChanged.emit()

    @Slot()
    def copyStrumToChord(self) -> None:
        self._copy_strum_to_chord_state()

        self._emit_synth_change("chord", selection_changed=True)
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
        runtime = self._runtime(role)
        if not runtime.select(synth_index):
            return
        self._emit_synth_change(role, selection_changed=True)
        self._send_synth_state(role)

    @Slot(str, float)
    def setChordSynthControl(
        self,
        key: str,
        value: float,
    ) -> None:
        self._set_synth_control("chord", key, value)

    @Slot(str, float)
    def editChordSynthControl(
        self,
        key: str,
        value: float,
    ) -> None:
        self._set_synth_control("chord", key, value, emit_controls=False)

    @Slot(str, float)
    def setStrumSynthControl(
        self,
        key: str,
        value: float,
    ) -> None:
        self._set_synth_control("strum", key, value)

    @Slot(str, float)
    def editStrumSynthControl(
        self,
        key: str,
        value: float,
    ) -> None:
        self._set_synth_control("strum", key, value, emit_controls=False)

    @Slot(str, float)
    def setBassSynthControl(
        self,
        key: str,
        value: float,
    ) -> None:
        self._set_synth_control("bass", key, value)

    @Slot(str, float)
    def editBassSynthControl(
        self,
        key: str,
        value: float,
    ) -> None:
        self._set_synth_control("bass", key, value, emit_controls=False)

    def _set_synth_control(
        self,
        role: SynthRole,
        key: str,
        value: float,
        *,
        emit_controls: bool = True,
    ) -> None:
        runtime = self._runtime(role)
        if self._midi_control_blocks(
            {
                "screen": "omni",
                "kind": "synth_control",
                "role": role,
                "instrument": str(runtime.selected_definition.key),
                "control": str(key),
            }
        ):
            return
        if not runtime.set_control(key, value):
            return

        # UI live edits send the same complete logical state to AMY, but they
        # must not republish the QML control-list model on every mouse move:
        # resetting a Repeater delegate during an active drag drops Qt's mouse
        # grab after the first movement. Instrument switches, preset loads and
        # external API/MIDI writes keep the default controlsChanged emission.
        if emit_controls:
            self._emit_synth_change(role, selection_changed=False)
        self._send_synth_state(role)

    def _tuning_snapshot(self) -> TuningSnapshot:
        return TuningSnapshot(
            mode=TUNING_MODE_NAMES[self._tuning_mode_index],
            reference_hz=float(self._tuning_reference),
            bend_offset_hz=float(self._pitch_bend_offset_hz),
            intonation_tables=self._frozen_intonation_tables,
        )

    def _chord_snapshot(self) -> ChordSnapshot:
        return chord_snapshot(
            active_row=self._active_row,
            active_root_semitone=self._active_root_semitone,
            row_chord_indexes=self._row_chord_indexes,
            suffixes=tuple(chord.suffix for chord in self._chords),
            intervals=tuple(chord.intervals for chord in self._chords),
        )

    def performance_snapshot(self) -> OmniPerformanceSnapshot:
        """Return immutable OMNI context intentionally shared with MIDI."""

        return OmniPerformanceSnapshot(
            tuning=self._tuning_snapshot(),
            chord=self._chord_snapshot(),
        )

    def _effective_tuning_reference(self) -> float:
        return self._tuning_snapshot().effective_reference_hz

    def _tuning_note_offset(self) -> float:
        return tuning_note_offset(self._tuning_snapshot())

    def _intonation_factor(
        self,
        root_semitone: int | None,
        note: int | float,
    ) -> float:
        return intonation_factor(self._tuning_snapshot(), root_semitone, note)

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
        return tune_note(self._tuning_snapshot(), note, root_semitone)

    def _tuned_notes(
        self,
        notes: Sequence[int | float],
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
        return f"{self._tuned_note(note, root_semitone):.12f}"

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
        if self._active_row >= 0 and self._active_root_semitone >= 0:
            self._send_chord_state(play_now=False)

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

    def _stop_pitch_bend(self) -> None:
        self._pitch_bend_timer.stop()
        self._pitch_bend_direction = 0
        self._pitch_bend_returning = False

    def _publish_pitch_bend(self) -> None:
        self.tuningChanged.emit()
        self._refresh_tuning_on_active_notes()

    def _pitch_bend_tick(self) -> None:
        previous = self._pitch_bend_offset_hz
        if self._pitch_bend_returning:
            if abs(previous) <= 1.0:
                self._pitch_bend_offset_hz = 0.0
                self._stop_pitch_bend()
            else:
                self._pitch_bend_offset_hz = previous - math.copysign(1.0, previous)
        else:
            candidate = previous + float(self._pitch_bend_direction)
            base = float(self._tuning_reference)
            self._pitch_bend_offset_hz = max(415.0 - base, min(466.0 - base, candidate))
            if math.isclose(self._pitch_bend_offset_hz, previous, abs_tol=1e-9):
                return
        if not math.isclose(previous, self._pitch_bend_offset_hz, abs_tol=1e-9):
            self._publish_pitch_bend()

    @Slot(int)
    def beginPitchBend(self, direction: int) -> None:
        if self._midi_control_blocks({"screen": "omni", "kind": "tuning_reference"}):
            self._stop_pitch_bend()
            self._pitch_bend_offset_hz = 0.0
            return
        direction = 1 if int(direction) > 0 else -1
        self._pitch_bend_direction = direction
        self._pitch_bend_returning = False
        if not self._pitch_bend_timer.isActive():
            self._pitch_bend_timer.start()

    @Slot()
    def endPitchBend(self) -> None:
        if self._midi_control_blocks({"screen": "omni", "kind": "tuning_reference"}):
            self._stop_pitch_bend()
            self._pitch_bend_offset_hz = 0.0
            return
        self._pitch_bend_direction = 0
        if math.isclose(self._pitch_bend_offset_hz, 0.0, abs_tol=1e-9):
            self._stop_pitch_bend()
            return
        self._pitch_bend_returning = True
        if not self._pitch_bend_timer.isActive():
            self._pitch_bend_timer.start()

    @Slot(int)
    def setTuningReference(self, value: int) -> None:
        if self._midi_control_blocks({"screen": "omni", "kind": "tuning_reference"}):
            return
        clamped = max(415, min(466, int(value)))
        self._stop_pitch_bend()
        self._pitch_bend_offset_hz = 0.0

        if clamped == self._tuning_reference:
            self.tuningChanged.emit()
            return

        self._tuning_reference = clamped
        self.tuningChanged.emit()
        self._refresh_tuning_on_active_notes()

    def _preset_path(self, preset_number: int) -> Path:
        return self._preset_dir / f"p{preset_number}.json"

    @staticmethod
    def _write_json_atomic(
        path: Path,
        data: dict[str, Any],
    ) -> None:
        JsonStore(path).write(data)

    def _preset_snapshot(self) -> dict[str, Any]:
        synth_roles: dict[str, Any] = {}

        for role in ("chord", "strum", "bass"):
            runtime = self._runtime(role)

            synth_roles[role] = {
                "selected": self._synths[runtime.selected_index].key,
                "parameters": runtime.sparse_overrides(),
            }

        rhythm_settings = {}

        for index, rhythm in enumerate(self._rhythms):
            rhythm_settings[rhythm.key] = {
                "tempo": (
                    self.rhythmTempo
                    if index == self._rhythm.selected_index
                    else self._rhythm.tempo_by_rhythm[index]
                ),
                "percussion_activity": (self._rhythm.busyness_by_rhythm[index]),
                "chord_activity": (self._rhythm.chord_activity_by_rhythm[index]),
                "bass_activity": (self._rhythm.bass_activity_by_rhythm[index]),
                "fill_order": list(self._rhythm.fill_order_by_rhythm[index]),
                "fill_density_bars": FILL_DENSITY_BARS[
                    self._rhythm.fill_density_index_by_rhythm[index]
                ],
            }

        snapshot: dict[str, Any] = {
            "version": 1,
            "strum_mode": "LDR" if self._strum_ladder_mode else "APG",
            "chord_rows": [
                {
                    "chord": self._chords[self._row_chord_indexes[row_index]].suffix,
                    "octave": OCTAVE_NAMES[self._row_octave_indexes[row_index]],
                    "inversion": (self._row_inversion_indexes[row_index]),
                }
                for row_index in range(ROW_COUNT)
            ],
            "synths": synth_roles,
            "volumes": {
                "chord": self._chord_volume,
                "strum": self._strum_volume,
                "bass": self._bass_volume,
                "percussion": (self._percussion_volume),
            },
            "transport": {
                "bass_running": (self._bass_running),
            },
            "rhythm": {
                "selected": (self._selected_rhythm().key),
                "settings": rhythm_settings,
            },
            "tuning": {
                "mode": TUNING_MODE_NAMES[self._tuning_mode_index],
                "reference_hz": (self._tuning_reference),
            },
        }
        snapshot["effects"] = {
            "reverb_level": self._reverb_level,
            "reverb_liveness": self._reverb_liveness,
            "reverb_damping": self._reverb_damping,
            "reverb_drums": self._reverb_drums,
        }
        return snapshot

    def _ensure_preset_storage(self) -> None:
        self._preset_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._archive_legacy_bootstrap_presets()

        factory_dir = INSTRUMENT_DIR / "default_presets"
        fallback = self._preset_snapshot()

        for preset_number in range(
            1,
            PRESET_COUNT + 1,
        ):
            path = self._preset_path(preset_number)

            # Never overwrite an existing user preset. A missing pN.json is
            # seeded from the corresponding factory pN.json.
            if path.exists():
                continue

            factory_path = factory_dir / f"p{preset_number}.json"

            if factory_path.exists():
                try:
                    factory_data = json.loads(factory_path.read_text(encoding="utf-8"))

                    if not isinstance(
                        factory_data,
                        dict,
                    ):
                        raise ValueError("factory preset is not an object")

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
                        f"Could not seed P{preset_number} from {factory_path}: {exc}",
                        file=sys.stderr,
                    )

            # Last-resort compatibility fallback if installation files are
            # incomplete.
            self._write_json_atomic(
                path,
                fallback,
            )

        last_path = self._preset_dir / LAST_PRESET_FILE

        if not last_path.exists():
            self._write_json_atomic(
                last_path,
                {"preset": 1},
            )

    def _archive_legacy_bootstrap_presets(self) -> Path | None:
        """Move the obsolete identical bootstrap bank out of the active bank.

        Early Qt builds created all eighteen user presets from one placeholder
        snapshot.  Its synth and rhythm identifiers predate the AMY catalog, so
        retaining that bank makes every preset button appear ineffective.  The
        deliberately narrow signature below avoids replacing user-edited banks.
        """
        paths = [self._preset_path(preset_number) for preset_number in range(1, PRESET_COUNT + 1)]

        if not all(path.is_file() for path in paths):
            return None

        try:
            presets = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
        except (OSError, ValueError, json.JSONDecodeError):
            return None

        first = presets[0]
        if not isinstance(first, dict) or any(preset != first for preset in presets[1:]):
            return None

        synths = first.get("synths")
        rhythm = first.get("rhythm")
        if not isinstance(synths, dict) or not isinstance(rhythm, dict):
            return None

        try:
            signature = (
                synths["chord"]["selected"],
                synths["strum"]["selected"],
                synths["bass"]["selected"],
                rhythm["selected"],
            )
        except (KeyError, TypeError):
            return None

        if signature != ("prophet", "pluck", "fm", "waltz"):
            return None

        archive_dir = self._preset_dir / ("legacy-presets-" + time.strftime("%Y%m%d-%H%M%S"))
        suffix = 1
        while archive_dir.exists():
            archive_dir = self._preset_dir / (
                "legacy-presets-" + time.strftime("%Y%m%d-%H%M%S") + f"-{suffix}"
            )
            suffix += 1

        archive_dir.mkdir()
        for path in paths:
            path.replace(archive_dir / path.name)

        print(
            f"Archived obsolete preset bank to {archive_dir}; installing current factory presets."
        )
        return archive_dir

    def _read_preset(
        self,
        preset_number: int,
    ) -> dict[str, Any]:
        path = self._preset_path(preset_number)

        data = json.loads(path.read_text(encoding="utf-8"))

        if not isinstance(data, dict):
            raise ValueError(f"{path} does not contain a JSON object")

        return data

    def _load_startup_preset(self) -> None:
        last_path = self._preset_dir / LAST_PRESET_FILE

        preset_number = 1

        try:
            last_data = json.loads(last_path.read_text(encoding="utf-8"))
            preset_number = int(last_data.get("preset", 1))
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
            data = self._read_preset(preset_number)
            self._apply_preset_data(data)
            self._preset_reference_data = copy.deepcopy(data)
            self._selected_preset = preset_number
        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            json.JSONDecodeError,
        ) as exc:
            print(
                f"Could not load startup preset P{preset_number}: {exc}",
                file=sys.stderr,
            )
            self._selected_preset = 1

    def _reset_presettable_state_to_defaults(self) -> None:
        """Restore every presettable field to application/catalogue defaults."""
        suffix_to_index = {chord.suffix: index for index, chord in enumerate(self._chords)}
        octave_to_index = {name: index for index, name in enumerate(OCTAVE_NAMES)}
        row_defaults = self._defaults["chord_rows"]
        self._row_chord_indexes = [suffix_to_index[str(row["chord"])] for row in row_defaults]
        self._row_octave_indexes = [octave_to_index[str(row["octave"])] for row in row_defaults]
        self._row_inversion_indexes = []
        for row_index, row in enumerate(row_defaults):
            chord_index = self._row_chord_indexes[row_index]
            inversion_count = len(self._chords[chord_index].inversions)
            self._row_inversion_indexes.append(int(row.get("inversion", 0)) % inversion_count)

        for role in ("chord", "strum", "bass"):
            self._runtime(role).reset_to_defaults()

        volumes = self._defaults["volumes"]
        self._chord_volume = max(0.0, min(1.0, float(volumes["chord"])))
        self._strum_volume = max(0.0, min(1.0, float(volumes["strum"])))
        self._bass_volume = max(0.0, min(1.0, float(volumes["bass"])))
        self._percussion_volume = max(0.0, min(1.0, float(volumes["percussion"])))

        effects = self._defaults.get("effects", {})
        self._reverb_level = max(
            0.0,
            min(REVERB_LEVEL_MAX, float(effects.get("reverb_level", 0.0))),
        )
        self._reverb_liveness = max(0.0, min(1.0, float(effects.get("reverb_liveness", 0.5))))
        self._reverb_damping = max(0.0, min(1.0, float(effects.get("reverb_damping", 0.5))))
        self._reverb_drums = bool(effects.get("reverb_drums", False))

        transport = self._defaults["transport"]
        self._rhythm_running = False
        self._running_tempo = None
        self._bass_running = bool(transport["bass_running"])

        rhythm_key_to_index = {rhythm.key: index for index, rhythm in enumerate(self._rhythms)}
        default_rhythm_key = str(self._defaults["rhythm"]["selected"])
        self._rhythm.selected_index = rhythm_key_to_index[default_rhythm_key]
        self._rhythm.tempo_by_rhythm = [rhythm.tempo_default for rhythm in self._rhythms]
        self._rhythm.busyness_by_rhythm = [
            max(1, min(5, rhythm.default_busyness + 1)) for rhythm in self._rhythms
        ]
        self._rhythm.chord_activity_by_rhythm = [
            source_activity_to_ui(rhythm.default_chord_activity) for rhythm in self._rhythms
        ]
        self._rhythm.bass_activity_by_rhythm = [
            source_activity_to_ui(rhythm.default_bass_activity) for rhythm in self._rhythms
        ]
        self._rhythm.fill_order_by_rhythm = [[] for _ in self._rhythms]
        self._rhythm.fill_density_index_by_rhythm = [0 for _ in self._rhythms]

        tuning = self._defaults.get("tuning", {})
        mode = str(tuning.get("mode", "EQ"))
        self._tuning_mode_index = (
            TUNING_MODE_NAMES.index(mode)
            if mode in TUNING_MODE_NAMES
            else DEFAULT_TUNING_MODE_INDEX
        )
        self._tuning_reference = max(
            415,
            min(466, int(tuning.get("reference_hz", DEFAULT_TUNING_REFERENCE))),
        )
        self._stop_pitch_bend()
        self._pitch_bend_offset_hz = 0.0
        self._stop_tempo_nudge()
        self._strum_ladder_mode = False

    def _capture_running_preset_state(self) -> RunningPresetState | None:
        """Snapshot the centrally declared live controls for preset recall."""
        if not self._rhythm_running:
            return None

        rhythm_index = self._rhythm.selected_index
        active_row_octave = (
            (self._active_row, self._row_octave_indexes[self._active_row])
            if 0 <= self._active_row < ROW_COUNT
            else None
        )
        return RunningPresetState(
            attributes={
                name: copy.deepcopy(getattr(self, name))
                for name in self.RUNNING_PRESET_PRESERVED_ATTRIBUTES
            },
            rhythm_controls=(
                self._rhythm.busyness_by_rhythm[rhythm_index],
                self._rhythm.chord_activity_by_rhythm[rhythm_index],
                self._rhythm.bass_activity_by_rhythm[rhythm_index],
                list(self._rhythm.fill_order_by_rhythm[rhythm_index]),
                self._rhythm.fill_density_index_by_rhythm[rhythm_index],
            ),
            active_row_octave=active_row_octave,
        )

    def _restore_running_preset_state(
        self,
        state: RunningPresetState | None,
    ) -> None:
        if state is None:
            return

        for name, value in state.attributes.items():
            setattr(self, name, value)

        rhythm_index = self._rhythm.selected_index
        (
            self._rhythm.busyness_by_rhythm[rhythm_index],
            self._rhythm.chord_activity_by_rhythm[rhythm_index],
            self._rhythm.bass_activity_by_rhythm[rhythm_index],
            self._rhythm.fill_order_by_rhythm[rhythm_index],
            self._rhythm.fill_density_index_by_rhythm[rhythm_index],
        ) = state.rhythm_controls
        if state.active_row_octave is not None:
            row_index, octave_index = state.active_row_octave
            self._row_octave_indexes[row_index] = octave_index

    def _apply_runtime_preset_data(self, data: dict[str, Any]) -> None:
        """Apply a user-selected preset under the live-performance policy."""
        live_state = self._capture_running_preset_state()
        try:
            self._apply_preset_data(data)
        finally:
            self._restore_running_preset_state(live_state)

    def _apply_preset_data(
        self,
        data: dict[str, Any],
    ) -> None:
        self._reset_presettable_state_to_defaults()
        plan = compile_omni_preset_plan(
            data,
            chord_suffixes=tuple(chord.suffix for chord in self._chords),
            chord_inversion_counts=tuple(len(chord.inversions) for chord in self._chords),
            octave_names=OCTAVE_NAMES,
            default_rows=tuple(
                ChordRowPreset(
                    self._row_chord_indexes[index],
                    self._row_octave_indexes[index],
                    self._row_inversion_indexes[index],
                )
                for index in range(ROW_COUNT)
            ),
            default_volumes=(
                self._chord_volume,
                self._strum_volume,
                self._bass_volume,
                self._percussion_volume,
            ),
            default_effects=EffectsPreset(
                self._reverb_level,
                self._reverb_liveness,
                self._reverb_damping,
                self._reverb_drums,
            ),
            default_bass_running=self._bass_running,
            rhythm_keys=tuple(rhythm.key for rhythm in self._rhythms),
            default_selected_rhythm_index=self._rhythm.selected_index,
            default_rhythm_settings=tuple(
                RhythmSettingPreset(
                    self._rhythm.tempo_by_rhythm[index],
                    self._rhythm.busyness_by_rhythm[index],
                    self._rhythm.chord_activity_by_rhythm[index],
                    self._rhythm.bass_activity_by_rhythm[index],
                    tuple(self._rhythm.fill_order_by_rhythm[index]),
                    self._rhythm.fill_density_index_by_rhythm[index],
                )
                for index in range(len(self._rhythms))
            ),
            fill_density_bars=FILL_DENSITY_BARS,
            tuning_modes=TUNING_MODE_NAMES,
            default_tuning_mode_index=self._tuning_mode_index,
            default_tuning_reference_hz=self._tuning_reference,
            reverb_level_max=REVERB_LEVEL_MAX,
        )
        self._strum_ladder_mode = plan.strum_ladder_mode
        for index, row in enumerate(plan.chord_rows):
            self._row_chord_indexes[index] = row.chord_index
            self._row_octave_indexes[index] = row.octave_index
            self._row_inversion_indexes[index] = row.inversion_index

        synth_data = data.get("synths", {})
        if isinstance(synth_data, dict):
            for role in ("chord", "strum", "bass"):
                role_data = synth_data.get(role, {})
                if isinstance(role_data, dict):
                    self._runtime(role).load_preset(role_data)

        (
            self._chord_volume,
            self._strum_volume,
            self._bass_volume,
            self._percussion_volume,
        ) = plan.volumes
        self._reverb_level = plan.effects.level
        self._reverb_liveness = plan.effects.liveness
        self._reverb_damping = plan.effects.damping
        self._reverb_drums = plan.effects.drums
        self._bass_running = plan.bass_running
        self._rhythm.selected_index = plan.selected_rhythm_index
        for index, setting in enumerate(plan.rhythm_settings):
            self._rhythm.tempo_by_rhythm[index] = setting.tempo
            self._rhythm.busyness_by_rhythm[index] = setting.percussion_activity
            self._rhythm.chord_activity_by_rhythm[index] = setting.chord_activity
            self._rhythm.bass_activity_by_rhythm[index] = setting.bass_activity
            self._rhythm.fill_order_by_rhythm[index] = list(setting.fill_order)
            self._rhythm.fill_density_index_by_rhythm[index] = setting.fill_density_index
        self._tuning_mode_index = plan.tuning_mode_index
        self._tuning_reference = int(plan.tuning_reference_hz)
        self._stop_pitch_bend()
        self._pitch_bend_offset_hz = 0.0
        self._stop_tempo_nudge()

        # The active chord and its touch lifecycle are live performance state,
        # not preset data.  Preserve their row/root identity so the destination
        # preset can change the sounding chord type without silencing it, and
        # so the matching button-up still releases a physically held chord.
        self._strum_last_index = None

    def _emit_full_preset_state(self) -> None:
        self._emit_state_changed()

        self.chordVolumeChanged.emit()
        self.strumVolumeChanged.emit()
        self.bassVolumeChanged.emit()
        self.percussionVolumeChanged.emit()
        self.reverbLevelChanged.emit()
        self.reverbLivenessChanged.emit()
        self.reverbDampingChanged.emit()
        self.reverbDrumsIncludedChanged.emit()
        self.strumModeChanged.emit()
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
            self._preset_dir / LAST_PRESET_FILE,
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
            data = self._read_preset(preset_number)
            self._apply_runtime_preset_data(data)
        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            json.JSONDecodeError,
        ) as exc:
            print(
                f"Could not load P{preset_number}: {exc}",
                file=sys.stderr,
            )
            return

        self._selected_preset = preset_number
        self._preset_reference_data = copy.deepcopy(data)
        self._write_last_preset()

        self._emit_full_preset_state()
        self.presetChanged.emit()

        # Runtime preset selection is always a live state transition.  The
        # startup/recovery reset path silences manual notes and clears chord
        # identity, which is incorrect even when rhythm transport is stopped.
        self._send_live_preset_state()

    @Slot()
    def storeSelectedPreset(self) -> None:
        snapshot = self._preset_snapshot()
        self._write_json_atomic(
            self._preset_path(self._selected_preset),
            snapshot,
        )
        self._preset_reference_data = copy.deepcopy(snapshot)
        self._write_last_preset()
        self.presetChanged.emit()
        self.presetStored.emit(self._selected_preset)

    def _preset_role_data(self, role: SynthRole) -> dict[str, Any]:
        synths = self._preset_reference_data.get("synths", {})
        if not isinstance(synths, dict):
            return {}
        value = synths.get(role, {})
        return value if isinstance(value, dict) else {}

    def _preset_volume_for_role(self, role: SynthRole) -> float:
        volumes = self._preset_reference_data.get("volumes", {})
        if not isinstance(volumes, dict):
            volumes = {}
        default = float(self._defaults["volumes"][role])
        return max(0.0, min(1.0, float(volumes.get(role, default))))

    def _reset_synth_role_to_preset(
        self,
        role: SynthRole,
        *,
        preserved_controls: dict[tuple[str, str], float] | None = None,
        preserved_volume: float | None = None,
    ) -> None:
        runtime = self._runtime(role)
        runtime.reset_selected_from_preset(self._preset_role_data(role))
        for (instrument, control), value in (preserved_controls or {}).items():
            runtime.set_instrument_control(instrument, control, value)
        volume = (
            self._preset_volume_for_role(role)
            if preserved_volume is None
            else max(0.0, min(1.0, float(preserved_volume)))
        )
        if role == "chord":
            self._chord_volume = volume
            self.chordVolumeChanged.emit()
            amp_address = self._chord_amp_address
        elif role == "strum":
            self._strum_volume = volume
            self.strumVolumeChanged.emit()
            amp_address = self._strum_amp_address
        else:
            self._bass_volume = volume
            self.bassVolumeChanged.emit()
            amp_address = self._bass_amp_address
        self._emit_synth_change(role, selection_changed=False)
        self._send_synth_state(role)
        self._client.send_message(amp_address, volume)

    @Slot()
    def resetBassToPreset(self) -> None:
        # Deliberately does not touch bass synth selection or bass on/off.
        self._reset_synth_role_to_preset("bass")

    @Slot()
    def resetStrumToPreset(self) -> None:
        self._reset_synth_role_to_preset("strum")

    @Slot()
    def resetChordSynthToPreset(self) -> None:
        self._reset_synth_role_to_preset("chord")

    @Slot()
    def resetChordRowsToPreset(self) -> None:
        rows = self._preset_reference_data.get("chord_rows", [])
        defaults = self._defaults["chord_rows"]
        if not isinstance(rows, list) or len(rows) != ROW_COUNT:
            rows = defaults
        suffix_to_index = {chord.suffix: i for i, chord in enumerate(self._chords)}
        octave_to_index = {name: i for i, name in enumerate(OCTAVE_NAMES)}
        for row_index in range(ROW_COUNT):
            stored = rows[row_index] if isinstance(rows[row_index], dict) else {}
            fallback = defaults[row_index]
            chord_key = str(stored.get("chord", fallback["chord"]))
            octave_key = str(stored.get("octave", fallback["octave"]))
            chord_index = suffix_to_index.get(chord_key, suffix_to_index[str(fallback["chord"])])
            octave_index = octave_to_index.get(octave_key, octave_to_index[str(fallback["octave"])])
            self._row_chord_indexes[row_index] = chord_index
            self._row_octave_indexes[row_index] = octave_index
            inversion_count = len(self._chords[chord_index].inversions)
            self._row_inversion_indexes[row_index] = (
                int(stored.get("inversion", fallback.get("inversion", 0))) % inversion_count
            )
        self._strum_last_index = None
        self._emit_state_changed()
        for row_index in range(ROW_COUNT):
            self._refresh_row_chord_notes(row_index)

    @Slot()
    def panic(self) -> None:
        # Stop and invalidate all performance state locally first.
        self._rhythm_running = False
        self._running_tempo = None
        self._bass_running = False
        self._pressed_chords.clear()
        self._pressed_chord_order.clear()
        self._promoted_chords.clear()
        self._chord_activity_hold_override = False

        self._active_row = -1
        self._active_root_semitone = -1
        self._strum_last_index = None

        # Dedicated panic packet silences AMY and forces the serial backend
        # to rebuild all five synth instances, so Panic is also a recovery
        # operation after any allocation/transport fault.
        self._client.send_message(
            self._panic_address,
            1,
        )

        # Redundant explicit state messages keep the UI and receiver state
        # converged after the hard AMY reset/rebuild.
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
        self._send_chord_state(play_now=False)

        self._emit_state_changed()
        self.rhythmStateChanged.emit()
        self.rhythmControlsChanged.emit()
        self.bassRunningChanged.emit()

    @Slot(int)
    def setRhythmIndex(self, rhythm_index: int) -> None:
        self._stop_tempo_nudge()
        if not 0 <= rhythm_index < len(self._rhythms):
            return
        if rhythm_index == self._rhythm.selected_index:
            return

        self._rhythm.selected_index = rhythm_index
        self.rhythmStateChanged.emit()
        self.rhythmControlsChanged.emit()
        self._send_rhythm_config()

    def _set_rhythm_tempo_value(self, value: float) -> bool:
        if self._midi_control_blocks({"screen": "omni", "kind": "rhythm_tempo"}):
            return False
        clamped = max(40.0, min(200.0, float(value)))
        index = self._rhythm.selected_index
        if abs(clamped - self._rhythm_tempo_value()) < 0.0001:
            return False
        self._rhythm.tempo_by_rhythm[index] = clamped
        if self._rhythm_running:
            self._running_tempo = clamped
        self.rhythmControlsChanged.emit()
        self._send_rhythm_config()
        return True

    def _stop_tempo_nudge(self) -> None:
        self._tempo_nudge_timer.stop()
        self._tempo_nudge_direction = 0
        self._tempo_nudge_pressed = False

    def _tempo_nudge_tick(self) -> None:
        current = self._rhythm_tempo_value()
        changed = self._set_rhythm_tempo_value(current + float(self._tempo_nudge_direction))
        moved = abs(self._rhythm_tempo_value() - self._tempo_nudge_origin)
        if (not changed) or (not self._tempo_nudge_pressed and moved >= 20.0 - 1e-9):
            self._stop_tempo_nudge()

    @Slot(int)
    def beginTempoNudge(self, direction: int) -> None:
        self._stop_tempo_nudge()
        if self._midi_control_blocks({"screen": "omni", "kind": "rhythm_tempo"}):
            return
        self._tempo_nudge_direction = 1 if int(direction) > 0 else -1
        self._tempo_nudge_origin = self._rhythm_tempo_value()
        self._tempo_nudge_pressed = True
        self._tempo_nudge_timer.start()

    @Slot()
    def endTempoNudge(self) -> None:
        if self._tempo_nudge_direction == 0:
            return
        self._tempo_nudge_pressed = False
        if abs(self._rhythm_tempo_value() - self._tempo_nudge_origin) >= 20.0 - 1e-9:
            self._stop_tempo_nudge()

    @Slot(float)
    def setRhythmTempo(self, value: float) -> None:
        self._stop_tempo_nudge()
        self._set_rhythm_tempo_value(value)

    @Slot(float)
    def setRhythmBusyness(self, value: float) -> None:
        level = max(1, min(5, int(round(float(value)))))
        index = self._rhythm.selected_index

        if level == self._rhythm.busyness_by_rhythm[index]:
            return

        self._rhythm.busyness_by_rhythm[index] = level
        self.rhythmControlsChanged.emit()
        self._send_rhythm_config()

    @Slot(int)
    def toggleRhythmFill(self, fill_index: int) -> None:
        fill_index = int(fill_index)
        if not 0 <= fill_index < 5:
            return
        rhythm_index = self._rhythm.selected_index
        order = list(self._rhythm.fill_order_by_rhythm[rhythm_index])
        if fill_index in order:
            order.remove(fill_index)
        else:
            # The most recently enabled fill is musically next. Existing
            # enabled fills retain their relative cycling order.
            order.insert(0, fill_index)
        self._rhythm.fill_order_by_rhythm[rhythm_index] = order
        self.rhythmControlsChanged.emit()
        self._send_rhythm_config()

    @Slot(float)
    def setRhythmFillDensity(self, value: float) -> None:
        if self._midi_control_blocks({"screen": "omni", "kind": "rhythm_fill_density"}):
            return
        density_index = max(
            0,
            min(
                len(FILL_DENSITY_BARS) - 1,
                int(round(float(value))),
            ),
        )
        rhythm_index = self._rhythm.selected_index
        if self._rhythm.fill_density_index_by_rhythm[rhythm_index] == density_index:
            return
        self._rhythm.fill_density_index_by_rhythm[rhythm_index] = density_index
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

        level = max(1, min(4, int(round(float(value)))))
        index = self._rhythm.selected_index

        if level == self._rhythm.chord_activity_by_rhythm[index]:
            return

        self._rhythm.chord_activity_by_rhythm[index] = level
        self.rhythmControlsChanged.emit()

        # Replace the automatic chord pattern immediately, including inside
        # the currently playing bar. CHORD ON/OFF owns the actual gate.
        self._send_rhythm_chord_enabled()
        self._send_rhythm_config()

    @Slot(float)
    def setRhythmBassActivity(self, value: float) -> None:
        level = max(1, min(5, int(round(float(value)))))
        index = self._rhythm.selected_index

        if level == self._rhythm.bass_activity_by_rhythm[index]:
            return

        self._rhythm.bass_activity_by_rhythm[index] = level
        self.rhythmControlsChanged.emit()
        self._send_rhythm_config()

    @Slot()
    def toggleRhythm(self) -> None:
        if not self._rhythm_running:
            self._running_tempo = self._rhythm.tempo_by_rhythm[self._rhythm.selected_index]
            self._rhythm_running = True
            self._send_rhythm_config()

            # Publish the accompaniment gate before starting AMY transport.
            # The AMY backend is still stopped at this point, so this updates
            # its state without triggering a second sequencer rebuild.
            self._send_rhythm_chord_enabled()
            self._client.send_message(
                self._rhythm_running_address,
                1,
            )
        else:
            # Stopping retains the effective live configuration in the UI.
            if self._running_tempo is not None:
                self._rhythm.tempo_by_rhythm[self._rhythm.selected_index] = self._running_tempo
            self._rhythm_running = False
            self._running_tempo = None
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

        chord = self._chords[self._row_chord_indexes[row_index]]
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
        return 0 <= row_index < ROW_COUNT and root_semitone in NOTE_NAMES_BY_SEMITONE

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
        enabled = self._effective_chord_activity() > 0

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
            root_semitone = key[1] if key is not None else self._active_root_semitone
            payload["notes"] = self._tuned_notes(
                notes,
                root_semitone,
            )

        if action == "start":
            payload["rhythm_running"] = bool(self._rhythm_running)

        self._debug(
            "osc_manual_chord",
            action=action,
            voice_id=payload.get("id"),
            notes=payload.get("notes"),
            packet_rhythm_running=(payload.get("rhythm_running")),
            **self._debug_chord_state(),
        )

        self._client.send_message(
            self._chord_manual_address,
            json.dumps(
                payload,
                separators=(",", ":"),
            ),
        )

    def _update_hold_override(self, *, publish: bool = True) -> None:
        should_override = bool(self._promoted_chords)

        self._debug(
            "hold_override_check",
            requested=should_override,
            **self._debug_chord_state(),
        )

        if should_override == self._chord_activity_hold_override:
            return

        old_value = self._chord_activity_hold_override
        self._chord_activity_hold_override = should_override

        self._debug(
            "hold_override_changed",
            old=old_value,
            new=should_override,
            **self._debug_chord_state(),
        )

        self.rhythmControlsChanged.emit()
        if publish:
            self._send_rhythm_chord_enabled()

    def _finalize_chord_release(
        self,
        key: tuple[int, int],
    ) -> None:
        if key not in self._pressed_chords:
            return

        row_index, root_semitone = key

        self._debug(
            "chord_release_finalized",
            row=row_index,
            root=root_semitone,
            **self._debug_chord_state(),
        )

        self._send_manual_chord(
            "stop",
            key=key,
        )

        self._pressed_chords.discard(key)
        self._promoted_chords.discard(key)

        try:
            self._pressed_chord_order.remove(key)
        except ValueError:
            pass

        if (
            self._active_row == row_index
            and self._active_root_semitone == root_semitone
            and self._pressed_chord_order
        ):
            next_row, next_root = self._pressed_chord_order[-1]
            self._set_active_chord(
                next_row,
                next_root,
            )
            self._send_chord_state(play_now=False)
            # The AMY backend intentionally uses one fixed manual-chord
            # synth.  If an older still-held chord becomes active again after
            # the newer chord is released, retrigger it on that synth.
            self._send_manual_chord(
                "start",
                key=(next_row, next_root),
                notes=self._current_notes(),
            )

        self._update_hold_override()

        self._debug(
            "releaseChord_exit",
            row=row_index,
            root=root_semitone,
            **self._debug_chord_state(),
        )

    def _release_all_pressed_chords(self) -> None:
        # stop_all is intentionally unconditional. It also clears a voice
        # left behind by a previous GUI run or an interrupted touch sequence.
        self._send_manual_chord("stop_all")
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

        # Every chord touch immediately selects the active chord used by the
        # manual synth, strum, bass and automatic chord lane. A quick tap may
        # therefore replace those lanes' pitches, but it never closes the
        # automatic chord lane or drains its note-on tags.
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
        key = (row_index, root_semitone)
        if key not in self._pressed_chords or key in self._promoted_chords:
            return

        # Qt/QML owns long-press recognition. Promotion performs only the
        # accompaniment takeover; the active chord and its replacement pitches
        # were already published on pointer-down.
        self._promoted_chords.add(key)
        self._debug(
            "chord_hold_promoted",
            row=row_index,
            root=root_semitone,
            **self._debug_chord_state(),
        )
        self._update_hold_override()

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

        # A real pointer-up owns the lifetime of manual synth 3. Stop it now,
        # independently of rhythm phase, then restore the automatic lane if
        # this contact had already been promoted to a hold.
        self._finalize_chord_release(key)

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

        chord = self._chords[self._row_chord_indexes[row_index]]
        inversion_index = self._row_inversion_indexes[row_index]
        octave_base = OCTAVE_BASES[self._row_octave_indexes[row_index]]
        root_midi = octave_base + root_semitone

        return [root_midi + interval for interval in chord.inversions[inversion_index]]

    def _current_notes(self) -> list[int]:
        if self._active_row < 0 or self._active_root_semitone < 0:
            return []

        return self._notes_for_chord(
            self._active_row,
            self._active_root_semitone,
        )

    def _current_bass_notes(self) -> list[int]:
        if self._active_row < 0 or self._active_root_semitone < 0:
            return []

        chord = self._chords[self._row_chord_indexes[self._active_row]]

        # One low-register octave of unique chord tones. The bass remains
        # rooted around octave 2 regardless of the selected chord octave.
        pitch_classes = sorted({interval % 12 for interval in chord.intervals})
        bass_root = 36 + self._active_root_semitone

        return [bass_root + pitch_class for pitch_class in pitch_classes]

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
            "rhythm_running": bool(self._rhythm_running),
            "rhythm_chord_enabled": bool(self._effective_chord_activity() > 0),
        }

        self._debug(
            "osc_chord_state",
            play_now=bool(play_now),
            notes=payload.get("notes"),
            bass_notes=payload.get("bass_notes"),
            packet_rhythm_running=(payload.get("rhythm_running")),
            **self._debug_chord_state(),
        )

        self._client.send_message(
            self._chord_state_address,
            json.dumps(payload, separators=(",", ":")),
        )

    def _arpeggio_notes(self) -> list[int]:
        if self._active_row < 0 or self._active_root_semitone < 0:
            return []

        chord = self._chords[self._row_chord_indexes[self._active_row]]

        # Convert the chord definition to pitch classes only. This deliberately
        # ignores both the row octave and the selected inversion.
        pitch_classes = {
            (self._active_root_semitone + interval) % 12 for interval in chord.intervals
        }

        return [
            midi_note
            for midi_note in range(
                STRUM_LOW_MIDI,
                STRUM_HIGH_MIDI + 1,
            )
            if midi_note % 12 in pitch_classes
        ]

    def _active_strum_pattern(
        self,
    ) -> tuple[ChordType, tuple[int, ...], tuple[int, ...]] | None:
        if self._active_row < 0 or self._active_root_semitone < 0:
            return None

        chord = self._chords[self._row_chord_indexes[self._active_row]]
        if self._strum_ladder_mode:
            intervals, degree_offsets = ladder_pattern(chord.suffix)
        else:
            intervals = chord.intervals
            degree_offsets = tuple(
                CHORD_DEGREE_BY_INTERVAL.get(
                    interval,
                    CHORD_DEGREE_BY_INTERVAL[interval % 12],
                )
                for interval in intervals
            )
        return chord, intervals, degree_offsets

    def _strum_note_names(self) -> list[str]:
        pattern = self._active_strum_pattern()
        if pattern is None:
            return []
        chord, intervals, degree_offsets = pattern
        return spell_strum_note_names(
            self._active_root_semitone,
            chord.suffix,
            intervals,
            degree_offsets,
        )

    def _ladder_notes(self) -> list[int]:
        if self._active_row < 0 or self._active_root_semitone < 0:
            return []
        chord = self._chords[self._row_chord_indexes[self._active_row]]
        intervals, _ = ladder_pattern(chord.suffix)
        pitch_classes = {(self._active_root_semitone + interval) % 12 for interval in intervals}
        return [
            note
            for note in range(STRUM_LOW_MIDI, STRUM_HIGH_MIDI + 1)
            if note % 12 in pitch_classes
        ]

    def _strum_notes(self) -> list[int]:
        return self._ladder_notes() if self._strum_ladder_mode else self._arpeggio_notes()

    def _strum_index(self, normalized_y: float) -> int | None:
        notes = self._strum_notes()

        if not notes:
            return None

        y = max(0.0, min(1.0, float(normalized_y)))
        return round((1.0 - y) * (len(notes) - 1))

    def _play_strum_index(self, index: int) -> None:
        notes = self._strum_notes()
        if not notes or index < 0 or index >= len(notes):
            return
        self._client.send_message(
            self._strum_note_address,
            self._tuned_note_text(
                notes[index],
                self._active_root_semitone,
            ),
        )

    @Slot(float)
    def strumTap(self, normalized_y: float) -> None:
        index = self._strum_index(normalized_y)
        if index is None:
            return
        self._play_strum_index(index)

    def _decode_strum_position(self, value: float) -> float:
        value = float(value)
        self._set_strum_ladder_mode(value >= 2.0)
        return value - 2.0 if self._strum_ladder_mode else value

    def _set_strum_ladder_mode(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == self._strum_ladder_mode:
            return
        self._strum_ladder_mode = enabled
        self.strumModeChanged.emit()
        self.strumNoteNamesChanged.emit()

    @Slot(bool)
    def setStrumLadderMode(self, enabled: bool) -> None:
        self._set_strum_ladder_mode(enabled)

    @Slot()
    def toggleStrumLadderMode(self) -> None:
        self._set_strum_ladder_mode(not self._strum_ladder_mode)

    @Slot(float)
    def strumStart(self, normalized_y: float) -> None:
        normalized_y = self._decode_strum_position(normalized_y)
        self._strum_last_index = self._strum_index(normalized_y)
        # Sound the note immediately on press.  The old touch path only
        # emitted a note after a move or release, which meant a perfectly
        # valid press could remain silent depending on QML touch delivery.
        if self._strum_last_index is not None:
            self._play_strum_index(self._strum_last_index)

    @Slot(float)
    def strumMove(self, normalized_y: float) -> None:
        normalized_y = self._decode_strum_position(normalized_y)
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
            self._play_strum_index(index)

        self._strum_last_index = new_index

    @Slot()
    def strumEnd(self) -> None:
        self._strum_last_index = None

    def _selected_synth(
        self,
        role: SynthRole,
    ) -> SynthDefinition:
        return self._runtime(role).selected_definition

    def _send_synth_state(self, role: SynthRole) -> None:
        if role == "chord":
            address = self._chord_synth_address
        elif role == "strum":
            address = self._strum_synth_address
        else:
            address = self._bass_synth_address
        self._client.send_message(
            address,
            self._runtime(role).transport_payload(),
        )

    def _rhythm_payload(self) -> dict[str, Any]:
        rhythm = self._selected_rhythm()
        index = self._rhythm.selected_index
        busyness = self._rhythm.busyness_by_rhythm[index]
        chord_activity = self._effective_chord_activity()
        bass_activity = self._rhythm.bass_activity_by_rhythm[index]

        chord_source = ui_activity_to_source(chord_activity) if chord_activity > 0 else None
        bass_source = ui_activity_to_source(bass_activity) if bass_activity <= 4 else None

        return {
            "id": rhythm.key,
            "label": rhythm.label,
            "meter": rhythm.meter,
            "length_beats": rhythm.length_beats,
            "tempo": self.rhythmTempo,
            "busyness": busyness,
            "chord_activity": chord_activity,
            "bass_activity": bass_activity,
            "percussion_activity": busyness,
            "fill_order": list(self._rhythm.fill_order_by_rhythm[index]),
            "fill_density_bars": FILL_DENSITY_BARS[
                self._rhythm.fill_density_index_by_rhythm[index]
            ],
            "chord_events": (
                [copy.deepcopy(event) for event in rhythm.chord_levels[chord_source]]
                if chord_source is not None
                else []
            ),
            "bass_events": (
                [copy.deepcopy(event) for event in rhythm.bass_levels[bass_source]]
                if bass_source is not None
                else []
            ),
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

    def _send_live_preset_state(self) -> None:
        """Apply preset configuration without touching live rhythm transport."""
        self._client.send_message(self._chord_amp_address, self._chord_volume)
        self._client.send_message(self._strum_amp_address, self._strum_volume)
        self._client.send_message(self._bass_amp_address, self._bass_volume)
        self._client.send_message(
            self._percussion_amp_address,
            self._percussion_volume,
        )
        self._send_reverb_state()
        self._send_synth_state("chord")
        self._send_synth_state("strum")
        self._send_synth_state("bass")
        self._send_master_volume()
        self._send_rhythm_config()
        self._client.send_message(
            self._bass_running_address,
            1 if self._bass_running else 0,
        )
        self._send_rhythm_chord_enabled()
        if self._active_row >= 0 and self._active_root_semitone >= 0:
            self._send_chord_state(play_now=False)
            active_key = (self._active_row, self._active_root_semitone)
            if active_key in self._pressed_chords:
                self._send_manual_chord(
                    "update",
                    key=active_key,
                    notes=self._current_notes(),
                )

    def send_initial_state(self) -> None:
        self._debug(
            "send_initial_state_enter",
            **self._debug_chord_state(),
        )

        # Hard-quiesce the receiver during startup/recovery before replacing
        # complete instrument state. Live preset changes deliberately use
        # _send_live_preset_state() and never enter this transport-reset path.
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
        self._pressed_chords.clear()
        self._pressed_chord_order.clear()
        self._promoted_chords.clear()
        self._chord_activity_hold_override = False
        self._send_chord_state(play_now=False)

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
        self._send_reverb_state()

        self._send_synth_state("chord")
        self._send_synth_state("strum")
        self._send_synth_state("bass")
        self._send_master_volume()
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


def parse_arguments(
    arguments: Sequence[str] | None = None,
    *,
    default_config_path: Path | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Qt Quick Omnichord using native AMY commands over serial")
    )
    parser.add_argument(
        "--amy-config",
        type=Path,
        default=default_config_path or CONFIG_DIR / "amy_config.json",
        help="AMY serial/backend JSON configuration file.",
    )
    parser.add_argument(
        "--serial-port",
        default=None,
        help="Override serial.port from amy_config.json (for example /dev/serial0).",
    )
    parser.add_argument(
        "--serial-baud",
        type=int,
        default=None,
        help="Override serial.baud from amy_config.json.",
    )
    parser.add_argument(
        "--local-amy",
        action="store_const",
        const=str(Path.home() / ".omnichord" / "amy.sock"),
        dest="amy_socket",
        help=("Connect to the external AMY service at ~/.omnichord/amy.sock."),
    )
    parser.add_argument(
        "--amy-socket",
        default=None,
        help=(
            "Connect to an external AMY local socket "
            "(packet or LF-framed stream, depending on the platform)."
        ),
    )
    parser.add_argument(
        "--amy-local-name",
        default=None,
        help=(
            "Connect to an external AMY service through Qt local IPC "
            "(a named pipe in the native Windows package)."
        ),
    )
    parser.add_argument(
        "--capture-screenshots-dir",
        type=Path,
        default=None,
        help=(
            "Render current OMNI and MIDI screens into this directory, "
            "then exit. Intended for the repository screenshot helper."
        ),
    )

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
        help=("Request the OpenGL Qt Quick RHI backend explicitly."),
    )

    platform_group = parser.add_mutually_exclusive_group()
    platform_group.add_argument(
        "--x11",
        action="store_true",
        help=("Run through XWayland/XCB instead of native Wayland (diagnostic option)."),
    )
    platform_group.add_argument(
        "--wayland",
        action="store_true",
        help=("Force the native Wayland Qt platform plugin (diagnostic option)."),
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
        "--reverb-address",
        default="/effects/reverb",
    )
    parser.add_argument(
        "--master-volume-address",
        default="/master/volume",
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
            "Log detailed chord-touch and backend state transitions to ~/.omnichord/debug-*.jsonl"
        ),
    )
    parser.add_argument(
        "--debug-file",
        type=Path,
        default=None,
        help=("Write debug JSONL to this path; implies --debug."),
    )
    parser.add_argument(
        "--slider-trace",
        action="store_true",
        help=("Print QML slider press/move/current-value diagnostics to stderr."),
    )
    return parser.parse_args(arguments)


def run_application(
    args: argparse.Namespace,
    dependencies: ApplicationDependencies,
) -> int:
    migrate_user_layout()
    user_config_dir = ensure_user_configs(dependencies.paths.config)

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

    def synth_fallback_notice(role: str, requested: str, fallback: str) -> None:
        print(
            f"Warning: unknown {role} synth {requested!r} in defaults.json; using {fallback!r}",
            file=sys.stderr,
            flush=True,
        )

    resources = load_application_resources(
        dependencies,
        user_config_dir=user_config_dir,
        synth_fallback_notice=synth_fallback_notice,
    )
    defaults = resources.defaults
    chords = resources.chords
    synths = resources.synths
    rhythms = resources.rhythms
    title_config = resources.title

    QQuickStyle.setStyle("Basic")

    app = QGuiApplication(sys.argv)
    app.setApplicationName("Qt Omnichord")

    runtime = dependencies.resolve_package_runtime(
        platform_name=QGuiApplication.platformName(),
        private_files_dir=dependencies.private_files_dir(),
        amy_socket=args.amy_socket,
        amy_local_name=args.amy_local_name,
    )
    args.amy_socket = runtime.amy_socket
    args.amy_local_name = runtime.amy_local_name

    for diagnostic in dependencies.display_diagnostics(QGuiApplication.platformName()):
        print(diagnostic, file=sys.stderr, flush=True)

    def transport_notice(
        selection: ClientSelection,
        resolved: ResolvedAmyConfig,
    ) -> None:
        if selection.kind == "local":
            message = f"AMY backend: Qt local IPC {selection.endpoint}"
        elif selection.kind == "socket":
            message = f"AMY backend: external socket {selection.endpoint}"
        else:
            message = (
                "AMY serial backend: "
                f"{resolved.transport.serial_port} @ "
                f"{resolved.transport.serial_baud} baud"
            )
        print(message, file=sys.stderr, flush=True)

    graph = compose_application_graph(
        args,
        dependencies,
        resources,
        user_config_dir=user_config_dir,
        transport_notice=transport_notice,
    )
    amy_client = graph.client
    backend = graph.backend

    engine = QQmlApplicationEngine()
    context = engine.rootContext()

    context.setContextProperty("backend", backend)
    context.setContextProperty(
        "sliderTrace",
        bool(args.slider_trace) or os.environ.get("OMNICHORD_SLIDER_TRACE") == "1",
    )
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
    start_fullscreen = bool(window_defaults.get("start_fullscreen", False))
    if args.fullscreen:
        start_fullscreen = True
    elif args.windowed:
        start_fullscreen = False

    scale_to_fit = bool(window_defaults.get("scale_to_fit", True)) and not args.no_scale_to_fit

    context.setContextProperty(
        "startFullscreen",
        start_fullscreen,
    )
    context.setContextProperty(
        "scaleToFit",
        scale_to_fit,
    )

    engine.load(QUrl.fromLocalFile(str(dependencies.paths.gui / "Main.qml")))

    if not engine.rootObjects():
        amy_client.close()
        return 1

    backend.send_initial_state()

    if args.capture_screenshots_dir is not None:
        capture_dir = args.capture_screenshots_dir.expanduser().resolve()
        capture_dir.mkdir(parents=True, exist_ok=True)
        window = cast(QQuickWindow, engine.rootObjects()[0])

        # Stage representative controls through the normal input-processing
        # paths. The resulting bar contains MIDI and OSC rotaries and buttons.
        populate_screenshot_input_controls(backend.midiPlayer, backend.midiPlayer)
        # Select C minor from factory preset 1 so the OMNI capture also
        # demonstrates the active chord and its correctly spelled C/E-flat/G
        # strum-note guide.
        backend.pressChord(0, 0)

        def capture_screen(name: str) -> bool:
            image = window.grabWindow()
            path = capture_dir / f"{name}.png"
            if image.isNull() or not image.save(str(path), b"PNG"):
                print(
                    f"Could not capture Qt screen to {path}",
                    file=sys.stderr,
                    flush=True,
                )
                return False
            print(f"Captured {path}", file=sys.stderr, flush=True)
            return True

        def capture_omni() -> None:
            window.setProperty("midiScreen", False)
            if not capture_screen("omni"):
                app.exit(3)
                return
            backend.releaseChord(0, 0)
            window.setProperty("midiScreen", True)
            # Allow MidiScreen's visible-state timer to publish the injected
            # CC model before grabbing the second frame.
            QTimer.singleShot(750, capture_midi)

        def capture_midi() -> None:
            if not capture_screen("midi"):
                app.exit(3)
                return
            app.quit()

        # Give the software scene graph a complete frame before the first
        # grab. This works with QT_QPA_PLATFORM=offscreen as used by the helper.
        QTimer.singleShot(1500, capture_omni)

    # Make teardown order explicit. QML must be destroyed while the Python
    # backend QObject is still alive; otherwise its context property becomes
    # null and dozens of bindings log TypeErrors during application shutdown.
    exit_code = app.exec()

    # Destroy the QML engine/root objects first.
    del engine

    # QML can no longer generate performance messages, so stop AMY and close
    # the UART before releasing the backend object that owns the client.
    amy_client.close()

    return exit_code
