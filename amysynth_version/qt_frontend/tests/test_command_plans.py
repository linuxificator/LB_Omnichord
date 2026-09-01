#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[1]
CODE = FRONTEND / "code"
sys.path.insert(0, str(CODE))

from amy_parameter_plan import compile_parameter_commands  # noqa: E402
from rhythm_command_plan import (  # noqa: E402
    compile_bass_events,
    compile_chord_pattern_plan,
    compile_drum_activity_commands,
    compile_fill_definition,
    compile_fill_schedule_commands,
    compile_tagged_lane,
)


@dataclass(frozen=True)
class _Event:
    tick: int
    role: str
    velocity: int


@dataclass(frozen=True)
class _Fill:
    index: int
    duration_ticks: int
    allowed_start_beats: tuple[int, ...]
    beat_unit_ticks: int
    events: tuple[_Event, ...]
    continue_roles: frozenset[str]


@dataclass(frozen=True)
class _Rhythm:
    rhythm_id: str
    period_ticks: int
    period_bars: int
    levels: tuple[tuple[_Event, ...], ...]
    fills: tuple[_Fill, ...]


def _hit_body(
    rhythm_id: str,
    role: str,
    velocity: int,
    *,
    fill: bool,
) -> str:
    kind = "f" if fill else "a"
    return f"{kind}{rhythm_id}:{role}:{velocity}"


