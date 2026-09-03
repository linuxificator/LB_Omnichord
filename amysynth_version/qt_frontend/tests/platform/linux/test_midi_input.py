from __future__ import annotations

import json
import os
import pty
import socket
import subprocess
import sys
import tempfile
import threading
import time
import tty
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


class LinuxMidiInputIntegrationTests(unittest.TestCase):
    def test_real_midi_bytes_reach_a_bound_application_control(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            config_dir = temp / ".omnichord" / "config"
            config_dir.mkdir(parents=True)
            config = json.loads(
                (ROOT / "config" / "amy_config.json").read_text(encoding="utf-8")
            )
            midi_master, midi_slave = pty.openpty()
            tty.setraw(midi_slave)
            config["midi_input"]["device_glob"] = os.ttyname(midi_slave)
            config_dir.joinpath("amy_config.json").write_text(
                json.dumps(config), encoding="utf-8"
            )
            preset_dir = temp / ".omnichord" / "omni_presets"
            preset_dir.mkdir(parents=True)
            preset = json.loads(
                (
                    ROOT
                    / "instruments"
                    / "default_presets"
                    / "p1.json"
                ).read_text(encoding="utf-8")
            )
            preset["midi_control_bindings"] = [
                {
                    "channel": 1,
                    "controller": 74,
                    "target": {
                        "screen": "omni",
                        "kind": "reverb_level",
                    },
                }
            ]
            preset_dir.joinpath("p1.json").write_text(
                json.dumps(preset), encoding="utf-8"
            )
            inactive_preset = json.loads(
                (
                    ROOT
                    / "instruments"
                    / "default_presets"
                    / "p2.json"
                ).read_text(encoding="utf-8")
            )
            inactive_preset["midi_control_bindings"] = [
                {
                    "channel": 1,
                    "controller": 75,
                    "target": {
                        "screen": "omni",
                        "kind": "reverb_liveness",
                    },
                }
            ]
            preset_dir.joinpath("p2.json").write_text(
                json.dumps(inactive_preset), encoding="utf-8"
            )
            socket_path = temp / "amy.sock"
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
            listener.settimeout(15.0)
            listener.bind(str(socket_path))
            listener.listen(1)
            socket_error: list[BaseException] = []
            wire_packets: list[str] = []
            application_connected = threading.Event()

            def drain_amy_commands() -> None:
                try:
                    connection, _ = listener.accept()
                    application_connected.set()
                    with connection:
                        while packet := connection.recv(65536):
                            wire_packets.append(packet.decode("ascii"))
                except OSError:
                    # The test closes the listener during teardown.
                    pass
                except BaseException as exc:
                    socket_error.append(exc)

            receiver = threading.Thread(
                target=drain_amy_commands,
                name="midi-cc-test-amy-socket",
                daemon=True,
            )
            receiver.start()
            env = dict(
                os.environ,
                HOME=str(temp),
                QT_QPA_PLATFORM="offscreen",
                QT_QUICK_BACKEND="software",
            )
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(ROOT / "code" / "main.py"),
                    "--amy-socket",
                    str(socket_path),
                    "--windowed",
                    "--software-renderer",
                ],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            try:
                self.assertTrue(application_connected.wait(timeout=10.0))
                time.sleep(0.5)
                wire_packets.clear()
                os.write(midi_master, bytes((0xB0, 74, 0, 0xB0, 74, 1)))
                deadline = time.monotonic() + 5.0
                while time.monotonic() < deadline:
                    if any("h0.02" in packet for packet in wire_packets):
                        break
                    if process.poll() is not None:
                        break
                    time.sleep(0.05)
            finally:
                if process.poll() is None:
                    process.terminate()
                output, _ = process.communicate(timeout=3)
                os.close(midi_master)
                os.close(midi_slave)
                listener.close()
                receiver.join(timeout=3.0)

            self.assertEqual(socket_error, [])
            self.assertFalse(receiver.is_alive())
            self.assertNotIn("TypeError", output)
            self.assertNotIn("QQmlApplicationEngine failed", output)
            self.assertNotIn("Cannot assign to non-existent property", output)
            self.assertNotIn("Required property", output)
            self.assertTrue(
                any("h0.02" in packet for packet in wire_packets),
                f"bound CC did not change AMY reverb: {wire_packets!r}",
            )


if __name__ == "__main__":
    unittest.main()
