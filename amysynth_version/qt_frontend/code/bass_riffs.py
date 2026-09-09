from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from catalog_schema import read_versioned_catalog

BASS_RIFF_RANK_MIN = 1
BASS_RIFF_RANK_MAX = 5


def clamp_bass_riff_rank(value: int | float) -> int:
    return max(BASS_RIFF_RANK_MIN, min(BASS_RIFF_RANK_MAX, int(round(value))))


@dataclass(frozen=True)
class BassRiffEvent:
    tick: int
    duration_ticks: int
    pitch_offset: int
    velocity: int
    accent: bool
    slide_to_next: bool


@dataclass(frozen=True)
class BassRiffDefinition:
    index: int
    riff_id: str
    name: str
    normalized_anchor_midi: int
    compatible_chords: tuple[str, ...]
    compatible_rhythms: tuple[str, ...]
    activity_rank: int
    selection_weight: int
    ppq: int
    phrase_ticks: int
    events: tuple[BassRiffEvent, ...]


class BassRiffCatalog:
    """Validated, stable riff catalogue indexed by rhythm and chord suffix."""

    def __init__(self, riffs: Collection[BassRiffDefinition]) -> None:
        self.riffs = tuple(sorted(riffs, key=lambda riff: riff.index))
        self._by_id = MappingProxyType(
            {riff.riff_id: riff for riff in self.riffs}
        )
        by_context: dict[tuple[str, str], list[BassRiffDefinition]] = {}
        for riff in self.riffs:
            for rhythm_id in riff.compatible_rhythms:
                for chord_suffix in riff.compatible_chords:
                    by_context.setdefault(
                        (rhythm_id, chord_suffix), []
                    ).append(riff)
        self._by_context = MappingProxyType(
            {
                context: tuple(
                    sorted(
                        values,
                        key=lambda riff: (
                            riff.activity_rank,
                            -riff.selection_weight,
                            riff.index,
                        ),
                    )
                )
                for context, values in by_context.items()
            }
        )

    def candidates(
        self,
        rhythm_id: str,
        chord_suffix: str,
    ) -> tuple[BassRiffDefinition, ...]:
        return self._by_context.get((rhythm_id, chord_suffix), ())

    def candidates_at_rank(
        self,
        rhythm_id: str,
        chord_suffix: str,
        activity_rank: int,
    ) -> tuple[BassRiffDefinition, ...]:
        """Return deterministic candidates for one visible activity rank."""

        rank = clamp_bass_riff_rank(activity_rank)
        return tuple(
            riff
            for riff in self.candidates(rhythm_id, chord_suffix)
            if riff.activity_rank == rank
        )

    def choose(
        self,
        rhythm_id: str,
        chord_suffix: str,
        activity_rank: int,
        *,
        preserve_riff_id: str | None = None,
    ) -> BassRiffDefinition | None:
        """Choose within a rank, retaining identity when still compatible."""

        candidates = self.candidates_at_rank(
            rhythm_id,
            chord_suffix,
            activity_rank,
        )
        if preserve_riff_id:
            preserved = next(
                (
                    riff
                    for riff in candidates
                    if riff.riff_id == preserve_riff_id
                ),
                None,
            )
            if preserved is not None:
                return preserved
        return candidates[0] if candidates else None

    def by_id(self, riff_id: str | None) -> BassRiffDefinition | None:
        if not riff_id:
            return None
        return self._by_id.get(str(riff_id))


def _required_list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"bass riff field {field!r} must be a non-empty list")
    return value


def _required_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"bass riff field {field!r} must be an integer")
    return value


