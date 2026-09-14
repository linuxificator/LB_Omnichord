from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from external_chord_input import (  # noqa: E402
    ExternalChordAction,
    ExternalChordInputState,
)


class ExternalChordInputStateTests(unittest.TestCase):
    def test_first_key_starts_and_matching_release_stops(self) -> None:
        state = ExternalChordInputState()

        self.assertEqual(
            state.note_on(7, 60, screen_chord_held=False),
            (ExternalChordAction("start", (7, 60)),),
        )
        self.assertEqual(state.active, (7, 60))
        self.assertEqual(
            state.note_off(7, 60),
            (ExternalChordAction("stop", (7, 60)),),
        )
        self.assertIsNone(state.active)

    def test_last_still_held_key_takes_over_after_active_release(self) -> None:
        state = ExternalChordInputState()
        state.note_on(7, 60, screen_chord_held=False)

        self.assertEqual(state.note_on(7, 62, screen_chord_held=False), ())
        self.assertEqual(state.note_on(7, 64, screen_chord_held=False), ())
        self.assertEqual(
            state.note_off(7, 60),
            (
                ExternalChordAction("stop", (7, 60)),
                ExternalChordAction("start", (7, 64)),
            ),
        )
        self.assertEqual(state.active, (7, 64))

        self.assertEqual(state.note_off(7, 62), ())
        self.assertEqual(
            state.note_off(7, 64),
            (ExternalChordAction("stop", (7, 64)),),
        )

    def test_released_pending_key_never_starts(self) -> None:
        state = ExternalChordInputState()
        state.note_on(7, 60, screen_chord_held=False)
        state.note_on(7, 64, screen_chord_held=False)

        self.assertEqual(state.note_off(7, 64), ())
        self.assertEqual(
            state.note_off(7, 60),
            (ExternalChordAction("stop", (7, 60)),),
        )

    def test_screen_owned_note_pair_is_ignored_until_its_release(self) -> None:
        state = ExternalChordInputState()

        self.assertEqual(
            state.note_on(7, 60, screen_chord_held=True),
            (),
        )
        self.assertEqual(
            state.note_on(7, 60, screen_chord_held=False),
            (),
        )
        self.assertEqual(state.note_off(7, 60), ())
        self.assertIsNone(state.active)

        self.assertEqual(
            state.note_on(7, 60, screen_chord_held=False),
            (ExternalChordAction("start", (7, 60)),),
        )

    def test_reset_stops_active_and_discards_pending_and_ignored_keys(self) -> None:
        state = ExternalChordInputState()
        state.note_on(7, 60, screen_chord_held=False)
        state.note_on(7, 64, screen_chord_held=False)
        state.note_on(7, 67, screen_chord_held=True)

        self.assertEqual(
            state.reset(),
            (ExternalChordAction("stop", (7, 60)),),
        )
        self.assertIsNone(state.active)
        self.assertEqual(state.note_off(7, 60), ())
        self.assertEqual(state.note_off(7, 64), ())
        self.assertEqual(state.note_off(7, 67), ())


if __name__ == "__main__":
    unittest.main()
