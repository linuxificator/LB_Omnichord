from __future__ import annotations

import json
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any


FRONTEND = Path(__file__).resolve().parents[2]
SUPPORT = FRONTEND / "tests" / "support"
PEER = SUPPORT / "external_input_peer.py"
PROBE = SUPPORT / "external_input_probe.py"


def _unused_udp_port() -> int:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])
    finally:
        probe.close()


class ExternalInputProcessContracts(unittest.TestCase):
    def test_midi_sender_and_parser_are_distinct_processes(self) -> None:
        sender = subprocess.Popen(
            [sys.executable, str(PEER), "midi", "--output", "-"],
            cwd=FRONTEND,
            stdout=subprocess.PIPE,
        )
        assert sender.stdout is not None
        receiver = subprocess.run(
            [sys.executable, str(PROBE), "midi"],
            cwd=FRONTEND,
            stdin=sender.stdout,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
        sender.stdout.close()
        sender_status = sender.wait(timeout=3)

        self.assertEqual(sender_status, 0)
        self.assertEqual(receiver.returncode, 0, receiver.stderr)
        result: dict[str, Any] = json.loads(receiver.stdout)
        self.assertNotEqual(sender.pid, int(result["pid"]))
        events = result["events"]
        self.assertEqual(
            [
                (
                    event["kind"],
                    event["channel"],
                    event["data"],
                    event["value"],
                    event["is_on"],
                )
                for event in events
            ],
            [
                ("control", 1, 119, 24, False),
                ("control", 1, 119, 96, False),
                ("note", 1, 118, 127, True),
                ("note", 1, 118, 0, False),
                ("control", 1, 128, 8192, False),
            ],
        )

    def test_osc_sender_and_receiver_are_distinct_processes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lb-external-osc-") as raw:
            root = Path(raw)
            port = _unused_udp_port()
            ready = root / "ready"
            config = root / "amy_config.json"
            config.write_text(
                json.dumps(
                    {
                        "osc_input": {
                            "enabled": True,
                            "listen_address": "127.0.0.1",
                            "listen_port": port,
                        }
                    }
                ),
                encoding="utf-8",
            )
            receiver = subprocess.Popen(
                [
                    sys.executable,
                    str(PROBE),
                    "osc",
                    "--port",
                    str(port),
                    "--ready",
                    str(ready),
                ],
                cwd=FRONTEND,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            deadline = time.monotonic() + 5.0
            while not ready.is_file() and time.monotonic() < deadline:
                if receiver.poll() is not None:
                    break
                time.sleep(0.01)
            if not ready.is_file():
                receiver_stdout, receiver_stderr = receiver.communicate(timeout=1)
                self.fail(
                    "OSC receiver did not become ready: "
                    f"stdout={receiver_stdout!r} stderr={receiver_stderr!r}"
                )

            sender = subprocess.run(
                [
                    sys.executable,
                    str(PEER),
                    "osc",
                    "--config",
                    str(config),
                    "--duration",
                    "0.2",
                    "--interval",
                    "0.01",
                ],
                cwd=FRONTEND,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
                check=False,
            )
            receiver_stdout, receiver_stderr = receiver.communicate(timeout=5)

        self.assertEqual(sender.returncode, 0, sender.stderr)
        self.assertEqual(
            receiver.returncode,
            0,
            f"sender={sender.stdout}\nstdout={receiver_stdout}\n"
            f"stderr={receiver_stderr}",
        )
        sender_started = json.loads(sender.stdout.splitlines()[0])
        result: dict[str, Any] = json.loads(receiver_stdout)
        self.assertNotEqual(int(sender_started["pid"]), int(result["pid"]))
        self.assertTrue(result["complete"])
        identities = {
            (event["address"], event["value_type"])
            for event in result["events"]
        }
        self.assertIn(("/package-smoke/rotary", "continuous"), identities)
        self.assertIn(("/package-smoke/button", "button"), identities)


if __name__ == "__main__":
    unittest.main()
