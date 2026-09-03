from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

from amy_parameter_plan import format_amy_float


ScheduledEvent = tuple[int, int, str]
GroupedEvent = tuple[int, int, str]

SEQUENCE_CONTROL_STOP = 0
SEQUENCE_CONTROL_START = 1
SEQUENCE_CONTROL_GATE = 2
SEQUENCE_CONTROL_PUBLISH = 3


class DrumEventLike(Protocol):
    @property
    def role(self) -> str: ...

    @property
    def tick(self) -> int: ...

    @property
    def velocity(self) -> int: ...


class FillLike(Protocol):
    @property
    def index(self) -> int: ...

    @property
    def duration_ticks(self) -> int: ...

    @property
    def beat_unit_ticks(self) -> int: ...

    @property
    def allowed_start_beats(self) -> tuple[int, ...]: ...

    @property
    def continue_roles(self) -> frozenset[str]: ...

    @property
    def events(self) -> Sequence[DrumEventLike]: ...


class RhythmLike(Protocol):
    @property
    def rhythm_id(self) -> str: ...

    @property
    def period_ticks(self) -> int: ...

    @property
    def period_bars(self) -> int: ...

    @property
    def levels(self) -> Sequence[Sequence[DrumEventLike]]: ...


class DrumHitBody(Protocol):
    def __call__(
        self,
        rhythm_id: str,
        role: str,
        velocity: int,
        *,
        fill: bool,
    ) -> str: ...


FillT = TypeVar("FillT", bound=FillLike)


def sequence_control_command(
    group: int,
    action: int,
    value: int = 0,
    quantize: int = 0,
    execution_tag: int | None = None,
) -> str:
    """Encode AMY's generic sequencer-group control operation."""

    if int(group) <= 0:
        raise ValueError("sequencer group tags start at 1")
    values = [int(group), int(action), int(value), max(0, int(quantize))]
    if execution_tag is not None:
        values.append(int(execution_tag))
    return f"zQ{','.join(str(item) for item in values)}Z"


@dataclass(frozen=True, slots=True)
class GroupDefinitionPlan:
    commands: tuple[str, ...]
    tag_count: int
    high_water: int


def compile_group_definition(
    *,
    group: int,
    length: int,
    events: Sequence[GroupedEvent],
    previous_high_water: int = 0,
) -> GroupDefinitionPlan:
    """Stage and atomically publish one complete sequencer-group revision."""

    group_value = int(group)
    length_value = int(length)
    if group_value <= 0:
        raise ValueError("sequencer group tags start at 1")
    if length_value <= 0:
        raise ValueError("sequencer group length must be positive")

    commands: list[str] = []
    for tag, (tick, period, body) in enumerate(events):
        tick_value = int(tick)
        period_value = int(period)
        if tick_value < 0 or tick_value >= length_value:
            raise ValueError(
                f"group {group_value} event tick {tick_value} is outside length {length_value}"
            )
        if period_value < 0:
            raise ValueError("grouped event period must not be negative")
        command_body = str(body)
        if command_body.endswith("Z"):
            command_body = command_body[:-1]
        commands.append(
            f"H{tick_value},{period_value},{tag},{group_value}{command_body}Z"
        )

    high_water = max(len(events), max(0, int(previous_high_water)))
    for tag in range(len(events), high_water):
        commands.append(f"H0,0,{tag},{group_value}Z")
    commands.append(
        sequence_control_command(
            group_value,
            SEQUENCE_CONTROL_PUBLISH,
            length_value,
        )
    )
    return GroupDefinitionPlan(tuple(commands), len(events), high_water)


def _period_divisors(period: int) -> tuple[int, ...]:
    value = max(1, int(period))
    lower: list[int] = []
    upper: list[int] = []
    for candidate in range(1, math.isqrt(value) + 1):
        if value % candidate:
            continue
        lower.append(candidate)
        paired = value // candidate
        if paired != candidate:
            upper.append(paired)
    return tuple(lower + list(reversed(upper)))


