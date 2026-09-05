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
    compile_chord_sequence_plan,
    compile_drum_activity_sequences,
    compile_fill_sequence,
    compile_fill_schedule,
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

    def test_tagged_lane_replaces_one_cumulative_sequence_at_a_boundary(self) -> None:
        plan = compile_tagged_lane(
            name="bass",
            start=20,
            count=4,
            events=[(9, 8, "n60l1i2Z")],
        )
        self.assertEqual(
            plan.commands,
            (
                "HC20,0,8Z",
                "HR20Z",
                "H1,8,20n60l1i2Z",
                "HC20,1,8Z",
            ),
        )

    def test_chord_plan_owns_note_on_and_matching_release(self) -> None:
        plan = compile_chord_sequence_plan(
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
            sequence_start=100,
            sequence_count=20,
            synth=4,
            ppq=48,
        )
        self.assertEqual(
            plan.definitions,
            (
                "HR100Z",
                "H0,0,100n60l0.8i4Z",
                "H12,0,100n60l0i4Z",
                "H24,0,100n64l0.8i4Z",
                "H36,0,100n64l0i4Z",
            ),
        )
        self.assertEqual(
            plan.triggers,
            ((0, 192, "HC100,1,1Z"),),
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
        drum_plan = compile_drum_activity_sequences(
            rhythm=rhythm,
            percussion_activity=1,
            roles=("hat", "kick"),
            sequence_start=10,
            rhythm_running=True,
            quantize_live=True,
            hit_body=_hit_body,
        )
        self.assertEqual(
            drum_plan.commands,
            (
                "HR10Z",
                "HC10,0,192Z",
                "HR11Z",
                "H0,192,11ar1:kick:127Z",
                "HC11,0,192Z",
                "HC11,1,192Z",
            ),
        )
        definition = compile_fill_sequence(
            rhythm_id="r1",
            fill=fill,
            sequence_tag=30,
            roles=("hat", "kick", "snare"),
            role_indexes={"hat": 0, "kick": 1, "snare": 2},
            drum_sequence_start=10,
            hit_body=_hit_body,
        )
        self.assertEqual(
            definition.commands,
            (
                "HR30Z",
                "H0,0,30HC11,2,96,0Z",
                "H0,0,30HC12,2,96,0Z",
                "H0,0,30fr1:snare:100Z",
            ),
        )
        schedule = compile_fill_schedule(
            fills=(fill,),
            order=(0,),
            density_bars=4,
            bar_ticks=192,
            lane_start=40,
            lane_count=2,
            sequence_tag=lambda item: 29 + item.index,
        )
        self.assertEqual(
            schedule.commands,
            (
                "HC40,0,192Z",
                "HR40Z",
                "H96,768,40HC30,1,1Z",
                "HC40,1,192Z",
            ),
        )


if __name__ == "__main__":
    unittest.main()
