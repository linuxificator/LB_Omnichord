from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from supercollider_linux_realtime import (  # noqa: E402
    SCHED_FIFO,
    SCHED_RESET_ON_FORK,
    SCHED_RR,
    _is_realtime,
    _owned_server_pid,
    configure_owned_supernova_realtime,
)


class SuperColliderLinuxRealtimeTests(unittest.TestCase):
    def test_process_discovery_requires_exact_executable_and_owned_session(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proc = root / "proc"
            expected = root / "runtime" / "supernova"
            expected.parent.mkdir()
            expected.touch()
            unrelated = root / "other" / "supernova"
            unrelated.parent.mkdir()
            unrelated.touch()

            def process(pid: int, session: int, executable: Path) -> None:
                target = proc / str(pid)
                target.mkdir(parents=True)
                # Fields after the parenthesized command begin with state,
                # ppid, process group and session ID.
                (target / "stat").write_text(
                    f"{pid} (supernova) S 1 {session} {session} 0 0\n",
                    encoding="utf-8",
                )
                (target / "exe").symlink_to(executable)

            process(201, 100, expected)
            process(202, 999, expected)
            process(203, 100, unrelated)

            self.assertEqual(
                _owned_server_pid(100, expected, proc_root=proc),
                201,
            )

    def test_reset_on_fork_flag_still_counts_as_realtime(self) -> None:
        policy = SCHED_RR | SCHED_RESET_ON_FORK
        self.assertTrue(_is_realtime((policy, 20)))
        self.assertFalse(_is_realtime((getattr(os, "SCHED_OTHER", 0), 0)))

    def test_non_linux_host_is_a_no_op(self) -> None:
        result = configure_owned_supernova_realtime(
            123,
            Path("/missing/supernova"),
            platform="darwin",
            timeout=0,
        )
        self.assertEqual(result.status, "not-applicable")

    def test_only_owned_dsp_pool_is_promoted_through_rtkit(self) -> None:
        threads = {
            701: "DSP Thread 0",
            702: "DSP Thread 1",
            703: "DSP Thread 2",
        }
        reset_flag = SCHED_RESET_ON_FORK
        schedulers = {
            701: (SCHED_RR | reset_flag, 20),
            702: (getattr(os, "SCHED_OTHER", 0), 0),
            703: (getattr(os, "SCHED_OTHER", 0), 0),
        }
        calls: list[list[str]] = []

        def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            if "get-property" in command:
                return subprocess.CompletedProcess(command, 0, "i 20\n", "")
            tid = int(command[-2])
            schedulers[tid] = (SCHED_RR | reset_flag, int(command[-1]))
            return subprocess.CompletedProcess(command, 0, "", "")

        with (
            patch(
                "supercollider_linux_realtime._wait_for_dsp_pool",
                return_value=(700, threads),
            ),
            patch(
                "supercollider_linux_realtime._scheduler",
                side_effect=lambda tid: schedulers.get(tid),
            ),
        ):
            result = configure_owned_supernova_realtime(
                600,
                Path("/opt/sc/bin/supernova"),
                environment={
                    "PATH": "/usr/bin",
                    "LD_LIBRARY_PATH": "/app/lib",
                    "LD_PRELOAD": "/app/preload.so",
                },
                run=fake_run,
                which=lambda name: "/usr/bin/busctl" if name == "busctl" else None,
            )

        self.assertEqual(result.status, "promoted")
        self.assertEqual(result.server_pid, 700)
        self.assertEqual(result.dsp_threads, 3)
        self.assertEqual(result.promoted_threads, 2)
        promotion_calls = [call for call in calls if "call" in call]
        self.assertEqual([call[-2] for call in promotion_calls], ["702", "703"])
        self.assertTrue(
            all(call[-3] == "700" and call[-1] == "20" for call in promotion_calls)
        )

    def test_existing_realtime_pool_does_not_invoke_rtkit(self) -> None:
        threads = {801: "DSP Thread 0", 802: "DSP Thread 1"}
        with (
            patch(
                "supercollider_linux_realtime._wait_for_dsp_pool",
                return_value=(800, threads),
            ),
            patch(
                "supercollider_linux_realtime._scheduler",
                return_value=(SCHED_FIFO, 10),
            ),
        ):
            result = configure_owned_supernova_realtime(
                750,
                Path("/opt/sc/bin/supernova"),
                run=lambda *_args, **_kwargs: self.fail("RealtimeKit was invoked"),
                which=lambda _name: self.fail("busctl lookup was attempted"),
            )

        self.assertEqual(result.status, "already-realtime")


if __name__ == "__main__":
    unittest.main()
