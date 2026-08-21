#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[1]
CODE = FRONTEND / "code"
sys.path.insert(0, str(CODE))

import main as omnichord  # noqa: E402
from amy_serial import AmySerialClient  # noqa: E402


class BackendHarness:
    """Minimal non-QML harness for InstrumentBackend's synth-state methods."""

    def __init__(self, synths: tuple[omnichord.SynthDefinition, ...]) -> None:
        self._synths = synths
        self._chord_synth = self._make_synth_runtime(0)
        self._strum_synth = self._make_synth_runtime(0)
        self._bass_synth = self._make_synth_runtime(0)
        self.sent_roles: list[str] = []

    def _make_synth_runtime(self, selected_index: int) -> omnichord.SynthRuntime:
        return omnichord.SynthRuntime(
            selected_index=selected_index,
            values_by_synth=[
                {
                    control.key: control.default
                    for control in synth.controls
                }
                for synth in self._synths
            ],
        )

    def _fresh_synth_runtime(self, selected_index: int) -> omnichord.SynthRuntime:
        return self._make_synth_runtime(selected_index)

    def _runtime(self, role: str) -> omnichord.SynthRuntime:
        if role == "chord":
            return self._chord_synth
        if role == "strum":
            return self._strum_synth
        return self._bass_synth

    def _send_synth_params(self, role: str) -> None:
        self.sent_roles.append(role)


class InstrumentDefaultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        (
            cls.synths,
            cls.default_chord,
            cls.default_strum,
            cls.default_bass,
        ) = omnichord.load_synth_catalog(FRONTEND / "instruments" / "synths.json")
        cls.by_key = {synth.key: synth for synth in cls.synths}
        cls.index_by_key = {synth.key: index for index, synth in enumerate(cls.synths)}

    @staticmethod
    def control(synth: omnichord.SynthDefinition, key: str) -> omnichord.SynthControl:
        return next(control for control in synth.controls if control.key == key)

    @classmethod
    def control_default(cls, synth: omnichord.SynthDefinition, key: str) -> float:
        return cls.control(synth, key).default

    def test_every_slider_has_explicit_physical_range(self) -> None:
        self.assertEqual(len(self.synths), 123)
        for synth in self.synths:
            for control in synth.controls:
                self.assertGreaterEqual(control.minimum, 0.0, (synth.key, control.key))
                self.assertGreaterEqual(control.default, control.minimum)
                self.assertLessEqual(control.default, control.maximum)

        # Sustain is a 0..1 level.  Zero must be the left edge, never the
        # midpoint of a legacy -1..1 "native sentinel" range.
        for synth in self.synths:
            sustain = next(
                (control for control in synth.controls if control.key == "sustain"),
                None,
            )
            if sustain is not None:
                self.assertEqual(sustain.minimum, 0.0)
                self.assertEqual(sustain.maximum, 1.0)

        self.assertEqual(
            self.control_default(self.by_key["juno_068"], "attack_ms"),
            20.0,
        )
        self.assertEqual(
            self.control_default(self.by_key["juno_089"], "attack_ms"),
            20.0,
        )
        self.assertEqual(
            self.control_default(self.by_key["juno_074"], "attack_ms"),
            600.0,
        )

    def test_four_edited_instruments_are_all_serialized_sparse(self) -> None:
        values = [
            {control.key: control.default for control in synth.controls}
            for synth in self.synths
        ]
        changed_keys = ["juno_007", "juno_008", "juno_068", "dx7_143"]

        for offset, key in enumerate(changed_keys, start=1):
            index = self.index_by_key[key]
            synth = self.synths[index]
            control = self.control(synth, "attack_ms")
            values[index]["attack_ms"] = min(
                control.maximum,
                control.default + 10.0 * offset,
            )

        overrides = omnichord.collect_synth_parameter_overrides(self.synths, values)
        self.assertEqual(set(overrides), set(changed_keys))
        for key in changed_keys:
            self.assertEqual(set(overrides[key]), {"attack_ms"})

    def test_slider_edit_survives_switch_away_and_back(self) -> None:
        harness = BackendHarness(self.synths)
        piano_index = self.index_by_key["juno_007"]
        organ_index = self.index_by_key["juno_008"]
        runtime = harness._chord_synth

        runtime.selected_index = piano_index
        original = runtime.values_by_synth[piano_index]["attack_ms"]
        edited = original + 70.0
        omnichord.InstrumentBackend._set_synth_control(
            harness,
            "chord",
            "attack_ms",
            edited,
        )

        runtime.selected_index = organ_index
        runtime.selected_index = piano_index
        self.assertEqual(runtime.values_by_synth[piano_index]["attack_ms"], edited)
        self.assertEqual(harness.sent_roles, ["chord"])

    def test_sparse_preset_overlays_defaults_and_old_minus_one_is_unset(self) -> None:
        harness = BackendHarness(self.synths)
        piano_key = "juno_007"
        piano = self.by_key[piano_key]
        default_attack = self.control_default(piano, "attack_ms")
        default_cutoff = self.control_default(piano, "filter_hz")
        edited_attack = default_attack + 80.0

        data = {
            "selected": piano_key,
            "parameters": {
                piano_key: {
                    "attack_ms": edited_attack,
                    "filter_hz": -1.0,
                }
            },
        }

        runtime = omnichord.InstrumentBackend._apply_synth_preset(
            harness,
            "chord",
            data,
        )
        piano_index = self.index_by_key[piano_key]
        values = runtime.values_by_synth[piano_index]
        self.assertEqual(runtime.selected_index, piano_index)
        self.assertEqual(values["attack_ms"], edited_attack)
        self.assertEqual(values["filter_hz"], default_cutoff)

        # A control absent from the sparse JSON must also be the instrument default.
        self.assertEqual(
            values["release_ms"],
            self.control_default(piano, "release_ms"),
        )

    def test_repeater_sustain_command_does_not_touch_filter(self) -> None:
        client = object.__new__(AmySerialClient)
        client.selected_synth = {"chord": "juno_050"}
        client.patch_map = {"juno_050": 50}
        client.synth_params = {"chord": {"sustain": 0.42}}

        commands = AmySerialClient._param_commands_for_synth(
            client,
            "chord",
            3,
            {"sustain"},
        )

        self.assertEqual(commands, ["v0A,,,0.42,,i3Z"])
        self.assertFalse(any("F" in command or "R" in command for command in commands))

    def test_full_parameter_message_applies_only_changed_key(self) -> None:
        client = object.__new__(AmySerialClient)
        client.synth_params = {
            "chord": {
                "filter_hz": 8999.7,
                "resonance": 1.348,
                "sustain": 1.0,
            }
        }
        client._adsr_override_active = {"chord": True}
        applied: list[set[str] | None] = []
        client._apply_supported_params = (
            lambda role, parameter_keys=None: applied.append(parameter_keys)
        )
        client._configure_synth = lambda role: None

        AmySerialClient._set_params(
            client,
            "chord",
            [
                "filter_hz", 8999.7,
                "resonance", 1.348,
                "sustain", 0.42,
            ],
        )

        self.assertEqual(applied, [{"sustain"}])


    def test_atomic_instrument_state_restores_edited_resonance(self) -> None:
        client = object.__new__(AmySerialClient)
        client.patch_map = {"juno_050": 50}
        client.selected_synth = {"chord": "juno_000"}
        client.synth_params = {"chord": {"resonance": 0.93}}
        client._adsr_override_active = {"chord": False}
        client.synth_id = {
            "strum": 2, "manual_chord": 3, "rhythm_chord": 4
        }
        client._manual_active_id = None
        client._manual_active_notes = []

        configured: list[tuple[str, dict[str, float]]] = []
        client._configure_synth = lambda role: configured.append(
            (role, dict(client.synth_params[role]))
        )

        AmySerialClient._set_synth_state(
            client,
            "chord",
            {
                "name": "juno_050",
                "params": [
                    "filter_hz", 8999.7,
                    "resonance", 7.5,
                    "attack_ms", 0.0,
                    "decay_ms", 0.0,
                    "sustain", 1.0,
                    "release_ms", 0.0,
                ],
            },
        )

        self.assertEqual(client.selected_synth["chord"], "juno_050")
        self.assertEqual(client.synth_params["chord"]["resonance"], 7.5)
        self.assertEqual(configured, [("chord", client.synth_params["chord"])])

    def test_chord_patch_and_restore_commands_are_adjacent_per_synth(self) -> None:
        client = object.__new__(AmySerialClient)
        emitted: list[str] = []
        client._role_synth_ids = lambda role: (3, 4)
        client._configure_one_synth = (
            lambda role, synth: emitted.append(f"K:{synth}")
        )
        client._param_commands_for_synth = (
            lambda role, synth: [f"R7.5:{synth}"]
        )
        client._wire = emitted.append

        AmySerialClient._configure_synth(client, "chord")

        self.assertEqual(
            emitted,
            ["K:3", "R7.5:3", "K:4", "R7.5:4"],
        )


if __name__ == "__main__":
    unittest.main()
