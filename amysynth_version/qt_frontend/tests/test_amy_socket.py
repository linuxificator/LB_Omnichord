from __future__ import annotations

import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from PySide6.QtCore import QCoreApplication


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from amy_transport import _QtLocalSocketWriter, _UnixSocketWriter  # noqa: E402
from unix_wire_socket import listen_unix_wire_socket  # noqa: E402


class AmySocketWriterTests(unittest.TestCase):
    def test_service_listener_and_client_negotiate_the_same_mode(self) -> None:
        with tempfile.TemporaryDirectory(prefix="amy-listener-test-") as tmp:
            path = Path(tmp) / "amy.sock"
            server, server_stream = listen_unix_wire_socket(path)
            server.settimeout(2.0)
            writer = _UnixSocketWriter(str(path))
            try:
                client, _ = server.accept()
                with client:
                    writer.high("K215i5Z")
                    expected = b"K215i5Z\n" if server_stream else b"K215i5Z"
                    self.assertEqual(client.recv(1024), expected)
            finally:
                writer.close()
                server.close()

    def test_each_wire_request_is_one_seqpacket(self) -> None:
        with tempfile.TemporaryDirectory(prefix="amy-socket-test-") as tmp:
            path = Path(tmp) / "amy.sock"
            server = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
            server.bind(str(path))
            server.listen(1)
            packets: list[bytes] = []
            received = threading.Event()

            def receive() -> None:
                client, _ = server.accept()
                with client:
                    packets.append(client.recv(1024))
                    packets.append(client.recv(1024))
                    received.set()

            thread = threading.Thread(target=receive, daemon=True)
            thread.start()
            writer = _UnixSocketWriter(str(path))
            try:
                writer.high("K215i5Z")
                writer.high("n60l1i5Z")
                self.assertTrue(received.wait(2.0))
            finally:
                writer.close()
                thread.join(timeout=1.0)
                server.close()

            self.assertEqual(packets, [b"K215i5Z", b"n60l1i5Z"])

    def test_stream_endpoint_frames_each_wire_request(self) -> None:
        with tempfile.TemporaryDirectory(prefix="amy-stream-test-") as tmp:
            path = Path(tmp) / "amy.sock"
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(str(path))
            server.listen(1)
            received = bytearray()
            complete = threading.Event()

            def receive() -> None:
                client, _ = server.accept()
                with client:
                    while received.count(b"\n") < 2:
                        received.extend(client.recv(1024))
                    complete.set()

            thread = threading.Thread(target=receive, daemon=True)
            thread.start()
            writer = _UnixSocketWriter(str(path))
            try:
                writer.high("K215i5Z")
                writer.high("n60l1i5Z")
                self.assertTrue(complete.wait(2.0))
            finally:
                writer.close()
                thread.join(timeout=1.0)
                server.close()

            self.assertEqual(bytes(received), b"K215i5Z\nn60l1i5Z\n")

    def test_qt_local_transport_frames_each_wire_request(self) -> None:
        app = QCoreApplication.instance() or QCoreApplication([])
        self.assertIsNotNone(app)
        with tempfile.TemporaryDirectory(prefix="amy-qt-local-test-") as tmp:
            path = Path(tmp) / "amy.sock"
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(str(path))
            server.listen(1)
            received = bytearray()
            complete = threading.Event()

            def receive() -> None:
                client, _ = server.accept()
                with client:
                    while received.count(b"\n") < 2:
                        received.extend(client.recv(1024))
                    complete.set()

            thread = threading.Thread(target=receive, daemon=True)
            thread.start()
            writer = _QtLocalSocketWriter(str(path))
            try:
                writer.high("K215i5Z")
                writer.high("n60l1i5Z")
                self.assertTrue(complete.wait(2.0))
            finally:
                writer.close()
                thread.join(timeout=1.0)
                server.close()

            self.assertEqual(bytes(received), b"K215i5Z\nn60l1i5Z\n")


if __name__ == "__main__":
    unittest.main()
