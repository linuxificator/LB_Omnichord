from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from engine_protocol import NoteOff, NoteOn  # noqa: E402
from resolved_config import resolve_amy_config_data  # noqa: E402
from supercollider_client import SuperColliderClient  # noqa: E402


class _FakeSuperCollider:
    def __init__(self, *, incomplete_once: bool = False) -> None:
        self.messages: list[tuple[str, tuple[object, ...]]] = []
        self.incomplete_once = incomplete_once
        self.commit_count = 0
        self.ready = threading.Event()
        dispatcher = Dispatcher()
        dispatcher.set_default_handler(self._accept)
        # A single receive loop preserves packet order and gives each test a
        # deterministic boundary without changing the production UDP client.
        self.server = BlockingOSCUDPServer(("127.0.0.1", 0), dispatcher)
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
            self.commit_count += 1
            client = SimpleUDPClient("127.0.0.1", int(self.messages[0][1][2]))
            try:
                incomplete = self.incomplete_once and self.commit_count == 1
                client.send_message(
                    "/omni/v1/ack",
                    [
                        arguments[0],
                        arguments[1],
                        "received" if incomplete else "applied",
                        1,
                        0.0,
                        "incomplete" if incomplete else "ok",
                    ],
                )
            finally:
                client._sock.close()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1.0)

    def wait_for_messages(
        self,
        address: str,
        *,
        count: int = 1,
        timeout: float = 1.0,
    ) -> bool:
        """Wait until the separate fake engine has received the UDP packets."""

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if sum(item[0] == address for item in self.messages) >= count:
                return True
            time.sleep(0.005)
        return sum(item[0] == address for item in self.messages) >= count


class SuperColliderClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fake = _FakeSuperCollider()
        self.temporary = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temporary.name) / "supercollider.json"
        self.config_path.write_text(
            json.dumps(
                {
                    "config_revision": 2,
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
                        "max_buffers": 8192,
                        "realtime_memory_kib": 262144,
                    },
                    "samples": {
                        "vsco_root": "/not-used-by-client",
                        "repository": "https://github.com/linuxificator/VSCO-2-CE.git",
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

    def close_client(self, client: SuperColliderClient) -> None:
        client.close()
        self.assertTrue(
            self.fake.wait_for_messages("/omni/v1/shutdown"),
            "fake engine did not consume the client's shutdown boundary",
        )

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
        self.assertTrue(
            all(
                program.startswith("sc.sclork.")
                for program in client._selected_program.values()
            )
        )
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
        client.set_owner_sustain("test", True)
        client.set_owner_sustain("test", False)
        self.close_client(client)

        addresses = [address for address, _ in self.fake.messages]
        self.assertIn("/omni/v1/hello", addresses)
        self.assertIn("/omni/v1/note/on", addresses)
        self.assertIn("/omni/v1/note/off", addresses)
        self.assertIn("/omni/v1/owner/sustain", addresses)
        self.assertIn("/omni/v1/panic", addresses)
        self.assertIn("/omni/v1/shutdown", addresses)

    def test_global_pitch_bend_crosses_the_typed_engine_boundary(self) -> None:
        address_names = (
            "chord_amp",
            "strum_amp",
            "bass_amp",
            "percussion_amp",
            "master_volume",
            "reverb",
            "chord_synth",
            "strum_synth",
            "bass_synth",
            "manual_chord",
            "chord_state",
            "strum_note",
            "bass_running",
            "rhythm_config",
            "rhythm_chord_enabled",
            "pitch_bend",
            "rhythm_running",
            "panic",
        )
        addresses = {name: f"/test/{name}" for name in address_names}
        client = SuperColliderClient(
            config=None,
            addresses=addresses,
            resolved_config=self.resolved,
            runtime_config_path=self.config_path,
            asset_root=ROOT,
        )

        client.send_message(addresses["pitch_bend"], -0.125)
        self.close_client(client)

        bends = [
            arguments
            for address, arguments in self.fake.messages
            if address == "/omni/v1/global/pitch-bend"
        ]
        self.assertEqual(len(bends), 1)
        self.assertEqual(bends[0][0], client.session)
        self.assertAlmostEqual(float(bends[0][2]), -0.125)

    def test_program_revisions_and_parameters_are_part_scoped(self) -> None:
        client = SuperColliderClient(
            config=None,
            addresses={},
            resolved_config=self.resolved,
            runtime_config_path=self.config_path,
            asset_root=ROOT,
        )

        client._set_program(
            "chord", {"name": "sc.omni.acid303", "params": ["gain", 0.3]}
        )
        chord_revision = client._program_revision["chord"]
        client._set_program(
            "bass", {"name": "sc.omni.acid303", "params": ["gain", 0.8]}
        )
        bass_revision = client._program_revision["bass"]
        self.close_client(client)

        self.assertNotEqual(chord_revision, bass_revision)
        prepares = [
            arguments
            for address, arguments in self.fake.messages
            if address == "/omni/v1/program/prepare"
        ]
        self.assertEqual(
            [(item[2], item[3], item[4]) for item in prepares],
            [
                ("omni/manual", "sc.omni.acid303", chord_revision),
                ("rhythm/chords", "sc.omni.acid303", chord_revision),
                ("rhythm/bass", "sc.omni.acid303", bass_revision),
            ],
        )

    def test_strum_gesture_carries_the_selected_program_revision(self) -> None:
        client = SuperColliderClient(
            config=None,
            addresses={},
            resolved_config=self.resolved,
            runtime_config_path=self.config_path,
            asset_root=ROOT,
        )
        client._set_program(
            "strum", {"name": "sc.omni.acid303", "params": ["gain", 0.4]}
        )
        revision = client._program_revision["strum"]

        client._strum_note(64.25)
        self.close_client(client)

        gestures = [
            arguments
            for address, arguments in self.fake.messages
            if address == "/omni/v1/gesture/note"
        ]
        self.assertEqual(len(gestures), 1)
        self.assertEqual(gestures[0][4], "sc.omni.acid303")
        self.assertEqual(int(gestures[0][10]), revision)
        self.assertEqual(len(gestures[0]), 11)

    def test_direct_drum_hit_selects_requested_kit_before_crossing_boundary(self) -> None:
        client = SuperColliderClient(
            config=None,
            addresses={},
            resolved_config=self.resolved,
            runtime_config_path=self.config_path,
            asset_root=ROOT,
        )

        client.drum_hit(
            owner="midi/drums",
            logical_key=36,
            velocity=0.5,
            logical_bus=10,
            kit_id="sc-808",
        )
        self.assertTrue(self.fake.wait_for_messages("/omni/v1/drum/hit"))
        self.close_client(client)

        hits = [
            arguments
            for address, arguments in self.fake.messages
            if address == "/omni/v1/drum/hit"
        ]
        self.assertEqual(len(hits), 1)
        self.assertEqual(len(hits[0]), 7)
        self.assertEqual(hits[0][2], "midi/drums")
        self.assertEqual(hits[0][3], "sc.sclork.kick808")
        self.assertEqual(hits[0][4], 36)
        self.assertAlmostEqual(float(hits[0][5]), 0.5)
        self.assertEqual(hits[0][6], 10)

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
        self.close_client(client)

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

    def test_incomplete_transaction_retries_same_indexed_payload(self) -> None:
        from engine_protocol import SequenceDefinition
        from musical_sequence_plan import LanePlan

        self.fake.close()
        self.fake = _FakeSuperCollider(incomplete_once=True)
        raw_config = json.loads(self.config_path.read_text(encoding="utf-8"))
        raw_config["language"]["port"] = self.fake.port
        self.config_path.write_text(json.dumps(raw_config), encoding="utf-8")
        client = SuperColliderClient(
            config=None,
            addresses={},
            resolved_config=self.resolved,
            runtime_config_path=self.config_path,
            asset_root=ROOT,
        )
        acknowledgement = client.publish_lane(
            LanePlan(
                lane="retry",
                generation=1,
                alignment_ticks=1,
                definitions=(
                    SequenceDefinition(
                        "retry/root", 1, "root", "retry", 48, (), "fixture"
                    ),
                ),
            )
        )
        self.close_client(client)
        self.assertEqual(acknowledgement, ("applied", 1, 0.0, "ok"))
        self.assertEqual(self.fake.commit_count, 2)

    def test_sample_program_activates_only_after_engine_ready_status(self) -> None:
        client = SuperColliderClient(
            config=None,
            addresses={},
            resolved_config=self.resolved,
            runtime_config_path=self.config_path,
            asset_root=ROOT,
        )
        previous = client._selected_program["strum"]
        program = "sample.vsco.marimba"
        client._set_program("strum", {"name": program, "params": []})
        self.assertEqual(client._selected_program["strum"], previous)
        pending_key = next(key for key in client._pending_programs if key[0] == program)

        sender = SimpleUDPClient("127.0.0.1", client.reply_port)
        try:
            sender.send_message(
                "/omni/v1/program/status",
                [client.session, program, pending_key[1], "ready", "ready"],
            )
        finally:
            sender._sock.close()
        deadline = time.monotonic() + 1.0
        while client._selected_program["strum"] != program and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(client._selected_program["strum"], program)
        self.close_client(client)

    def test_direct_sample_note_waits_for_ready_and_obeys_early_note_off(self) -> None:
        client = SuperColliderClient(
            config=None,
            addresses={},
            resolved_config=self.resolved,
            runtime_config_path=self.config_path,
            asset_root=ROOT,
        )
        program = "sample.vsco.marimba"
        revision = client.allocate_program_revision()
        client.configure_part("midi/row/0", program, revision, 4, {})
        first = NoteOn(
            owner="midi/row/0",
            handle="midi/row/0/60",
            program_id=program,
            program_revision=revision,
            logical_key=60,
            frequency_hz=261.625565,
            velocity=0.7,
            logical_bus=4,
        )
        client.note_on(first)
        self.assertFalse(
            any(address == "/omni/v1/note/on" for address, _ in self.fake.messages)
        )
        client.note_off(NoteOff(first.owner, first.handle))

        second = NoteOn(
            owner="midi/row/0",
            handle="midi/row/0/64",
            program_id=program,
            program_revision=revision,
            logical_key=64,
            frequency_hz=329.627557,
            velocity=0.7,
            logical_bus=4,
        )
        client.note_on(second)
        sender = SimpleUDPClient("127.0.0.1", client.reply_port)
        try:
            sender.send_message(
                "/omni/v1/program/status",
                [client.session, program, revision, "ready", "ready"],
            )
        finally:
            sender._sock.close()
        deadline = time.monotonic() + 1.0
        while not any(
            address == "/omni/v1/note/on" for address, _ in self.fake.messages
        ) and time.monotonic() < deadline:
            time.sleep(0.01)
        note_ons = [
            arguments
            for address, arguments in self.fake.messages
            if address == "/omni/v1/note/on"
        ]
        self.assertEqual(len(note_ons), 1)
        self.assertEqual(note_ons[0][3], second.handle)
        self.close_client(client)

    def test_superseded_and_replaced_sample_revisions_are_released(self) -> None:
        client = SuperColliderClient(
            config=None,
            addresses={},
            resolved_config=self.resolved,
            runtime_config_path=self.config_path,
            asset_root=ROOT,
        )
        client._set_program("strum", {"name": "sample.vsco.marimba", "params": []})
        first_key = next(iter(client._pending_programs))
        client._set_program("strum", {"name": "sample.vsco.vibraphone", "params": []})
        second_key = next(iter(client._pending_programs))
        self.assertNotEqual(first_key, second_key)
        self.assertNotIn(first_key, client._pending_programs)

        sender = SimpleUDPClient("127.0.0.1", client.reply_port)
        try:
            sender.send_message(
                "/omni/v1/program/status",
                [client.session, second_key[0], second_key[1], "ready", "ready"],
            )
        finally:
            sender._sock.close()
        deadline = time.monotonic() + 1.0
        while client._selected_program["strum"] != second_key[0] and time.monotonic() < deadline:
            time.sleep(0.01)
        client._set_program("strum", {"name": "sample.vsco.xylophone", "params": []})
        third_key = next(iter(client._pending_programs))
        sender = SimpleUDPClient("127.0.0.1", client.reply_port)
        try:
            sender.send_message(
                "/omni/v1/program/status",
                [client.session, third_key[0], third_key[1], "ready", "ready"],
            )
        finally:
            sender._sock.close()
        deadline = time.monotonic() + 1.0
        while client._selected_program["strum"] != third_key[0] and time.monotonic() < deadline:
            time.sleep(0.01)
        self.close_client(client)

        releases = [
            arguments
            for address, arguments in self.fake.messages
            if address == "/omni/v1/program/release"
        ]
        released_keys = {(str(item[2]), int(item[3])) for item in releases}
        self.assertIn(first_key, released_keys)
        self.assertIn(second_key, released_keys)


if __name__ == "__main__":
    unittest.main()
