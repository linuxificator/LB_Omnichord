from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast


@dataclass(frozen=True, slots=True)
class ScDrumEvent:
    tick: int
    role: str
    slot: str
    velocity: int
    semantic_roles: frozenset[str]
    max_duration_ms: int

    @property
    def gate_key(self) -> str:
        return f"{self.role}/{self.slot}"


@dataclass(frozen=True, slots=True)
class ScDrumArrangement:
    kit_id: str
    rhythm_id: str
    meter: str
    period_ticks: int
    levels: tuple[tuple[ScDrumEvent, ...], ...]


@dataclass(frozen=True, slots=True)
class ScDrumFill:
    variant_id: str
    base_fill_id: str
    kit_id: str
    rhythm_id: str
    slot_level: int
    duration_ticks: int
    allowed_start_beats: tuple[int, ...]
    events: tuple[ScDrumEvent, ...]
    gain: float
    continuation_keys: frozenset[str]
    continuation_levels: tuple[tuple[ScDrumEvent, ...], ...]


class ScMusicCatalog:
    def __init__(
        self,
        arrangements: list[ScDrumArrangement],
        fills: list[ScDrumFill],
        *,
        ppq: int,
        digest: str,
    ) -> None:
        self.ppq = int(ppq)
        self.digest = str(digest)
        self._arrangements = MappingProxyType(
            {(item.kit_id, item.rhythm_id): item for item in arrangements}
        )
        grouped: dict[tuple[str, str], list[ScDrumFill]] = {}
        for fill in fills:
            grouped.setdefault((fill.kit_id, fill.rhythm_id), []).append(fill)
        self._fills = MappingProxyType(
            {
                key: tuple(sorted(values, key=lambda item: item.slot_level))
                for key, values in grouped.items()
            }
        )
        if len(self._arrangements) != len(arrangements):
            raise ValueError("SC music catalogue contains duplicate arrangements")
        if any(len(values) != 5 for values in self._fills.values()):
            raise ValueError("SC music catalogue requires five fills per kit/rhythm")
        if set(self._arrangements) != set(self._fills):
            raise ValueError("SC arrangement and fill coverage differ")

    def arrangement(self, kit_id: str, rhythm_id: str) -> ScDrumArrangement:
        key = (str(kit_id), str(rhythm_id))
        try:
            return self._arrangements[key]
        except KeyError as exc:
            raise ValueError(f"unknown SC kit/rhythm arrangement {key!r}") from exc

    def fills(self, kit_id: str, rhythm_id: str) -> tuple[ScDrumFill, ...]:
        key = (str(kit_id), str(rhythm_id))
        try:
            return self._fills[key]
        except KeyError as exc:
            raise ValueError(f"unknown SC kit/rhythm fills {key!r}") from exc

    @property
    def roles(self) -> frozenset[str]:
        """Return the complete semantic role vocabulary used by this catalog."""

        arrangement_roles = {
            event.role
            for arrangement in self._arrangements.values()
            for level in arrangement.levels
            for event in level
        }
        fill_roles = {
            event.role
            for fills in self._fills.values()
            for fill in fills
            for event in fill.events
        }
        return frozenset(arrangement_roles | fill_roles)


