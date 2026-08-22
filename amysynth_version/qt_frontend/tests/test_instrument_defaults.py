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
from synth_state import SynthState  # noqa: E402


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

    @staticmethod
    def bare_client() -> AmySerialClient:
        """Minimal receiver object for pure state-convergence unit tests."""
        client = object.__new__(AmySerialClient)
        client.selected_synth = {
            "chord": "juno_000",
            "strum": "juno_028",
            "bass": "dx7_143",
        }
        client.synth_params = {"chord": {}, "strum": {}, "bass": {}}
        client._adsr_override_active = {
            "chord": False,
            "strum": False,
            "bass": False,
        }
        client.synth_id = {
            "strum": 2,
            "manual_chord": 3,
            "rhythm_chord": 4,
        }
        client._manual_active_id = None
        client._manual_active_notes = []
        client.rhythm_running = False
        client._wire = lambda command: None
        return client

    def test_every_slider_has_explicit_physical_range(self) -> None:
        self.assertEqual(len(self.synths), 124)
        self.assertIn("physical_strings", self.by_key)
        physical = self.by_key["physical_strings"]
        self.assertEqual(physical.label, "Ph. Strings")
        decay = self.control(physical, "ks_feedback")
        self.assertEqual(decay.label, "DECAY")
        self.assertEqual(decay.group, "extra")
        self.assertGreaterEqual(decay.minimum, 0.90)
        self.assertGreater(decay.maximum, 0.99)

        for synth in self.synths:
            for control in synth.controls:
                self.assertGreaterEqual(control.minimum, 0.0, (synth.key, control.key))
                self.assertGreaterEqual(control.default, control.minimum)
                self.assertLessEqual(control.default, control.maximum)

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
        state = SynthState(self.synths, 0)
        changed_keys = ["juno_007", "juno_008", "juno_068", "dx7_143"]

        for offset, key in enumerate(changed_keys, start=1):
            index = self.index_by_key[key]
            self.assertTrue(state.select(index) or state.selected_index == index)
            synth = self.synths[index]
            control = self.control(synth, "attack_ms")
            edited = min(
                control.maximum,
                control.default + 10.0 * offset,
            )
            self.assertTrue(state.set_control("attack_ms", edited))

        overrides = state.sparse_overrides()
        self.assertEqual(set(overrides), set(changed_keys))
        for key in changed_keys:
            self.assertEqual(set(overrides[key]), {"attack_ms"})

    def test_slider_edit_survives_switch_away_and_back(self) -> None:
        state = SynthState(self.synths, 0)
        piano_index = self.index_by_key["juno_007"]
        organ_index = self.index_by_key["juno_008"]

        state.select(piano_index)
        original = state.selected_values["attack_ms"]
        edited = original + 70.0
        self.assertTrue(state.set_control("attack_ms", edited))

        self.assertTrue(state.select(organ_index))
        self.assertTrue(state.select(piano_index))
        self.assertEqual(state.selected_values["attack_ms"], edited)

    def test_sparse_preset_overlays_defaults_and_old_minus_one_is_unset(self) -> None:
        state = SynthState(self.synths, 0)
        piano_key = "juno_007"
        piano = self.by_key[piano_key]
        default_attack = self.control_default(piano, "attack_ms")
        default_cutoff = self.control_default(piano, "filter_hz")
        edited_attack = default_attack + 80.0

        state.load_preset(
            {
                "selected": piano_key,
                "parameters": {
                    piano_key: {
                        "attack_ms": edited_attack,
                        "filter_hz": -1.0,
                    }
                },
            }
        )
        self.assertEqual(state.selected_index, self.index_by_key[piano_key])
        self.assertEqual(state.selected_values["attack_ms"], edited_attack)
        self.assertEqual(state.selected_values["filter_hz"], default_cutoff)
        self.assertEqual(
            state.selected_values["release_ms"],
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

    def test_full_state_message_applies_only_changed_key(self) -> None:
        client = self.bare_client()
        client.patch_map = {"juno_050": 50}
        client.selected_synth["chord"] = "juno_050"
        client.synth_params["chord"] = {
            "filter_hz": 8999.7,
            "resonance": 1.348,
            "sustain": 1.0,
        }
        client._adsr_override_active["chord"] = True
        applied: list[set[str] | None] = []
        client._apply_supported_params = (
            lambda role, parameter_keys=None: applied.append(parameter_keys)
        )
        client._configure_synth = lambda role: None

        AmySerialClient._set_synth_state(
            client,
            "chord",
            {
                "name": "juno_050",
                "params": [
                    "filter_hz", 8999.7,
                    "resonance", 1.348,
                    "sustain", 0.42,
                ],
            },
        )

        self.assertEqual(applied, [{"sustain"}])

    def test_atomic_instrument_state_restores_edited_resonance(self) -> None:
        client = self.bare_client()
        client.patch_map = {"juno_050": 50}
        client.synth_params["chord"] = {"resonance": 0.93}

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

    def test_live_chord_instrument_change_does_not_rebuild_sequencer(self) -> None:
        client = self.bare_client()
        client.patch_map = {"juno_050": 50}
        client.rhythm_running = True

        calls: list[tuple[str, object]] = []
        client._wire = lambda command: calls.append(("wire", command))
        client._configure_synth = lambda role: calls.append(("configure", role))

        AmySerialClient._set_synth_state(
            client,
            "chord",
            {
                "name": "juno_050",
                "params": ["resonance", 7.5],
            },
        )

        self.assertEqual(
            calls,
            [("wire", "l0i4Z"), ("configure", "chord")],
        )
        self.assertFalse(
            any(
                command in {"zY0Z", "zY1Z", "S4096Z"}
                for kind, command in calls
                if kind == "wire"
            )
        )

    def test_stopped_rhythm_is_not_rebuilt_on_chord_instrument_change(self) -> None:
        client = self.bare_client()
        client.patch_map = {"juno_050": 50}
        calls: list[tuple[str, object]] = []
        client._wire = lambda command: calls.append(("wire", command))
        client._configure_synth = lambda role: calls.append(("configure", role))

        AmySerialClient._set_synth_state(
            client,
            "chord",
            {"name": "juno_050", "params": ["resonance", 7.5]},
        )

        self.assertEqual(
            calls,
            [("wire", "l0i4Z"), ("configure", "chord")],
        )


if __name__ == "__main__":
    unittest.main()
