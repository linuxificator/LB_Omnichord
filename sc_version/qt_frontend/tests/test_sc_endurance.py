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

from sc_endurance import (  # noqa: E402
    action_cycle,
    analyze_wave,
    pcm_chord_switch_cycle,
    startup_bass_riff_cycle,
    vsco_drum_role_cycle,
)


class _Synth:
    def __init__(self, kind: str, key: str = "fixture") -> None:
        self.kind = kind
        self.key = key


class SuperColliderEnduranceTests(unittest.TestCase):
    def test_startup_bass_riff_scenario_needs_no_transport_restart(self) -> None:
        actions = list(startup_bass_riff_cycle())
        names = [action.name for action in actions]
        self.assertEqual(names.count("ensureRhythmRunning"), 1)
        self.assertLess(
            names.index("ensureRhythmRunning"),
            names.index("pressChord"),
        )
        self.assertEqual(
            next(
                action.args
                for action in actions
                if action.name == "setRhythmBassActivity"
            ),
            (5.0,),
        )

    def test_vsco_drum_scenario_forces_selection_and_sustained_playback(self) -> None:
        actions = list(vsco_drum_role_cycle())
        selections = [
            action.args[0]
            for action in actions
            if action.name == "setDrumKitIndex"
        ]
        self.assertEqual(selections, [1, 0])
        self.assertTrue(
            any(
                action.name == "ensureRhythmRunning"
                and action.args == (True,)
                and action.dwell >= 5.0
                for action in actions
            )
        )

    def test_pcm_chord_switch_scenario_repeats_flute_during_arpeggio(self) -> None:
        keys = (
            "sample.vsco.uprightpiano",
            "sample.vsco.flute-ks",
            "sample.vsco.marimba",
            "sample.vsco.flute-ks.art.c-2-sustain-vibrato",
        )
        synths = [_Synth("sample", key) for key in keys]
        actions = list(pcm_chord_switch_cycle(synths))
        flute_index = keys.index("sample.vsco.flute-ks")
        selected = [
            int(action.args[0])
            for action in actions
            if action.name == "setChordSynthIndex"
        ]
        self.assertGreaterEqual(selected.count(flute_index), 12)
        arpeggio = next(
            index
            for index, action in enumerate(actions)
            if action.name == "ensureChordArpeggioRunning"
        )
        first_switch = next(
            index
            for index, action in enumerate(actions)
            if action.name == "setChordSynthIndex"
        )
        self.assertLess(arpeggio, first_switch)

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
        percussion_attacks = [
            action
            for action in actions
            if action.name == "injectMidiNote"
            and action.args[0] == 10
            and action.args[3] is True
        ]
        self.assertEqual(len(percussion_attacks), 18)
        self.assertEqual(
            {action.args[1] for action in percussion_attacks},
            {36, 38, 42, 46, 49},
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