def _require_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def load_sc_music_catalog(path: Path) -> ScMusicCatalog:
    raw_bytes = path.read_bytes()
    raw = json.loads(raw_bytes)
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("unsupported SC kit-groove catalogue")
    ppq = _require_int(raw.get("ppq"), "ppq")
    if ppq != 96:
        raise ValueError("SC kit-groove catalogue must use 96 PPQ")
    roles_raw = raw.get("roles")
    slots_raw = raw.get("slots")
    semantic_sets_raw = raw.get("semantic_role_sets")
    sequences_raw = raw.get("event_sequences")
    if not all(
        isinstance(value, list)
        for value in (roles_raw, slots_raw, semantic_sets_raw, sequences_raw)
    ):
        raise ValueError("SC kit-groove dictionaries must be arrays")
    roles = cast(list[Any], roles_raw)
    slots = cast(list[Any], slots_raw)
    semantic_sets = cast(list[Any], semantic_sets_raw)
    sequences = cast(list[Any], sequences_raw)

    decoded: list[tuple[ScDrumEvent, ...]] = []
    for sequence_index, sequence in enumerate(sequences):
        if not isinstance(sequence, list):
            raise ValueError(f"event sequence {sequence_index} must be an array")
        events: list[ScDrumEvent] = []
        previous = -1
        for atom in sequence:
            if not isinstance(atom, list) or len(atom) != 6:
                raise ValueError(f"event sequence {sequence_index} has invalid atoms")
            tick, role_index, velocity, slot_index, semantic_index, max_duration = map(int, atom)
            if tick < previous or tick < 0:
                raise ValueError(f"event sequence {sequence_index} is not ordered")
            if tick % 2:
                raise ValueError(
                    f"event sequence {sequence_index} cannot convert exactly to 48 PPQ"
                )
            if not 1 <= velocity <= 127:
                raise ValueError(f"event sequence {sequence_index} has invalid velocity")
            if max_duration < 0:
                raise ValueError(f"event sequence {sequence_index} has invalid duration cap")
            try:
                role = str(roles[role_index])
                slot = str(slots[slot_index])
                semantic_raw = semantic_sets[semantic_index]
            except IndexError as exc:
                raise ValueError(
                    f"event sequence {sequence_index} references an unknown dictionary item"
                ) from exc
            if not isinstance(semantic_raw, list):
                raise ValueError("SC drum semantic role set must be an array")
            try:
                semantic_roles = frozenset(str(roles[int(index)]) for index in semantic_raw)
            except IndexError as exc:
                raise ValueError("SC drum event references an unknown semantic role") from exc
            if not semantic_roles or role not in semantic_roles:
                raise ValueError("SC drum event primary role must be semantic")
            events.append(
                ScDrumEvent(tick, role, slot, velocity, semantic_roles, max_duration)
            )
            previous = tick
        decoded.append(tuple(events))

    def event_sequence(index: object) -> tuple[ScDrumEvent, ...]:
        value = _require_int(index, "event sequence index")
        try:
            return decoded[value]
        except IndexError as exc:
            raise ValueError(f"unknown event sequence {value}") from exc

    arrangements: list[ScDrumArrangement] = []
    for row in raw.get("arrangements", ()):
        if not isinstance(row, dict):
            raise ValueError("SC arrangement must be an object")
        levels = tuple(event_sequence(index) for index in row.get("levels", ()))
        if len(levels) != 5:
            raise ValueError("SC arrangement must have five activity levels")
        period = _require_int(row.get("period_ticks"), "arrangement period_ticks")
        if period <= 0 or period % 2 or any(
            event.tick >= period for level in levels for event in level
        ):
            raise ValueError("SC arrangement has an invalid 96 PPQ period or event")
        arrangements.append(
            ScDrumArrangement(
                str(row["kit_id"]),
                str(row["rhythm_id"]),
                str(row["meter"]),
                period,
                levels,
            )
        )

    fills: list[ScDrumFill] = []
    for row in raw.get("fills", ()):
        if not isinstance(row, dict):
            raise ValueError("SC fill must be an object")
        fill_events = event_sequence(row.get("sequence"))
        duration = _require_int(row.get("duration_ticks"), "fill duration_ticks")
        starts = tuple(int(value) for value in row.get("allowed_start_beats", ()))
        level = _require_int(row.get("slot_level"), "fill slot_level")
        gain = float(row.get("gain", 0.0))
        if (
            duration <= 0
            or duration % 2
            or not starts
            or not 1 <= level <= 5
            or gain <= 0
        ):
            raise ValueError(f"invalid fill {row.get('variant_id')!r}")
        if any(event.tick >= duration for event in fill_events):
            raise ValueError(f"fill {row.get('variant_id')!r} event is out of range")
        continuation = frozenset(
            f"{str(value[0])}/{str(value[1])}"
            for value in row.get("continuation_keys", ())
            if isinstance(value, list) and len(value) == 2
        )
        continuation_levels = tuple(
            event_sequence(index) for index in row.get("continuation_levels", ())
        )
        if len(continuation_levels) != 5:
            raise ValueError(f"fill {row.get('variant_id')!r} needs five continuations")
        fills.append(
            ScDrumFill(
                str(row["variant_id"]),
                str(row["base_fill_id"]),
                str(row["kit_id"]),
                str(row["rhythm_id"]),
                level,
                duration,
                starts,
                fill_events,
                gain,
                continuation,
                continuation_levels,
            )
        )
    return ScMusicCatalog(
        arrangements,
        fills,
        ppq=ppq,
        digest=hashlib.sha256(raw_bytes).hexdigest(),
    )
