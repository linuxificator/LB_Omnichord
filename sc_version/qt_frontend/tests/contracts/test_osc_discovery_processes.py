from __future__ import annotations

import json
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[2]
PEER = FRONTEND / "tests" / "support" / "osc_discovery_peer.py"


def _unused_udp_port() -> int:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.bind(("0.0.0.0", 0))
        return int(probe.getsockname()[1])
    finally:
        probe.close()


class OscDiscoveryProcessContracts(unittest.TestCase):
    def test_external_browser_finds_running_osc_input_by_name(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lb-osc-discovery-") as raw:
            root = Path(raw)
            ready = root / "ready"
            stop = root / "stop"
            port = _unused_udp_port()
            name = f"LB Omnichord test {port}"
            publisher = subprocess.Popen(
                [
                    sys.executable,
                    str(PEER),
                    "advertise",
                    "--name",
                    name,
                    "--port",
                    str(port),
                    "--ready",
                    str(ready),
                    "--stop",
                    str(stop),
                ],
                cwd=FRONTEND,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                deadline = time.monotonic() + 5.0
                while not ready.exists() and time.monotonic() < deadline:
                    if publisher.poll() is not None:
                        break
                    time.sleep(0.02)
                if not ready.exists():
                    stdout, stderr = publisher.communicate(timeout=2)
                    self.fail(f"OSC publisher did not start: stdout={stdout!r} stderr={stderr!r}")
                publisher_pid = int(ready.read_text(encoding="utf-8"))

                browser = subprocess.run(
                    [
                        sys.executable,
                        str(PEER),
                        "browse",
                        "--name",
                        name,
                    ],
                    cwd=FRONTEND,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=12,
                    check=False,
                )
            finally:
                stop.touch()
                publisher_stdout, publisher_stderr = publisher.communicate(timeout=5)

        self.assertEqual(
            browser.returncode,
            0,
            f"stdout={browser.stdout!r} stderr={browser.stderr!r} "
            f"publisher_stdout={publisher_stdout!r} "
            f"publisher_stderr={publisher_stderr!r}",
        )
        result = json.loads(browser.stdout)
        self.assertEqual(result["name"], f"{name}._osc._udp.local.")
        self.assertEqual(result["port"], port)
        self.assertTrue(result["addresses"])
        self.assertNotEqual(publisher_pid, result["pid"])


if __name__ == "__main__":
    unittest.main()
