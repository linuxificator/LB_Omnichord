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


def _integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProtocolValidationError(f"{name} must be an integer")
    return value


def _number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProtocolValidationError(f"{name} must be numeric")
    return _finite(name, float(value))


def _atoms(kind: EventKind, values: tuple[str | int | float, ...]) -> None:
    expected = {
        "launch": 1,
        "gateBegin": 4,
        "rootStop": 1,
        "rootStart": 1,
        "noteOn": 11,
        "noteOff": 2,
        "voiceSet": 3,
        "drumHit": 8,
    }[kind]
    if len(values) != expected:
        raise ProtocolValidationError(
            f"{kind} requires {expected} atoms, received {len(values)}"
        )

    if kind in ("launch", "rootStop", "rootStart"):
        _identity(f"{kind} definition", str(values[0]))
        return
    if kind == "gateBegin":
        _identity("gate target", str(values[0]))
        _identity("gate token", str(values[1]))
        if _integer("gate duration_ticks", values[2]) <= 0:
            raise ProtocolValidationError("gate duration_ticks must be positive")
        scope = _identity("gate scope", str(values[3]))
        if scope not in ("drumHit", "launch", "noteOn"):
            raise ProtocolValidationError(
                "gate scope must be drumHit, launch or noteOn"
            )
        return
    if kind == "noteOn":
        _identity("note handle", str(values[0]))
        _identity("note owner", str(values[1]))
        _identity("note program", str(values[2]))
        if _integer("program revision", values[3]) <= 0:
            raise ProtocolValidationError("program revision must be positive")
        logical_key = _integer("logical key", values[4])
        if not 0 <= logical_key <= 127:
            raise ProtocolValidationError("logical key must be in 0..127")
        if _number("note frequency", values[5]) <= 0:
            raise ProtocolValidationError("note frequency must be positive")
        velocity = _number("note velocity", values[6])
        if not 0 <= velocity <= 1:
            raise ProtocolValidationError("note velocity must be in 0..1")
        _identity("note articulation", str(values[7]))
        accent = _integer("note accent", values[8])
        if accent not in (0, 1):
            raise ProtocolValidationError("note accent must be 0 or 1")
        accent_amount = _number("note accent amount", values[9])
        if not 0 <= accent_amount <= 1:
            raise ProtocolValidationError("note accent amount must be in 0..1")
        logical_bus = _integer("logical bus", values[10])
        if not 0 <= logical_bus <= 10:
            raise ProtocolValidationError("logical bus must be in 0..10")
        return
    if kind == "noteOff":
        _identity("note handle", str(values[0]))
        release_velocity = _number("release velocity", values[1])
        if not 0 <= release_velocity <= 1:
            raise ProtocolValidationError("release velocity must be in 0..1")
        return
    if kind == "voiceSet":
        _identity("voice handle", str(values[0]))
        _identity("voice parameter", str(values[1]))
        _number("voice value", values[2])
        return
    if kind == "drumHit":
        _identity("drum owner", str(values[0]))
        _identity("drum gate key", str(values[1]))
        _identity("drum program", str(values[2]))
        if _integer("drum program revision", values[3]) <= 0:
            raise ProtocolValidationError("drum program revision must be positive")
        _identity("drum pad", str(values[4]))
        logical_key = _integer("drum logical key", values[5])
        if not 0 <= logical_key <= 127:
            raise ProtocolValidationError("drum logical key must be in 0..127")
        velocity = _number("drum velocity", values[6])
        if not 0 <= velocity <= 1:
            raise ProtocolValidationError("drum velocity must be in 0..1")
        logical_bus = _integer("logical bus", values[7])
        if not 0 <= logical_bus <= 10:
            raise ProtocolValidationError("logical bus must be in 0..10")


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
        _atoms(self.kind, self.atoms)


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
