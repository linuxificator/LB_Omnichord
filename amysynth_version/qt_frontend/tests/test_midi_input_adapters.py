from __future__ import annotations

import ast
import sys
import tempfile
import threading
import time
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QObject, QThread, Signal, Slot


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
sys.path.insert(0, str(CODE))

from midi_control import MidiControlState, PITCH_BEND_CONTROLLER  # noqa: E402
from midi_input import (  # noqa: E402
    MidiByteStreamParser,
    MidiByteStreamState,
    MidiInputEvent,
    OrderedMidiInputEmitter,
)
from midi_linux import LinuxMidiInputPort, linux_technologies  # noqa: E402
from midi_platform_adapters import (  # noqa: E402
    create_midi_input_port,
    midi_input_technologies,
)
from midi_player import (  # noqa: E402
    MidiPlayerBackend,
    _QueuedMidiInputEventRelay,
)
from resolved_config import load_resolved_amy_config  # noqa: E402


def midi_config():
    return load_resolved_amy_config(ROOT / "config" / "amy_config.json").midi_input


class MidiInputAdapterTests(unittest.TestCase):
    def test_normalized_events_are_immutable_and_totally_ordered(self) -> None:
        events: list[MidiInputEvent] = []
        emitter = OrderedMidiInputEmitter(events.append)
        start = threading.Barrier(3)

        def notes() -> None:
            start.wait()
            emitter.note("raw", 1, 60, 100, True)

        def controls() -> None:
            start.wait()
            emitter.control("seq", 2, 74, 99)

        threads = [threading.Thread(target=notes), threading.Thread(target=controls)]
        for thread in threads:
            thread.start()
        start.wait()
        for thread in threads:
            thread.join(timeout=1.0)

        self.assertEqual([event.sequence for event in events], [1, 2])
        self.assertEqual({event.kind for event in events}, {"note", "control"})
        with self.assertRaises(FrozenInstanceError):
            events[0].sequence = 9  # type: ignore[misc]

    def test_raw_streams_preserve_independent_running_status(self) -> None:
        events: list[MidiInputEvent] = []
        emitter = OrderedMidiInputEmitter(events.append)
        first = MidiByteStreamParser(emitter, "first")
        second = MidiByteStreamParser(emitter, "second")
        first_state = MidiByteStreamState()
        second_state = MidiByteStreamState()

        first.feed(bytes([0x90, 60, 100, 61, 101]), first_state)
        second.feed(bytes([0xB1, 7, 64, 74, 99]), second_state)
        second.feed(bytes([0xE1, 0x00, 0x40]), second_state)

        self.assertEqual(
            [
                (event.kind, event.technology, event.channel, event.data, event.value)
                for event in events
            ],
            [
                ("note", "first", 1, 60, 100),
                ("note", "first", 1, 61, 101),
                ("control", "second", 2, 7, 64),
                ("control", "second", 2, 74, 99),
                ("control", "second", 2, PITCH_BEND_CONTROLLER, 8192),
            ],
        )

    def test_emitter_delivers_nothing_after_close(self) -> None:
        events: list[MidiInputEvent] = []
        emitter = OrderedMidiInputEmitter(events.append)
        emitter.activity("raw")
        emitter.close()
        emitter.note("raw", 1, 60, 100, True)
        emitter.close()
        self.assertEqual([event.kind for event in events], ["activity"])

    def test_package_profiles_select_only_their_capability_data(self) -> None:
        expected = {
            "linux": ("alsa_raw", "alsa_seq", "oss_midi"),
            "darwin": ("coremidi",),
            "win32": ("winmm",),
            "android": ("android_midi",),
            "freebsd": (),
        }
        for profile, keys in expected.items():
            with self.subTest(profile=profile):
                self.assertEqual(
                    tuple(
                        tech.key
                        for tech in midi_input_technologies(midi_config(), profile)
                    ),
                    keys,
                )

    def test_unavailable_adapters_share_lifecycle_and_status_contract(self) -> None:
        for profile in ("darwin", "win32", "android", "freebsd"):
            with self.subTest(profile=profile):
                port = create_midi_input_port(
                    lambda _event: self.fail("unsupported adapter emitted an event"),
                    midi_config(),
                    profile=profile,
                )
                self.assertEqual(port.lifecycle, "constructed")
                port.start()
                self.assertEqual(port.lifecycle, "ready")
                statuses = port.status_snapshot(now=10.0)
                self.assertTrue(
                    not statuses
                    or all(status.state == "unavailable" for status in statuses)
                )
                port.close()
                port.close()
                self.assertEqual(port.lifecycle, "closed")

    def test_disabled_linux_port_starts_no_native_readers(self) -> None:
        config = replace(midi_config(), enabled=False)
        with (
            patch("midi_linux.LinuxRawMidiReader") as raw_reader,
            patch("midi_linux.AlsaSequencerMidiReader") as sequencer_reader,
        ):
            port = LinuxMidiInputPort(lambda _event: None, config)
            port.start()

        raw_reader.assert_not_called()
        sequencer_reader.assert_not_called()
        self.assertTrue(
            all(status.state == "unavailable" for status in port.status_snapshot())
        )
        port.close()
        self.assertEqual(port.lifecycle, "closed")

    def test_enabled_linux_port_starts_two_raw_and_one_sequencer_reader(self) -> None:
        class Reader:
            def close(self) -> None:
                pass

        with (
            patch("midi_linux.LinuxRawMidiReader", return_value=Reader()) as raw,
            patch(
                "midi_linux.AlsaSequencerMidiReader",
                return_value=Reader(),
            ) as sequencer,
        ):
            port = LinuxMidiInputPort(lambda _event: None, midi_config())
            port.start()
            port.close()

        self.assertEqual(raw.call_count, 2)
        self.assertEqual(sequencer.call_count, 1)
        self.assertEqual(port.lifecycle, "closed")

    def test_linux_raw_status_reports_readable_path_and_activity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "midi0"
            path.write_bytes(b"")
            config = replace(
                midi_config(),
                device_glob=str(path),
                alsa_raw_globs=(str(path),),
            )
            port = LinuxMidiInputPort(lambda _event: None, config)
            statuses = port.status_snapshot({"alsa_raw": 20.0}, now=10.0)

        raw = next(status for status in statuses if status.key == "alsa_raw")
        self.assertEqual(raw.state, "activity")
        self.assertTrue(raw.available)
        self.assertIn("midi0", raw.reason)
        port.close()

    def test_legacy_raw_override_is_preserved_by_linux_adapter(self) -> None:
        config = replace(
            midi_config(),
            device_glob="/tmp/legacy-midi",
            alsa_raw_globs=("/tmp/configured-midi",),
        )
        raw = linux_technologies(config)[0]
        self.assertEqual(
            raw.globs,
            ("/tmp/legacy-midi", "/tmp/configured-midi"),
        )

    def test_qt_boundary_drains_out_of_order_delivery_before_dispatch(self) -> None:
        backend = MidiPlayerBackend.__new__(MidiPlayerBackend)
        backend._last_midi_input_sequence = 0
        backend._pending_midi_input_events = {}
        backend._midi_input_closed = False
        backend._midi_control_state = MidiControlState()
        observed: list[tuple[str, int]] = []
        backend.process_midi_note = lambda _c, note, _v, _on: observed.append(
            ("note", note)
        )
        backend.process_midi_control = lambda _c, control, _v: observed.append(
            ("control", control)
        )
        backend.process_midi_button = lambda _c, note, _v: observed.append(
            ("button", note)
        )
        backend._mark_midi_tech_activity = lambda _key: observed.append(
            ("activity", 0)
        )

        backend._accept_midi_input_event(
            MidiInputEvent(2, "control", "raw", 1, 74, 99)
        )
        self.assertEqual(observed, [])
        backend._accept_midi_input_event(
            MidiInputEvent(1, "note", "raw", 1, 60, 100, True)
        )
        backend._accept_midi_input_event(
            MidiInputEvent(3, "button", "future", 1, 42, 127, True)
        )
        backend._accept_midi_input_event(MidiInputEvent(4, "activity", "raw"))

        self.assertEqual(
            observed,
            [("note", 60), ("control", 74), ("button", 42), ("activity", 0)],
        )

        backend._midi_input_closed = True
        backend._accept_midi_input_event(
            MidiInputEvent(5, "note", "raw", 1, 61, 100, True)
        )
        self.assertEqual(len(observed), 4)

    def test_worker_emission_runs_receiver_only_on_its_qt_thread(self) -> None:
        application = QCoreApplication.instance() or QCoreApplication([])

        class Receiver(QObject):
            event = Signal(object)

            def __init__(self) -> None:
                super().__init__()
                self.thread_matches: list[bool] = []
                self.event.connect(self.accept)

            @Slot(object)
            def accept(self, _event: object) -> None:
                self.thread_matches.append(QThread.currentThread() == self.thread())

        receiver = Receiver()
        relay = _QueuedMidiInputEventRelay(receiver.event.emit)
        worker = threading.Thread(
            target=lambda: relay(MidiInputEvent(1, "activity", "test"))
        )
        worker.start()
        worker.join(timeout=1.0)
        deadline = time.monotonic() + 1.0
        while not receiver.thread_matches and time.monotonic() < deadline:
            application.processEvents()
            time.sleep(0.001)

        self.assertEqual(receiver.thread_matches, [True])

    def test_portable_midi_player_has_no_native_import_or_device_probe(self) -> None:
        source = (CODE / "midi_player.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imports.update(
            node.module.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        self.assertTrue(imports.isdisjoint({"ctypes", "glob", "select", "midi_linux"}))
        self.assertNotIn("/dev/", source)
        self.assertNotIn("self.process_midi_note,", source)


if __name__ == "__main__":
    unittest.main()
