from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal


PROTOCOL_VERSION = 1
PPQ = 48
EventKind = Literal[
    "launch",
    "gateBegin",
    "rootStop",
    "rootStart",
    "noteOn",
    "noteOff",
    "voiceSet",
    "drumHit",
]
DefinitionKind = Literal["root", "finite"]


class ProtocolValidationError(ValueError):
    """An invalid operation was rejected before crossing the OSC boundary."""


def _finite(name: str, value: float) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ProtocolValidationError(f"{name} must be finite")
    return result


def _identity(name: str, value: str) -> str:
    result = str(value)
    if not result or len(result.encode("utf-8")) > 192:
        raise ProtocolValidationError(f"{name} must contain 1..192 UTF-8 bytes")
    return result


@dataclass(frozen=True, slots=True)
class SequenceEvent:
    tick: int
    ordinal: int
    kind: EventKind
    atoms: tuple[str | int | float, ...] = ()

    def __post_init__(self) -> None:
        if self.tick < 0:
            raise ProtocolValidationError("event tick must be nonnegative")
        if self.ordinal < 0:
            raise ProtocolValidationError("event ordinal must be nonnegative")
        if self.kind not in (
            "launch",
            "gateBegin",
            "rootStop",
            "rootStart",
            "noteOn",
            "noteOff",
            "voiceSet",
            "drumHit",
        ):
            raise ProtocolValidationError(f"unknown event kind {self.kind!r}")
        for atom in self.atoms:
            if isinstance(atom, float):
                _finite("event atom", atom)


@dataclass(frozen=True, slots=True)
class SequenceDefinition:
    definition_id: str
    revision: int
    kind: DefinitionKind
    lane: str
    period_ticks: int
    events: tuple[SequenceEvent, ...]
    source_identity: str

    def __post_init__(self) -> None:
        _identity("definition_id", self.definition_id)
        _identity("lane", self.lane)
        _identity("source_identity", self.source_identity)
        if self.revision <= 0:
            raise ProtocolValidationError("definition revision must be positive")
        if self.kind not in ("root", "finite"):
            raise ProtocolValidationError(f"unknown definition kind {self.kind!r}")
        if self.kind == "root" and self.period_ticks <= 0:
            raise ProtocolValidationError("root period must be positive")
        if self.kind == "finite" and self.period_ticks != 0:
            raise ProtocolValidationError("finite definition period must be zero")
        ordered = tuple(sorted(self.events, key=lambda event: (event.tick, event.ordinal)))
        if self.events != ordered:
            raise ProtocolValidationError(
                "definition events must be ordered by tick and ordinal"
            )

    @property
    def max_end_tick(self) -> int:
        return max((event.tick for event in self.events), default=0)


@dataclass(frozen=True, slots=True)
class NoteOn:
    owner: str
    handle: str
    program_id: str
    program_revision: int
    logical_key: int
    frequency_hz: float
    velocity: float
    logical_bus: int

    def __post_init__(self) -> None:
        _identity("owner", self.owner)
        _identity("handle", self.handle)
        _identity("program_id", self.program_id)
        if self.program_revision <= 0:
            raise ProtocolValidationError("program_revision must be positive")
        if not 0 <= self.logical_key <= 127:
            raise ProtocolValidationError("logical_key must be in 0..127")
        if _finite("frequency_hz", self.frequency_hz) <= 0.0:
            raise ProtocolValidationError("frequency_hz must be positive")
        if not 0.0 <= _finite("velocity", self.velocity) <= 1.0:
            raise ProtocolValidationError("velocity must be in 0..1")
        if not 0 <= self.logical_bus <= 10:
            raise ProtocolValidationError("logical_bus must be in 0..10")


@dataclass(frozen=True, slots=True)
class NoteOff:
    owner: str
    handle: str
    release_velocity: float = 0.0

    def __post_init__(self) -> None:
        _identity("owner", self.owner)
        _identity("handle", self.handle)
        if not 0.0 <= _finite("release_velocity", self.release_velocity) <= 1.0:
            raise ProtocolValidationError("release_velocity must be in 0..1")


@dataclass(frozen=True, slots=True)
class VoiceSet:
    handle: str
    parameter: str
    value: float

    def __post_init__(self) -> None:
        _identity("handle", self.handle)
        _identity("parameter", self.parameter)
        _finite("value", self.value)
