from __future__ import annotations

import json
import os
import pty
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "code" / "main.py"
PORT = 18765


def request_json(method: str, path: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(
        f"http://127.0.0.1:{PORT}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_health(process: subprocess.Popen[str], timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate(timeout=1)
            raise AssertionError(
                f"Qt application exited early with {process.returncode}\n"
                f"stdout:\n{stdout}\nstderr:\n{stderr}"
            )
        try:
            result = request_json("GET", "/health")
            if result.get("ok"):
                return
        except (URLError, TimeoutError, ConnectionError) as exc:
            last_error = exc
        time.sleep(0.1)
    raise AssertionError(f"test API did not become ready: {last_error}")


def tx_commands(log_path: Path) -> list[str]:
    lines = log_path.read_text(encoding="utf-8").splitlines()
    commands: list[str] = []
    for line in lines:
        if " TX-HIGH " in line or " TX-LOW " in line:
            commands.append(line.rsplit(None, 1)[-1])
    return commands


def wait_for_commands(log_path: Path, expected: list[str], start: int, timeout: float = 5.0) -> list[str]:
    deadline = time.monotonic() + timeout
    latest: list[str] = []
    while time.monotonic() < deadline:
        if log_path.exists():
            latest = tx_commands(log_path)[start:]
            if all(command in latest for command in expected):
                return latest
        time.sleep(0.05)
    raise AssertionError(
        f"missing AMY commands {expected}; commands after action were:\n"
        + "\n".join(latest)
    )


def action(name: str, *args: object) -> dict:
    result = request_json("POST", "/action", {"action": name, "args": list(args)})
    if not result.get("ok"):
        raise AssertionError(f"action {name} failed: {result}")
    return result


def main() -> int:
    master_fd, slave_fd = pty.openpty()
    serial_port = os.ttyname(slave_fd)

    with tempfile.TemporaryDirectory(prefix="omnichord-ci-") as temp_home:
        home = Path(temp_home)
        log_path = home / ".omnichord" / "amy_debug.log"
        env = os.environ.copy()
        env["HOME"] = str(home)
        env["PYTHONUNBUFFERED"] = "1"

        process = subprocess.Popen(
            [
                "xvfb-run",
                "-a",
                sys.executable,
                str(MAIN),
                "--windowed",
                "--serial-port",
                serial_port,
                "--serial-baud",
                "1000000",
                "--test-api-port",
                str(PORT),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            wait_for_health(process)
            startup = wait_for_commands(
                log_path,
                [
                    "zY0Z",
                    "S12288Z",
                    "i0iv4in1Z",
                    "K143i1iv1Z",
                    "K28i2iv2Z",
                    "K4i3iv7Z",
                    "K4i4iv4Z",
                ],
                0,
                timeout=8.0,
            )
            print(f"startup AMY commands: {len(startup)}")

            start = len(tx_commands(log_path))
            action("pressChord", 0, 0)
            wait_for_commands(
                log_path,
                ["l0i3Z", "n48l1i3Z", "n52l1i3Z", "n55l1i3Z"],
                start,
            )
            action("releaseChord", 0, 0)
            time.sleep(1.6)

            start = len(tx_commands(log_path))
            action("pressChord", 1, 9)
            wait_for_commands(
                log_path,
                ["l0i3Z", "n57l1i3Z", "n60l1i3Z", "n64l1i3Z"],
                start,
            )
            action("releaseChord", 1, 9)
            time.sleep(1.6)

            print("Qt/AMY integration test passed")
            return 0
        finally:
            process.terminate()
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate(timeout=5)
            if stdout:
                print(stdout)
            if stderr:
                print(stderr, file=sys.stderr)
            os.close(master_fd)
            os.close(slave_fd)


if __name__ == "__main__":
    raise SystemExit(main())
