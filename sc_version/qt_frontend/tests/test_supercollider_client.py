from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from engine_protocol import NoteOff, NoteOn  # noqa: E402
from resolved_config import resolve_amy_config_data  # noqa: E402
from supercollider_client import SuperColliderClient  # noqa: E402


class _FakeSuperCollider:
    def __init__(self) -> None:
        self.messages: list[tuple[str, tuple[object, ...]]] = []
        self.ready = threading.Event()
        dispatcher = Dispatcher()
        dispatcher.set_default_handler(self._accept)
        self.server = ThreadingOSCUDPServer(("127.0.0.1", 0), dispatcher)
        self.port = int(self.server.server_address[1])
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def _accept(self, address: str, *arguments: object) -> None:
        self.messages.append((address, arguments))
        if address == "/omni/v1/hello":
            client = SimpleUDPClient("127.0.0.1", int(arguments[2]))
            try:
                client.send_message(
                    "/omni/v1/ready",
                    ["fake-engine", 1, "fake-catalog", "ready"],
                )
            finally:
                client._sock.close()
            self.ready.set()
        elif address == "/omni/v1/tx/commit":
            client = SimpleUDPClient("127.0.0.1", int(self.messages[0][1][2]))
            try:
                client.send_message(
                    "/omni/v1/ack",
                    [arguments[0], arguments[1], "applied", 1, 0.0, "ok"],
                )
            finally:
                client._sock.close()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1.0)


class SuperColliderClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fake = _FakeSuperCollider()
        self.temporary = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temporary.name) / "supercollider.json"
        self.config_path.write_text(
            json.dumps(
                {
                    "config_revision": 1,
                    "protocol_version": 1,
                    "language": {
                        "host": "127.0.0.1",
                        "port": self.fake.port,
                        "startup_timeout_seconds": 1.0,
                        "message_payload_bytes": 1000,
                    },
                    "server": {
                        "sample_rate": 48000,
                        "block_size": 64,
                        "latency_seconds": 0.02,
                        "max_nodes": 4096,
                        "realtime_memory_kib": 262144,
                    },
                    "samples": {
                        "vsco_root": "/not-used-by-client",
                        "ram_budget_mib": 4096,
                    },
                }
            ),
            encoding="utf-8",
        )
        raw = json.loads((ROOT / "config" / "amy_config.json").read_text())
        self.resolved = resolve_amy_config_data(
            raw,
            source_path=ROOT / "config" / "amy_config.json",
            source_kind="shipped",
        )

    def tearDown(self) -> None:
        self.fake.close()
        self.temporary.cleanup()

    def test_handshake_and_typed_note_lifecycle_cross_process_boundary(self) -> None:
        client = SuperColliderClient(
            config=None,
            addresses={},
            resolved_config=self.resolved,
            runtime_config_path=self.config_path,
            asset_root=ROOT,
        )
        self.assertTrue(self.fake.ready.wait(1.0))
        self.assertEqual(client.engine_session, "fake-engine")
        client.note_on(
            NoteOn(
                owner="test",
                handle="test/60",
                program_id="builtin.safe",
                program_revision=1,
                logical_key=60,
                frequency_hz=261.625565,
                velocity=0.75,
                logical_bus=4,
            )
        )
        client.note_off(NoteOff(owner="test", handle="test/60"))
        client.close()

        addresses = [address for address, _ in self.fake.messages]
        self.assertIn("/omni/v1/hello", addresses)
        self.assertIn("/omni/v1/note/on", addresses)
        self.assertIn("/omni/v1/note/off", addresses)
        self.assertIn("/omni/v1/panic", addresses)
        self.assertIn("/omni/v1/shutdown", addresses)

    def test_lane_transaction_is_indexed_and_acknowledged(self) -> None:
        from engine_protocol import SequenceDefinition, SequenceEvent
        from musical_sequence_plan import LanePlan

        client = SuperColliderClient(
            config=None,
            addresses={},
            resolved_config=self.resolved,
            runtime_config_path=self.config_path,
            asset_root=ROOT,
        )
        acknowledgement = client.publish_lane(
            LanePlan(
                lane="test",
                generation=1,
                alignment_ticks=1,
                definitions=(
                    SequenceDefinition(
                        definition_id="test/root",
                        revision=1,
                        kind="root",
                        lane="test",
                        period_ticks=48,
                        events=(SequenceEvent(0, 0, "launch", ("test/child",)),),
                        source_identity="fixture",
                    ),
                    SequenceDefinition(
                        definition_id="test/child",
                        revision=1,
                        kind="finite",
                        lane="test",
                        period_ticks=0,
                        events=(),
                        source_identity="fixture-child",
                    ),
                ),
            )
        )
        client.close()

        self.assertEqual(acknowledgement, ("applied", 1, 0.0, "ok"))
        transaction = [
            (address, arguments)
            for address, arguments in self.fake.messages
            if address.startswith("/omni/v1/tx/")
        ]
        self.assertEqual(
            [address for address, _arguments in transaction],
            [
                "/omni/v1/tx/begin",
                "/omni/v1/tx/def",
                "/omni/v1/tx/event",
                "/omni/v1/tx/def",
                "/omni/v1/tx/commit",
            ],
        )
        packet_indexes = [arguments[2] for _address, arguments in transaction[1:-1]]
        self.assertEqual(packet_indexes, [0, 1, 2])


if __name__ == "__main__":
    unittest.main()
