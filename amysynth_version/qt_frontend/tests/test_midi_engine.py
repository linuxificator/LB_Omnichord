from __future__ import annotations

import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from midi_player import (  # noqa: E402
    MidiAmyEngine,
    MidiPlayerBackend,
    _LinuxRawMidiReader,
    _MidiInputTechManager,
)
from midi_control import NOTE_BUTTON_OFFSET, PITCH_BEND_CONTROLLER  # noqa: E402
from midi_control import MidiControlState  # noqa: E402
from synth_state import SynthState  # noqa: E402


class _RecordingWriter:
    def __init__(self, events: list[tuple[str, object]]) -> None:
        self.events = events

    def delay(self, seconds: float) -> None:
        self.events.append(("delay", seconds))


class _Client:
    def __init__(self) -> None:
        self.events: list[tuple[str, object]] = []
        self.writer = _RecordingWriter(self.events)
        self.config = {
            "midi_player": {},
            "buses": {
                "midi_rows": [4, 5, 6, 7, 8, 9],
                "midi_drums": 10,
            },
            "performance": {"synth_alloc_guard_ms": 12.0},
        }
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
    def test_midi_platform_techs_are_filtered_by_runtime_platform(self) -> None:
        cases = {
            "linux": ("alsa_raw", "alsa_seq", "oss_midi"),
            "darwin": ("coremidi",),
            "win32": ("winmm",),
            "android": ("android_midi",),
            "freebsd": (),
        }
        for profile, expected in cases.items():
            with self.subTest(profile=profile):
                techs = _MidiInputTechManager.platform_techs(
                    {"device_glob": "/tmp/midi-test"},
                    profile,
                )
                self.assertEqual(
                    tuple(item["key"] for item in techs),
                    expected,
                )

        linux = _MidiInputTechManager.platform_techs(
            {"device_glob": "/tmp/midi-test"},
            "linux",
        )
        self.assertEqual(linux[0]["globs"], ["/tmp/midi-test"])

    def test_linux_legacy_raw_glob_is_preserved_with_new_config(self) -> None:
        linux = _MidiInputTechManager.platform_techs(
            {
                "device_glob": "/tmp/legacy-midi",
                "alsa_raw_globs": ["/tmp/configured-midi"],
            },
            "linux",
        )

        self.assertEqual(
            linux[0]["globs"],
            ["/tmp/legacy-midi", "/tmp/configured-midi"],
        )

    def test_non_linux_profiles_expose_only_their_platform_tech(self) -> None:
        expected = {
            "darwin": ("coremidi", "CoreMIDI"),
            "win32": ("winmm", "WinMM MIDI"),
            "android": ("android_midi", "Android MIDI"),
        }
        for profile, (key, label) in expected.items():
            with self.subTest(profile=profile):
                techs = _MidiInputTechManager.platform_techs({}, profile)
                self.assertEqual(len(techs), 1)
                self.assertEqual(techs[0]["key"], key)
                self.assertEqual(techs[0]["label"], label)
                self.assertEqual(techs[0]["backend"], "unsupported")

    def test_midi_tech_status_marks_readable_inputs_and_activity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "midi0"
            path.write_bytes(b"")
            manager = _MidiInputTechManager.__new__(_MidiInputTechManager)
            manager._enabled = True
            manager._techs = [
                {
                    "key": "test_raw",
                    "label": "Test raw",
                    "backend": "byte_stream",
                    "globs": [str(path)],
                },
                {
                    "key": "missing_raw",
                    "label": "Missing raw",
                    "backend": "byte_stream",
                    "globs": [str(Path(directory) / "missing")],
                },
            ]

            snapshot = manager.status_snapshot({"test_raw": 20.0}, now=10.0)

            self.assertEqual(snapshot[0]["state"], "activity")
            self.assertTrue(snapshot[0]["available"])
            self.assertEqual(snapshot[1]["state"], "unavailable")
            self.assertFalse(snapshot[1]["available"])

    def test_unsupported_platform_techs_are_visible_red_not_listened(self) -> None:
        expected = ("darwin", "win32", "android")
        for profile in expected:
            with self.subTest(profile=profile):
                manager = _MidiInputTechManager.__new__(_MidiInputTechManager)
                manager._enabled = True
                manager._listener_readers = {}
                manager._techs = _MidiInputTechManager.platform_techs(
                    {},
                    profile,
                )

                snapshot = manager.status_snapshot({}, now=10.0)

                self.assertEqual(len(snapshot), 1)
                self.assertEqual(snapshot[0]["state"], "unavailable")
                self.assertFalse(snapshot[0]["available"])
                self.assertIn("not bundled", snapshot[0]["reason"])

    def test_disabled_midi_input_starts_no_platform_readers(self) -> None:
        for profile in ("linux", "darwin", "win32", "android"):
            with self.subTest(profile=profile):
                with (
                    patch("midi_player._LinuxRawMidiReader") as raw_reader,
                    patch("midi_player._AlsaSequencerMidiReader") as seq_reader,
                ):
                    manager = _MidiInputTechManager(
                        lambda *_args: None,
                        lambda *_args: None,
                        lambda *_args: None,
                        {"enabled": False, "tech_profile": profile},
                    )

                raw_reader.assert_not_called()
                seq_reader.assert_not_called()
                snapshot = manager.status_snapshot({}, now=10.0)
                self.assertTrue(snapshot)
                self.assertTrue(
                    all(item["state"] == "unavailable" for item in snapshot)
                )

    def test_linux_midi_manager_starts_real_alsa_sequencer_listener(self) -> None:
        with (
            patch("midi_player._LinuxRawMidiReader") as raw_reader,
            patch("midi_player._AlsaSequencerMidiReader") as seq_reader,
        ):
            raw_reader.return_value = object()
            seq_reader.return_value = object()

            manager = _MidiInputTechManager(
                lambda *_args: None,
                lambda *_args: None,
                lambda *_args: None,
                {"enabled": True, "tech_profile": "linux"},
            )

        self.assertEqual(seq_reader.call_count, 1)
        self.assertEqual(raw_reader.call_count, 2)
        self.assertIn("alsa_seq", manager._listener_readers)

    def test_non_linux_managers_do_not_start_raw_or_alsa_seq_readers(self) -> None:
        for profile in ("darwin", "win32", "android"):
            with self.subTest(profile=profile):
                with (
                    patch("midi_player._LinuxRawMidiReader") as raw_reader,
                    patch("midi_player._AlsaSequencerMidiReader") as seq_reader,
                ):
                    manager = _MidiInputTechManager(
                        lambda *_args: None,
                        lambda *_args: None,
                        lambda *_args: None,
                        {"enabled": True, "tech_profile": profile},
                    )

                raw_reader.assert_not_called()
                seq_reader.assert_not_called()
                self.assertEqual(manager._listener_readers, {})

    def test_alsa_sequencer_status_comes_from_running_listener(self) -> None:
        class Listener:
            def status_snapshot(self, activity: bool) -> dict[str, object]:
                return {
                    "state": "activity" if activity else "listening",
                    "available": True,
                    "reason": "client 128:0",
                }

        manager = _MidiInputTechManager.__new__(_MidiInputTechManager)
        manager._enabled = True
        manager._listener_readers = {"alsa_seq": Listener()}
        manager._techs = [
            {
                "key": "alsa_seq",
                "label": "ALSA seq",
                "backend": "alsa_seq",
            }
        ]

        snapshot = manager.status_snapshot({"alsa_seq": 20.0}, now=10.0)

        self.assertEqual(snapshot[0]["state"], "activity")
        self.assertTrue(snapshot[0]["available"])
        self.assertEqual(snapshot[0]["reason"], "client 128:0")

    def test_midi_tech_parsers_keep_running_status_per_stream(self) -> None:
        notes = []
        controls = []

        def reader() -> _LinuxRawMidiReader:
            item = _LinuxRawMidiReader.__new__(_LinuxRawMidiReader)
            item._callback = lambda *args: notes.append(args)
            item._control_callback = lambda *args: controls.append(args)
            return item

        first = reader()
        second = reader()
        state_a: dict[str, object] = {}
        state_b: dict[str, object] = {}

        first._parse_stream(bytes([0x90, 60, 100, 61, 101]), state_a)
        second._parse_stream(bytes([0xB1, 7, 64, 74, 99]), state_b)
        second._parse_stream(bytes([0xE1, 0x00, 0x40]), state_b)

        self.assertEqual(notes, [(1, 60, 100, True), (1, 61, 101, True)])
        self.assertEqual(
            controls,
            [
                (2, 7, 64),
                (2, 74, 99),
                (2, PITCH_BEND_CONTROLLER, 8192),
            ],
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
        backend._queue_midi_button = lambda *_args: self.fail(
            "MIDI Note On/Off must not be treated as controller buttons"
        )

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
        expected = round(
            20.0 * (20000.0 / 20.0) ** (64.0 / 127.0)
        )
        self.assertEqual(middle, expected)
        self.assertNotAlmostEqual(middle, (20.0 + 20000.0) / 2.0)

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
        ]

        entries = backend._normalized_binding_entries("omni", data)

        self.assertEqual(
            [key for key, _target in entries],
            [
                (1, 74),
                (2, PITCH_BEND_CONTROLLER),
                (3, NOTE_BUTTON_OFFSET + 42),
            ],
        )

    def test_midi_button_takeover_blocks_other_button_targets(self) -> None:
        backend = MidiPlayerBackend.__new__(MidiPlayerBackend)
        backend._applying_midi_control = 0
        backend._midi_control_lock = threading.Lock()
        backend._held_midi_button_targets = {"omni:button:rhythm_toggle"}

        self.assertFalse(
            backend.midiButtonTargetBlocked(
                {
                    "screen": "omni",
                    "kind": "button",
                    "action": "rhythm_toggle",
                }
            )
        )
        self.assertTrue(
            backend.midiButtonTargetBlocked(
                {
                    "screen": "omni",
                    "kind": "button",
                    "action": "master_mute",
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

    def test_pitch_bend_binding_applies_center_value_immediately(self) -> None:
        backend = MidiPlayerBackend.__new__(MidiPlayerBackend)
        backend._midi_control_state = MidiControlState()
        backend._midi_control_lock = threading.Lock()
        backend._write_cc_test_log = lambda *_args, **_kwargs: None
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
        backend._midi_control_state.select_control(
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

    def test_instrument_balance_multiplier_applies_to_midi_volume(self) -> None:
        client = _Client()
        client.config["instrument_levels"] = {"dx7_215": 0.4}
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

        class Timer:
            def __init__(self, _delay: float, callback: object) -> None:
                self.callback = callback
                self.daemon = False

            def start(self) -> None:
                return

        with patch("midi_player.threading.Timer", Timer):
            for note in (60.0, 64.0, 67.0, 71.0, 72.0):
                engine.preview_note(0, note)

        commands = [value for kind, value in client.events if kind == "wire"]
        fifth_on = commands.index("n72l0.826771654i5Z")
        self.assertEqual(commands[fifth_on - 1], "n60l0i5Z")
        self.assertEqual(
            engine._preview_active_notes[0],
            [64.0, 67.0, 71.0, 72.0],
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
        reverb_commands = [
            value
            for kind, value in client.events
            if kind == "wire" and str(value).startswith("y")
        ]
        self.assertEqual(
            reverb_commands,
            [
                "y4h0.4,0.6,0.7Z",
                "y5h0.4,0.6,0.7Z",
                "y6h0.4,0.6,0.7Z",
                "y7h0.4,0.6,0.7Z",
                "y8h0.4,0.6,0.7Z",
                "y9h0.4,0.6,0.7Z",
                "y10h0,0.6,0.7Z",
            ],
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