class PureCommandPlanTests(unittest.TestCase):
    def test_pure_modules_have_no_ui_or_transport_imports(self) -> None:
        forbidden = {
            "PySide6",
            "serial",
            "socket",
            "amy_transport",
            "midi_player",
        }
        for filename in ("amy_parameter_plan.py", "rhythm_command_plan.py"):
            tree = ast.parse((CODE / filename).read_text(encoding="utf-8"))
            imports = {
                alias.name.split(".")[0]
                for node in ast.walk(tree)
                if isinstance(node, (ast.Import, ast.ImportFrom))
                for alias in node.names
            }
            self.assertFalse(imports & forbidden, filename)

    def test_juno_parameter_plan_is_exact_and_selective(self) -> None:
        params = {
            "filter_hz": 440.0,
            "resonance": 0.7,
            "lfo_hz": 2.5,
            "attack_ms": 10.0,
            "sustain": 0.5,
        }
        self.assertEqual(
            compile_parameter_commands(
                patch=3,
                synth=7,
                parameters=params,
                selected_keys={"filter_hz"},
            ),
            ("v0F440i7Z",),
        )
        self.assertEqual(
            compile_parameter_commands(patch=3, synth=7, parameters=params),
            (
                "v0F440i7Z",
                "v0R0.7i7Z",
                "v1f2.5i7Z",
                "v0A10,,,0.5,,i7Z",
            ),
        )

    def test_dx7_envelope_update_resends_owned_complete_envelope(self) -> None:
        self.assertEqual(
            compile_parameter_commands(
                patch=130,
                synth=9,
                parameters={
                    "attack_ms": 8.0,
                    "decay_ms": 90.0,
                    "sustain": 0.75,
                    "release_ms": 120.0,
                    "feedback": 0.2,
                },
                selected_keys={"attack_ms"},
            ),
            ("v0a,,,1A8,1,90,0.75,120,0i9Z",),
        )

    def test_tagged_lane_replaces_and_clears_to_high_water(self) -> None:
        plan = compile_tagged_lane(
            name="bass",
            start=20,
            count=4,
            previous_high_water=3,
            events=[(9, 8, "n60l1i2Z")],
        )
        self.assertEqual(plan.high_water, 3)
        self.assertEqual(
            plan.commands,
            (
                "H1,8,20n60l1i2Z",
                "H0,0,21Z",
                "H0,0,22Z",
            ),
        )

    def test_chord_plan_owns_note_on_and_matching_release(self) -> None:
        plan = compile_chord_pattern_plan(
            config={
                "length_beats": 4,
                "chord_events": [{"time": 0, "amp": 0.8}],
                "chord_arpeggio": {
                    "enabled": True,
                    "notes_per_beat": 2,
                    "direction": "up",
                },
            },
            enabled=True,
            chord_notes=(60.0, 64.0),
            max_chord_notes=7,
            chord_gate_beats=0.5,
            pattern_start=100,
            pattern_count=20,
            synth=4,
            ppq=48,
        )
        self.assertEqual(
            plan.definitions[:4],
            (
                "zQB103,13Z",
                "zQE103,0,13,0n60l0.8i4Z",
                "zQE103,12,0,1n60l0i4Z",
                "zQC103Z",
            ),
        )
        self.assertEqual(
            plan.triggers,
            ((0, 192, "zQT103,0,0"), (24, 192, "zQT104,0,0")),
        )

    def test_bass_plan_supports_activity_and_riff_inputs(self) -> None:
        activity = compile_bass_events(
            config={
                "length_beats": 4,
                "bass_events": [{"time": 1, "degree": 1, "amp": 0.5}],
            },
            running=True,
            bass_notes=(36.0, 40.0),
            bass_riff=None,
            synth=2,
            bass_gate_beats=0.25,
            ppq=48,
        )
        self.assertEqual(
            activity,
            ((48, 192, "n40l0.5i2"), (60, 192, "n40l0i2")),
        )
        riff = compile_bass_events(
            config={"length_beats": 4, "bass_mode": "riff"},
            running=True,
            bass_notes=(),
            bass_riff={
                "ppq": 96,
                "phrase_ticks": 192,
                "events": [
                    {
                        "tick": 24,
                        "duration_ticks": 48,
                        "note": 43,
                        "velocity": 127,
                    }
                ],
            },
            synth=2,
            bass_gate_beats=0.25,
            ppq=48,
        )
        self.assertEqual(
            riff,
            ((12, 96, "n43l1i2"), (36, 96, "n43l0i2")),
        )

    def test_drum_and_fill_plans_are_deterministic(self) -> None:
        fill = _Fill(
            index=1,
            duration_ticks=192,
            allowed_start_beats=(3,),
            beat_unit_ticks=96,
            events=(_Event(0, "snare", 100),),
            continue_roles=frozenset({"hat"}),
        )
        rhythm = _Rhythm(
            rhythm_id="r1",
            period_ticks=384,
            period_bars=1,
            levels=((_Event(0, "kick", 127),),) * 5,
            fills=(fill,),
        )
        self.assertEqual(
            compile_drum_activity_commands(
                rhythm=rhythm,
                percussion_activity=1,
                roles=("hat", "kick"),
                pattern_start=10,
                rhythm_running=True,
                quantize_live=True,
                hit_body=_hit_body,
            ),
            (
                "zQS10,192Z",
                "zQB11,192Z",
                "zQE11,0,192,0ar1:kick:127Z",
                "zQC11Z",
                "zQT11,1,192,11Z",
            ),
        )
        definition = compile_fill_definition(
            rhythm_id="r1",
            fill=fill,
            pattern=30,
            roles=("hat", "kick", "snare"),
            role_indexes={"hat": 0, "kick": 1, "snare": 2},
            drum_pattern_start=10,
            hit_body=_hit_body,
        )
        self.assertEqual(
            definition,
            (
                "zQB30,96Z",
                "zQE30,0,96,0zQM11,96Z",
                "zQE30,0,96,1zQM12,96Z",
                "zQE30,0,96,2fr1:snare:100Z",
                "zQC30Z",
            ),
        )
        schedule = compile_fill_schedule_commands(
            fills=(fill,),
            order=(0,),
            density_bars=4,
            bar_ticks=192,
            lane_start=40,
            lane_count=2,
            previous_high_water=2,
            quantize_live=True,
            pattern_id=lambda item: 29 + item.index,
        )
        self.assertEqual(schedule.high_water, 2)
        self.assertEqual(
            schedule.commands,
            ("zQA30,0,96,768,192,40Z", "H0,0,41Z"),
        )


if __name__ == "__main__":
    unittest.main()
