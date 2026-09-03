from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[1]
MAIN = FRONTEND / "code" / "main.py"


class PackageChordInputTests(unittest.TestCase):
    def test_package_smoke_drives_qml_tap_hold_and_active_border(self) -> None:
        with tempfile.TemporaryDirectory(prefix="omnichord-qml-smoke-") as raw:
            root = Path(raw)
            socket_path = root / "amy.sock"
            status_path = root / "smoke.status"
            packets: list[str] = []
            server_error: list[BaseException] = []

            listener = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
            self.addCleanup(listener.close)
            listener.settimeout(20.0)
            listener.bind(str(socket_path))
            listener.listen(1)

            def receive_packets() -> None:
                try:
                    connection, _ = listener.accept()
                    with connection:
                        while True:
                            packet = connection.recv(65536)
                            if not packet:
                                break
                            packets.append(packet.decode("ascii"))
                except BaseException as exc:
                    server_error.append(exc)

            receiver = threading.Thread(
                target=receive_packets,
                name="package-smoke-socket",
                daemon=True,
            )
            receiver.start()

            environment = os.environ.copy()
            environment.update(
                {
                    "HOME": str(root / "home"),
                    "QT_QPA_PLATFORM": "offscreen",
                    "QT_QUICK_BACKEND": "software",
                    "OMNICHORD_PACKAGE_SMOKE_STATUS": str(status_path),
                }
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(MAIN),
                    "--amy-socket",
                    str(socket_path),
                    "--windowed",
                    "--package-smoke-test",
                ],
                cwd=FRONTEND,
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=25,
                check=False,
            )
            listener.close()
            receiver.join(timeout=3.0)

            self.assertEqual(
                completed.returncode,
                0,
                "package input smoke failed\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}",
            )
            self.assertEqual(server_error, [])
            self.assertFalse(receiver.is_alive())

            status = status_path.read_text(encoding="utf-8")
            for checkpoint in (
                "qml-root-ready",
                "midi-input-profile-verified",
                "midi-control-simulation-observed",
                "midi-button-simulation-observed",
                "osc-udp-rotary-observed",
                "osc-udp-button-observed",
                "osc-tech-activity-observed",
                "smoke-audio-levels-full",
                "qml-chord-press-observed",
                "active-chord-visible",
                "qml-chord-tap-released",
                "qml-chord-hold-promoted",
                "qml-chord-hold-released",
                "qml-slider-drag-visible",
                "qml-slider-release-visible",
                "event-loop-exited",
            ):
                self.assertIn(checkpoint, status)

            note_on = re.compile(
                r"^n[-+0-9.]+l(?!0(?:Z|[A-Za-z]))[-+0-9.]+i3Z$"
            )
            self.assertGreaterEqual(
                sum(bool(note_on.match(packet)) for packet in packets),
                6,
                packets,
            )
            self.assertIn("i3iV1Z", packets)
            self.assertIn("i4iV1Z", packets)
            self.assertGreaterEqual(packets.count("l0i3Z"), 2, packets)


if __name__ == "__main__":
    unittest.main()
