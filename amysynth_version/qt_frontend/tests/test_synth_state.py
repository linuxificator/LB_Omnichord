from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from synth_state import SynthState  # noqa: E402


def control(key: str, default: float, minimum: float, maximum: float):
    return SimpleNamespace(
        key=key,
        label=key,
        group="extra",
        default=default,
        minimum=minimum,
        maximum=maximum,
        step=1.0,
        decimals=2,
    )


def definition(key: str, cutoff: float, resonance: float):
    return SimpleNamespace(
        key=key,
        label=key,
        controls=(
            control("filter_hz", cutoff, 20.0, 18000.0),
            control("resonance", resonance, 0.51, 12.0),
        ),
    )


class SynthStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.definitions = (
            definition("a", 500.0, 1.0),
            definition("b", 900.0, 2.0),
        )

    def test_preset_ui_transport_and_serialization_share_one_state(self) -> None:
        state = SynthState(self.definitions, 0)
        state.load_preset(
            {
                "selected": "b",
                "parameters": {
                    "b": {"filter_hz": 1200.0},
                },
            }
        )

        self.assertEqual(state.selected_index, 1)
        self.assertEqual(state.selected_values["filter_hz"], 1200.0)
        # Unspecified preset values come from the selected instrument default.
        self.assertEqual(state.selected_values["resonance"], 2.0)

        payload = state.transport_payload()
        self.assertEqual(payload["name"], "b")
        self.assertEqual(
            payload["params"],
            ["filter_hz", 1200.0, "resonance", 2.0],
        )

        self.assertTrue(state.set_control("filter_hz", 1350.0))
        self.assertEqual(state.selected_values["filter_hz"], 1350.0)
        self.assertEqual(
            state.transport_payload()["params"],
            ["filter_hz", 1350.0, "resonance", 2.0],
        )
        self.assertEqual(
            state.sparse_overrides(),
            {"b": {"filter_hz": 1350.0}},
        )

    def test_switch_away_and_back_retains_each_instrument_values(self) -> None:
        state = SynthState(self.definitions, 0)
        self.assertTrue(state.set_control("filter_hz", 700.0))
        self.assertTrue(state.select(1))
        self.assertTrue(state.set_control("filter_hz", 1100.0))
        self.assertTrue(state.select(0))
        self.assertEqual(state.selected_values["filter_hz"], 700.0)
        self.assertTrue(state.select(1))
        self.assertEqual(state.selected_values["filter_hz"], 1100.0)

    def test_copy_uses_same_complete_state(self) -> None:
        source = SynthState(self.definitions, 1)
        source.set_control("filter_hz", 1500.0)
        target = SynthState(self.definitions, 0)
        target.copy_from(source)
        self.assertEqual(target.selected_index, 1)
        self.assertEqual(target.transport_payload(), source.transport_payload())


if __name__ == "__main__":
    unittest.main()
