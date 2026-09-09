from __future__ import annotations

import json
import sys
import threading
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

import app_core  # noqa: E402
from midi_player import (  # noqa: E402
    DEFAULT_CHORD_INPUT_CHANNEL,
    DEFAULT_MIDI_CHANNELS,
    LEGACY_FACTORY_MIDI_CHANNELS,
    MidiAmyEngine,
    MidiPlayerBackend,
    _migrated_factory_channel_defaults,
)
from midi_control import NOTE_BUTTON_OFFSET, PITCH_BEND_CONTROLLER  # noqa: E402
from midi_control import MidiControlState  # noqa: E402
from gm_percussion import (  # noqa: E402
    GM_PERCUSSION_NAMES,
    MIDI_DRUM_REFERENCE_ROW_VOLUME,
    OMNI_REFERENCE_PERCUSSION_VOLUME,
    midi_drum_amplitude,
    resolve_gm_percussion,
)
from midi_platform_profile import resolve_midi_tech_profile  # noqa: E402
from resolved_config import resolve_amy_config_data  # noqa: E402
from synth_state import SynthState  # noqa: E402


class _RecordingWriter:
    def __init__(self, events: list[tuple[str, object]]) -> None:
        self.events = events

    def delay(self, seconds: float) -> None:
        self.events.append(("delay", seconds))


class _ManualScheduler:
    def __init__(self) -> None:
        self.calls: list[tuple[float, object, str | None]] = []

    def schedule(
        self,
        delay_seconds: float,
        callback: object,
        *,
        replace_key: str | None = None,
    ) -> int:
        self.calls.append((delay_seconds, callback, replace_key))
        return len(self.calls)


class _Client:
    def __init__(
        self,
        *,
        instrument_levels: dict[str, float] | None = None,
    ) -> None:
        self.events: list[tuple[str, object]] = []
        self.writer = _RecordingWriter(self.events)
        self.application_scheduler = _ManualScheduler()
        config = json.loads((ROOT / "config" / "amy_config.json").read_text(encoding="utf-8"))
        config["performance"]["synth_alloc_guard_ms"] = 12.0
        if instrument_levels is not None:
            config["instrument_levels"] = instrument_levels
        self.resolved_config = resolve_amy_config_data(
            config,
            source_path=ROOT / "config" / "amy_config.json",
            source_kind="external",
        )
        self.patch_map = {"dx7_215": 215}

    def _wire(self, command: str) -> None:
        self.events.append(("wire", command))

    @staticmethod
    def _f(value: float) -> str:
        return f"{float(value):.9g}"

    @staticmethod
    def _patch_compatibility_commands(
        patch: int,
        synth: int,
    ) -> list[str]:
        return [f"compat-{patch}-{synth}"]


