from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ExternalChordKey = tuple[int, int]
ExternalChordActionKind = Literal["start", "stop"]


@dataclass(frozen=True, slots=True)
class ExternalChordAction:
    kind: ExternalChordActionKind
    key: ExternalChordKey


class ExternalChordInputState:
    """Monophonic external-key priority without musical or transport policy."""

    def __init__(self) -> None:
        self._active: ExternalChordKey | None = None
        self._held_order: list[ExternalChordKey] = []
        self._ignored: set[ExternalChordKey] = set()

    @property
    def active(self) -> ExternalChordKey | None:
        return self._active

    def note_on(
        self,
        channel: int,
        note: int,
        *,
        screen_chord_held: bool,
    ) -> tuple[ExternalChordAction, ...]:
        key = (int(channel), int(note))
        if key in self._ignored or key in self._held_order:
            return ()
        if screen_chord_held:
            self._ignored.add(key)
            return ()

        self._held_order.append(key)
        if self._active is not None:
            return ()
        self._active = key
        return (ExternalChordAction("start", key),)

    def note_off(
        self,
        channel: int,
        note: int,
    ) -> tuple[ExternalChordAction, ...]:
        key = (int(channel), int(note))
        if key in self._ignored:
            self._ignored.discard(key)
            return ()
        if key not in self._held_order:
            return ()

        self._held_order.remove(key)
        if key != self._active:
            return ()

        actions = [ExternalChordAction("stop", key)]
        self._active = self._held_order[-1] if self._held_order else None
        if self._active is not None:
            actions.append(ExternalChordAction("start", self._active))
        return tuple(actions)

    def reset(self) -> tuple[ExternalChordAction, ...]:
        actions = (
            (ExternalChordAction("stop", self._active),)
            if self._active is not None
            else ()
        )
        self._active = None
        self._held_order.clear()
        self._ignored.clear()
        return actions
