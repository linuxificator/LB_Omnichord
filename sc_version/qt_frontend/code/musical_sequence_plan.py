from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
from typing import Any

from drum_patterns import DrumPatternCatalog
from engine_protocol import PPQ, SequenceDefinition, SequenceEvent
from bass_sequence_source import bass_gesture_sources, scaled_bass_source


@dataclass(frozen=True, slots=True)
class LanePlan:
    lane: str
    generation: int
    alignment_ticks: int
    definitions: tuple[SequenceDefinition, ...]

    def __post_init__(self) -> None:
        if not self.lane:
            raise ValueError("lane must not be empty")
        if self.generation <= 0:
            raise ValueError("lane generation must be positive")
        if self.alignment_ticks < 0:
            raise ValueError("alignment_ticks must not be negative")
        ids = [definition.definition_id for definition in self.definitions]
        if len(ids) != len(set(ids)):
            raise ValueError(f"lane {self.lane!r} contains duplicate definitions")
        available = set(ids)
        for definition in self.definitions:
            for event in definition.events:
                if event.kind == "launch" and str(event.atoms[0]) not in available:
                    raise ValueError(
                        f"{definition.definition_id} launches missing definition "
                        f"{event.atoms[0]!r}"
                    )


def _frequency(note: float) -> float:
    return float(440.0 * (2.0 ** ((float(note) - 69.0) / 12.0)))


def _event(
    tick: int,
    ordinal: int,
    kind: str,
    *atoms: str | int | float,
) -> SequenceEvent:
    return SequenceEvent(
        tick=max(0, int(tick)),
        ordinal=max(0, int(ordinal)),
        kind=kind,  # type: ignore[arg-type]
        atoms=tuple(atoms),
    )


def compile_chord_lane(
    *,
    config: Mapping[str, Any] | None,
    enabled: bool,
    chord_notes: Sequence[float],
    max_chord_notes: int,
    chord_gate_beats: float,
    program_id: str,
    program_revision: int,
    logical_bus: int,
    generation: int,
) -> LanePlan:
    """Compile accompaniment without AMY strings or a host-side clock."""

    lane = "chords"
    if not config or not enabled or not chord_notes:
        return LanePlan(lane, generation, 1, ())
    source_events = tuple(
        event for event in config.get("chord_events", ()) if isinstance(event, Mapping)
    )
    if not source_events:
        return LanePlan(lane, generation, 1, ())

    period = max(1, round(float(config["length_beats"]) * PPQ))
    velocities = sorted(
        {max(0.0, min(1.0, float(event.get("amp", 1.0)))) for event in source_events}
    )
    arpeggio_raw = config.get("chord_arpeggio", {})
    arpeggio = arpeggio_raw if isinstance(arpeggio_raw, Mapping) else {}
    arpeggiated = bool(arpeggio.get("enabled", False))
    notes = list(chord_notes)
    if not arpeggiated:
        notes = notes[: max(1, int(max_chord_notes))]
        step = 0
        gate = max(1, round(float(chord_gate_beats) * PPQ))
    else:
        rate = max(1, min(4, int(arpeggio.get("notes_per_beat", 1))))
        step = max(1, round(PPQ / rate))
        gate = max(1, round(float(chord_gate_beats) * step))
        if str(arpeggio.get("direction", "up")).lower() == "down":
            notes.reverse()

    children: list[SequenceDefinition] = []
    child_ids: dict[float, str] = {}
    for velocity_index, velocity in enumerate(velocities):
        child_id = f"chords/gesture/{velocity_index}"
        child_ids[velocity] = child_id
        events: list[SequenceEvent] = []
        ordinal = 0
        for note_index, note in enumerate(notes):
            handle = f"note/{note_index}"
            start = note_index * step
            events.append(
                _event(
                    start,
                    ordinal,
                    "noteOn",
                    handle,
                    "rhythm/chords",
                    program_id,
                    int(program_revision),
                    max(0, min(127, int(round(note)))),
                    _frequency(note),
                    velocity,
                    "ordinary",
                    0,
                    int(logical_bus),
                )
            )
            ordinal += 1
            events.append(_event(start + gate, ordinal, "noteOff", handle, 0.0))
            ordinal += 1
        children.append(
            SequenceDefinition(
                definition_id=child_id,
                revision=generation,
                kind="finite",
                lane=lane,
                period_ticks=0,
                events=tuple(sorted(events, key=lambda item: (item.tick, item.ordinal))),
                source_identity=f"{config.get('id', '')}:chord:{velocity:.9g}",
            )
        )

    root_events = tuple(
        _event(
            round(float(source.get("time", 0.0)) * PPQ),
            ordinal,
            "launch",
            child_ids[max(0.0, min(1.0, float(source.get("amp", 1.0))))],
        )
        for ordinal, source in enumerate(source_events)
    )
    root = SequenceDefinition(
        definition_id="chords/root",
        revision=generation,
        kind="root",
        lane=lane,
        period_ticks=period,
        events=tuple(sorted(root_events, key=lambda item: (item.tick, item.ordinal))),
        source_identity=f"{config.get('id', '')}:chord-root",
    )
    return LanePlan(lane, generation, 1, (root, *children))


