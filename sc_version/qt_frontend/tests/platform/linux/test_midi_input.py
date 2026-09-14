from __future__ import annotations

import json
import os
import pty
import socket
import subprocess
import sys
import tempfile
import time
import tty
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FAKE_SC = ROOT / "tests" / "support" / "fake_supercollider_service.py"


def free_udp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def read_messages(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line]


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
            sc_port = free_udp_port()
            sc_log = temp / "supercollider-osc.jsonl"
            sc_config = json.loads(
                (ROOT / "config" / "supercollider.json").read_text(
                    encoding="utf-8"
                )
            )
            sc_config["language"]["port"] = sc_port
            sc_config_path = temp / "supercollider.json"
            sc_config_path.write_text(json.dumps(sc_config), encoding="utf-8")
            fake_sc = subprocess.Popen(
                [
                    sys.executable,
                    str(FAKE_SC),
                    "--port",
                    str(sc_port),
                    "--log",
                    str(sc_log),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            env = dict(
                os.environ,
                HOME=str(temp),
                QT_QPA_PLATFORM="offscreen",
                QT_QUICK_BACKEND="software",
                OMNICHORD_SC_CONFIG=str(sc_config_path),
            )
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(ROOT / "code" / "main.py"),
                    "--windowed",
                    "--software-renderer",
                ],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            try:
                deadline = time.monotonic() + 10.0
                while time.monotonic() < deadline:
                    if any(
                        item["address"] == "/omni/v1/hello"
                        for item in read_messages(sc_log)
                    ):
                        break
                    if process.poll() is not None or fake_sc.poll() is not None:
                        break
                    time.sleep(0.05)
                else:
                    self.fail("application did not connect to the SC test service")
                time.sleep(0.5)
                checkpoint = len(read_messages(sc_log))
                os.write(midi_master, bytes((0xB0, 74, 0, 0xB0, 74, 1)))
                deadline = time.monotonic() + 5.0
                while time.monotonic() < deadline:
                    if any(
                        item["address"] == "/omni/v1/mixer/room"
                        for item in read_messages(sc_log)[checkpoint:]
                    ):
                        break
                    if process.poll() is not None:
                        break
                    time.sleep(0.05)
            finally:
                if process.poll() is None:
                    process.terminate()
                output, _ = process.communicate(timeout=3)
                if fake_sc.poll() is None:
                    fake_sc.terminate()
                fake_output, _ = fake_sc.communicate(timeout=3)
                os.close(midi_master)
                os.close(midi_slave)

            self.assertNotIn("TypeError", output)
            self.assertNotIn("QQmlApplicationEngine failed", output)
            self.assertNotIn("Cannot assign to non-existent property", output)
            self.assertNotIn("Required property", output)
            self.assertEqual(fake_sc.returncode, 0, fake_output)
            self.assertTrue(
                any(
                    item["address"] == "/omni/v1/mixer/room"
                    for item in read_messages(sc_log)[checkpoint:]
                ),
                "bound CC did not change SuperCollider room level: "
                f"returncode={process.returncode!r}, "
                f"messages={read_messages(sc_log)[checkpoint:]!r}, "
                f"output={output!r}",
            )


if __name__ == "__main__":
    unittest.main()
