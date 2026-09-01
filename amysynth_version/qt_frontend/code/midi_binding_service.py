from __future__ import annotations

import copy
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from midi_control import (
    NOTE_BUTTON_LAST,
    NOTE_BUTTON_OFFSET,
    PITCH_BEND_CONTROLLER,
    ControlKey,
    MidiControlState,
)


TargetNormalizer = Callable[[Any], dict[str, Any] | None]


@dataclass(frozen=True, slots=True)
class BindingEntry:
    key: ControlKey
    target_items: tuple[tuple[str, Any], ...]

    def target(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self.target_items))


@dataclass(frozen=True, slots=True)
class MidiBindingPresentation:
    indicator_items: tuple[tuple[tuple[str, Any], ...], ...]

    def qml_model(self) -> list[dict[str, Any]]:
        return [copy.deepcopy(dict(item)) for item in self.indicator_items]


class MidiBindingService:
    """Thread-safe binding normalization, persistence and presentation port."""

    def __init__(
        self,
        state: MidiControlState,
        lock: threading.Lock | threading.RLock,
    ) -> None:
        self.state = state
        self._lock = lock

    def normalize_entries(
        self,
        screen: str,
        data: Any,
        normalize_target: TargetNormalizer,
    ) -> tuple[BindingEntry, ...]:
        entries: list[BindingEntry] = []
        if not isinstance(data, list):
            return ()
        for raw in data:
            if not isinstance(raw, dict):
                continue
            target_data = raw.get("target")
            if not isinstance(target_data, dict):
                continue
            target_source = dict(target_data)
            target_source["screen"] = str(screen)
            target = normalize_target(target_source)
            if target is None:
                continue
            try:
                channel = int(raw.get("channel", 0))
                source_type = str(raw.get("source_type", "cc"))
                if source_type == "pitch_bend":
                    controller = PITCH_BEND_CONTROLLER
                elif source_type == "note_button":
                    controller = NOTE_BUTTON_OFFSET + int(raw.get("note", -1))
                else:
                    controller = int(raw.get("controller", -1))
                key = self.state.key(channel, controller)
            except (TypeError, ValueError):
                continue
            if source_type == "pitch_bend" and key[1] != PITCH_BEND_CONTROLLER:
                continue
            if source_type == "note_button" and not (
                NOTE_BUTTON_OFFSET <= key[1] <= NOTE_BUTTON_LAST
            ):
                continue
            if source_type not in ("cc", "pitch_bend", "note_button"):
                continue
            if source_type == "cc" and not 0 <= key[1] <= 127:
                continue
            entries.append(BindingEntry(key, tuple(sorted(copy.deepcopy(target).items()))))
        return tuple(entries)

    @staticmethod
    def as_state_entries(
        entries: tuple[BindingEntry, ...],
    ) -> list[tuple[ControlKey, dict[str, Any]]]:
        return [(entry.key, entry.target()) for entry in entries]

    def replace_screen(
        self,
        screen: str,
        entries: tuple[BindingEntry, ...],
    ) -> bool:
        with self._lock:
            return bool(
                self.state.replace_screen_bindings(
                    str(screen),
                    self.as_state_entries(entries),
                )
            )

    def serialize(self, screen: str) -> list[dict[str, Any]]:
        with self._lock:
            return cast(
                list[dict[str, Any]],
                self.state.serialize_bindings(str(screen)),
            )

    def presentation(self) -> MidiBindingPresentation:
        with self._lock:
            model = cast(list[dict[str, Any]], self.state.visible_model())
        return MidiBindingPresentation(
            tuple(tuple(sorted(copy.deepcopy(item).items())) for item in model)
        )