def _validate_declared_references(
    raw: Any,
    known_rhythms: set[str],
    known_chords: set[str],
) -> set[str]:
    known_scales = {
        str(row["id"])
        for row in _required_list(raw.get("scale_vocabulary"), "scale_vocabulary")
        if isinstance(row, dict) and row.get("id")
    }
    declared_rhythms = {
        str(row["id"])
        for row in _required_list(raw.get("rhythm_types"), "rhythm_types")
        if isinstance(row, dict) and row.get("id")
    }
    declared_chords = {
        str(row["id"])
        for row in _required_list(raw.get("chord_types"), "chord_types")
        if isinstance(row, dict) and row.get("id")
    }
    if declared_rhythms != known_rhythms:
        raise ValueError("bass riff rhythm IDs do not match rhythms.json")
    if declared_chords != known_chords:
        raise ValueError("bass riff chord IDs do not match chords.csv")
    return known_scales


def _validate_context_coverage(
    catalog: BassRiffCatalog,
    known_rhythms: set[str],
    known_chords: set[str],
) -> None:
    missing = [
        (rhythm_id, chord_suffix, ranks)
        for rhythm_id in sorted(known_rhythms)
        for chord_suffix in sorted(known_chords)
        if (
            ranks := {
                riff.activity_rank
                for riff in catalog.candidates(rhythm_id, chord_suffix)
            }
        )
        != set(range(BASS_RIFF_RANK_MIN, BASS_RIFF_RANK_MAX + 1))
    ]
    if missing:
        raise ValueError(
            "bass riff catalogue does not provide ranks 1..5 for "
            f"{missing[0][0]!r}/{missing[0][1]!r}; got {sorted(missing[0][2])}"
        )


