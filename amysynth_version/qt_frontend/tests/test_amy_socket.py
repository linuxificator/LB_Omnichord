from __future__ import annotations

import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from amy_transport import _QtLocalSocketWriter, _UnixSocketWriter  # noqa: E402


class AmySocketWriterTests(unittest.TestCase):
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

    def test_stream_platforms_frame_each_wire_request(self) -> None:
        self._assert_stream_framing("darwin")

    def _assert_stream_framing(self, platform: str) -> None:
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
            with patch("amy_transport.sys.platform", platform):
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
