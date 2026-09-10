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
    compile_bass_sequence_plan,
    compile_chord_sequence_plan,
    compile_drum_activity_sequences,
    compile_fill_sequence,
    compile_fill_schedule,
    compile_tagged_lane,
)
from tb303 import Tb303Parameters  # noqa: E402


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
    output_gain: float = 1.0


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
    fill_id: str | None = None,
    fill_gain: float = 1.0,
) -> str:
    kind = "f" if fill else "a"
    suffix = "" if fill_gain == 1.0 else f":gain={fill_gain:g}"
    return f"{kind}{rhythm_id}:{role}:{velocity}{suffix}"


class PureCommandPlanTests(unittest.TestCase):
    @staticmethod
    def _bass_plan(**kwargs: object):
        return compile_bass_sequence_plan(
            sequence_start=20,
            sequence_count=56,
            **kwargs,
        )

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
        activity = self._bass_plan(
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
        self.assertEqual(activity.triggers, ((48, 192, "HC21,1,1Z"),))
        self.assertEqual(
            activity.definitions,
            ("HR21Z", "H0,0,21n40l0.7i2Z", "H12,0,21n40l0i2Z"),
        )
        riff = self._bass_plan(
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
        self.assertEqual(riff.triggers, ((12, 96, "HC21,1,1Z"),))
        self.assertEqual(
            riff.definitions,
            ("HR21Z", "H0,0,21n43l1i2Z", "H24,0,21n43l0i2Z"),
        )

    def test_bass_activity_calibration_is_bounded_and_riff_is_unchanged(self) -> None:
        activity = self._bass_plan(
            config={
                "length_beats": 4,
                "bass_events": [
                    {"time": 0, "degree": 0, "amp": 0.88},
                    {"time": 1, "degree": 0, "amp": 0.0},
                ],
            },
            running=True,
            bass_notes=(36.0,),
            bass_riff=None,
            synth=2,
            bass_gate_beats=0.25,
            ppq=48,
        )
        self.assertIn("H0,0,21n36l1i2Z", activity.definitions)
        self.assertIn("H12,0,21n36l0i2Z", activity.definitions)

        riff = self._bass_plan(
            config={"length_beats": 4, "bass_mode": "riff"},
            running=True,
            bass_notes=(),
            bass_riff={
                "ppq": 48,
                "phrase_ticks": 192,
                "events": [
                    {"tick": 0, "duration_ticks": 12, "note": 36, "velocity": 64}
                ],
            },
            synth=2,
            bass_gate_beats=0.25,
            ppq=48,
        )
        self.assertIn("H0,0,21n36l0.503937008i2Z", riff.definitions)

    def test_bass_harmony_update_preserves_launcher_identity_and_phase(self) -> None:
        common = {
            "config": {"length_beats": 4, "bass_mode": "riff"},
            "running": True,
            "bass_notes": (),
            "synth": 1,
            "bass_gate_beats": 0.25,
            "ppq": 48,
        }
        c_plan = self._bass_plan(
            **common,
            bass_riff={
                "id": "same-riff",
                "ppq": 48,
                "phrase_ticks": 192,
                "events": [
                    {"tick": 24, "duration_ticks": 12, "note": 36, "velocity": 96}
                ],
            },
        )
        e_plan = self._bass_plan(
            **common,
            bass_riff={
                "id": "same-riff",
                "ppq": 48,
                "phrase_ticks": 192,
                "events": [
                    {"tick": 24, "duration_ticks": 12, "note": 40, "velocity": 96}
                ],
            },
        )

        self.assertEqual(c_plan.identity, e_plan.identity)
        self.assertEqual(c_plan.triggers, e_plan.triggers)
        self.assertNotEqual(c_plan.definitions, e_plan.definitions)

    def test_tb303_slide_chain_is_native_and_ignores_destination_accent(self) -> None:
        plan = self._bass_plan(
            config={"length_beats": 4, "bass_mode": "riff"},
            running=True,
            bass_notes=(),
            bass_riff={
                "ppq": 48,
                "phrase_ticks": 192,
                "events": [
                    {
                        "tick": 0,
                        "duration_ticks": 12,
                        "note": 36,
                        "velocity": 100,
                        "accent": True,
                        "slide_to_next": True,
                    },
                    {
                        "tick": 24,
                        "duration_ticks": 12,
                        "note": 38,
                        "velocity": 90,
                        "accent": True,
                        "slide_to_next": True,
                    },
                    {
                        "tick": 48,
                        "duration_ticks": 12,
                        "note": 40,
                        "velocity": 80,
                        "accent": False,
                        "slide_to_next": False,
                    },
                ],
            },
            synth=1,
            bass_gate_beats=0.25,
            ppq=48,
            tb303_parameters=Tb303Parameters(),
        )
        self.assertEqual(plan.triggers, ((0, 192, "HC21,1,1Z"),))
        self.assertEqual(
            plan.definitions,
            (
                "HR21Z",
                "H0,0,21a1.175F,,,,2.7m0n36l0.787401575i1Z",
                "H24,0,21a1F,,,,2m60n38i1Z",
                "H48,0,21a1F,,,,2m60n40i1Z",
                "H60,0,21l0i1Z",
            ),
        )
        self.assertNotIn("l", plan.definitions[2])
        self.assertIn("a1F,,,,2", plan.definitions[2])

    def test_tb303_activity_uses_accent_without_changing_ordinary_plan(self) -> None:
        config = {
            "length_beats": 4,
            "bass_events": [
                {"time": 1, "degree": 1, "amp": 0.5, "accent": True},
            ],
        }
        ordinary = self._bass_plan(
            config=config,
            running=True,
            bass_notes=(36.0, 40.0),
            bass_riff=None,
            synth=1,
            bass_gate_beats=0.25,
            ppq=48,
        )
        tb303 = self._bass_plan(
            config=config,
            running=True,
            bass_notes=(36.0, 40.0),
            bass_riff=None,
            synth=1,
            bass_gate_beats=0.25,
            ppq=48,
            tb303_parameters=Tb303Parameters(),
        )
        self.assertIn("H0,0,21n40l0.7i1Z", ordinary.definitions)
        self.assertIn(
            "H0,0,21a1.175F,,,,2.7m0n40l0.700787402i1Z",
            tb303.definitions,
        )
        self.assertIn("H12,0,21l0i1Z", tb303.definitions)

    def test_tb303_loop_release_precedes_next_attack_at_tick_zero(self) -> None:
        with self.assertRaisesRegex(ValueError, "silent handover"):
            self._bass_plan(
                config={"length_beats": 1, "bass_mode": "riff"},
                running=True,
                bass_notes=(),
                bass_riff={
                    "ppq": 48,
                    "phrase_ticks": 48,
                    "events": [
                        {
                            "tick": 0,
                            "duration_ticks": 48,
                            "note": 36,
                            "velocity": 100,
                            "accent": False,
                            "slide_to_next": False,
                        }
                    ],
                },
                synth=1,
                bass_gate_beats=0.25,
                ppq=48,
                tb303_parameters=Tb303Parameters(),
            )

    def test_activity_release_across_wrap_stays_with_next_attack(self) -> None:
        plan = self._bass_plan(
            config={
                "length_beats": 1,
                "bass_events": [
                    {"time": 0, "degree": 0, "amp": 0.5},
                    {"time": 0.75, "degree": 1, "amp": 0.5},
                ],
            },
            running=True,
            bass_notes=(36.0, 40.0),
            bass_riff=None,
            synth=2,
            bass_gate_beats=0.3,
            ppq=48,
        )

        self.assertEqual(plan.triggers, ((36, 48, "HC21,1,1Z"),))
        self.assertEqual(
            plan.definitions,
            (
                "HR21Z",
                "H0,0,21n40l0.7i2Z",
                "H12,0,21n36l0.7i2Z",
                "H26,0,21n36l0i2Z",
            ),
        )
        self.assertEqual(plan.drain_ticks, 26)

    def test_dense_activity_retriggers_get_release_safe_gestures(self) -> None:
        plan = self._bass_plan(
            config={
                "length_beats": 1,
                "bass_events": [
                    {"time": 0, "degree": 0, "amp": 0.5},
                    {"time": 0.25, "degree": 1, "amp": 0.5},
                    {"time": 0.5, "degree": 0, "amp": 0.5},
                    {"time": 0.75, "degree": 1, "amp": 0.5},
                ],
            },
            running=True,
            bass_notes=(36.0, 40.0),
            bass_riff=None,
            synth=2,
            bass_gate_beats=0.3,
            ppq=48,
        )

        self.assertEqual(
            tuple(tick for tick, _period, _body in plan.triggers),
            (0, 12, 24, 36),
        )
        self.assertEqual(plan.gesture_count, 4)
        self.assertEqual(plan.drain_ticks, 11)
        self.assertIn("H11,0,21n36l0i2Z", plan.definitions)
        self.assertIn("H11,0,24n40l0i2Z", plan.definitions)

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
