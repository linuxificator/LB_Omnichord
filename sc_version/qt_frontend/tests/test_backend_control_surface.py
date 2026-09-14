from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[1]
SUPPORT = ROOT / "tests" / "support"
CODE = ROOT / "code"
for module_dir in (SUPPORT, CODE):
    if str(module_dir) not in sys.path:
        sys.path.insert(0, str(module_dir))

from backend_control_surface import BackendControlSurface  # noqa: E402


class BackendControlSurfaceTests(unittest.TestCase):
    def test_browser_helpers_remain_in_test_process_adapter(self) -> None:
        midi = SimpleNamespace(
            setDrumKitIndex=Mock(),
            toggleSynthKind=Mock(),
            setSynthBrowserIndex=Mock(),
            selectSampleChoice=Mock(),
            toggleSustain=Mock(),
        )
        adapter = BackendControlSurface(SimpleNamespace(midiPlayer=midi))

        adapter.setMidiDrumKitIndex(3)
        adapter.toggleMidiSynthKind(2)
        adapter.setMidiSynthBrowserIndex(2, 7)
        adapter.selectMidiSampleChoice(2, 91)
        adapter.toggleMidiSustain(2)

        midi.setDrumKitIndex.assert_called_once_with(3)
        midi.toggleSynthKind.assert_called_once_with(2)
        midi.setSynthBrowserIndex.assert_called_once_with(2, 7)
        midi.selectSampleChoice.assert_called_once_with(2, 91)
        midi.toggleSustain.assert_called_once_with(2)

    def test_endurance_state_helpers_are_idempotent_public_actions(self) -> None:
        backend = SimpleNamespace(
            rhythmRunning=False,
            bassRunning=True,
            chordArpeggioEnabled=False,
            toggleRhythm=Mock(),
            toggleBassRunning=Mock(),
            toggleChordArpeggio=Mock(),
        )
        adapter = BackendControlSurface(backend)

        adapter.ensureRhythmRunning(True)
        adapter.ensureBassRunning(True)
        adapter.ensureChordArpeggioRunning(True)

        backend.toggleRhythm.assert_called_once_with()
        backend.toggleBassRunning.assert_not_called()
        backend.toggleChordArpeggio.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
