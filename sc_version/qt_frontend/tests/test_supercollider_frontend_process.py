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
from urllib.request import ProxyHandler, Request, build_opener


ROOT = Path(__file__).resolve().parents[1]
HEADLESS_APP = ROOT / "tests" / "integration" / "headless_app.py"
FAKE_SC = ROOT / "tests" / "support" / "fake_supercollider_service.py"
SCREENSHOT_HELPER = ROOT / "capture_screenshots.py"


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
    # The control process is an explicit loopback boundary. CI host proxy
    # variables must never route this request outside the machine.
    with build_opener(ProxyHandler({})).open(request, timeout=2) as response:
        return json.loads(response.read())


def stop_process(process: subprocess.Popen[str]) -> tuple[str, str]:
    if process.poll() is None:
        if hasattr(os, "killpg"):
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.send_signal(signal.CTRL_BREAK_EVENT)
    try:
        return process.communicate(timeout=4)
    except subprocess.TimeoutExpired:
        if hasattr(os, "killpg"):
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        return process.communicate(timeout=2)


def wait_for_graceful_exit(
    process: subprocess.Popen[str],
    *,
    timeout: float = 2.0,
) -> tuple[str, str]:
    """Let an owned peer consume its shutdown packet before signalling it."""

    try:
        return process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        return stop_process(process)


class SuperColliderFrontendProcessTests(unittest.TestCase):
    def test_public_screenshot_helper_uses_the_sc_process_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(SCREENSHOT_HELPER), "--output", directory],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for name in ("omni.png", "midi.png"):
                frame = Path(directory) / name
                self.assertTrue(frame.is_file(), result.stdout + result.stderr)
                self.assertGreater(frame.stat().st_size, 100_000)
                self.assertTrue(frame.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))

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
                start_new_session=os.name != "nt",
                creationflags=(
                    subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
                ),
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
                OMNICHORD_TEST_LOAD_QML="1",
                QT_QPA_PLATFORM="offscreen",
                QT_QUICK_BACKEND="software",
                QSG_INFO="0",
                PYTHONUNBUFFERED="1",
            )
            application = subprocess.Popen(
                [sys.executable, str(HEADLESS_APP)],
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=os.name != "nt",
                creationflags=(
                    subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
                ),
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

                frame = temp / "frontend.png"
                captured = request_json(
                    api_port,
                    "POST",
                    "/action",
                    {"action": "captureGui", "args": [str(frame)]},
                )
                self.assertTrue(captured.get("ok"), captured)
                result = captured.get("result")
                self.assertIsInstance(result, dict)
                assert isinstance(result, dict)
                self.assertGreaterEqual(int(result["width"]), 640)
                self.assertGreaterEqual(int(result["height"]), 360)
                self.assertGreaterEqual(int(result["sampled_colours"]), 8)
                self.assertTrue(frame.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))

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

                # Exercise the production MIDI Tumbler while QML is loaded.
                # Browser changes used to recreate the Python list model from
                # a broad stateVersion binding.  Rapid changes then made the
                # Tumbler and its currentIndex binding feed back into one
                # another, producing a QML binding loop.
                for index in range(24):
                    changed = request_json(
                        api_port,
                        "POST",
                        "/action",
                        {
                            "action": "setMidiSynthIndex",
                            "args": [index % 5, index],
                        },
                    )
                    self.assertTrue(changed.get("ok"), changed)
            finally:
                app_stdout, app_stderr = stop_process(application)
                # Closing the frontend sends the engine a typed shutdown UDP
                # packet. Let the separate process consume it before falling
                # back to signal-based cleanup; otherwise fast macOS runners
                # can race a valid shutdown and report SIGTERM as a failure.
                engine_stdout, engine_stderr = wait_for_graceful_exit(engine)

            self.assertEqual(application.returncode, 0, app_stdout + app_stderr)
            self.assertEqual(engine.returncode, 0, engine_stdout + engine_stderr)
            self.assertIn("TEST_QML_READY=1", app_stdout + app_stderr)
            self.assertNotIn("Binding loop detected", app_stdout + app_stderr)


if __name__ == "__main__":
    unittest.main()
