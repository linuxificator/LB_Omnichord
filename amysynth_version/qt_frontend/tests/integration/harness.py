from __future__ import annotations

import json
import os
import pty
import re
import select
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable
from urllib.error import URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
TEST_APP = Path(__file__).with_name("headless_app.py")


def free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def request_json(
    port: int,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _terminate_process_group(
    process: subprocess.Popen[str],
) -> tuple[str, str]:
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        return process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        return process.communicate(timeout=5)


class SerialAmyBridge:
    """Receive the application's real serial output through a Linux PTY.

    With ``native_amy=True`` every complete LF-delimited serial line is also
    fed into the installed CPython AMY extension.  AMY is rendered at roughly
    real-time block cadence so reset/sequencer behavior is exercised rather
    than merely parsed.  The bridge can then read back actual synth state with
    ``amy.get_synth_commands`` / ``amy.dump_state``.
    """

    def __init__(self, artifact_dir: Path, *, native_amy: bool) -> None:
        self.artifact_dir = artifact_dir
        self.native_amy = bool(native_amy)
        self.master_fd, self.slave_fd = pty.openpty()
        self.serial_port = os.ttyname(self.slave_fd)
        os.set_blocking(self.master_fd, False)

        self.lines: list[str] = []
        self.raw_chunks: list[bytes] = []
        self._buffer = bytearray()
        self._line_condition = threading.Condition()
        self._last_rx = time.monotonic()
        self._closed = False
        self._thread: threading.Thread | None = None
        self._amy_lock = threading.Lock()
        self._native_peak = 0
        self._native_log_path = artifact_dir / "native_amy_state.log"
        self._serial_log_path = artifact_dir / "serial_rx.log"

        self.amy = None
        self.c_amy = None
        self._block_seconds = 0.003
        if self.native_amy:
            try:
                import amy  # type: ignore
                import c_amy  # type: ignore
            except ImportError as exc:
                raise RuntimeError(
                    "native AMY suite requires the pinned LB Omnichord AMY "
                    "release installed"
                ) from exc
            self.amy = amy
            self.c_amy = c_amy
            try:
                c_amy.live(
                    audio=False,
                    default_synths=0,
                    max_buses=11,
                    max_oscs=336,
                    max_sequencer_tags=1280,
                    max_sequence_events=64,
                    max_sequence_executions=40,
                )
            except (AttributeError, TypeError) as exc:
                raise RuntimeError(
                    "installed AMY lacks the pinned reusable-sequence and "
                    "offline-render API"
                ) from exc
            self._block_seconds = float(amy.AMY_BLOCK_SIZE) / float(
                amy.AMY_SAMPLE_RATE
            )
            self._write_native_log(
                "START",
                {
                    "block_size": int(amy.AMY_BLOCK_SIZE),
                    "sample_rate": int(amy.AMY_SAMPLE_RATE),
                    "max_buses": 11,
                    "max_oscs": 336,
                    "max_sequencer_tags": 1280,
                    "max_sequence_events": 64,
                    "max_sequence_executions": 40,
                },
            )

        self._thread = threading.Thread(
            target=self._run,
            name="omnichord-serial-native-bridge",
            daemon=True,
        )
        self._thread.start()

    def _write_native_log(self, kind: str, value: Any) -> None:
        self._native_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._native_log_path.open("a", encoding="utf-8") as handle:
            handle.write(
                f"{time.monotonic():.6f} {kind} "
                f"{json.dumps(value, ensure_ascii=False, default=str)}\n"
            )

    def _record_lines(self, lines: list[str]) -> None:
        accepted = [line.strip("\r") for line in lines if line.strip("\r")]
        if not accepted:
            return

        for line in accepted:
            if self.native_amy:
                assert self.amy is not None
                with self._amy_lock:
                    self.amy.send_wire(line)
                    reset_match = re.fullmatch(r"S(\d+)Z", line)
                    if reset_match:
                        reset_flags = int(reset_match.group(1))
                        if reset_flags & int(self.amy.RESET_SEQUENCER):
                            # The real audio callback keeps running independently
                            # while the application's serial writer observes its
                            # post-reset barrier.  This test bridge receives and
                            # renders on one thread, so an unlucky busy read loop
                            # can otherwise ingest the later pattern triggers
                            # before it renders the queued reset.  Process the
                            # reset delta here; a timebase reset needs one further
                            # block because AMY deliberately applies that part at
                            # the following block boundary.
                            self._render_native_block_locked()
                            if reset_flags & int(self.amy.RESET_TIMEBASE):
                                self._render_native_block_locked()
                self._write_native_log("WIRE", line)

        # In native mode lines become observable only after AMY has ingested
        # the complete batch.  Otherwise wait_for_lines(zY1) could wake the
        # test before the bridge called amy.send_wire(zY1), letting a fast test
        # render ahead of the transport-start event it was waiting for.
        with self._line_condition:
            self.lines.extend(accepted)
            self._last_rx = time.monotonic()
            self._line_condition.notify_all()
        with self._serial_log_path.open("a", encoding="utf-8") as handle:
            handle.write("".join(f"{line}\n" for line in accepted))

    def _read_serial(self) -> None:
        lines: list[str] = []
        while True:
            try:
                chunk = os.read(self.master_fd, 65536)
            except BlockingIOError:
                break
            except OSError:
                break
            if not chunk:
                break
            self.raw_chunks.append(chunk)
            self._buffer.extend(chunk)
            while b"\n" in self._buffer:
                raw, _, remainder = self._buffer.partition(b"\n")
                self._buffer[:] = remainder
                try:
                    line = raw.decode("ascii")
                except UnicodeDecodeError:
                    line = raw.decode("ascii", errors="replace")
                lines.append(line)
        self._record_lines(lines)

    def _render_native_block_locked(self) -> None:
        assert self.c_amy is not None
        block = self.c_amy.render_to_list()
        if block:
            self._native_peak = max(
                self._native_peak,
                max(abs(int(sample)) for sample in block),
            )

    def _render_block(self) -> None:
        if not self.native_amy:
            return
        with self._amy_lock:
            self._render_native_block_locked()

    def reset_audio_peak(self) -> None:
        if not self.native_amy:
            raise RuntimeError("native AMY is not enabled")
        with self._amy_lock:
            self._native_peak = 0

    def audio_peak(self) -> int:
        if not self.native_amy:
            raise RuntimeError("native AMY is not enabled")
        with self._amy_lock:
            return int(self._native_peak)

    def render_until_audio(self, duration_seconds: float) -> bool:
        """Advance a bounded amount of AMY time independent of runner load."""
        if not self.native_amy:
            raise RuntimeError("native AMY is not enabled")
        maximum_blocks = max(
            1,
            int(max(0.0, float(duration_seconds)) / self._block_seconds) + 1,
        )
        for _ in range(maximum_blocks):
            self._render_block()
            if self.audio_peak() > 0:
                return True
        return False

    def _run(self) -> None:
        next_render = time.monotonic()
        while not self._closed:
            now = time.monotonic()
            timeout = max(0.0, min(0.02, next_render - now))
            try:
                readable, _, _ = select.select(
                    [self.master_fd], [], [], timeout
                )
            except (OSError, ValueError):
                break
            if readable:
                self._read_serial()

            if self.native_amy:
                now = time.monotonic()
                rendered = 0
                while now >= next_render and rendered < 8:
                    self._render_block()
                    next_render += self._block_seconds
                    rendered += 1
                if rendered == 8 and now >= next_render:
                    # Do not try to replay an arbitrarily large scheduling lag;
                    # resume from current real time instead.
                    next_render = now + self._block_seconds

        self._read_serial()

    def count(self) -> int:
        with self._line_condition:
            return len(self.lines)

    def lines_since(self, start: int) -> list[str]:
        with self._line_condition:
            return list(self.lines[start:])

    def wait_for_lines(
        self,
        expected: list[str],
        *,
        start: int = 0,
        timeout: float = 5.0,
    ) -> list[str]:
        deadline = time.monotonic() + timeout
        with self._line_condition:
            while True:
                latest = list(self.lines[start:])
                if all(command in latest for command in expected):
                    return latest
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AssertionError(
                        "missing serial commands "
                        f"{expected}; commands after checkpoint were:\n"
                        + "\n".join(latest)
                    )
                self._line_condition.wait(timeout=min(0.05, remaining))

    def wait_for_line_match(
        self,
        predicate: Callable[[str], bool],
        description: str,
        *,
        start: int = 0,
        timeout: float = 5.0,
    ) -> list[str]:
        deadline = time.monotonic() + timeout
        with self._line_condition:
            while True:
                latest = list(self.lines[start:])
                if any(predicate(line) for line in latest):
                    return latest
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AssertionError(
                        f"missing serial command {description}; "
                        "commands after checkpoint were:\n"
                        + "\n".join(latest)
                    )
                self._line_condition.wait(timeout=min(0.05, remaining))

    def wait_idle(self, idle_seconds: float = 0.08, timeout: float = 5.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._line_condition:
                age = time.monotonic() - self._last_rx
            if age >= idle_seconds:
                if self.native_amy:
                    # Cross a few additional render boundaries after the final
                    # host command so immediate deltas are settled.
                    for _ in range(4):
                        self._render_block()
                return
            time.sleep(min(0.02, idle_seconds / 2.0))
        raise AssertionError("serial transport did not become idle")

    def synth_commands(self, synth: int) -> list[str]:
        if not self.native_amy:
            raise RuntimeError("native AMY is not enabled")
        assert self.c_amy is not None
        with self._amy_lock:
            # The high-level amy.get_synth_commands wrapper is a replayable
            # text blob.  The C API returns the typed list of individual wire
            # commands, which is what state comparisons need.
            result = list(self.c_amy.get_synth_commands(int(synth), False))
        self._write_native_log(f"SYNTH-{synth}", result)
        return result

    def dump_state(self, checkpoint: str) -> str:
        if not self.native_amy:
            return ""
        assert self.amy is not None
        with self._amy_lock:
            value = str(self.amy.dump_state())
        self._write_native_log(f"DUMP-{checkpoint}", value)
        return value

    def checkpoint(self, name: str, synths: tuple[int, ...] = (3, 4)) -> None:
        if not self.native_amy:
            return
        payload = {
            str(synth): self.synth_commands(synth) for synth in synths
        }
        self._write_native_log(f"CHECKPOINT-{name}", payload)
        self.dump_state(name)

    @staticmethod
    def normalize_synth_commands(commands: list[str], synth: int) -> list[str]:
        # get_synth_commands() contains the instrument number in synth-layer
        # commands.  Normalize only that token so synth 3 and 4 can be compared
        # as configurations rather than as identities.
        pattern = re.compile(rf"i{int(synth)}(?=(?:i[A-Za-z]|[A-Za-z]|Z|$))")
        return [pattern.sub("i#", command) for command in commands]

    def assert_synths_equivalent(self, left: int, right: int) -> None:
        left_commands = self.synth_commands(left)
        right_commands = self.synth_commands(right)
        left_norm = self.normalize_synth_commands(left_commands, left)
        right_norm = self.normalize_synth_commands(right_commands, right)
        if left_norm != right_norm:
            raise AssertionError(
                f"native AMY synth {left} and {right} differ\n"
                f"synth {left}:\n" + "\n".join(left_commands) + "\n"
                f"synth {right}:\n" + "\n".join(right_commands)
            )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self.native_amy and self.c_amy is not None:
            with self._amy_lock:
                self.c_amy.stop()
        for fd in (self.master_fd, self.slave_fd):
            try:
                os.close(fd)
            except OSError:
                pass


class HeadlessApp:
    def __init__(self, *, native_amy: bool = False) -> None:
        self._temp = tempfile.TemporaryDirectory(prefix="omnichord-test-")
        self.home = Path(self._temp.name)
        artifact_root = Path(
            os.environ.get(
                "OMNICHORD_TEST_ARTIFACT_DIR",
                str(self.home / "artifacts"),
            )
        )
        artifact_root.mkdir(parents=True, exist_ok=True)
        self.artifact_dir = artifact_root
        self.frontend_log = self.home / ".omnichord" / "amy_debug.log"
        # Production defaults command logging to off. This integration probe
        # deliberately opts in because one test verifies scheduler ordering
        # from the independently written transport log.
        test_config = json.loads(
            (ROOT / "config" / "amy_config.json").read_text(encoding="utf-8")
        )
        test_config["debug"]["log_amy_commands"] = True
        test_config_dir = self.home / ".omnichord" / "config"
        test_config_dir.mkdir(parents=True, exist_ok=True)
        self.test_amy_config = test_config_dir / "amy_config.json"
        self.test_amy_config.write_text(
            json.dumps(test_config, indent=2) + "\n",
            encoding="utf-8",
        )
        self.api_port = free_tcp_port()
        self.bridge = SerialAmyBridge(
            self.artifact_dir,
            native_amy=native_amy,
        )

        env = os.environ.copy()
        env["HOME"] = str(self.home)
        env["PYTHONUNBUFFERED"] = "1"
        env["OMNICHORD_TEST_API_PORT"] = str(self.api_port)

        self.process = subprocess.Popen(
            [
                sys.executable,
                str(TEST_APP),
                "--amy-config",
                str(self.test_amy_config),
                "--serial-port",
                self.bridge.serial_port,
                "--serial-baud",
                "1000000",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        self._wait_for_health()

    def _wait_for_health(self, timeout: float = 20.0) -> None:
        deadline = time.monotonic() + timeout
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                stdout, stderr = self.process.communicate(timeout=1)
                raise AssertionError(
                    f"headless application exited early with "
                    f"{self.process.returncode}\nstdout:\n{stdout}\n"
                    f"stderr:\n{stderr}"
                )
            try:
                result = request_json(
                    self.api_port, "GET", "/health"
                )
                if result.get("ok"):
                    return
            except (URLError, TimeoutError, ConnectionError) as exc:
                last_error = exc
            time.sleep(0.05)
        raise AssertionError(f"test API did not become ready: {last_error}")

    def action(self, name: str, *args: object) -> Any:
        result = request_json(
            self.api_port,
            "POST",
            "/action",
            {"action": name, "args": list(args)},
        )
        if not result.get("ok"):
            raise AssertionError(f"action {name} failed: {result}")
        return result.get("result")

    def query(self, name: str) -> Any:
        result = request_json(
            self.api_port,
            "POST",
            "/query",
            {"name": name},
        )
        if not result.get("ok"):
            raise AssertionError(f"query {name} failed: {result}")
        return result.get("result")

    def wait_for_frontend_log(
        self,
        needle: str,
        *,
        timeout: float = 5.0,
    ) -> str:
        """Wait until the asynchronous transport log contains ``needle``."""

        deadline = time.monotonic() + timeout
        latest = ""
        while time.monotonic() < deadline:
            try:
                latest = self.frontend_log.read_text(encoding="utf-8")
            except FileNotFoundError:
                latest = ""
            if needle in latest:
                return latest
            time.sleep(0.01)
        raise AssertionError(
            f"frontend transport log did not contain {needle!r}; log was:\n"
            + latest
        )

    def copy_frontend_log(self) -> None:
        if self.frontend_log.exists():
            shutil.copy2(
                self.frontend_log,
                self.artifact_dir / "frontend_amy_debug.log",
            )

    def close(self) -> None:
        stdout = ""
        stderr = ""
        try:
            stdout, stderr = _terminate_process_group(self.process)
        finally:
            self.copy_frontend_log()
            (self.artifact_dir / "app_stdout.log").write_text(
                stdout or "", encoding="utf-8"
            )
            (self.artifact_dir / "app_stderr.log").write_text(
                stderr or "", encoding="utf-8"
            )
            self.bridge.close()
            self._temp.cleanup()

    def __enter__(self) -> "HeadlessApp":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.bridge.native_amy:
            try:
                self.bridge.checkpoint("final")
            except Exception as checkpoint_exc:
                with (self.artifact_dir / "checkpoint_error.log").open(
                    "a", encoding="utf-8"
                ) as handle:
                    handle.write(repr(checkpoint_exc) + "\n")
        self.close()
