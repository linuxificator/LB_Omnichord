from __future__ import annotations

import copy
import time
from typing import Any, Iterable


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
        double_tap_window: float = 0.55,
        replacement_duration: float = 0.42,
    ) -> None:
        self.capacity = max(1, int(capacity))
        self.blue_timeout = float(blue_timeout)
        self.double_tap_window = float(double_tap_window)
        self.replacement_duration = float(replacement_duration)

        self.controls: list[dict[str, Any]] = []
        self.values: dict[ControlKey, int] = {}
        self.clock = 0
        self.bindings: dict[ControlKey, dict[str, Any]] = {}
        self._target_to_control: dict[str, ControlKey] = {}
        self.learn_key: ControlKey | None = None
        self.blue_since: dict[ControlKey, float] = {}
        self._target_taps: dict[str, float] = {}

    @staticmethod
    def key(channel: int, controller: int) -> ControlKey:
        return (
            max(1, min(16, int(channel))),
            max(0, min(127, int(controller))),
        )

    @staticmethod
    def target_id(target: dict[str, Any]) -> str:
        return str(target["id"])

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
        return {
            "channel": key[0],
            "controller": key[1],
            "value": int(self.values.get(key, 0)),
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
        value = max(0, min(127, int(value)))
        previous = self.values.get(key)
        self.values[key] = value
        if previous is None or previous == value:
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
            model["state"] = self.status(key)
            model["evicting"] = evicting
            model["displayChannel"] = int(
                item.get("outgoingChannel", key[0]) if evicting else key[0]
            )
            model["displayController"] = int(
                item.get("outgoingController", key[1]) if evicting else key[1]
            )
            model["displayValue"] = int(
                item.get("outgoingValue", item.get("value", 0))
                if evicting
                else item.get("value", 0)
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

    def select_control(self, key: ControlKey, *, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else float(now)
        key = self.key(*key)
        if self.learn_key == key:
            self.learn_key = None
            self.blue_since.pop(key, None)
            return True
        previous_target = self.bindings.pop(key, None)
        if previous_target is not None:
            self._target_to_control.pop(self.target_id(previous_target), None)
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
        self._target_taps.pop(target_id, None)
        return True

    def is_target_bound(self, target: dict[str, Any]) -> bool:
        return self.target_id(target) in self._target_to_control

    def _unbind_target(self, target: dict[str, Any], now: float) -> bool:
        target_id = self.target_id(target)
        key = self._target_to_control.pop(target_id, None)
        self._target_taps.pop(target_id, None)
        if key is None:
            return False
        self.bindings.pop(key, None)
        self.blue_since[key] = now
        self.ensure_visible(key, now=now)
        return True

    def target_tapped(
        self,
        target: dict[str, Any],
        *,
        now: float | None = None,
    ) -> bool:
        now = time.monotonic() if now is None else float(now)
        target_id = self.target_id(target)
        if target_id not in self._target_to_control:
            self._target_taps.pop(target_id, None)
            return False
        previous = self._target_taps.get(target_id)
        self._target_taps[target_id] = now
        if previous is None or now - previous > self.double_tap_window:
            return False
        return self._unbind_target(target, now)

    def target_moved(
        self,
        target: dict[str, Any],
        *,
        now: float | None = None,
    ) -> bool:
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
        return [
            {
                "channel": key[0],
                "controller": key[1],
                "target": copy.deepcopy(target),
            }
            for key, target in sorted(self.bindings.items())
            if str(target.get("screen")) == str(screen)
        ]

    def replace_screen_bindings(
        self,
        screen: str,
        entries: Iterable[tuple[ControlKey, dict[str, Any]]],
        *,
        now: float | None = None,
    ) -> bool:
        now = time.monotonic() if now is None else float(now)
        screen = str(screen)
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
