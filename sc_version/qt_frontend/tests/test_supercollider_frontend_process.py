from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.error import URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
HEADLESS_APP = ROOT / "tests" / "integration" / "headless_app.py"
FAKE_SC = ROOT / "tests" / "support" / "fake_supercollider_service.py"


def free_port(socket_type: int) -> int:
    with socket.socket(socket.AF_INET, socket_type) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def messages(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def request_json(
    port: int,
    method: str,
    path: str,
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    body = None if payload is None else json.dumps(payload).encode()
    request = Request(
        f"http://127.0.0.1:{port}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=2) as response:
        return json.loads(response.read())


def stop_process(process: subprocess.Popen[str]) -> tuple[str, str]:
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
    try:
        return process.communicate(timeout=4)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        return process.communicate(timeout=2)


class SuperColliderFrontendProcessTests(unittest.TestCase):
    def test_manual_chord_crosses_real_frontend_and_separate_engine_processes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            sc_port = free_port(socket.SOCK_DGRAM)
            api_port = free_port(socket.SOCK_STREAM)
            engine_log = temp / "engine.jsonl"
            engine_ready = temp / "engine.ready"
            runtime = json.loads(
                (ROOT / "config" / "supercollider.json").read_text()
            )
            runtime["language"]["port"] = sc_port
            runtime_path = temp / "supercollider.json"
            runtime_path.write_text(json.dumps(runtime))

            engine = subprocess.Popen(
                [
                    sys.executable,
                    str(FAKE_SC),
                    "--port",
                    str(sc_port),
                    "--log",
                    str(engine_log),
                    "--ready-file",
                    str(engine_ready),
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            engine_deadline = time.monotonic() + 3
            while not engine_ready.exists() and time.monotonic() < engine_deadline:
                if engine.poll() is not None:
                    break
                time.sleep(0.01)
            if not engine_ready.exists():
                engine_stdout, engine_stderr = stop_process(engine)
                self.fail(
                    "fake SC service did not bind before frontend startup:\n"
                    + engine_stdout
                    + engine_stderr
                )
            env = dict(
                os.environ,
                HOME=str(temp),
                OMNICHORD_SC_CONFIG=str(runtime_path),
                OMNICHORD_TEST_API_PORT=str(api_port),
                PYTHONUNBUFFERED="1",
            )
            application = subprocess.Popen(
                [sys.executable, str(HEADLESS_APP)],
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            try:
                healthy = False
                deadline = time.monotonic() + 12
                while time.monotonic() < deadline:
                    try:
                        if request_json(api_port, "GET", "/health").get("ok"):
                            healthy = True
                            break
                    except (URLError, TimeoutError, ConnectionError):
                        pass
                    if application.poll() is not None or engine.poll() is not None:
                        break
                    time.sleep(0.05)
                if not healthy:
                    app_stdout, app_stderr = stop_process(application)
                    engine_stdout, engine_stderr = stop_process(engine)
                    self.fail(
                        "SC frontend did not become healthy:\n"
                        + app_stdout
                        + app_stderr
                        + engine_stdout
                        + engine_stderr
                    )

                checkpoint = len(messages(engine_log))
                pressed = request_json(
                    api_port,
                    "POST",
                    "/action",
                    {"action": "pressChord", "args": [0, 0]},
                )
                self.assertTrue(pressed.get("ok"), pressed)
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    delta = messages(engine_log)[checkpoint:]
                    if sum(
                        item["address"] == "/omni/v1/note/on" for item in delta
                    ) >= 3:
                        break
                    time.sleep(0.02)
                else:
                    self.fail("manual chord note-ons did not reach SC")

                released = request_json(
                    api_port,
                    "POST",
                    "/action",
                    {"action": "releaseChord", "args": [0, 0]},
                )
                self.assertTrue(released.get("ok"), released)
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    delta = messages(engine_log)[checkpoint:]
                    if sum(
                        item["address"] == "/omni/v1/note/off" for item in delta
                    ) >= 3:
                        break
                    time.sleep(0.02)
                else:
                    self.fail("manual chord note-offs did not reach SC")
            finally:
                app_stdout, app_stderr = stop_process(application)
                engine_stdout, engine_stderr = stop_process(engine)

            self.assertEqual(application.returncode, 0, app_stdout + app_stderr)
            self.assertEqual(engine.returncode, 0, engine_stdout + engine_stderr)


if __name__ == "__main__":
    unittest.main()