class MidiAmyEngineTests(unittest.TestCase):
    def test_external_strum_position_crosses_each_new_note_once(self) -> None:
        backend = app_core.InstrumentBackend.__new__(app_core.InstrumentBackend)
        backend._external_strum_last_index = None
        backend._strum_index = lambda value: int(round(float(value) * 4))
        played: list[int] = []
        backend._play_strum_index = played.append

        backend.strumControlPosition(0.25)
        backend.strumControlPosition(0.26)
        backend.strumControlPosition(0.75)

        self.assertEqual(played, [1, 2, 3])
        self.assertEqual(backend._external_strum_last_index, 3)

    def test_every_factory_preset_reserves_channel_one_and_uses_gm_drums(self) -> None:
        self.assertEqual(DEFAULT_CHORD_INPUT_CHANNEL, 1)
        self.assertEqual(DEFAULT_MIDI_CHANNELS, (2, 3, 4, 5, 6, 10))
        for number in range(1, 19):
            with self.subTest(preset=number):
                data = json.loads(
                    (
                        ROOT
                        / "instruments"
                        / "midi_default_presets"
                        / f"m{number}.json"
                    ).read_text(encoding="utf-8")
                )
                self.assertEqual(
                    tuple(int(row["channel"]) for row in data["rows"]),
                    DEFAULT_MIDI_CHANNELS,
                )
                self.assertEqual(data["rows"][-1]["selected"], "drum_kit_0")

    def test_only_untouched_legacy_factory_channels_are_migrated(self) -> None:
        stored: dict[str, object] | None = None
        factory: dict[str, object] | None = None
        for number in (1, 18):
            factory = json.loads(
                (
                    ROOT
                    / "instruments"
                    / "midi_default_presets"
                    / f"m{number}.json"
                ).read_text(encoding="utf-8")
            )
            stored = json.loads(json.dumps(factory))
            for row, channel in zip(stored["rows"], LEGACY_FACTORY_MIDI_CHANNELS):
                row["channel"] = channel
            if number == 18:
                stored["rows"][-1]["selected"] = "physical_strings"
                stored["rows"][-1]["volume"] = 0.34

            self.assertEqual(
                _migrated_factory_channel_defaults(stored, factory),
                factory,
            )

        assert stored is not None and factory is not None
        customized = json.loads(json.dumps(stored))
        customized["rows"][0]["volume"] = 0.99
        self.assertIsNone(
            _migrated_factory_channel_defaults(customized, factory)
        )

    def test_all_general_midi_percussion_notes_resolve(self) -> None:
        client = _Client()
        drums = client.resolved_config.drums
        configured = dict(drums.sample_map)
        sounds = {
            note: resolve_gm_percussion(
                note,
                kit=drums.kit,
                configured_samples=configured,
            )
            for note in GM_PERCUSSION_NAMES
        }

        self.assertEqual(set(sounds), set(range(35, 82)))
        self.assertTrue(all(sound is not None for sound in sounds.values()))
        self.assertIsNone(
            resolve_gm_percussion(34, kit=drums.kit, configured_samples=configured)
        )
        self.assertIsNone(
            resolve_gm_percussion(82, kit=drums.kit, configured_samples=configured)
        )

    def test_reported_controller_notes_and_duplicate_note_60_all_emit_hits(self) -> None:
        client = _Client()
        engine = MidiAmyEngine(client)
        client.events.clear()

        notes = (48, 50, 51, 53, 55, 56, 58, 60, 60, 62, 63, 65, 67, 68, 70, 72)
        for note in notes:
            engine.drum_hit(note, 60, MIDI_DRUM_REFERENCE_ROW_VOLUME)

        commands = [value for kind, value in client.events if kind == "wire"]
        self.assertEqual(len(commands), len(notes))
        self.assertEqual(sum("p5n65" in command for command in commands), 2)

    def test_midi_velocity_60_matches_equal_velocity_omni_reference(self) -> None:
        gain = 5.0
        midi = midi_drum_amplitude(
            60,
            MIDI_DRUM_REFERENCE_ROW_VOLUME,
            gain,
        )
        omni = (60.0 / 127.0) * gain * OMNI_REFERENCE_PERCUSSION_VOLUME

        self.assertAlmostEqual(midi, omni)
        self.assertLess(
            midi_drum_amplitude(30, MIDI_DRUM_REFERENCE_ROW_VOLUME, gain),
            midi,
        )
        self.assertGreater(
            midi_drum_amplitude(120, MIDI_DRUM_REFERENCE_ROW_VOLUME, gain),
            midi,
        )
        self.assertEqual(midi_drum_amplitude(60, 0.0, gain), 0.0)

    def test_drum_row_uses_configured_channel_and_release_does_not_retrigger(self) -> None:
        class Engine:
            def __init__(self) -> None:
                self.hits: list[tuple[int, int, float]] = []

            def drum_hit(self, note: int, velocity: int, volume: float) -> None:
                self.hits.append((note, velocity, volume))

        backend = MidiPlayerBackend.__new__(MidiPlayerBackend)
        backend.owner = type(
            "Owner",
            (),
            {"processExternalChordInput": lambda *_args: None},
        )()
        backend.engine = Engine()
        backend.channels = [6, 99, 99, 99, 99, 99]
        backend.volumes = [0.28] * 6
        backend._chord_input_channel = 99
        backend._is_drum = lambda row: row == 0

        backend.process_midi_note(5, 60, 60, True)
        backend.process_midi_note(6, 60, 60, True)
        backend.process_midi_note(6, 60, 0, False)

        self.assertEqual(backend.engine.hits, [(60, 60, 0.28)])

        backend.channels[0] = 0
        backend.process_midi_note(11, 62, 70, True)
        self.assertEqual(backend.engine.hits[-1], (62, 70, 0.28))

    def test_pcm_drum_synth_ignores_note_offs_without_tracking_them(self) -> None:
        client = _Client()
        MidiAmyEngine(client)

        commands = [value for kind, value in client.events if kind == "wire"]
        self.assertIn("i11iv8in1iy10if2Z", commands)

    def test_shipped_midi_profile_is_auto_and_resolves_per_package(self) -> None:
        config = json.loads((ROOT / "config" / "amy_config.json").read_text(encoding="utf-8"))
        configured = config["midi_input"]["tech_profile"]
        self.assertEqual(configured, "auto")

        cases = (
            ("wayland", "linux", "linux"),
            ("cocoa", "darwin", "darwin"),
            ("windows", "win32", "win32"),
            ("android", "android", "android"),
            ("offscreen", "freebsd14", "freebsd14"),
        )
        for qpa, runtime, expected in cases:
            with self.subTest(qpa=qpa, runtime=runtime):
                self.assertEqual(
                    resolve_midi_tech_profile(configured, qpa, runtime),
                    expected,
                )

    def test_explicit_midi_profile_remains_a_diagnostic_override(self) -> None:
        self.assertEqual(
            resolve_midi_tech_profile("linux", "windows", "win32"),
            "linux",
        )
        self.assertEqual(
            resolve_midi_tech_profile("DARWIN", "wayland", "linux"),
            "darwin",
        )

    def test_musical_midi_notes_do_not_create_controller_buttons(self) -> None:
        backend = MidiPlayerBackend.__new__(MidiPlayerBackend)
        backend.owner = type(
            "Owner",
            (),
            {
                "_active_row": -1,
                "_active_root_semitone": -1,
            },
        )()
        backend.channels = [99, 99, 99, 99, 99, 99]
        backend._chord_input_channel = 7
        backend.process_midi_note(1, 60, 100, True)
        backend.process_midi_note(1, 60, 0, False)

    def test_cc_mapping_follows_logarithmic_visual_slider_travel(self) -> None:
        class Control:
            key = "filter_hz"
            minimum = 20.0
            maximum = 20000.0
            step = 1.0
            scale = "log"

        class Definition:
            key = "filter_patch"
            controls = (Control(),)

        backend = MidiPlayerBackend.__new__(MidiPlayerBackend)
        backend.definitions = (Definition(),)
        backend.owner = type("Owner", (), {"_synths": ()})()
        target = {
            "id": "midi:synth_control:0:filter_patch:filter_hz",
            "screen": "midi",
            "kind": "synth_control",
            "row": 0,
            "instrument": "filter_patch",
            "control": "filter_hz",
        }

        middle = backend._mapped_target_value(target, 64)

        self.assertIsNotNone(middle)
        assert middle is not None
        expected = round(20.0 * (20000.0 / 20.0) ** (64.0 / 127.0))
        self.assertEqual(middle, expected)
        self.assertNotAlmostEqual(middle, (20.0 + 20000.0) / 2.0)

    def test_strum_and_chord_row_are_generic_continuous_targets(self) -> None:
        calls: list[tuple[object, ...]] = []
        owner = type(
            "Owner",
            (),
            {
                "_chords": tuple(range(40)),
                "_synths": (),
                "strumControlPosition": lambda _self, value: calls.append(
                    ("strum", value)
                ),
                "setRowChordType": lambda _self, row, index: calls.append(
                    ("chord", row, index)
                ),
            },
        )()
        backend = MidiPlayerBackend.__new__(MidiPlayerBackend)
        backend.owner = owner
        backend.definitions = ()
        backend._applying_midi_control = 0
        backend._midi_control_state = MidiControlState()

        strum = backend._normalize_control_target(
            {"screen": "omni", "kind": "strum_position"}
        )
        chord = backend._normalize_control_target(
            {"screen": "omni", "kind": "chord_type", "row": 2}
        )
        self.assertIsNotNone(strum)
        self.assertIsNotNone(chord)
        assert strum is not None
        assert chord is not None

        backend._apply_control_target(strum, 127, (1, 1))
        backend._apply_control_target(chord, 64, (1, 25))

        self.assertEqual(calls[0], ("strum", 0.0))
        self.assertEqual(calls[1], ("chord", 2, 20))

    def test_chord_gate_button_uses_existing_performance_action(self) -> None:
        calls: list[str] = []
        backend = MidiPlayerBackend.__new__(MidiPlayerBackend)
        backend.owner = type(
            "Owner",
            (),
            {"toggleChordGate": lambda _self: calls.append("chord_gate")},
        )()
        backend._midi_control_lock = threading.Lock()
        backend._held_midi_button_targets = set()
        backend._applying_midi_control = 0
        target = {
            "id": "omni:button:chord_gate",
            "screen": "omni",
            "kind": "button",
            "action": "chord_gate",
        }

        backend._apply_button_target(target, True)
        backend._apply_button_target(target, False)

        self.assertEqual(calls, ["chord_gate"])

    def test_preset_binding_loader_accepts_new_source_types(self) -> None:
        backend = MidiPlayerBackend.__new__(MidiPlayerBackend)
        backend._midi_control_state = MidiControlState()
        data = [
            {
                "channel": 1,
                "controller": 74,
                "target": {
                    "kind": "master_volume",
                },
            },
            {
                "channel": 2,
                "source_type": "pitch_bend",
                "target": {
                    "kind": "master_volume",
                },
            },
            {
                "channel": 3,
                "source_type": "note_button",
                "note": 42,
                "target": {
                    "kind": "button",
                    "action": "rhythm_toggle",
                },
            },
            {
                "source_type": "osc",
                "address": "/surface/master",
                "argument": 0,
                "value_type": "continuous",
                "target": {
                    "kind": "master_volume",
                },
            },
        ]

        entries = backend._normalized_binding_entries("omni", data)

        self.assertEqual([key for key, _target in entries[:3]], [
            (1, 74),
            (2, PITCH_BEND_CONTROLLER),
            (3, NOTE_BUTTON_OFFSET + 42),
        ])
        self.assertEqual(
            entries[3][0],
            backend._midi_control_state.osc_key("/surface/master", 0),
        )

    def test_bound_osc_value_uses_the_existing_control_target_path(self) -> None:
        backend = MidiPlayerBackend.__new__(MidiPlayerBackend)
        backend._midi_control_state = MidiControlState()
        backend._midi_control_lock = threading.Lock()
        backend._sync_blue_timer = lambda *_args, **_kwargs: None
        backend._bump_binding_state = lambda *_args, **_kwargs: None
        location_feedback: list[tuple[tuple[int, int], dict[str, object] | None]] = []
        backend._emit_binding_location_feedback = (
            lambda key, target: location_feedback.append(
                (key, dict(target) if target is not None else None)
            )
        )
        applied: list[tuple[dict[str, object], int, tuple[int, int]]] = []
        backend._apply_control_target = (
            lambda target, value, key: applied.append((dict(target), value, key))
        )

        state = backend._midi_control_state
        state.observe_osc("/surface/master", 0, 0.1, "continuous", now=1.0)
        _changed, _target, key = state.observe_osc(
            "/surface/master", 0, 0.2, "continuous", now=1.1
        )
        assert key is not None
        state.indicator_clicked(key, now=1.2)
        state.bind_learned_target(
            {"id": "midi:master_volume", "screen": "midi", "kind": "master_volume"},
            now=1.3,
        )

        backend.process_osc_control("/surface/master", 0, 0.75, "continuous")

        self.assertEqual(len(applied), 1)
        self.assertEqual(applied[0][0]["id"], "midi:master_volume")
        self.assertEqual(applied[0][1], 750_000)
        self.assertEqual(applied[0][2], key)
        self.assertEqual(location_feedback, [(key, applied[0][0])])

    def test_midi_button_takeover_blocks_other_button_targets(self) -> None:
        backend = MidiPlayerBackend.__new__(MidiPlayerBackend)
        backend._applying_midi_control = 0
        backend._midi_control_lock = threading.Lock()
        backend._held_midi_button_targets = {"omni:button:rhythm_toggle"}

        self.assertTrue(
            backend.midiButtonTargetBlocked(
                {
                    "screen": "omni",
                    "kind": "button",
                    "action": "rhythm_toggle",
                }
            )
        )
        self.assertFalse(
            backend.midiButtonTargetBlocked(
                {
                    "screen": "omni",
                    "kind": "button",
                    "action": "master_mute",
                }
            )
        )

        backend._held_midi_button_targets = {"omni:button:select_preset"}
        self.assertTrue(
            backend.midiButtonTargetBlocked(
                {
                    "screen": "omni",
                    "kind": "button",
                    "action": "select_preset",
                    "preset": 2,
                }
            )
        )
        self.assertFalse(
            backend.midiButtonTargetBlocked(
                {
                    "screen": "omni",
                    "kind": "button",
                    "action": "rhythm_busyness",
                    "level": 3,
                }
            )
        )

        backend._held_midi_button_targets.clear()
        self.assertFalse(
            backend.midiButtonTargetBlocked(
                {
                    "screen": "omni",
                    "kind": "button",
                    "action": "master_mute",
                }
            )
        )

    def test_midi_button_takeover_groups_and_tap_actions_are_scoped(self) -> None:
        backend = MidiPlayerBackend.__new__(MidiPlayerBackend)
        backend._applying_midi_control = 0
        backend._midi_control_lock = threading.Lock()
        backend._held_midi_button_targets = set()

        preset_one = backend._normalize_control_target(
            {
                "screen": "omni",
                "kind": "button",
                "action": "select_preset",
                "preset": 1,
            }
        )
        preset_two = backend._normalize_control_target(
            {
                "screen": "omni",
                "kind": "button",
                "action": "select_preset",
                "preset": 2,
            }
        )
        rate_two = backend._normalize_control_target(
            {
                "screen": "omni",
                "kind": "button",
                "action": "chord_arpeggio_rate",
                "rate": 2,
            }
        )
        rate_four = backend._normalize_control_target(
            {
                "screen": "omni",
                "kind": "button",
                "action": "chord_arpeggio_rate",
                "rate": 4,
            }
        )
        panic = backend._normalize_control_target(
            {
                "screen": "omni",
                "kind": "button",
                "action": "panic",
            }
        )

        self.assertIsNotNone(preset_one)
        self.assertIsNotNone(preset_two)
        self.assertIsNotNone(rate_two)
        self.assertIsNotNone(rate_four)
        self.assertIsNotNone(panic)
        assert preset_one is not None
        assert preset_two is not None
        assert rate_two is not None
        assert rate_four is not None
        assert panic is not None

        self.assertNotEqual(rate_two["id"], rate_four["id"])
        self.assertEqual(
            backend._button_takeover_group(preset_one),
            backend._button_takeover_group(preset_two),
        )
        self.assertEqual(
            backend._button_takeover_group(rate_two),
            backend._button_takeover_group(rate_four),
        )
        self.assertIsNone(backend._button_takeover_group(panic))

        backend._held_midi_button_targets.add(backend._button_takeover_group(preset_one))
        self.assertTrue(
            backend.midiButtonTargetBlocked(
                {
                    "screen": "omni",
                    "kind": "button",
                    "action": "select_preset",
                    "preset": 2,
                }
            )
        )
        self.assertFalse(
            backend.midiButtonTargetBlocked(
                {
                    "screen": "omni",
                    "kind": "button",
                    "action": "panic",
                }
            )
        )

    def test_pitch_bend_binding_applies_center_value_immediately(self) -> None:
        backend = MidiPlayerBackend.__new__(MidiPlayerBackend)
        backend._midi_control_state = MidiControlState()
        backend._midi_control_lock = threading.Lock()
        backend._sync_blue_timer = lambda *_args, **_kwargs: None
        backend._bump_binding_state = lambda *_args, **_kwargs: None
        applied: list[tuple[dict[str, object], int, tuple[int, int]]] = []

        def apply_target(
            target: dict[str, object],
            midi_value: int,
            source_key: tuple[int, int],
        ) -> None:
            applied.append((dict(target), int(midi_value), source_key))

        backend._apply_control_target = apply_target
        backend._midi_control_state.indicator_clicked(
            (1, PITCH_BEND_CONTROLLER),
            now=1.0,
        )

        learned = backend.activateControlTarget(
            {
                "screen": "midi",
                "kind": "master_volume",
            }
        )

        self.assertTrue(learned)
        self.assertEqual(len(applied), 1)
        self.assertEqual(applied[0][1], 8192)
        self.assertEqual(applied[0][2], (1, PITCH_BEND_CONTROLLER))
        self.assertEqual(applied[0][0]["id"], "midi:master_volume")

    def test_indicator_click_unlinks_green_before_blue_can_start_learn(self) -> None:
        backend = MidiPlayerBackend.__new__(MidiPlayerBackend)
        backend._midi_control_state = MidiControlState()
        backend._midi_control_lock = threading.Lock()
        backend._sync_blue_timer = lambda *_args, **_kwargs: None
        backend._bump_binding_state = lambda *_args, **_kwargs: None

        state = backend._midi_control_state
        state.observe(1, 74, 0, now=1.0)
        state.observe(1, 74, 1, now=1.1)
        state.indicator_clicked((1, 74), now=1.2)
        state.bind_learned_target(
            {"id": "omni:master_volume", "screen": "omni"},
            now=1.3,
        )

        backend.clickControlIndicator(1, 74)
        self.assertEqual(state.status((1, 74)), "blue")
        self.assertIsNone(state.learn_key)

        backend.clickControlIndicator(1, 74)
        self.assertEqual(state.status((1, 74)), "learn")
        self.assertEqual(state.learn_key, (1, 74))

    def test_instrument_balance_multiplier_applies_to_midi_volume(self) -> None:
        client = _Client(instrument_levels={"dx7_215": 0.4})
        engine = MidiAmyEngine(client)
        client.events.clear()
        engine.configure_row(0, "dx7_215", {}, 0.5)
        self.assertIn(("wire", "i5iV0.2Z"), client.events)

    def test_rom_patch_waits_before_parameters_and_routing(self) -> None:
        client = _Client()
        engine = MidiAmyEngine(client)
        client.events.clear()

        engine.configure_row(
            0,
            "dx7_215",
            {"algorithm": 7.0},
            0.28,
        )
        self.assertEqual(
            client.events,
            [
                ("wire", "K215i5iv4iy4Z"),
                ("delay", 0.012),
                ("wire", "compat-215-5"),
                ("wire", "v0o7i5Z"),
                ("wire", "i5iy4Z"),
                ("wire", "i5iV0.28Z"),
                ("wire", "y4h0Z"),
                ("wire", "y4hS1,1Z"),
                ("wire", "y4V1Z"),
            ],
        )

    def test_master_volume_is_scoped_to_all_midi_buses(self) -> None:
        client = _Client()
        engine = MidiAmyEngine(client)
        client.events.clear()

        engine.set_master_volume(0.35)

        self.assertEqual(
            [value for kind, value in client.events if kind == "wire"],
            [f"y{bus}V0.35Z" for bus in range(4, 11)],
        )

        client.events.clear()
        engine.configure_row(0, "dx7_215", {}, 0.5)
        self.assertIn(("wire", "y4V0.35Z"), client.events)

    def test_only_reconfiguration_silences_an_existing_synth(self) -> None:
        client = _Client()
        engine = MidiAmyEngine(client)
        client.events.clear()

        engine.configure_row(5, "dx7_215", {}, 0.5)
        first_commands = [value for kind, value in client.events if kind == "wire"]
        self.assertNotIn("l0i10Z", first_commands)

        client.events.clear()
        engine.configure_row(5, "dx7_215", {}, 0.5)
        second_commands = [value for kind, value in client.events if kind == "wire"]
        self.assertEqual(second_commands[0], "l0i10Z")

    def test_unallocated_drum_row_is_not_sent_a_note_off(self) -> None:
        client = _Client()
        engine = MidiAmyEngine(client)
        client.events.clear()

        engine.silence_row(5)

        self.assertEqual(client.events, [])

    def test_strum_preview_releases_before_exceeding_voice_count(self) -> None:
        client = _Client()
        engine = MidiAmyEngine(client)
        client.events.clear()

        for note in (60.0, 64.0, 67.0, 71.0, 72.0):
            engine.preview_note(0, note)

        commands = [value for kind, value in client.events if kind == "wire"]
        fifth_on = commands.index("n72l0.826771654i5Z")
        self.assertEqual(commands[fifth_on - 1], "n60l0i5Z")
        self.assertEqual(
            engine._preview_active_notes[0],
            [64.0, 67.0, 71.0, 72.0],
        )
        self.assertEqual(
            [call[2] for call in client.application_scheduler.calls],
            ["midi-preview-tail-0"] * 5,
        )

    def test_every_midi_instrument_has_an_isolated_effect_bus(self) -> None:
        client = _Client()
        engine = MidiAmyEngine(client)

        self.assertEqual(engine.row_buses, (4, 5, 6, 7, 8, 9))
        self.assertEqual(engine.drum_bus, 10)

        client.events.clear()
        engine.configure_row(2, "dx7_215", {}, 0.5)
        self.assertIn(("wire", "K215i7iv4iy6Z"), client.events)
        self.assertIn(("wire", "i7iy6Z"), client.events)

        client.events.clear()
        engine.set_reverb(0.4, 0.6, 0.7, False)
        self.assertIn(("wire", "hR1,0.4,0.6,0.7Z"), client.events)
        reverb_commands = [
            value for kind, value in client.events if kind == "wire" and str(value).startswith("y")
        ]
        self.assertEqual(
            reverb_commands,
            [
                "y4h0Z",
                "y4hS1,1Z",
                "y5h0Z",
                "y5hS1,1Z",
                "y6h0Z",
                "y6hS1,1Z",
                "y7h0Z",
                "y7hS1,1Z",
                "y8h0Z",
                "y8hS1,1Z",
                "y9h0Z",
                "y9hS1,1Z",
                "y10h0Z",
                "y10hS1,0Z",
            ],
        )

        client.events.clear()
        engine.set_reverb(0.5, 0.6, 0.7, False)
        self.assertEqual(client.events, [("wire", "hR1,0.5,0.6,0.7Z")])

        client.events.clear()
        engine.set_reverb(0.5, 0.6, 0.7, True)
        self.assertEqual(
            client.events,
            [("wire", "y10hS1,1Z")],
        )

    def test_native_defaults_are_not_resent_by_midi_state(self) -> None:
        class Control:
            key = "filter_hz"
            label = "VCF base"
            group = "extra"
            default = 6000.0
            native_default = 6000.0
            minimum = 20.0
            maximum = 18000.0
            step = 1.0
            decimals = 0
            unit = "Hz"
            scale = "log"

        class Definition:
            key = "juno_068"
            label = "Harpsichord 1"
            controls = (Control(),)

        state = SynthState((Definition(),), 0)

        self.assertEqual(
            state.transport_payload(),
            {"name": "juno_068", "params": []},
        )


if __name__ == "__main__":
    unittest.main()
