from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast


BASS_ACTIVITY_VELOCITY_GAIN = 1.4


def scaled_bass_source(
    *,
    config: Mapping[str, Any],
    bass_notes: Sequence[float],
    bass_riff: Mapping[str, Any] | None,
    bass_gate_beats: float,
    ppq: int,
    quantize_activity_velocity: bool,
) -> tuple[int, tuple[dict[str, Any], ...], tuple[Any, ...]]:
    """Normalize either bass source without attaching it to an engine clock."""

    mode = str(config.get("bass_mode", "activity"))
    if mode == "riff":
        if not bass_riff:
            return 1, (), ("riff", None)
        source_ppq = max(1, int(bass_riff.get("ppq", ppq)))
        phrase_ticks = max(1, int(bass_riff.get("phrase_ticks", source_ppq)))
        period = max(1, round(phrase_ticks * ppq / source_ppq))
        source_events = bass_riff.get("events", [])
        if not isinstance(source_events, list):
            return period, (), ("riff", bass_riff.get("id"))
        events = tuple(
            {
                "tick": round(float(event.get("tick", 0)) * ppq / source_ppq),
                "duration": max(
                    1,
                    round(float(event.get("duration_ticks", 1)) * ppq / source_ppq),
                ),
                "note": float(event.get("note", 36.0)),
                "velocity": max(
                    0.0,
                    min(1.0, float(event.get("velocity", 0)) / 127.0),
                ),
                "accent": bool(event.get("accent", False)),
                "slide_to_next": bool(event.get("slide_to_next", False)),
                "link_to_next": str(
                    event.get(
                        "link_to_next",
                        "legato_glide" if bool(event.get("slide_to_next", False)) else "none",
                    )
                ),
                "accent_amount": max(
                    0.0,
                    min(
                        1.0,
                        float(
                            event.get(
                                "accent_amount",
                                1.0 if bool(event.get("accent", False)) else 0.0,
                            )
                        ),
                    ),
                ),
                "gate_policy": str(event.get("gate_policy", "authored_detached")),
                "glide_time_ms": max(0.0, float(event.get("glide_time_ms", 0.0))),
                "fallback_duration": max(
                    1,
                    round(
                        float(event.get("fallback_duration_ticks", event.get("duration_ticks", 1)))
                        * ppq
                        / source_ppq
                    ),
                ),
            }
            for event in source_events
            if isinstance(event, Mapping)
        )
        return period, events, ("riff", str(bass_riff.get("id", "")))

    period = max(1, round(float(config["length_beats"]) * ppq))
    source_events = config.get("bass_events", [])
    if not bass_notes or not isinstance(source_events, list):
        return period, (), ("activity", config.get("id"), config.get("bass_activity"))
    gate = max(1, round(bass_gate_beats * ppq))
    events_list: list[dict[str, Any]] = []
    for event in source_events:
        if not isinstance(event, Mapping):
            continue
        velocity = max(
            0.0,
            min(
                1.0,
                float(event.get("amp", 1.0)) * BASS_ACTIVITY_VELOCITY_GAIN,
            ),
        )
        if quantize_activity_velocity:
            velocity = round(velocity * 127.0) / 127.0
        events_list.append(
            {
                "tick": round(float(event.get("time", 0.0)) * ppq),
                "duration": gate,
                "note": float(
                    bass_notes[int(event.get("degree", 0)) % len(bass_notes)]
                ),
                "velocity": velocity,
                "accent": bool(event.get("accent", False)),
                "slide_to_next": False,
                "link_to_next": "none",
                "accent_amount": 1.0 if bool(event.get("accent", False)) else 0.0,
                "gate_policy": "authored_detached",
                "glide_time_ms": 0.0,
                "fallback_duration": gate,
            }
        )
    events = tuple(
        sorted(
            events_list,
            key=lambda event: int(cast(int | float | str, event["tick"])),
        )
    )
    timing = tuple((event["tick"], event["duration"]) for event in events)
    return (
        period,
        events,
        (
            "activity",
            str(config.get("id", "")),
            int(config.get("bass_activity", 0)),
            timing,
        ),
    )


def bass_gesture_sources(
    events: Sequence[Mapping[str, Any]],
    period: int,
) -> tuple[tuple[Mapping[str, Any], ...], ...]:
    """Partition one circular phrase only at guaranteed silent boundaries."""

    if not events:
        return ()
    ordered_ticks = [int(event["tick"]) for event in events]
    if ordered_ticks != sorted(ordered_ticks):
        raise ValueError("bass events must be ordered by tick")
    if ordered_ticks[0] < 0 or ordered_ticks[-1] >= period:
        raise ValueError("bass event ticks must lie inside the phrase period")

    gaps: list[bool] = []
    for index, event in enumerate(events):
        end_tick = int(event["tick"]) + int(event["duration"])
        next_tick = (
            int(events[index + 1]["tick"])
            if index + 1 < len(events)
            else period + int(events[0]["tick"])
        )
        gaps.append(
            not bool(event.get("slide_to_next", False)) and end_tick < next_tick
        )
    if not any(gaps):
        if len(events) > 1 and not any(
            bool(event.get("slide_to_next", False)) for event in events
        ):
            separated: list[tuple[Mapping[str, Any], ...]] = []
            for index, source in enumerate(events):
                next_tick = (
                    int(events[index + 1]["tick"])
                    if index + 1 < len(events)
                    else period + int(events[0]["tick"])
                )
                interval = next_tick - int(source["tick"])
                if interval < 2:
                    break
                event = dict(source)
                event["duration"] = min(int(event["duration"]), interval - 1)
                separated.append((event,))
            else:
                return tuple(separated)
        raise ValueError(
            "bass phrase must contain a silent handover somewhere in its cycle"
        )

    rotation = 0 if gaps[-1] else gaps.index(True) + 1
    ordered: list[tuple[int, Mapping[str, Any]]] = []
    for offset in range(len(events)):
        source_index = (rotation + offset) % len(events)
        event = dict(events[source_index])
        if source_index < rotation:
            event["tick"] = int(event["tick"]) + period
        ordered.append((source_index, event))

    gestures: list[tuple[Mapping[str, Any], ...]] = []
    start = 0
    for index, (source_index, _event) in enumerate(ordered[:-1]):
        if gaps[source_index]:
            gestures.append(tuple(event for _, event in ordered[start : index + 1]))
            start = index + 1
    gestures.append(tuple(event for _, event in ordered[start:]))
    return tuple(gestures)