def load_bass_riff_catalog(
    path: Path,
    *,
    rhythm_ids: Collection[str],
    chord_suffixes: Collection[str],
) -> BassRiffCatalog:
    raw = read_versioned_catalog(
        path,
        "bass_riffs_v1.schema.json",
        schema_directory=path.parent / "schema",
    )

    known_rhythms = {str(value) for value in rhythm_ids}
    known_chords = {str(value) for value in chord_suffixes}
    if not known_rhythms or not known_chords:
        raise ValueError("bass riff catalogue requires rhythm and chord IDs")

    known_scales = _validate_declared_references(
        raw,
        known_rhythms,
        known_chords,
    )

    riffs: list[BassRiffDefinition] = []
    indexes: set[int] = set()
    riff_ids: set[str] = set()
    for row in _required_list(raw.get("riffs"), "riffs"):
        if not isinstance(row, dict):
            raise ValueError("every bass riff must be an object")
        index = _required_int(row.get("index"), "index")
        riff_id = str(row.get("riff_id", ""))
        if index <= 0 or index in indexes:
            raise ValueError(f"duplicate or invalid bass riff index {index}")
        if not riff_id or riff_id in riff_ids:
            raise ValueError(f"duplicate or empty bass riff ID {riff_id!r}")
        indexes.add(index)
        riff_ids.add(riff_id)

        if row.get("normalized_root") != "C":
            raise ValueError(f"bass riff {riff_id!r} is not normalized to C")
        anchor = _required_int(
            row.get("normalized_anchor_midi"), "normalized_anchor_midi"
        )
        if anchor != 36:
            raise ValueError(f"bass riff {riff_id!r} is not anchored at C2")
        activity_rank = _required_int(row.get("activity_rank"), "activity_rank")
        if not BASS_RIFF_RANK_MIN <= activity_rank <= BASS_RIFF_RANK_MAX:
            raise ValueError(f"bass riff {riff_id!r} has invalid activity rank")
        selection_weight = _required_int(
            row.get("selection_weight"), "selection_weight"
        )
        if selection_weight <= 0:
            raise ValueError(f"bass riff {riff_id!r} has invalid selection weight")

        compatible_rhythms = tuple(
            str(value)
            for value in _required_list(
                row.get("compatible_rhythms"), "compatible_rhythms"
            )
        )
        compatible_chords = tuple(
            str(value)
            for value in _required_list(
                row.get("compatible_chords"), "compatible_chords"
            )
        )
        compatible_scales = {
            str(value)
            for value in _required_list(
                row.get("compatible_scales"), "compatible_scales"
            )
        }
        unknown_rhythms = set(compatible_rhythms) - known_rhythms
        unknown_chords = set(compatible_chords) - known_chords
        unknown_scales = compatible_scales - known_scales
        if unknown_rhythms:
            raise ValueError(
                f"bass riff {riff_id!r} has unknown rhythms {sorted(unknown_rhythms)}"
            )
        if unknown_chords:
            raise ValueError(
                f"bass riff {riff_id!r} has unknown chords {sorted(unknown_chords)}"
            )
        if unknown_scales:
            raise ValueError(
                f"bass riff {riff_id!r} has unknown scales {sorted(unknown_scales)}"
            )

        timing = row.get("timing")
        if not isinstance(timing, dict):
            raise ValueError(f"bass riff {riff_id!r} has no timing object")
        ppq = _required_int(timing.get("ppq"), "timing.ppq")
        phrase_ticks = _required_int(
            timing.get("phrase_ticks"), "timing.phrase_ticks"
        )
        if ppq <= 0 or phrase_ticks <= 0:
            raise ValueError(f"bass riff {riff_id!r} has invalid timing")

        events: list[BassRiffEvent] = []
        previous_tick = -1
        for event in _required_list(timing.get("events"), "timing.events"):
            if not isinstance(event, dict):
                raise ValueError(f"bass riff {riff_id!r} has a non-object event")
            tick = _required_int(event.get("tick"), "event.tick")
            duration = _required_int(
                event.get("duration_ticks"), "event.duration_ticks"
            )
            pitch_offset = _required_int(
                event.get("pitch_offset_semitones_from_C2"),
                "event.pitch_offset_semitones_from_C2",
            )
            velocity = _required_int(event.get("velocity"), "event.velocity")
            accent = event.get("accent")
            slide_to_next = event.get("slide_to_next")
            if tick < 0 or tick >= phrase_ticks or tick < previous_tick:
                raise ValueError(f"bass riff {riff_id!r} has an invalid event tick")
            if duration <= 0:
                raise ValueError(f"bass riff {riff_id!r} has a non-positive duration")
            if not 0 <= velocity <= 127:
                raise ValueError(f"bass riff {riff_id!r} has an invalid velocity")
            if not isinstance(accent, bool):
                raise ValueError(f"bass riff {riff_id!r} has an invalid accent flag")
            if not isinstance(slide_to_next, bool):
                raise ValueError(
                    f"bass riff {riff_id!r} has an invalid slide_to_next flag"
                )
            previous_tick = tick
            events.append(
                BassRiffEvent(
                    tick=tick,
                    duration_ticks=duration,
                    pitch_offset=pitch_offset,
                    velocity=velocity,
                    accent=accent,
                    slide_to_next=slide_to_next,
                )
            )

        riffs.append(
            BassRiffDefinition(
                index=index,
                riff_id=riff_id,
                name=str(row.get("name", riff_id)),
                normalized_anchor_midi=anchor,
                compatible_chords=compatible_chords,
                compatible_rhythms=compatible_rhythms,
                activity_rank=activity_rank,
                selection_weight=selection_weight,
                ppq=ppq,
                phrase_ticks=phrase_ticks,
                events=tuple(events),
            )
        )

    catalog = BassRiffCatalog(riffs)
    _validate_context_coverage(catalog, known_rhythms, known_chords)
    return catalog


def transpose_riff_events(
    riff: BassRiffDefinition,
    root_semitone: int,
) -> tuple[dict[str, int | bool], ...]:
    root = int(root_semitone) % 12
    return tuple(
        {
            "tick": event.tick,
            "duration_ticks": event.duration_ticks,
            "note": riff.normalized_anchor_midi + event.pitch_offset + root,
            "velocity": event.velocity,
            "accent": event.accent,
            "slide_to_next": event.slide_to_next,
        }
        for event in riff.events
    )