def compile_bass_lane(
    *,
    config: Mapping[str, Any] | None,
    running: bool,
    bass_notes: Sequence[float],
    bass_gate_beats: float,
    program_id: str,
    program_revision: int,
    logical_bus: int,
    generation: int,
) -> LanePlan:
    """Compile monophonic finite bass gestures and a phase-owning root."""

    lane = "bass"
    if not config or not running:
        return LanePlan(lane, generation, 1, ())
    raw_riff = config.get("bass_riff")
    bass_riff = raw_riff if isinstance(raw_riff, Mapping) else None
    period, source_events, identity = scaled_bass_source(
        config=config,
        bass_notes=bass_notes,
        bass_riff=bass_riff,
        bass_gate_beats=bass_gate_beats,
        ppq=PPQ,
        quantize_activity_velocity=False,
    )
    sources = bass_gesture_sources(source_events, period)
    definitions: list[SequenceDefinition] = []
    launches: list[SequenceEvent] = []
    for gesture_index, source in enumerate(sources):
        child_id = f"bass/gesture/{gesture_index}"
        start_tick = int(source[0]["tick"])
        events: list[SequenceEvent] = []
        ordinal = 0
        previous_slides = False
        for note_index, note_event in enumerate(source):
            tick = int(note_event["tick"]) - start_tick
            note = float(note_event["note"])
            accent = bool(note_event.get("accent", False)) and not previous_slides
            if previous_slides:
                events.append(
                    _event(tick, ordinal, "voiceSet", "voice", "frequency_hz", _frequency(note))
                )
                ordinal += 1
            else:
                events.append(
                    _event(
                        tick,
                        ordinal,
                        "noteOn",
                        "voice",
                        "rhythm/bass",
                        program_id,
                        int(program_revision),
                        max(0, min(127, int(round(note)))),
                        _frequency(note),
                        float(note_event["velocity"]),
                        "accent" if accent else "ordinary",
                        1 if accent else 0,
                        int(logical_bus),
                    )
                )
                ordinal += 1
            slides = bool(note_event.get("slide_to_next", False))
            end_tick = int(note_event["tick"]) + int(note_event["duration"])
            next_tick = (
                int(source[note_index + 1]["tick"])
                if note_index + 1 < len(source)
                else None
            )
            if not slides and (next_tick is None or end_tick <= next_tick):
                events.append(
                    _event(end_tick - start_tick, ordinal, "noteOff", "voice", 0.0)
                )
                ordinal += 1
            previous_slides = slides
        definitions.append(
            SequenceDefinition(
                definition_id=child_id,
                revision=generation,
                kind="finite",
                lane=lane,
                period_ticks=0,
                events=tuple(sorted(events, key=lambda item: (item.tick, item.ordinal))),
                source_identity=f"{identity!r}:{gesture_index}",
            )
        )
        launches.append(
            _event(start_tick % period, gesture_index, "launch", child_id)
        )
    if launches:
        definitions.insert(
            0,
            SequenceDefinition(
                definition_id="bass/root",
                revision=generation,
                kind="root",
                lane=lane,
                period_ticks=period,
                events=tuple(sorted(launches, key=lambda item: (item.tick, item.ordinal))),
                source_identity=f"{identity!r}:root",
            ),
        )
    return LanePlan(lane, generation, 1, tuple(definitions))


def _fill_occurrences(
    order: Sequence[int],
    fills: Sequence[Any],
) -> tuple[tuple[Any, int], ...]:
    if not order:
        return ()
    position = 0
    start_indexes = {index: 0 for index in order}
    seen: set[tuple[int, tuple[int, ...]]] = set()
    result: list[tuple[Any, int]] = []
    while True:
        signature = (position, tuple(start_indexes[index] for index in order))
        if signature in seen:
            return tuple(result)
        seen.add(signature)
        local_index = order[position]
        fill = fills[local_index]
        allowed_index = start_indexes[local_index]
        result.append((fill, fill.allowed_start_beats[allowed_index]))
        start_indexes[local_index] = (allowed_index + 1) % len(fill.allowed_start_beats)
        position = (position + 1) % len(order)


