from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from midi_control import MidiControlState  # noqa: E402


def target(name: str, screen: str = "midi") -> dict[str, object]:
    return {
        "id": f"{screen}:{name}",
        "screen": screen,
        "kind": "volume",
        "row": 0,
    }


def change(
    state: MidiControlState,
    controller: int,
    *,
    channel: int = 1,
    now: float,
    value: int = 1,
) -> tuple[bool, dict[str, object] | None, tuple[int, int] | None]:
    state.observe(channel, controller, value - 1, now=now - 0.01)
    return state.observe(channel, controller, value, now=now)


class MidiControlStateTests(unittest.TestCase):
    def test_true_lru_and_outgoing_red_replacement_model(self) -> None:
        state = MidiControlState(capacity=3)
        change(state, 10, now=1.0)
        change(state, 11, now=2.0)
        change(state, 12, now=3.0)
        state.observe(1, 10, 2, now=4.0)

        change(state, 13, now=5.0)

        self.assertEqual(
            {(item["channel"], item["controller"]) for item in state.controls},
            {(1, 10), (1, 12), (1, 13)},
        )
        replacing = next(
            item for item in state.visible_model(now=5.1)
            if item["controller"] == 13
        )
        self.assertTrue(replacing["evicting"])
        self.assertEqual(replacing["displayController"], 11)
        settled = next(
            item for item in state.visible_model(now=5.5)
            if item["controller"] == 13
        )
        self.assertFalse(settled["evicting"])
        self.assertEqual(settled["displayController"], 13)

    def test_red_learn_is_unique_toggleable_and_never_evicted(self) -> None:
        state = MidiControlState(capacity=2)
        change(state, 1, now=1.0)
        change(state, 2, now=2.0)
        state.select_control((1, 1), now=3.0)
        self.assertEqual(state.status((1, 1)), "learn")

        change(state, 3, now=4.0)
        self.assertIsNotNone(state._visible((1, 1)))
        self.assertIsNone(state._visible((1, 2)))

        state.select_control((1, 1), now=5.0)
        self.assertEqual(state.status((1, 1)), "idle")
        state.select_control((1, 3), now=6.0)
        self.assertEqual(state.status((1, 3)), "learn")
        self.assertEqual(state.status((1, 1)), "idle")

    def test_hidden_green_binding_survives_and_returns_on_activity(self) -> None:
        state = MidiControlState(capacity=2)
        change(state, 1, now=1.0)
        change(state, 2, now=2.0)
        state.select_control((1, 1), now=2.1)
        state.bind_learned_target(target("volume"), now=2.2)

        change(state, 3, now=3.0)
        self.assertIsNone(state._visible((1, 1)))
        self.assertIn((1, 1), state.bindings)

        changed, mapped, key = state.observe(1, 1, 2, now=4.0)
        self.assertTrue(changed)
        self.assertEqual(key, (1, 1))
        self.assertEqual(mapped, target("volume"))
        self.assertIsNotNone(state._visible((1, 1)))

    def test_one_to_one_replacement_and_double_tap_unbind(self) -> None:
        state = MidiControlState(capacity=3)
        change(state, 1, now=1.0)
        change(state, 2, now=2.0)
        shared = target("shared")

        state.select_control((1, 1), now=3.0)
        state.bind_learned_target(shared, now=3.1)
        state.select_control((1, 2), now=3.2)
        state.bind_learned_target(shared, now=3.3)

        self.assertNotIn((1, 1), state.bindings)
        self.assertEqual(state.status((1, 1)), "blue")
        self.assertEqual(state.status((1, 2)), "bound")
        self.assertFalse(state.target_tapped(shared, now=4.0))
        self.assertTrue(state.target_tapped(shared, now=4.3))
        self.assertEqual(state.status((1, 2)), "blue")
        self.assertEqual(state.omni_led_state(), "blue")

        self.assertTrue(state.expire_blue(now=35.0))
        self.assertEqual(state.omni_led_state(), "idle")
        self.assertIsNone(state._visible((1, 1)))
        self.assertIsNone(state._visible((1, 2)))

    def test_clicking_green_starts_relearn_and_second_click_cancels_to_off(self) -> None:
        state = MidiControlState(capacity=2)
        change(state, 1, now=1.0)
        binding = target("volume")
        state.select_control((1, 1), now=2.0)
        state.bind_learned_target(binding, now=2.1)
        self.assertEqual(state.status((1, 1)), "bound")

        state.select_control((1, 1), now=3.0)
        self.assertEqual(state.status((1, 1)), "learn")
        self.assertNotIn((1, 1), state.bindings)
        state.select_control((1, 1), now=3.1)
        self.assertEqual(state.status((1, 1)), "idle")

    def test_real_move_unbinds_and_oldest_blue_can_leave_early(self) -> None:
        state = MidiControlState(capacity=2)
        first = target("first")
        second = target("second")
        for controller, binding, start in (
            (1, first, 1.0),
            (2, second, 2.0),
        ):
            change(state, controller, now=start)
            state.select_control((1, controller), now=start + 0.1)
            state.bind_learned_target(binding, now=start + 0.2)
            self.assertTrue(state.target_moved(binding, now=start + 0.3))

        change(state, 3, now=4.0)
        self.assertIsNone(state._visible((1, 1)))
        self.assertNotIn((1, 1), state.blue_since)
        self.assertEqual(state.status((1, 2)), "blue")

    def test_genuine_movement_returns_blue_control_to_idle(self) -> None:
        state = MidiControlState(capacity=2)
        binding = target("volume")
        change(state, 1, now=1.0)
        state.select_control((1, 1), now=2.0)
        state.bind_learned_target(binding, now=2.1)
        self.assertTrue(state.target_moved(binding, now=3.0))
        self.assertEqual(state.status((1, 1)), "blue")

        changed, mapped, key = state.observe(1, 1, 1, now=3.5)
        self.assertFalse(changed)
        self.assertIsNone(mapped)
        self.assertIsNone(key)
        self.assertEqual(state.status((1, 1)), "blue")

        changed, mapped, key = state.observe(1, 1, 2, now=4.0)

        self.assertTrue(changed)
        self.assertEqual(key, (1, 1))
        self.assertIsNone(mapped)
        self.assertEqual(state.status((1, 1)), "idle")
        self.assertEqual(state.omni_led_state(), "idle")
        visible = state._visible((1, 1))
        self.assertIsNotNone(visible)
        assert visible is not None
        self.assertEqual(visible["value"], 2)

    def test_screen_specific_bindings_round_trip(self) -> None:
        state = MidiControlState(capacity=4)
        midi_target = target("midi")
        omni_target = target("omni", screen="omni")
        state.replace_screen_bindings(
            "midi",
            [((1, 7), midi_target)],
            now=1.0,
        )
        state.replace_screen_bindings(
            "omni",
            [((2, 8), omni_target)],
            now=2.0,
        )

        self.assertEqual(
            state.serialize_bindings("midi"),
            [{"channel": 1, "controller": 7, "target": midi_target}],
        )
        self.assertEqual(
            state.serialize_bindings("omni"),
            [{"channel": 2, "controller": 8, "target": omni_target}],
        )

    def test_preset_binding_conflict_prefers_incoming_and_expires_feedback(self) -> None:
        state = MidiControlState(capacity=4, preset_feedback_duration=2.0)
        displaced = target("old", screen="omni")
        incoming = target("new", screen="omni")
        state.replace_screen_bindings(
            "omni",
            [((1, 7), displaced)],
            now=1.0,
        )

        entries = [((1, 7), incoming)]
        self.assertEqual(
            state.preset_conflict_target_ids(entries),
            {displaced["id"], incoming["id"]},
        )
        state.replace_screen_bindings("omni", entries, now=10.0)

        self.assertFalse(state.is_target_bound(displaced))
        self.assertTrue(state.is_target_bound(incoming))
        self.assertEqual(
            state.target_visual_state(displaced, now=11.99),
            "preset-displaced",
        )
        self.assertEqual(
            state.target_visual_state(incoming, now=11.99),
            "preset-incoming",
        )
        self.assertFalse(state.expire_preset_feedback(now=11.99))
        self.assertTrue(state.expire_preset_feedback(now=12.0))
        self.assertEqual(state.target_visual_state(displaced, now=12.0), "idle")
        self.assertEqual(state.target_visual_state(incoming, now=12.0), "bound")


if __name__ == "__main__":
    unittest.main()
