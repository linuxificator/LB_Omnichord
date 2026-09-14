from __future__ import annotations

from array import array
import math
from pathlib import Path
import sys
import tempfile
import unittest
import wave


ROOT = Path(__file__).resolve().parents[1]
ENDURANCE = ROOT / "tests" / "endurance"
sys.path.insert(0, str(ENDURANCE))

from sc_endurance import action_cycle, analyze_wave  # noqa: E402


class _Synth:
    def __init__(self, kind: str) -> None:
        self.kind = kind


class SuperColliderEnduranceTests(unittest.TestCase):
    def test_cycle_covers_timing_audio_catalogue_and_external_controls(self) -> None:
        actions = list(
            action_cycle(
                0,
                [_Synth("synth") for _ in range(8)]
                + [_Synth("sample") for _ in range(8)],
            )
        )
        names = {action.name for action in actions}
        self.assertTrue(
            {
                "setRhythmIndex", "setRhythmFillDensity", "setChordArpeggioRate",
                "setChordSynthIndex", "setStrumSynthIndex", "setBassSynthIndex",
                "setMidiSynthIndex", "injectMidiNote", "injectMidiPitchBend",
                "injectOscControl", "setDrumKitIndex", "setMidiDrumKitIndex",
                "panic",
                "ensureRhythmRunning", "ensureBassRunning",
                "ensureChordArpeggioRunning",
            }.issubset(names)
        )
        self.assertEqual(
            {action.args[0] for action in actions if action.name == "setRhythmIndex"},
            set(range(18)),
        )
        self.assertEqual(
            {action.args[0] for action in actions if action.name == "setDrumKitIndex"},
            set(range(15)),
        )
        self.assertEqual(
            {
                action.args[0]
                for action in actions
                if action.name == "setMidiDrumKitIndex"
            },
            set(range(15)),
        )

    def test_audio_analyzer_reports_level_clipping_and_silence(self) -> None:
        rate = 8_000
        samples = array("h")
        for index in range(rate):
            value = round(4000 * math.sin(2 * math.pi * 440 * index / rate))
            samples.extend((value, value))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tone.wav"
            with wave.open(str(path), "wb") as target:
                target.setnchannels(2)
                target.setsampwidth(2)
                target.setframerate(rate)
                target.writeframes(samples.tobytes())
            metrics = analyze_wave(path)
        self.assertGreater(metrics.rms, 0.08)
        self.assertLess(metrics.peak, 0.2)
        self.assertEqual(metrics.clipped_fraction, 0)
        self.assertLess(metrics.longest_silent_seconds, 0.01)

    def test_gui_cycle_captures_both_production_screens(self) -> None:
        actions = list(
            action_cycle(
                0,
                [_Synth("synth"), _Synth("sample")],
                Path("/tmp/gui-endurance-contract"),
            )
        )
        captures = [item for item in actions if item.name == "captureGui"]
        self.assertEqual(len(captures), 2)
        self.assertTrue(any("gui-omni" in str(item.args[0]) for item in captures))
        self.assertTrue(any("gui-midi" in str(item.args[0]) for item in captures))


if __name__ == "__main__":
    unittest.main()
