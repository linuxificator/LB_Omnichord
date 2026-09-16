from __future__ import annotations

import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from app_core import InstrumentBackend  # noqa: E402


class ChordTapHarness:
    def __init__(self, *, audible: bool) -> None:
        self._external_chord_input = type("External", (), {"active": None})()
        self._pressed_chords: set[tuple[int, int]] = set()
        self._pressed_chord_order: list[tuple[int, int]] = []
        self._promoted_chords: set[tuple[int, int]] = set()
        self._sounding_chords: set[tuple[int, int]] = set()
        self._chord_tap_audible = audible
        self._active_row = -1
        self._active_root_semitone = -1
        self.manual: list[tuple[str, tuple[int, int] | None]] = []
        self.selected: list[tuple[int, int]] = []
        self.state_updates = 0
        self.hold_updates = 0

    def _valid_chord_selection(self, row: int, root: int) -> bool:
        return 0 <= row < 4 and 0 <= root < 12

    def _debug(self, *_args: object, **_kwargs: object) -> None:
        pass

    def _debug_chord_state(self) -> dict[str, object]:
        return {}

    def _set_active_chord(self, row: int, root: int) -> None:
        self._active_row = row
        self._active_root_semitone = root
        self.selected.append((row, root))

    def _send_chord_state(self, *, play_now: bool) -> None:
        self.state_updates += 1

    def _send_manual_chord(
        self,
        action: str,
        key: tuple[int, int] | None = None,
        notes: list[int] | None = None,
        **_kwargs: object,
    ) -> None:
        self.manual.append((action, key))

    def _current_notes(self) -> list[int]:
        return [60, 64, 67]

    def _update_hold_override(self) -> None:
        self.hold_updates += 1

    def _finalize_chord_release(self, key: tuple[int, int]) -> None:
        InstrumentBackend._finalize_chord_release(self, key)  # type: ignore[arg-type]


class ChordTapAuditionTests(unittest.TestCase):
    def test_audible_tap_starts_on_press_and_stops_on_release(self) -> None:
        backend = ChordTapHarness(audible=True)

        InstrumentBackend.pressChord(backend, 0, 0)  # type: ignore[arg-type]
        InstrumentBackend.releaseChord(backend, 0, 0)  # type: ignore[arg-type]

        self.assertEqual(backend.selected, [(0, 0)])
        self.assertEqual(backend.state_updates, 1)
        self.assertEqual(backend.manual, [("start", (0, 0)), ("stop", (0, 0))])
        self.assertFalse(backend._sounding_chords)

    def test_silent_tap_still_selects_chord_without_start_or_stop(self) -> None:
        backend = ChordTapHarness(audible=False)

        InstrumentBackend.pressChord(backend, 1, 5)  # type: ignore[arg-type]
        InstrumentBackend.releaseChord(backend, 1, 5)  # type: ignore[arg-type]

        self.assertEqual(backend.selected, [(1, 5)])
        self.assertEqual(backend.state_updates, 1)
        self.assertEqual(backend.manual, [])

    def test_hold_starts_at_framework_promotion_when_tap_is_silent(self) -> None:
        backend = ChordTapHarness(audible=False)

        InstrumentBackend.pressChord(backend, 2, 7)  # type: ignore[arg-type]
        InstrumentBackend.promoteChordHold(backend, 2, 7)  # type: ignore[arg-type]
        InstrumentBackend.releaseChord(backend, 2, 7)  # type: ignore[arg-type]

        self.assertEqual(backend.manual, [("start", (2, 7)), ("stop", (2, 7))])
        self.assertEqual(backend.hold_updates, 2)
        self.assertFalse(backend._promoted_chords)


if __name__ == "__main__":
    unittest.main()