def _drum_atoms(
    *,
    catalog: DrumPatternCatalog,
    kit: str,
    rhythm_id: str,
    role: str,
    velocity: int,
    logical_bus: int,
    fill: bool = False,
    fill_id: str | None = None,
    fill_gain: float = 1.0,
) -> tuple[str | int | float, ...]:
    sound = catalog.resolve(
        kit,
        rhythm_id,
        role,
        fill=fill,
        fill_id=fill_id,
    )
    level = max(0.0, min(1.0, float(velocity) / 127.0))
    if fill:
        level *= max(0.0, float(fill_gain))
    program = (
        f"sample.{kit}.preset-{sound.preset}"
        if sound.preset is not None
        else f"sample.{kit}.patch-{sound.synth_patch}"
    )
    return (
        role,
        program,
        int(sound.note),
        float(level),
        int(logical_bus),
    )


def compile_drum_lane(
    *,
    config: Mapping[str, Any] | None,
    catalog: DrumPatternCatalog,
    kit: str,
    logical_bus: int,
    generation: int,
) -> LanePlan:
    """Compile periodic activity, finite fills and deterministic fill launches."""

    lane = "drums"
    if not config:
        return LanePlan(lane, generation, 1, ())
    rhythm = catalog.rhythm(str(config.get("id", "")))
    level_index = max(0, min(4, int(config.get("percussion_activity", 1)) - 1))
    roles = sorted({event.role for level in rhythm.levels for event in level})
    length = rhythm.period_ticks // 2
    definitions: list[SequenceDefinition] = []
    for role in roles:
        events = tuple(
            _event(
                event.tick // 2,
                ordinal,
                "drumHit",
                *_drum_atoms(
                    catalog=catalog,
                    kit=kit,
                    rhythm_id=rhythm.rhythm_id,
                    role=role,
                    velocity=event.velocity,
                    logical_bus=logical_bus,
                ),
            )
            for ordinal, event in enumerate(
                item for item in rhythm.levels[level_index] if item.role == role
            )
        )
        if events:
            definitions.append(
                SequenceDefinition(
                    definition_id=f"drums/activity/{role}",
                    revision=generation,
                    kind="root",
                    lane=lane,
                    period_ticks=length,
                    events=events,
                    source_identity=f"{rhythm.rhythm_id}:level-{level_index + 1}:{role}",
                )
            )

    raw_order = config.get("fill_order", ())
    order = tuple(
        dict.fromkeys(
            int(index)
            for index in raw_order
            if 0 <= int(index) < len(rhythm.fills)
        )
    ) if isinstance(raw_order, list) else ()
    occurrences = _fill_occurrences(order, rhythm.fills)
    for fill in rhythm.fills:
        fill_events: list[SequenceEvent] = []
        ordinal = 0
        duration = fill.duration_ticks // 2
        for role in roles:
            if role not in fill.continue_roles:
                fill_events.append(
                    _event(0, ordinal, "gateBegin", role, f"{fill.fill_id}/{role}", duration, "drumHit")
                )
                ordinal += 1
        for hit in fill.events:
            fill_events.append(
                _event(
                    hit.tick // 2,
                    ordinal,
                    "drumHit",
                    *_drum_atoms(
                        catalog=catalog,
                        kit=kit,
                        rhythm_id=rhythm.rhythm_id,
                        role=hit.role,
                        velocity=hit.velocity,
                        logical_bus=logical_bus,
                        fill=True,
                        fill_id=fill.fill_id,
                        fill_gain=fill.output_gain,
                    ),
                )
            )
            ordinal += 1
        definitions.append(
            SequenceDefinition(
                definition_id=f"drums/fill/{fill.fill_id}",
                revision=generation,
                kind="finite",
                lane=lane,
                period_ticks=0,
                events=tuple(sorted(fill_events, key=lambda item: (item.tick, item.ordinal))),
                source_identity=fill.fill_id,
            )
        )

    if occurrences:
        bar_ticks = max(1, (rhythm.period_ticks // rhythm.period_bars) // 2)
        density = max(1, int(config.get("fill_density_bars", 8)))
        schedule_period = len(occurrences) * density * bar_ticks
        schedule_events = tuple(
            _event(
                index * density * bar_ticks
                + (start_beat - 1) * (fill.beat_unit_ticks // 2),
                index,
                "launch",
                f"drums/fill/{fill.fill_id}",
            )
            for index, (fill, start_beat) in enumerate(occurrences)
        )
        definitions.append(
            SequenceDefinition(
                definition_id="drums/fill-schedule",
                revision=generation,
                kind="root",
                lane=lane,
                period_ticks=schedule_period,
                events=schedule_events,
                source_identity=f"{rhythm.rhythm_id}:fills:{','.join(map(str, order))}",
            )
        )
        alignment = bar_ticks
    else:
        alignment = max(1, math.gcd(*(definition.period_ticks for definition in definitions if definition.kind == "root")))

    return LanePlan(lane, generation, alignment, tuple(definitions))
