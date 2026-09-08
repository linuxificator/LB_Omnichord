from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))

from runtime_cpu_affinity import (  # noqa: E402
    LOCAL_AMY_FRONTEND_ENV,
    apply_local_amy_affinity,
    frontend_uses_local_amy_service,
    local_amy_affinity_plan,
    read_device_model,
    current_thread_ids,
)


class RuntimeCpuAffinityTests(unittest.TestCase):
    def test_four_core_pi_reserves_highest_cpu_for_service(self) -> None:
        plan = local_amy_affinity_plan(
            "Raspberry Pi 4 Model B Rev 1.5",
            {3, 1, 0, 2},
        )

        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan.frontend_cpus, frozenset({0, 1, 2}))
        self.assertEqual(plan.service_cpus, frozenset({3}))

    def test_plan_respects_an_existing_nonzero_cpuset(self) -> None:
        plan = local_amy_affinity_plan(
            "Raspberry Pi 5 Model B Rev 1.0",
            {4, 5, 6, 7},
        )

        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan.frontend_cpus, frozenset({4, 5, 6}))
        self.assertEqual(plan.service_cpus, frozenset({7}))

    def test_non_pi_and_small_cpuset_keep_os_policy(self) -> None:
        self.assertIsNone(local_amy_affinity_plan("Generic Linux", range(4)))
        self.assertIsNone(
            local_amy_affinity_plan("Raspberry Pi 4 Model B", range(3))
        )

    def test_apply_selects_only_the_role_owned_cpus(self) -> None:
        calls: list[tuple[int, set[int]]] = []
        diagnostics = io.StringIO()

        plan = apply_local_amy_affinity(
            "service",
            model="Raspberry Pi 4 Model B",
            get_affinity=lambda _pid: {0, 1, 2, 3},
            set_affinity=lambda pid, cpus: calls.append((pid, cpus)),
            thread_ids=lambda: (41, 42),
            diagnostics=diagnostics,
        )

        self.assertIsNotNone(plan)
        self.assertEqual(calls, [(0, {3}), (41, {3}), (42, {3})])
        self.assertIn("service -> CPU(s) 3", diagnostics.getvalue())

    def test_affinity_failure_is_visible_and_nonfatal(self) -> None:
        diagnostics = io.StringIO()

        def reject(_pid: int, _cpus: set[int]) -> None:
            raise PermissionError("not permitted")

        result = apply_local_amy_affinity(
            "frontend",
            model="Raspberry Pi 5 Model B",
            get_affinity=lambda _pid: {0, 1, 2, 3},
            set_affinity=reject,
            thread_ids=lambda: (),
            diagnostics=diagnostics,
        )

        self.assertIsNone(result)
        self.assertIn("keeping OS defaults", diagnostics.getvalue())

    def test_device_model_strips_kernel_nul_terminator(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model"
            path.write_bytes(b"Raspberry Pi 4 Model B\0")
            self.assertEqual(read_device_model(path), "Raspberry Pi 4 Model B")

    def test_thread_id_reader_ignores_non_numeric_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "9").mkdir()
            (path / "3").mkdir()
            (path / "not-a-thread").mkdir()
            self.assertEqual(current_thread_ids(path), (3, 9))

    def test_frontend_marker_is_explicit(self) -> None:
        self.assertTrue(
            frontend_uses_local_amy_service({LOCAL_AMY_FRONTEND_ENV: "1"})
        )
        self.assertFalse(
            frontend_uses_local_amy_service({LOCAL_AMY_FRONTEND_ENV: "0"})
        )
        self.assertFalse(frontend_uses_local_amy_service({}))


if __name__ == "__main__":
    unittest.main()
