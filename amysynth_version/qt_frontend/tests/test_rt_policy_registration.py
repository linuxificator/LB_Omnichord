from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
TOOL = ROOT / "tools" / "raspberry_pi" / "rt_pi_runtime.py"
sys.path.insert(0, str(CODE))

import rt_policy_registration as client  # noqa: E402
import runtime_platform_adapters as adapters  # noqa: E402


def load_runtime():
    spec = importlib.util.spec_from_file_location("rt_policy_runtime_test", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runtime = load_runtime()


CHILD = """
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from rt_policy_registration import register_policy_role
registration = register_policy_role(
    sys.argv[2], sys.argv[3], runtime_directory=Path(sys.argv[4])
)
print(json.dumps({
    "pid": os.getpid(),
    "accepted": registration.accepted,
    "applied": registration.applied,
    "issue": registration.issue,
}), flush=True)
sys.stdin.buffer.read()
registration.close()
"""


class RegistrationBoundaryTests(unittest.TestCase):
    def _child(self, role: str, endpoint: Path, directory: Path) -> subprocess.Popen[str]:
        return subprocess.Popen(
            [
                sys.executable,
                "-c",
                CHILD,
                str(CODE),
                role,
                str(endpoint),
                str(directory),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def _accept(self, watcher):
        events = watcher.selector.select(timeout=5)
        self.assertTrue(events, "registration client did not connect")
        return watcher.accept()

    @staticmethod
    def _stop_child(process: subprocess.Popen[str]) -> None:
        assert process.stdin is not None
        process.stdin.close()
        process.wait(timeout=5)
        assert process.stdout is not None and process.stderr is not None
        process.stdout.close()
        process.stderr.close()

    def test_kernel_credentials_bind_exact_service_and_frontend_to_endpoint(self) -> None:
        calls: list[tuple[int, int, int | None]] = []

        def apply(service_pid: int, uid: int, *, frontend_pid: int | None = None):
            calls.append((service_pid, uid, frontend_pid))
            return {"verified": True}

        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            endpoint = directory / "amy.sock"
            watcher = runtime.RegistrationWatcher(
                os.getuid(), runtime_directory=directory, apply_policy=apply
            )
            try:
                watcher.open()
            except PermissionError as exc:
                self.skipTest(f"sandbox blocks Unix sockets: {exc}")
            self.assertEqual(stat.S_IMODE(watcher.path.stat().st_mode), 0o622)
            service = self._child("amy-service", endpoint, directory)
            frontend: subprocess.Popen[str] | None = None
            try:
                service_registration = self._accept(watcher)
                service_result = json.loads(service.stdout.readline())  # type: ignore[union-attr]
                self.assertTrue(service_result["applied"])
                self.assertIsNotNone(service_registration)
                assert service_registration is not None
                self.assertEqual(service_registration.pid, service.pid)
                self.assertEqual(calls[-1], (service.pid, os.getuid(), None))

                frontend = self._child("frontend", endpoint, directory)
                frontend_registration = self._accept(watcher)
                frontend_result = json.loads(frontend.stdout.readline())  # type: ignore[union-attr]
                self.assertTrue(frontend_result["applied"])
                self.assertIsNotNone(frontend_registration)
                assert frontend_registration is not None
                self.assertEqual(frontend_registration.pid, frontend.pid)
                self.assertEqual(calls[-1], (service.pid, os.getuid(), frontend.pid))
            finally:
                for process in (frontend, service):
                    if process is None:
                        continue
                    self._stop_child(process)
                watcher.close()

    def test_kernel_uid_mismatch_is_rejected_before_policy_application(self) -> None:
        applied: list[bool] = []
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            watcher = runtime.RegistrationWatcher(
                os.getuid(),
                runtime_directory=directory,
                apply_policy=lambda *_args, **_kwargs: applied.append(True),
            )
            try:
                watcher.open()
            except PermissionError as exc:
                self.skipTest(f"sandbox blocks Unix sockets: {exc}")
            service = self._child("amy-service", directory / "amy.sock", directory)
            try:
                events = watcher.selector.select(timeout=5)
                self.assertTrue(events)
                with mock.patch.object(
                    runtime,
                    "peer_credentials",
                    return_value=(service.pid, os.getuid() + 1, os.getgid()),
                ):
                    registration = watcher.accept()
                result = json.loads(service.stdout.readline())  # type: ignore[union-attr]
                self.assertIsNone(registration)
                self.assertFalse(result["accepted"])
                self.assertIn("does not match", result["issue"])
                self.assertEqual(applied, [])
            finally:
                self._stop_child(service)
                watcher.close()

    def test_frontend_cannot_bind_to_an_unrelated_service_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            watcher = runtime.RegistrationWatcher(
                os.getuid(),
                runtime_directory=directory,
                apply_policy=lambda *_args, **_kwargs: {"verified": True},
            )
            try:
                watcher.open()
            except PermissionError as exc:
                self.skipTest(f"sandbox blocks Unix sockets: {exc}")
            frontend = self._child("frontend", directory / "other.sock", directory)
            try:
                registration = self._accept(watcher)
                result = json.loads(frontend.stdout.readline())  # type: ignore[union-attr]
                self.assertIsNotNone(registration)
                self.assertTrue(result["accepted"])
                self.assertFalse(result["applied"])
                self.assertIn("matching AMY service", result["issue"])
            finally:
                self._stop_child(frontend)
                watcher.close()

    def test_protocol_authorities_are_compatible(self) -> None:
        self.assertEqual(client.PROTOCOL, runtime.PROTOCOL)
        self.assertEqual(
            client.registration_socket_path(123),
            runtime.registration_socket_path(123),
        )

    def test_applied_policy_verification_checks_every_registered_layer(self) -> None:
        result = {
            "amy": {"tid": 101},
            "frontend": {"pid": 200},
            "pipewire": [
                {"process": "pipewire", "tid": 301, "fifo": 80},
                {"process": "pipewire-pulse", "tid": 302, "fifo": 75},
            ],
        }
        with (
            mock.patch.object(runtime, "task_ids", return_value=[200, 201]),
            mock.patch.object(runtime, "_policy_matches", return_value=True) as matches,
        ):
            runtime.verify_applied_policy(result, require_frontend=True)
        self.assertEqual(
            matches.call_args_list,
            [
                mock.call(101, {3}, os.SCHED_FIFO, 70),
                mock.call(200, {0, 1}, os.SCHED_OTHER, 0),
                mock.call(201, {0, 1}, os.SCHED_OTHER, 0),
                mock.call(301, {2}, os.SCHED_FIFO, 80),
                mock.call(302, {2}, os.SCHED_FIFO, 75),
            ],
        )

    def test_applied_policy_verification_rejects_one_wrong_thread(self) -> None:
        result = {
            "amy": {"tid": 101},
            "frontend": {"pid": None},
            "pipewire": [
                {"process": "pipewire", "tid": 301, "fifo": 80},
                {"process": "pipewire-pulse", "tid": 302, "fifo": 75},
            ],
        }
        with mock.patch.object(runtime, "_policy_matches", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "AMY callback"):
                runtime.verify_applied_policy(result, require_frontend=False)

    def test_runtime_adapter_skips_pi_policy_for_serial_transport(self) -> None:
        with mock.patch.object(adapters, "prepare_realtime_startup") as prepare:
            result = adapters.resolve_package_runtime(
                platform_name="wayland",
                private_files_dir=Path("/tmp/app"),
                amy_socket=None,
                amy_local_name=None,
            )
        prepare.assert_not_called()
        self.assertEqual(result.startup_warnings, ())

    def test_runtime_adapter_retains_registered_frontend_lifetime(self) -> None:
        closed: list[bool] = []
        startup = SimpleNamespace(
            warnings=("warning",),
            close=lambda: closed.append(True),
        )
        with mock.patch.object(adapters, "prepare_realtime_startup", return_value=startup) as prepare:
            result = adapters.resolve_package_runtime(
                platform_name="wayland",
                private_files_dir=Path("/tmp/app"),
                amy_socket="/tmp/amy.sock",
                amy_local_name=None,
            )
        prepare.assert_called_once_with("/tmp/amy.sock")
        self.assertEqual(result.startup_warnings, ("warning",))
        result.close()
        self.assertEqual(closed, [True])

    def test_runtime_adapter_import_does_not_require_unix_pwd_module(self) -> None:
        script = f"""
import builtins
import sys
sys.path.insert(0, {str(CODE)!r})
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name == 'pwd':
        raise ModuleNotFoundError('blocked pwd')
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
import runtime_platform_adapters
print('OK')
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "OK")


if __name__ == "__main__":
    unittest.main()