def compact_repeating_events(
    occurrences: list[tuple[int, str]],
    bar_period: int,
) -> list[ScheduledEvent]:
    """Encode an exact circular event set using deterministic short periods."""

    period = max(1, int(bar_period))
    ticks_by_body: dict[str, set[int]] = {}
    for tick, body in occurrences:
        ticks_by_body.setdefault(str(body), set()).add(int(tick) % period)

    divisors = _period_divisors(period)
    compacted: list[ScheduledEvent] = []
    for body, source_ticks in ticks_by_body.items():
        remaining = set(source_ticks)
        while remaining:
            best_period = period
            best_residue = min(remaining)
            best_cycle = {best_residue}
            for candidate_period in divisors:
                for residue in sorted({tick % candidate_period for tick in remaining}):
                    cycle = set(range(residue, period, candidate_period))
                    if cycle.issubset(remaining) and len(cycle) > len(best_cycle):
                        best_period = candidate_period
                        best_residue = residue
                        best_cycle = cycle
            compacted.append((best_residue, best_period, body))
            remaining.difference_update(best_cycle)
    return compacted


@dataclass(frozen=True, slots=True)
class TaggedLanePlan:
    commands: tuple[str, ...]
    high_water: int


def compile_tagged_lane(
    *,
    name: str,
    start: int,
    count: int,
    previous_high_water: int,
    events: list[ScheduledEvent],
) -> TaggedLanePlan:
    """Compile a complete replace/clear transaction for one AMY tag range."""

    if start < 0 or count <= 0:
        raise ValueError(f"invalid sequencer tag range for {name}")
    if len(events) > count:
        raise ValueError(
            f"sequencer lane {name} requires {len(events)} tags; range capacity is {count}"
        )
    high_water = max(int(previous_high_water), len(events))
    commands: list[str] = []
    for index, (tick, period, body) in enumerate(events):
        tag = start + index
        period_value = max(1, int(period))
        tick_value = max(0, int(tick)) % period_value
        command_body = str(body)
        if command_body.endswith("Z"):
            command_body = command_body[:-1]
        commands.append(f"H{tick_value},{period_value},{tag}{command_body}Z")
    for index in range(len(events), high_water):
        commands.append(f"H0,0,{start + index}Z")
    return TaggedLanePlan(tuple(commands), high_water)


@dataclass(frozen=True, slots=True)
class ChordGroupPlan:
    definitions: tuple[str, ...]
    triggers: tuple[ScheduledEvent, ...]
    tag_high_waters: tuple[tuple[int, int], ...]


