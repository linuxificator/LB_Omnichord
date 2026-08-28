from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from midi_control import MidiControlState  # noqa: E402
from midi_player import MidiPlayerBackend  # noqa: E402


class _Owner:
    def __init__(self, preset_dir: Path, selected: int = 2) -> None:
        self._preset_dir = preset_dir
        self._synths: tuple[object, ...] = ()
        self.selectedPreset = selected

    def _preset_path(self, number: int) -> Path:
        return self._preset_dir / f"p{number}.json"


def _binding(
    screen: str,
    channel: int,
    controller: int,
) -> dict[str, object]:
    target: dict[str, object]
    if screen == "midi":
        target = {"screen": screen, "kind": "volume", "row": 0}
    else:
        target = {"screen": screen, "kind": "volume", "role": "chord"}
    return {
        "channel": channel,
        "controller": controller,
        "target": target,
    }


class MidiBindingLocationTests(unittest.TestCase):
    def _backend(
        self,
        omni_dir: Path,
        midi_dir: Path,
    ) -> MidiPlayerBackend:
        backend = MidiPlayerBackend.__new__(MidiPlayerBackend)
        backend.owner = _Owner(omni_dir)
        backend.definitions = ()
        backend._selected_preset = 2
        backend._midi_control_state = MidiControlState()
        backend._preset_binding_locations = {}
        backend._preset_path = lambda number: midi_dir / f"m{number}.json"
        return backend

    def test_inactive_preset_index_excludes_both_selected_presets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            omni_dir = root / "omni"
            midi_dir = root / "midi"
            omni_dir.mkdir()
            midi_dir.mkdir()
            for screen, number, directory_path in (
                ("omni", 2, omni_dir),
                ("omni", 3, omni_dir),
                ("midi", 2, midi_dir),
                ("midi", 4, midi_dir),
            ):
                prefix = "p" if screen == "omni" else "m"
                directory_path.joinpath(f"{prefix}{number}.json").write_text(
                    json.dumps(
                        {"midi_control_bindings": [_binding(screen, 7, 74)]}
                    ),
                    encoding="utf-8",
                )

            backend = self._backend(omni_dir, midi_dir)
            backend._refresh_preset_binding_locations()

            self.assertEqual(
                backend._binding_feedback_locations((7, 74), None),
                (("midi", 4), ("omni", 3)),
            )

    def test_active_binding_wins_over_stored_inactive_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backend = self._backend(root, root)
            backend._preset_binding_locations = {
                (7, 74): (("midi", 4), ("omni", 3))
            }

            self.assertEqual(
                backend._binding_feedback_locations(
                    (7, 74),
                    {"screen": "midi", "kind": "volume", "row": 0},
                ),
                (("midi", 2),),
            )


if __name__ == "__main__":
    unittest.main()
