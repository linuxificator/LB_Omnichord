from __future__ import annotations

import copy
import time
from typing import Any, Iterable


PITCH_BEND_CONTROLLER = 128
NOTE_BUTTON_OFFSET = 256
NOTE_BUTTON_LAST = NOTE_BUTTON_OFFSET + 127

ControlKey = tuple[int, int]


class MidiControlState:
    """Own MIDI-CC learn, binding, visibility and eviction state.

    The class deliberately contains no Qt or AMY code.  It keeps the
    controller/slider relationship separate from the visible indicator bar:
    a green binding may be evicted from the bar without losing its musical
    target, and a later CC change can make it visible again.
    """

    def __init__(
        self,
        capacity: int = 17,
        *,
        blue_timeout: float = 30.0,
        replacement_duration: float = 0.42,
        preset_feedback_duration: float = 2.0,
    ) -> None:
        self.capacity = max(1, int(capacity))
        self.blue_timeout = float(blue_timeout)
        self.replacement_duration = float(replacement_duration)
        self.preset_feedback_duration = float(preset_feedback_duration)

        self.controls: list[dict[str, Any]] = []
        self.values: dict[ControlKey, int] = {}
        self.clock = 0
        self.bindings: dict[ControlKey, dict[str, Any]] = {}
        self._target_to_control: dict[str, ControlKey] = {}
        self.learn_key: ControlKey | None = None
        self.blue_since: dict[ControlKey, float] = {}
        self._preset_target_feedback: dict[str, tuple[str, float]] = {}

    @staticmethod
    def key(channel: int, controller: int) -> ControlKey:
        return (
            max(1, min(16, int(channel))),
            max(0, min(NOTE_BUTTON_LAST, int(controller))),
        )

    @staticmethod
    def target_id(target: dict[str, Any]) -> str:
        return str(target["id"])

    @staticmethod
    def source_type(key: ControlKey) -> str:
        controller = int(key[1])
        if controller == PITCH_BEND_CONTROLLER:
            return "pitch_bend"
        if NOTE_BUTTON_OFFSET <= controller <= NOTE_BUTTON_LAST:
            return "note_button"
        return "cc"

    @staticmethod
    def source_label(key: ControlKey) -> str:
        source_type = MidiControlState.source_type(key)
        if source_type == "pitch_bend":
            return f"CH{key[0]} PB"
        if source_type == "note_button":
            return f"CH{key[0]} N{key[1] - NOTE_BUTTON_OFFSET}"
        return f"CH{key[0]} CC{key[1]}"

    @staticmethod
    def value_max_for_key(key: ControlKey) -> int:
        return 16383 if MidiControlState.source_type(key) == "pitch_bend" else 127

    @staticmethod
    def default_value_for_key(key: ControlKey) -> int:
        return 8192 if MidiControlState.source_type(key) == "pitch_bend" else 0

    @staticmethod
    def display_value_for_key(key: ControlKey, value: int) -> int:
        maximum = MidiControlState.value_max_for_key(key)
        return int(round(max(0, min(maximum, int(value))) * 127 / maximum))

    def status(self, key: ControlKey) -> str:
        if self.learn_key == key:
            return "learn"
        if key in self.bindings:
            return "bound"
        if key in self.blue_since:
            return "blue"
        return "idle"

    def _visible(self, key: ControlKey) -> dict[str, Any] | None:
        return next(
            (
                item
                for item in self.controls
                if (item["channel"], item["controller"]) == key
            ),
            None,
        )

    def _eviction_candidate(
        self,
        now: float,
        *,
        exclude: ControlKey | None = None,
    ) -> dict[str, Any] | None:
        available = [
            item
            for item in self.controls
            if (item["channel"], item["controller"]) != exclude
            and float(item.get("replacementUntil", 0.0)) <= now
        ]
        ordinary = [
            item
            for item in available
            if self.status((item["channel"], item["controller"]))
            not in ("learn", "blue")
        ]
        if ordinary:
            return min(ordinary, key=lambda item: int(item["lastSeen"]))

        # A red learn control is never evicted. Blue controls are normally
        # protected, but the oldest blue control may leave early when every
        # available slot is protected, as required by the design contract.
        blues = [
            item
            for item in available
            if self.status((item["channel"], item["controller"])) == "blue"
        ]
        if not blues:
            return None
        return min(
            blues,
            key=lambda item: self.blue_since.get(
                (item["channel"], item["controller"]),
                now,
            ),
        )

    def _new_visible_item(self, key: ControlKey) -> dict[str, Any]:
        value = int(self.values.get(key, self.default_value_for_key(key)))
        return {
            "channel": key[0],
            "controller": key[1],
            "value": value,
            "lastSeen": int(self.clock),
            "pulse": int(self.clock),
            "replaced": 0,
        }

    def ensure_visible(
        self,
        key: ControlKey,
        *,
        now: float | None = None,
        allow_eviction: bool = True,
    ) -> bool:
        now = time.monotonic() if now is None else float(now)
        if self._visible(key) is not None:
            return True
        new_item = self._new_visible_item(key)
        if len(self.controls) < self.capacity:
            self.controls.append(new_item)
            return True
        if not allow_eviction:
            return False

        victim = self._eviction_candidate(now, exclude=key)
        if victim is None:
            return False
        index = self.controls.index(victim)
        victim_key = (int(victim["channel"]), int(victim["controller"]))
        if self.status(victim_key) == "blue":
            self.blue_since.pop(victim_key, None)

        new_item.update(
            {
                "replaced": int(self.clock),
                "replacementUntil": now + self.replacement_duration,
                "outgoingChannel": victim_key[0],
                "outgoingController": victim_key[1],
                "outgoingValue": int(victim.get("value", 0)),
            }
        )
        self.controls[index] = new_item
        return True

    def observe(
        self,
        channel: int,
        controller: int,
        value: int,
        *,
        now: float | None = None,
    ) -> tuple[bool, dict[str, Any] | None, ControlKey | None]:
        """Record one CC packet and return a target only for a real change."""
        now = time.monotonic() if now is None else float(now)
        key = self.key(channel, controller)
        source_type = self.source_type(key)
        value = max(0, min(self.value_max_for_key(key), int(value)))
        previous = self.values.get(key)
        self.values[key] = value
        if previous is None:
            if source_type == "pitch_bend":
                previous = self.default_value_for_key(key)
            elif source_type == "note_button":
                if value <= 0:
                    return False, None, None
            else:
                return False, None, None
        if previous == value:
            return False, None, None

        # Blue marks a recently unbound control.  Its next genuine movement
        # makes it an ordinary unbound control again; repeated packets do not.
        self.blue_since.pop(key, None)
        self.clock += 1
        item = self._visible(key)
        if item is None:
            self.ensure_visible(key, now=now)
            item = self._visible(key)
        if item is not None:
            item.update(
                {
                    "value": value,
                    "lastSeen": self.clock,
                    "pulse": self.clock,
                }
            )
        target = self.bindings.get(key)
        return True, copy.deepcopy(target) if target else None, key

    def visible_model(self, *, now: float | None = None) -> list[dict[str, Any]]:
        now = time.monotonic() if now is None else float(now)
        result: list[dict[str, Any]] = []
        for item in self.controls:
            model = dict(item)
            key = (int(item["channel"]), int(item["controller"]))
            evicting = float(item.get("replacementUntil", 0.0)) > now
            display_key = (
                int(item.get("outgoingChannel", key[0])),
                int(item.get("outgoingController", key[1])),
            ) if evicting else key
            raw_display_value = int(
                item.get("outgoingValue", item.get("value", 0))
                if evicting
                else item.get("value", 0)
            )
            model["state"] = self.status(key)
            model["evicting"] = evicting
            model["inputType"] = self.source_type(key)
            display_type = self.source_type(display_key)
            display_target = self.bindings.get(display_key)
            if (
                display_type == "cc"
                and isinstance(display_target, dict)
                and str(display_target.get("kind", "")) == "button"
            ):
                display_type = "button"
            model["displayType"] = display_type
            model["displayLabel"] = self.source_label(display_key)
            model["displayChannel"] = int(display_key[0])
            model["displayController"] = int(display_key[1])
            model["displayValue"] = self.display_value_for_key(
                display_key,
                raw_display_value,
            )
            model["rawValue"] = int(item.get("value", 0))
            model["buttonDown"] = (
                display_type in ("button", "note_button")
                and raw_display_value > 0
            )
            result.append(model)
        return result

    def set_capacity(self, capacity: int, *, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else float(now)
        capacity = max(1, int(capacity))
        changed = capacity != self.capacity
        self.capacity = capacity
        while len(self.controls) > capacity:
            victim = self._eviction_candidate(now)
            if victim is None:
                break
            key = (int(victim["channel"]), int(victim["controller"]))
            self.controls.remove(victim)
            self.blue_since.pop(key, None)
            changed = True
        return changed

    def indicator_clicked(
        self,
        key: ControlKey,
        *,
        now: float | None = None,
    ) -> bool:
        """Apply the single-click contract for a controller indicator.

        A bound (green) indicator is an unlink action only.  An unbound grey
        or blue indicator starts learn, while clicking the already-red learn
        indicator cancels learn.  Keeping these transitions here prevents the
        QML button from accidentally combining unlink and relearn.
        """
        now = time.monotonic() if now is None else float(now)
        key = self.key(*key)
        if self.learn_key == key:
            self.learn_key = None
            self.blue_since.pop(key, None)
            return True

        bound_target = self.bindings.get(key)
        if bound_target is not None:
            return self._unbind_target(bound_target, now)

        self.learn_key = key
        self.blue_since.pop(key, None)
        self.ensure_visible(key, now=now)
        return True

    def bind_learned_target(
        self,
        target: dict[str, Any],
        *,
        now: float | None = None,
    ) -> bool:
        now = time.monotonic() if now is None else float(now)
        if self.learn_key is None:
            return False
        key = self.learn_key
        target_id = self.target_id(target)

        previous_target = self.bindings.get(key)
        if previous_target is not None:
            self._target_to_control.pop(self.target_id(previous_target), None)

        displaced = self._target_to_control.get(target_id)
        if displaced is not None and displaced != key:
            self.bindings.pop(displaced, None)
            self.blue_since[displaced] = now
            self.ensure_visible(displaced, now=now)

        self.bindings[key] = copy.deepcopy(target)
        self._target_to_control[target_id] = key
        self.blue_since.pop(key, None)
        self.learn_key = None
        self.ensure_visible(key, now=now)
        return True

    def is_target_bound(self, target: dict[str, Any]) -> bool:
        return self.target_id(target) in self._target_to_control

    def target_visual_state(
        self,
        target: dict[str, Any],
        *,
        now: float | None = None,
    ) -> str:
        now = time.monotonic() if now is None else float(now)
        target_id = self.target_id(target)
        feedback = self._preset_target_feedback.get(target_id)
        if feedback is not None and feedback[1] > now:
            return feedback[0]
        return "bound" if target_id in self._target_to_control else "idle"

    def expire_preset_feedback(self, *, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else float(now)
        expired = [
            target_id
            for target_id, (_, until) in self._preset_target_feedback.items()
            if until <= now
        ]
        for target_id in expired:
            self._preset_target_feedback.pop(target_id, None)
        return bool(expired)

    def has_preset_feedback(self, *, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else float(now)
        return any(
            until > now
            for _, until in self._preset_target_feedback.values()
        )

    def preset_conflict_target_ids(
        self,
        entries: Iterable[tuple[ControlKey, dict[str, Any]]],
    ) -> set[str]:
        conflicts: set[str] = set()
        for raw_key, target in entries:
            key = self.key(*raw_key)
            old_target = self.bindings.get(key)
            if old_target is None:
                continue
            old_id = self.target_id(old_target)
            new_id = self.target_id(target)
            if old_id != new_id:
                conflicts.update((old_id, new_id))
        return conflicts

    def _unbind_target(self, target: dict[str, Any], now: float) -> bool:
        target_id = self.target_id(target)
        key = self._target_to_control.pop(target_id, None)
        if key is None:
            return False
        self.bindings.pop(key, None)
        self.blue_since[key] = now
        self.ensure_visible(key, now=now)
        return True

    def release_target_for_manual_edit(
        self,
        target: dict[str, Any],
        *,
        now: float | None = None,
    ) -> bool:
        """Release MIDI ownership immediately before a genuine UI edit."""
        now = time.monotonic() if now is None else float(now)
        return self._unbind_target(target, now)

    def expire_blue(self, *, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else float(now)
        expired = [
            key
            for key, started in self.blue_since.items()
            if now - started >= self.blue_timeout
        ]
        if not expired:
            return False
        for key in expired:
            self.blue_since.pop(key, None)
            item = self._visible(key)
            if item is not None:
                self.controls.remove(item)
        return True

    def omni_led_state(self) -> str:
        if self.learn_key is not None:
            return "learn"
        if self.blue_since:
            return "blue"
        return "idle"

    def serialize_bindings(self, screen: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for key, target in sorted(self.bindings.items()):
            if str(target.get("screen")) != str(screen):
                continue
            entry = {
                "channel": key[0],
                "controller": key[1],
                "target": copy.deepcopy(target),
            }
            source_type = self.source_type(key)
            if source_type != "cc":
                entry["source_type"] = source_type
                if source_type == "note_button":
                    entry["note"] = key[1] - NOTE_BUTTON_OFFSET
            result.append(entry)
        return result

    def replace_screen_bindings(
        self,
        screen: str,
        entries: Iterable[tuple[ControlKey, dict[str, Any]]],
        *,
        now: float | None = None,
    ) -> bool:
        now = time.monotonic() if now is None else float(now)
        screen = str(screen)
        entries = list(entries)
        previous_bindings = {
            key: copy.deepcopy(target)
            for key, target in self.bindings.items()
        }
        self._preset_target_feedback.clear()
        removed = [
            key
            for key, target in self.bindings.items()
            if str(target.get("screen")) == screen
        ]
        for key in removed:
            target = self.bindings.pop(key)
            self._target_to_control.pop(self.target_id(target), None)

        for raw_key, target in entries:
            key = self.key(*raw_key)
            target_id = self.target_id(target)
            previous_target = previous_bindings.get(key)
            if (
                previous_target is not None
                and self.target_id(previous_target) != target_id
            ):
                until = now + self.preset_feedback_duration
                self._preset_target_feedback[
                    self.target_id(previous_target)
                ] = ("preset-displaced", until)
                self._preset_target_feedback[target_id] = (
                    "preset-incoming",
                    until,
                )

            old_target = self.bindings.pop(key, None)
            if old_target is not None:
                self._target_to_control.pop(self.target_id(old_target), None)
            old_key = self._target_to_control.pop(target_id, None)
            if old_key is not None:
                self.bindings.pop(old_key, None)

            self.bindings[key] = copy.deepcopy(target)
            self._target_to_control[target_id] = key
            self.blue_since.pop(key, None)
            self.ensure_visible(key, now=now)
        return bool(removed) or bool(self.bindings)
