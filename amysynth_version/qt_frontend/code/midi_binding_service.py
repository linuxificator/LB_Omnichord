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
    activate_on_input: bool = False

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
            source_type = str(raw.get("source_type", "cc"))
            target_source = dict(target_data)
            target_source["screen"] = str(screen)
            # Presets written before global bend was separated from static
            # tuning used Pitch Bend as a 415..466 Hz reference controller.
            # Preserve those user presets by migrating that exact declaration
            # to the transient OMNI-owned AMY bend target on load.
            if (
                source_type == "pitch_bend"
                and str(screen) == "omni"
                and str(target_source.get("kind", "")) == "tuning_reference"
            ):
                target_source["kind"] = "pitch_bend"
            target = normalize_target(target_source)
            if target is None:
                continue
            try:
                if source_type == "osc":
                    address = str(raw.get("address", ""))
                    argument = int(raw.get("argument", 0))
                    value_type = str(raw.get("value_type", "continuous"))
                    if (
                        not address.startswith("/")
                        or argument < 0
                        or value_type not in ("continuous", "button")
                    ):
                        continue
                    key = self.state.osc_key(address, argument, value_type)
                elif source_type == "pitch_bend":
                    channel = int(raw.get("channel", 0))
                    controller = PITCH_BEND_CONTROLLER
                    key = self.state.key(channel, controller)
                elif source_type == "note_button":
                    channel = int(raw.get("channel", 0))
                    controller = NOTE_BUTTON_OFFSET + int(raw.get("note", -1))
                    key = self.state.key(channel, controller)
                else:
                    channel = int(raw.get("channel", 0))
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
            if source_type not in ("cc", "pitch_bend", "note_button", "osc"):
                continue
            if source_type == "cc" and not 0 <= key[1] <= 127:
                continue
            activate_on_input = raw.get("activate_on_input", False)
            if not isinstance(activate_on_input, bool):
                continue
            entries.append(
                BindingEntry(
                    key,
                    tuple(sorted(copy.deepcopy(target).items())),
                    activate_on_input,
                )
            )
        return tuple(entries)

    @staticmethod
    def as_state_entries(
        entries: tuple[BindingEntry, ...],
    ) -> list[tuple[ControlKey, dict[str, Any]]]:
        return [(entry.key, entry.target()) for entry in entries]

    @staticmethod
    def as_preset_state_entries(
        entries: tuple[BindingEntry, ...],
    ) -> list[tuple[ControlKey, dict[str, Any], bool]]:
        return [
            (entry.key, entry.target(), entry.activate_on_input)
            for entry in entries
        ]

    def replace_screen(
        self,
        screen: str,
        entries: tuple[BindingEntry, ...],
    ) -> bool:
        with self._lock:
            return bool(
                self.state.replace_screen_bindings(
                    str(screen),
                    self.as_preset_state_entries(entries),
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
