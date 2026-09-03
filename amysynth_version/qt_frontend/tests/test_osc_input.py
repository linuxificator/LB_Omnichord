from __future__ import annotations

import socket
import sys
import threading
import unittest
from pathlib import Path

from pythonosc.osc_bundle_builder import IMMEDIATELY, OscBundleBuilder
from pythonosc.osc_message_builder import OscMessageBuilder


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from osc_input import (  # noqa: E402
    OscInputEvent,
    PythonOscUdpInputPort,
    decode_osc_packet,
    production_osc_input_port,
)
from midi_control import MidiControlState  # noqa: E402
from midi_player import MidiPlayerBackend  # noqa: E402
from resolved_config import OscInputConfig  # noqa: E402


def message(address: str, *values: object) -> bytes:
    builder = OscMessageBuilder(address=address)
    for value in values:
        builder.add_arg(value)
    return builder.build().dgram


def unused_udp_port() -> int:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])
    finally:
        probe.close()


class OscPacketTests(unittest.TestCase):
    def test_decodes_numeric_arguments_and_ignores_other_types(self) -> None:
        self.assertEqual(
            decode_osc_packet(message("/surface/xy", 0.25, 2.0, "ignore", True)),
            (
                ("/surface/xy", 0, 0.25, "continuous"),
                ("/surface/xy", 1, 1.0, "button"),
                ("/surface/xy", 3, 1.0, "button"),
            ),
        )

    def test_preserves_bundle_message_order_and_survives_malformed_data(self) -> None:
        bundle = OscBundleBuilder(IMMEDIATELY)
        bundle.add_content(OscMessageBuilder(address="/first").build())
        second = OscMessageBuilder(address="/second")
        second.add_arg(0.4)
        bundle.add_content(second.build())
        third = OscMessageBuilder(address="/third")
        third.add_arg(False)
        bundle.add_content(third.build())

        self.assertEqual(
            decode_osc_packet(bundle.build().dgram),
            (
                ("/second", 0, 0.4000000059604645, "continuous"),
                ("/third", 0, 0.0, "button"),
            ),
        )
        self.assertEqual(decode_osc_packet(b"not an OSC packet"), ())


class OscUdpInputPortTests(unittest.TestCase):
    def test_receives_real_udp_after_bad_packet_and_closes_idempotently(self) -> None:
        received: list[OscInputEvent] = []
        arrived = threading.Event()

        def sink(event: OscInputEvent) -> None:
            received.append(event)
            arrived.set()

        port_number = unused_udp_port()
        port = PythonOscUdpInputPort(
            sink,
            OscInputConfig(True, "127.0.0.1", port_number),
        )
        port.start()
        self.assertEqual(port.lifecycle, "ready")
        listening = port.status_snapshot(0.0, True)
        self.assertIsNotNone(listening)
        assert listening is not None
        self.assertEqual(listening.state, "listening")
        self.assertTrue(listening.idle_led_visible)
        active = port.status_snapshot(float("inf"), True)
        self.assertIsNotNone(active)
        assert active is not None
        self.assertEqual(active.state, "activity")
        disconnected = port.status_snapshot(float("inf"), False)
        self.assertIsNotNone(disconnected)
        assert disconnected is not None
        self.assertEqual(disconnected.state, "unavailable")
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sender.sendto(b"malformed", ("127.0.0.1", port_number))
            sender.sendto(message("/filter", 0.75), ("127.0.0.1", port_number))
            self.assertTrue(arrived.wait(2.0))
        finally:
            sender.close()
            port.close()
            port.close()

        self.assertEqual(port.lifecycle, "closed")
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].sequence, 1)
        self.assertEqual(received[0].address, "/filter")
        self.assertAlmostEqual(received[0].value, 0.75)
        port._emitter.emit("/late", 0, 1.0, "button")
        self.assertEqual(len(received), 1)

    def test_disabled_and_bind_failure_are_explicit_capability_states(self) -> None:
        disabled = PythonOscUdpInputPort(
            lambda _event: None,
            OscInputConfig(False, "0.0.0.0", 8000),
        )
        disabled.start()
        self.assertEqual(disabled.lifecycle, "ready")
        self.assertIsNone(disabled.status_snapshot(float("inf"), True))
        disabled.close()

        unconfigured = PythonOscUdpInputPort(
            lambda _event: None,
            OscInputConfig(False, None, None, configured=False),
        )
        unconfigured.start()
        self.assertIsNone(unconfigured.status_snapshot(float("inf"), False))
        unconfigured.close()

        occupied = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        occupied.bind(("127.0.0.1", 0))
        try:
            port_number = int(occupied.getsockname()[1])
            failed = PythonOscUdpInputPort(
                lambda _event: None,
                OscInputConfig(True, "127.0.0.1", port_number),
            )
            failed.start()
            self.assertEqual(failed.lifecycle, "failed")
            self.assertTrue(failed.failure_reason)
            failed_status = failed.status_snapshot(0.0, True)
            self.assertIsNotNone(failed_status)
            assert failed_status is not None
            self.assertEqual(failed_status.state, "unavailable")
            failed.close()
        finally:
            occupied.close()

    def test_production_factory_requires_typed_resolved_config(self) -> None:
        with self.assertRaisesRegex(TypeError, "resolved OscInputConfig"):
            production_osc_input_port(lambda _event: None, {})

    def test_qt_boundary_drains_osc_events_in_sequence(self) -> None:
        backend = MidiPlayerBackend.__new__(MidiPlayerBackend)
        backend._last_osc_input_sequence = 0
        backend._pending_osc_input_events = {}
        backend._osc_input_closed = False
        backend._midi_control_state = MidiControlState()
        activity: list[bool] = []
        backend._mark_osc_input_activity = lambda: activity.append(True)
        observed: list[tuple[str, int, float, str]] = []
        backend.process_osc_control = (
            lambda address, argument, value, value_type: observed.append(
                (address, argument, value, value_type)
            )
        )

        backend._accept_osc_input_event(
            OscInputEvent(2, "/second", 1, 0.8, "continuous")
        )
        self.assertEqual(observed, [])
        backend._accept_osc_input_event(
            OscInputEvent(1, "/first", 0, 1.0, "button")
        )
        self.assertEqual(
            observed,
            [
                ("/first", 0, 1.0, "button"),
                ("/second", 1, 0.8, "continuous"),
            ],
        )
        backend._osc_input_closed = True
        backend._accept_osc_input_event(
            OscInputEvent(3, "/late", 0, 0.0, "button")
        )
        self.assertEqual(len(observed), 2)
        self.assertEqual(activity, [True, True])


if __name__ == "__main__":
    unittest.main()
