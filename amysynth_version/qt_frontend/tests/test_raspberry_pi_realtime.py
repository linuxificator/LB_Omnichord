from __future__ import annotations

import ast
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
sys.path.insert(0, str(CODE))

import raspberry_pi_realtime as realtime  # noqa: E402
import runtime_platform_adapters as adapters  # noqa: E402


def complete_facts() -> realtime.RealtimeFacts:
    return realtime.RealtimeFacts(
        "Raspberry Pi 4 Model B Rev 1.1",
        "rootwait isolcpus=domain,managed_irq,2-3 irqaffinity=0-1 threadirqs",
        "2-3",
        ("performance",),
        80,
    )


class RaspberryPiRealtimeTests(unittest.TestCase):
    def test_policy_change_preserves_pipewire_reset_on_fork_flag(self) -> None:
        reset = getattr(os, "SCHED_RESET_ON_FORK", 0x40000000)
        with (
            mock.patch.object(realtime.os, "sched_setaffinity"),
            mock.patch.object(
                realtime.os,
                "sched_getscheduler",
                return_value=os.SCHED_OTHER | reset,
            ),
            mock.patch.object(realtime.os, "sched_setscheduler") as scheduler,
        ):
            realtime.set_thread_policy(1041, realtime.PIPEWIRE_CPUS, 80)
        scheduler.assert_called_once_with(
            1041,
            os.SCHED_FIFO | reset,
            os.sched_param(80),
        )

    def test_pipewire_pulse_is_identified_by_its_native_thread_name(self) -> None:
        with (
            mock.patch.object(realtime, "_process_ids", return_value=(1001, 1012)),
            mock.patch.object(realtime, "_process_executable", return_value="pipewire"),
            mock.patch.object(
                realtime,
                "task_ids",
                side_effect=lambda pid: (pid, pid + 1),
            ),
            mock.patch.object(
                realtime,
                "_thread_name",
                side_effect=lambda pid, tid: {
                    (1001, 1001): "pipewire",
                    (1001, 1002): "data-loop.0",
                    (1012, 1012): "pipewire-pulse",
                    (1012, 1013): "data-loop.0",
                }[(pid, tid)],
            ),
        ):
            loops = realtime.discover_pipewire_loops(os.getuid())
        self.assertEqual(loops, {"pipewire": 1002, "pipewire-pulse": 1013})

    def test_exact_child_pid_is_required_and_never_discovered_by_name(self) -> None:
        with (
            mock.patch.object(realtime, "_owned_process", return_value=False),
            mock.patch.object(realtime, "_process_ids") as process_ids,
        ):
            result = realtime.apply_runtime_policy(
                4242,
                inspector=lambda: complete_facts(),
            )
        self.assertTrue(result.applicable)
        self.assertFalse(result.applied)
        self.assertIn("exact AMY child PID", result.issue)
        process_ids.assert_not_called()

    def test_wrapper_applies_the_measured_policy_once_to_exact_threads(self) -> None:
        calls: list[tuple[int, frozenset[int], int]] = []

        def set_policy(tid: int, cpus: frozenset[int], priority: int = 0) -> None:
            calls.append((tid, cpus, priority))

        with (
            mock.patch.object(realtime, "_owned_process", return_value=True),
            mock.patch.object(realtime, "task_ids", return_value=(4242, 4243, 4244)),
            mock.patch.object(realtime, "select_active_worker", return_value=4243) as select,
            mock.patch.object(
                realtime,
                "verify_pipewire_policy",
                return_value=(True, ""),
            ),
            mock.patch.object(realtime, "set_thread_policy", side_effect=set_policy),
            mock.patch.object(
                realtime, "verify_runtime_policy", return_value=(True, "")
            ) as verify,
        ):
            result = realtime.apply_runtime_policy(
                4242,
                inspector=lambda: complete_facts(),
            )

        self.assertTrue(result.applied)
        self.assertEqual(result.amy_audio_tid, 4243)
        select.assert_called_once_with(4242)
        verify.assert_called_once_with(4242, frontend_pid=None, uid=os.getuid())
        self.assertEqual(
            calls,
            [
                (4242, realtime.HOUSEKEEPING_CPUS, 0),
                (4243, realtime.HOUSEKEEPING_CPUS, 0),
                (4244, realtime.HOUSEKEEPING_CPUS, 0),
                (4243, realtime.AMY_AUDIO_CPUS, 70),
            ],
        )

    def test_readback_rejects_one_wrong_amy_thread(self) -> None:
        expected = {
            4242: (realtime.HOUSEKEEPING_CPUS, os.SCHED_OTHER, 0),
            4243: (realtime.AMY_AUDIO_CPUS, os.SCHED_FIFO, 70),
            4244: (realtime.HOUSEKEEPING_CPUS, os.SCHED_OTHER, 0),
            6001: (realtime.HOUSEKEEPING_CPUS, os.SCHED_OTHER, 0),
            5001: (realtime.PIPEWIRE_CPUS, os.SCHED_FIFO, 80),
            5002: (realtime.PIPEWIRE_CPUS, os.SCHED_FIFO, 75),
        }

        def matches(
            tid: int, cpus: frozenset[int], scheduler: int, priority: int
        ) -> bool:
            return expected.get(tid) == (cpus, scheduler, priority)

        with (
            mock.patch.object(realtime, "_owned_process", return_value=True),
            mock.patch.object(
                realtime,
                "task_ids",
                side_effect=lambda pid: {
                    4242: (4242, 4243, 4244),
                    6001: (6001,),
                }[pid],
            ),
            mock.patch.object(
                realtime,
                "discover_pipewire_loops",
                return_value={"pipewire": 5001, "pipewire-pulse": 5002},
            ),
            mock.patch.object(realtime, "_policy_matches", side_effect=matches),
        ):
            valid, issue = realtime.verify_runtime_policy(
                4242, frontend_pid=6001
            )
            expected[4244] = (realtime.AMY_AUDIO_CPUS, os.SCHED_FIFO, 70)
            invalid, invalid_issue = realtime.verify_runtime_policy(
                4242, frontend_pid=6001
            )

        self.assertTrue(valid, issue)
        self.assertFalse(invalid)
        self.assertIn("exactly one", invalid_issue)

    def test_runtime_adapter_skips_host_policy_for_serial_transport(self) -> None:
        with mock.patch.object(adapters, "prepare_realtime_startup") as prepare:
            result = adapters.resolve_package_runtime(
                platform_name="wayland",
                private_files_dir=Path("/tmp/app"),
                amy_socket=None,
                amy_local_name=None,
            )
        prepare.assert_not_called()
        self.assertEqual(result.startup_warnings, ())

    def test_runtime_adapter_verifies_wrapper_supplied_service_pid(self) -> None:
        startup = realtime.RealtimeStartup(("warning",))
        with (
            mock.patch.object(adapters, "service_pid_from_environment", return_value=4242),
            mock.patch.object(
                adapters, "prepare_realtime_startup", return_value=startup
            ) as prepare,
        ):
            result = adapters.resolve_package_runtime(
                platform_name="wayland",
                private_files_dir=Path("/tmp/app"),
                amy_socket="/tmp/amy.sock",
                amy_local_name=None,
            )
        prepare.assert_called_once_with("/tmp/amy.sock", service_pid=4242)
        self.assertEqual(result.startup_warnings, ("warning",))

    def test_service_pid_environment_rejects_missing_or_invalid_values(self) -> None:
        self.assertIsNone(realtime.service_pid_from_environment({}))
        self.assertIsNone(
            realtime.service_pid_from_environment(
                {realtime.SERVICE_PID_ENV: "not-a-pid"}
            )
        )
        self.assertEqual(
            realtime.service_pid_from_environment(
                {realtime.SERVICE_PID_ENV: "4242"}
            ),
            4242,
        )

    def test_platform_adapter_import_does_not_require_unix_only_pwd(self) -> None:
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

    def test_appimage_passes_the_child_pid_without_name_lookup(self) -> None:
        tree = ast.parse(
            (ROOT / "packaging" / "appimage_entry.py").read_text(encoding="utf-8")
        )
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "apply_runtime_policy"
        ]
        self.assertEqual(len(calls), 1)
        argument = calls[0].args[0]
        self.assertIsInstance(argument, ast.Attribute)
        assert isinstance(argument, ast.Attribute)
        self.assertEqual((argument.value.id, argument.attr), ("service", "pid"))


if __name__ == "__main__":
    unittest.main()