def compile_chord_group_plan(
    *,
    config: Mapping[str, Any] | None,
    enabled: bool,
    chord_notes: Sequence[float],
    max_chord_notes: int,
    chord_gate_beats: float,
    group_start: int,
    group_count: int,
    previous_tag_high_waters: Mapping[int, int],
    synth: int,
    ppq: int,
) -> ChordGroupPlan:
    """Compile chord/arpeggio phrase groups and repeating root triggers."""

    if not config or not enabled or not chord_notes:
        return ChordGroupPlan((), (), ())
    source_events = [event for event in config.get("chord_events", []) if isinstance(event, dict)]
    if not source_events:
        return ChordGroupPlan((), (), ())

    period = max(1, round(float(config["length_beats"]) * ppq))
    velocities = sorted(
        {max(0.0, min(1.0, float(event.get("amp", 1.0)))) for event in source_events}
    )
    velocity_slots = {
        format_amy_float(velocity): index for index, velocity in enumerate(velocities)
    }
    required = len(velocities)
    if required > group_count:
        raise ValueError(
            f"chord phrases need {required} AMY groups; reserved capacity is {group_count}"
        )

    commands: list[str] = []
    occurrences: list[tuple[int, str]] = []
    tag_high_waters: list[tuple[int, int]] = []
    raw_arpeggio = config.get("chord_arpeggio", {})
    arpeggio = raw_arpeggio if isinstance(raw_arpeggio, dict) else {}
    if not bool(arpeggio.get("enabled", False)):
        rhythm_notes = chord_notes[: max(1, max_chord_notes)]
        gate = max(1, round(chord_gate_beats * ppq))
        length = gate + 1
        for velocity_index, velocity in enumerate(velocities):
            group = group_start + velocity_index
            grouped_events = [
                (
                    0,
                    length,
                    f"n{format_amy_float(note)}"
                    f"l{format_amy_float(velocity)}i{synth}",
                )
                for note in rhythm_notes
            ]
            grouped_events.append((gate, 0, f"l0i{synth}"))
            definition = compile_group_definition(
                group=group,
                length=length,
                events=grouped_events,
                previous_high_water=previous_tag_high_waters.get(group, 0),
            )
            commands.extend(definition.commands)
            tag_high_waters.append((group, definition.high_water))
        for event in source_events:
            tick = round(float(event.get("time", 0.0)) * ppq)
            velocity = max(0.0, min(1.0, float(event.get("amp", 1.0))))
            group = group_start + velocity_slots[format_amy_float(velocity)]
            occurrences.append(
                (
                    tick,
                    sequence_control_command(
                        group,
                        SEQUENCE_CONTROL_START,
                        1,
                    ),
                )
            )
        return ChordGroupPlan(
            tuple(commands),
            tuple(compact_repeating_events(occurrences, period)),
            tuple(tag_high_waters),
        )

    note_count = len(chord_notes)
    rate = max(1, min(4, int(arpeggio.get("notes_per_beat", 1))))
    step = max(1, round(ppq / rate))
    gate = max(1, round(chord_gate_beats * step))
    length = (max(0, note_count - 1) * step) + gate + 1
    note_indexes = list(range(note_count))
    if str(arpeggio.get("direction", "up")).lower() == "down":
        note_indexes.reverse()
    for velocity_index, velocity in enumerate(velocities):
        group = group_start + velocity_index
        grouped_events = []
        for sequence_index, note_index in enumerate(note_indexes):
            note_text = format_amy_float(chord_notes[note_index])
            start_tick = sequence_index * step
            grouped_events.extend(
                (
                    (
                        start_tick,
                        length if start_tick == 0 else 0,
                        f"n{note_text}l{format_amy_float(velocity)}i{synth}",
                    ),
                    (start_tick + gate, 0, f"n{note_text}l0i{synth}"),
                )
            )
        definition = compile_group_definition(
            group=group,
            length=length,
            events=grouped_events,
            previous_high_water=previous_tag_high_waters.get(group, 0),
        )
        commands.extend(definition.commands)
        tag_high_waters.append((group, definition.high_water))
    for event in source_events:
        start_tick = round(float(event.get("time", 0.0)) * ppq)
        velocity = max(0.0, min(1.0, float(event.get("amp", 1.0))))
        velocity_index = velocity_slots[format_amy_float(velocity)]
        group = group_start + velocity_index
        occurrences.append(
            (
                start_tick,
                sequence_control_command(group, SEQUENCE_CONTROL_START, 1),
            )
        )
    return ChordGroupPlan(
        tuple(commands),
        tuple(compact_repeating_events(occurrences, period)),
        tuple(tag_high_waters),
    )


