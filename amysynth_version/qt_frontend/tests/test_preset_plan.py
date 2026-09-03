from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from preset_plan import (  # noqa: E402
    ChordRowPreset,
    EffectsPreset,
    RhythmSettingPreset,
    compile_omni_preset_plan,
)


def compile_plan(data: dict[str, object]):
    return compile_omni_preset_plan(
        data,
        chord_suffixes=("", "m7"),
        chord_inversion_counts=(3, 4),
        octave_names=("LOW", "MID"),
        default_rows=(
            ChordRowPreset(0, 0, 0),
            ChordRowPreset(1, 1, 1),
        ),
        default_volumes=(0.1, 0.2, 0.3, 0.4),
        default_effects=EffectsPreset(0.5, 0.6, 0.7, False),
        default_bass_running=True,
        rhythm_keys=("rock", "jazz"),
        default_selected_rhythm_index=0,
        default_rhythm_settings=(
            RhythmSettingPreset(100.0, 2, 2, 2, (0,), 0),
            RhythmSettingPreset(120.0, 3, 3, 3, (1,), 1),
        ),
        fill_density_bars=(0, 4, 8),
        tuning_modes=("EQ", "HARM"),
        default_tuning_mode_index=0,
        default_tuning_reference_hz=440,
        reverb_level_max=2.0,
    )


class PresetPlanTests(unittest.TestCase):
    def test_defaults_are_copied_to_frozen_plan(self) -> None:
        plan = compile_plan({})

        self.assertEqual(plan.chord_rows[1], ChordRowPreset(1, 1, 1))
        self.assertEqual(plan.volumes, (0.1, 0.2, 0.3, 0.4))
        self.assertEqual(plan.rhythm_settings[1].fill_order, (1,))
        self.assertTrue(plan.bass_running)

    def test_normalizes_legacy_effects_and_bounded_values(self) -> None:
        plan = compile_plan(
            {
                "strum_mode": "ldr",
                "chord_rows": [
                    {"chord": "m7", "octave": "MID", "inversion": 7},
                    {"chord": "missing", "octave": "missing", "inversion": -1},
                ],
                "volumes": {"chord": -1, "strum": 2},
                "effects": {"main_reverb": 9, "percussion_reverb": 0.1},
                "rhythm": {
                    "selected": "jazz",
                    "settings": {
                        "jazz": {
                            "tempo": 500,
                            "percussion_activity": 0,
                            "chord_activity": 9,
                            "bass_activity": 9,
                            "fill_order": [4, 4, -1, 2, 9],
                            "fill_density_bars": 8,
                        }
                    },
                },
                "tuning": {"mode": "HARM", "reference_hz": 466.9},
            }
        )

        self.assertTrue(plan.strum_ladder_mode)
        self.assertEqual(plan.chord_rows[0], ChordRowPreset(1, 1, 3))
        self.assertEqual(plan.chord_rows[1], ChordRowPreset(1, 1, 3))
        self.assertEqual(plan.volumes[:2], (0.0, 1.0))
        self.assertEqual(plan.effects, EffectsPreset(2.0, 0.6, 0.7, True))
        self.assertEqual(plan.selected_rhythm_index, 1)
        jazz = plan.rhythm_settings[1]
        self.assertEqual(
            (jazz.tempo, jazz.percussion_activity, jazz.chord_activity, jazz.bass_activity),
            (200.0, 1, 4, 5),
        )
        self.assertEqual(jazz.fill_order, (4, 2))
        self.assertEqual(jazz.fill_density_index, 2)
        self.assertEqual((plan.tuning_mode_index, plan.tuning_reference_hz), (1, 466.0))


if __name__ == "__main__":
    unittest.main()
