from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field


MIN_TUNING_REFERENCE_HZ = 415.0
MAX_TUNING_REFERENCE_HZ = 466.0
EQUAL_TEMPERAMENT_REFERENCE_HZ = 440.0

IntonationMatrix = tuple[tuple[float, ...], ...]


@dataclass(frozen=True, slots=True)
class TuningSnapshot:
    mode: str
    reference_hz: float
    bend_offset_hz: float = 0.0
    intonation_tables: tuple[tuple[str, IntonationMatrix], ...] = ()

    @property
    def effective_reference_hz(self) -> float:
        return max(
            MIN_TUNING_REFERENCE_HZ,
            min(MAX_TUNING_REFERENCE_HZ, self.reference_hz + self.bend_offset_hz),
        )

    def table(self) -> IntonationMatrix | None:
        return next(
            (matrix for name, matrix in self.intonation_tables if name == self.mode),
            None,
        )


@dataclass(frozen=True, slots=True)
class ChordSnapshot:
    active: bool
    row: int
    root_semitone: int
    suffix: str
    intervals: tuple[int, ...]

    @property
    def pitch_classes(self) -> frozenset[int]:
        return frozenset((self.root_semitone + interval) % 12 for interval in self.intervals)


@dataclass(frozen=True, slots=True)
class PerformanceStateSnapshot:
    chord_gate_state: int = 0
    bass_voicing_shift: int = 0
    chord_arpeggio_enabled: bool = False
    chord_arpeggio_rate: int = 1
    chord_arpeggio_descending: bool = False
    bass_notes: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class OmniPerformanceSnapshot:
    tuning: TuningSnapshot
    chord: ChordSnapshot
    performance: PerformanceStateSnapshot = field(default_factory=PerformanceStateSnapshot)


def freeze_intonation_tables(
    tables: Mapping[str, Sequence[Sequence[float]]],
) -> tuple[tuple[str, IntonationMatrix], ...]:
    return tuple(
        (
            str(name),
            tuple(tuple(float(value) for value in row) for row in matrix),
        )
        for name, matrix in sorted(tables.items())
    )


def tuning_note_offset(snapshot: TuningSnapshot) -> float:
    return 12.0 * math.log2(snapshot.effective_reference_hz / EQUAL_TEMPERAMENT_REFERENCE_HZ)


def intonation_factor(
    snapshot: TuningSnapshot,
    root_semitone: int | None,
    note: int | float,
) -> float:
    matrix = snapshot.table()
    if matrix is None or root_semitone is None:
        return 1.0
    root_pc = int(root_semitone) % 12
    note_pc = int(math.floor(float(note) + 0.5)) % 12
    return float(matrix[root_pc][note_pc])


def tune_note(
    snapshot: TuningSnapshot,
    note: int | float,
    root_semitone: int | None = None,
) -> float:
    return (
        float(note)
        + tuning_note_offset(snapshot)
        + 12.0 * math.log2(intonation_factor(snapshot, root_semitone, note))
    )


def chord_snapshot(
    *,
    active_row: int,
    active_root_semitone: int,
    row_chord_indexes: Sequence[int],
    suffixes: Sequence[str],
    intervals: Sequence[Sequence[int]],
) -> ChordSnapshot:
    if active_row < 0 or active_root_semitone < 0 or active_row >= len(row_chord_indexes):
        return ChordSnapshot(False, -1, 0, "", (0, 4, 7))
    chord_index = int(row_chord_indexes[active_row])
    if chord_index < 0 or chord_index >= len(intervals):
        return ChordSnapshot(False, -1, 0, "", (0, 4, 7))
    suffix = str(suffixes[chord_index]) if chord_index < len(suffixes) else ""
    return ChordSnapshot(
        True,
        int(active_row),
        int(active_root_semitone),
        suffix,
        tuple(int(value) for value in intervals[chord_index]),
    )