def compile_bass_events(
    *,
    config: Mapping[str, Any] | None,
    running: bool,
    bass_notes: Sequence[float],
    bass_riff: Mapping[str, Any] | None,
    synth: int,
    bass_gate_beats: float,
    ppq: int,
) -> tuple[ScheduledEvent, ...]:
    """Compile bass activity or riff data into scheduled wire bodies."""

    if not config or not running:
        return ()
    period = max(1, round(float(config["length_beats"]) * ppq))
    events: list[ScheduledEvent] = []
    if str(config.get("bass_mode", "activity")) == "riff":
        if not bass_riff:
            return ()
        source_ppq = max(1, int(bass_riff.get("ppq", ppq)))
        phrase_ticks = max(1, int(bass_riff.get("phrase_ticks", source_ppq)))
        riff_period = max(1, round(phrase_ticks * ppq / source_ppq))
        source_events = bass_riff.get("events", [])
        if not isinstance(source_events, list):
            return ()
        for event in source_events:
            if not isinstance(event, dict):
                continue
            tick = round(float(event.get("tick", 0)) * ppq / source_ppq)
            duration = max(
                1,
                round(float(event.get("duration_ticks", 1)) * ppq / source_ppq),
            )
            note = float(event.get("note", 36.0))
            velocity = max(
                0.0,
                min(1.0, float(event.get("velocity", 0)) / 127.0),
            )
            note_text = format_amy_float(note)
            events.extend(
                (
                    (
                        tick,
                        riff_period,
                        f"n{note_text}l{format_amy_float(velocity)}i{synth}",
                    ),
                    (tick + duration, riff_period, f"n{note_text}l0i{synth}"),
                )
            )
        return tuple(events)

    if not bass_notes:
        return ()
    gate = max(1, round(bass_gate_beats * ppq))
    source_events = config.get("bass_events", [])
    if not isinstance(source_events, list):
        return ()
    for event in source_events:
        if not isinstance(event, dict):
            continue
        degree = int(event.get("degree", 0))
        note = float(bass_notes[degree % len(bass_notes)])
        tick = round(float(event.get("time", 0.0)) * ppq)
        velocity = max(0.0, min(1.0, float(event.get("amp", 1.0))))
        note_text = format_amy_float(note)
        events.extend(
            (
                (
                    tick,
                    period,
                    f"n{note_text}l{format_amy_float(velocity)}i{synth}",
                ),
                (tick + gate, period, f"n{note_text}l0i{synth}"),
            )
        )
    return tuple(events)


def drum_quantum(rhythm: RhythmLike) -> int:
    return max(1, (rhythm.period_ticks // rhythm.period_bars) // 2)


@dataclass(frozen=True, slots=True)
class DrumGroupPlan:
    commands: tuple[str, ...]
    tag_high_waters: tuple[tuple[int, int], ...]


def compile_drum_activity_groups(
    *,
    rhythm: RhythmLike,
    percussion_activity: int,
    roles: Sequence[str],
    group_start: int,
    previous_tag_high_waters: Mapping[int, int],
    rhythm_running: bool,
    quantize_live: bool,
    hit_body: DrumHitBody,
) -> DrumGroupPlan:
    """Compile role phrase groups and optional quantized replacements."""

    level_index = max(0, min(4, int(percussion_activity) - 1))
    by_role: dict[str, list[DrumEventLike]] = {}
    for event in rhythm.levels[level_index]:
        by_role.setdefault(event.role, []).append(event)
    length = rhythm.period_ticks // 2
    quantum = drum_quantum(rhythm) if quantize_live else 0
    commands: list[str] = []
    tag_high_waters: list[tuple[int, int]] = []
    for role_index, role in enumerate(roles):
        group = group_start + role_index
        events = by_role.get(role, [])
        if not events:
            if rhythm_running:
                commands.append(
                    sequence_control_command(
                        group,
                        SEQUENCE_CONTROL_STOP,
                        0,
                        quantum,
                        group,
                    )
                )
            continue
        grouped_events: list[GroupedEvent] = []
        for event in events:
            event_tick = event.tick // 2
            event_period = length if event_tick == 0 else 0
            grouped_events.append(
                (
                    event_tick,
                    event_period,
                    hit_body(rhythm.rhythm_id, role, event.velocity, fill=False),
                )
            )
        definition = compile_group_definition(
            group=group,
            length=length,
            events=grouped_events,
            previous_high_water=previous_tag_high_waters.get(group, 0),
        )
        commands.extend(definition.commands)
        tag_high_waters.append((group, definition.high_water))
        if rhythm_running:
            commands.append(
                sequence_control_command(
                    group,
                    SEQUENCE_CONTROL_START,
                    0,
                    quantum,
                    group,
                )
            )
    return DrumGroupPlan(tuple(commands), tuple(tag_high_waters))


def compile_fill_group(
    *,
    rhythm_id: str,
    fill: FillLike,
    group: int,
    roles: Sequence[str],
    role_indexes: Mapping[str, int],
    drum_group_start: int,
    hit_body: DrumHitBody,
) -> GroupDefinitionPlan:
    """Compile one persistent fill phrase group."""

    length = fill.duration_ticks // 2
    events: list[GroupedEvent] = []
    for role in roles:
        if role in fill.continue_roles:
            continue
        role_group = drum_group_start + role_indexes[role]
        events.append(
            (
                0,
                length,
                sequence_control_command(
                    role_group,
                    SEQUENCE_CONTROL_GATE,
                    length,
                    0,
                    role_group,
                ),
            )
        )
    for event in fill.events:
        event_tick = event.tick // 2
        event_period = length if event_tick == 0 else 0
        events.append(
            (
                event_tick,
                event_period,
                hit_body(rhythm_id, event.role, event.velocity, fill=True),
            )
        )
    return compile_group_definition(group=group, length=length, events=events)


def fill_occurrences(
    order: Sequence[int],
    fills: Sequence[FillT],
) -> tuple[tuple[FillT, int], ...]:
    if not order:
        return ()
    position = 0
    start_indexes = {index: 0 for index in order}
    seen: set[tuple[int, tuple[int, ...]]] = set()
    occurrences: list[tuple[FillT, int]] = []
    while True:
        signature = (position, tuple(start_indexes[index] for index in order))
        if signature in seen:
            return tuple(occurrences)
        seen.add(signature)
        local_index = order[position]
        fill = fills[local_index]
        allowed_index = start_indexes[local_index]
        occurrences.append((fill, fill.allowed_start_beats[allowed_index]))
        start_indexes[local_index] = (allowed_index + 1) % len(fill.allowed_start_beats)
        position = (position + 1) % len(order)


@dataclass(frozen=True, slots=True)
class FillSchedulePlan:
    commands: tuple[str, ...]
    high_water: int


def compile_fill_schedule(
    *,
    fills: Sequence[FillT],
    order: Sequence[int],
    density_bars: int,
    bar_ticks: int,
    lane_start: int,
    lane_count: int,
    previous_high_water: int,
    group_tag: Callable[[FillT], int],
) -> FillSchedulePlan:
    """Compile a repeating fill cycle and stale-tag clears."""

    occurrences = fill_occurrences(order, fills)
    if len(occurrences) > lane_count:
        raise ValueError(
            f"fill cycle needs {len(occurrences)} root tags; drum range has {lane_count}"
        )
    high_water = max(previous_high_water, len(occurrences))
    density = max(1, int(density_bars))
    period = max(1, len(occurrences) * density * bar_ticks)
    events: list[ScheduledEvent] = []
    for occurrence_index, (fill, start_beat) in enumerate(occurrences):
        offset = occurrence_index * density * bar_ticks + (start_beat - 1) * (
            fill.beat_unit_ticks // 2
        )
        events.append(
            (
                offset,
                period,
                sequence_control_command(
                    group_tag(fill),
                    SEQUENCE_CONTROL_START,
                    1,
                ),
            )
        )
    lane = compile_tagged_lane(
        name="drums",
        start=lane_start,
        count=lane_count,
        previous_high_water=previous_high_water,
        events=events,
    )
    return FillSchedulePlan(lane.commands, lane.high_water)
