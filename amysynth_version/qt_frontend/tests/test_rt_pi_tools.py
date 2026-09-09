from __future__ import annotations

import importlib.util
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "raspberry_pi"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


config = load("rt_pi_config")
benchmark = load("rt_pi_benchmark")
strum = load("strum_uinput")
runtime = load("rt_pi_runtime")
trace = load("rt_pi_trace")


def load_path(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


realtime_status = load_path(
    "raspberry_pi_realtime",
    ROOT / "code" / "raspberry_pi_realtime.py",
)
asset_builder = load_path(
    "build_rpi_realtime_setup",
    ROOT / "packaging" / "build_rpi_realtime_setup.py",
)


class RtPiConfigTests(unittest.TestCase):
    def test_profiles_replace_only_owned_kernel_arguments(self) -> None:
        original = (
            "console=tty1 root=PARTUUID=abc rootwait quiet "
            "isolcpus=3 irqaffinity=0-2 threadirqs vendor.option=keep\n"
        )
        updated = config.update_kernel_cmdline(original, config.PROFILES["audio-split"])
        self.assertEqual(updated.count("isolcpus="), 1)
        self.assertEqual(updated.count("irqaffinity="), 1)
        self.assertEqual(updated.count("threadirqs"), 1)
        self.assertIn("vendor.option=keep", updated)
        self.assertIn("isolcpus=domain,managed_irq,2-3", updated)

    def test_stock_removes_managed_arguments_and_preserves_unknowns(self) -> None:
        updated = config.update_kernel_cmdline(
            "root=/dev/mmcblk0 threadirqs isolcpus=3 custom=yes\n",
            config.PROFILES["stock"],
        )
        self.assertEqual(updated, "root=/dev/mmcblk0 custom=yes\n")

    def test_startup_status_is_silent_outside_pi_4_and_pi_5(self) -> None:
        status = realtime_status.evaluate_realtime(
            realtime_status.RealtimeFacts("generic arm64", "", "", (), False)
        )
        self.assertFalse(status.applicable)
        self.assertTrue(status.complete)
        self.assertEqual(status.missing, ())

    def test_startup_status_reports_every_incomplete_realtime_layer(self) -> None:
        status = realtime_status.evaluate_realtime(
            realtime_status.RealtimeFacts(
                "Raspberry Pi 5 Model B Rev 1.0",
                "console=tty1 rootwait",
                "",
                ("ondemand",),
                False,
            )
        )
        self.assertTrue(status.applicable)
        self.assertFalse(status.complete)
        self.assertEqual(len(status.missing), 4)

    def test_startup_status_accepts_the_measured_split_profile(self) -> None:
        status = realtime_status.evaluate_realtime(
            realtime_status.RealtimeFacts(
                "Raspberry Pi 4 Model B Rev 1.1",
                "rootwait isolcpus=domain,managed_irq,2-3 "
                "irqaffinity=0-1 threadirqs",
                "2-3",
                ("performance", "performance"),
                True,
            )
        )
        self.assertTrue(status.applicable)
        self.assertTrue(status.complete)
        self.assertEqual(status.missing, ())

    def test_release_setup_asset_is_named_versioned_and_self_contained(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output, checksum = asset_builder.build(
                "R20260909153000",
                Path(temporary),
            )
            source = output.read_text(encoding="utf-8")
            fields = checksum.read_text(encoding="ascii").split()

        self.assertEqual(
            output.name,
            "LB_Omnichord.R20260909153000.Pi4-Pi5-realtime-setup.sh",
        )
        self.assertIn("Raspberry Pi 4", source)
        self.assertIn("Raspberry Pi 5", source)
        self.assertIn("apply --profile audio-split", source)
        self.assertIn("set-governor performance", source)
        self.assertIn("lb-omnichord-rt-policy@$target_user.service", source)
        self.assertIn("rt_pi_runtime.py", source)
        self.assertEqual(fields[1], output.name)
        self.assertEqual(fields[0], hashlib.sha256(source.encode()).hexdigest())

    def test_apply_reports_whether_the_running_kernel_needs_a_reboot(self) -> None:
        source = (TOOLS / "rt_pi_config.py").read_text(encoding="utf-8")
        self.assertIn("active, _checks = verify_profile(args.profile)", source)
        self.assertIn("profile is already active; reboot is not required", source)
        self.assertIn("reboot is required; verify after reconnecting", source)


class RtPiBenchmarkTests(unittest.TestCase):
    def test_wire_log_parser_selects_session_and_retains_timing(self) -> None:
        text = """\
2026-09-09T01:00:00.000+02:00 SESSION      --- AMY Omnichord start ---
2026-09-09T01:00:00.100+02:00 TX-HIGH      aZ
2026-09-09T01:00:00.350+02:00 TX-LOW       bZ
2026-09-09T02:00:00.000+02:00 SESSION      --- AMY Omnichord start ---
2026-09-09T02:00:01.000+02:00 TX-HIGH      cZ
"""
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "amy.log"
            path.write_text(text, encoding="utf-8")
            first = benchmark.parse_wire_log(path, 0)
            last = benchmark.parse_wire_log(path, -1)
        self.assertEqual([event.wire for event in first], ["aZ", "bZ"])
        self.assertAlmostEqual(first[1].offset_seconds, 0.25)
        self.assertEqual([event.wire for event in last], ["cZ"])
        self.assertEqual(last[0].offset_seconds, 0.0)

    def test_synthetic_profiles_obey_release_capacity(self) -> None:
        sine = benchmark.synthetic_commands("sine", 336)
        dx7 = benchmark.synthetic_commands("dx7", 42)
        self.assertTrue(any(command.startswith("v335w0") for command in sine))
        self.assertIn("K129i1iv10Z", dx7)
        with self.assertRaisesRegex(ValueError, "336"):
            benchmark.synthetic_commands("filtered-saw", 337)
        with self.assertRaisesRegex(ValueError, "42"):
            benchmark.synthetic_commands("dx7", 43)

    def test_audio_candidate_is_busiest_non_main_thread(self) -> None:
        samples = [
            benchmark.ThreadSample(100, "main", 0.2, 1.0, 10),
            benchmark.ThreadSample(102, "idle", 0.0, 0.0, 1),
            benchmark.ThreadSample(101, "audio", 22.0, 2.0, 100),
        ]
        selected = benchmark.select_audio_thread(samples, 100)
        self.assertEqual(selected.tid, 101)

    def test_interrupt_parser_keeps_per_cpu_counts_and_description(self) -> None:
        sample = """\
           CPU0       CPU1       CPU2       CPU3
 15:        903          0          0          0    GICv2 114 Level DMA IRQ
IPI0:       100        200        300        400       Rescheduling interrupts
"""
        parsed = benchmark.parse_interrupts(sample)
        self.assertEqual(parsed["15"][0], [903, 0, 0, 0])
        self.assertIn("DMA IRQ", parsed["15"][1])
        self.assertEqual(parsed["IPI0"][0], [100, 200, 300, 400])

    def test_external_strum_is_bounded_and_returns_to_start(self) -> None:
        points = strum.sweep_points(
            width=1920,
            height=1080,
            x_fraction=0.94,
            y_min_fraction=0.16,
            y_max_fraction=0.84,
            rate_hz=120,
            duration_seconds=1,
        )
        self.assertEqual(len(points), 120)
        self.assertEqual(points[0], points[-1])
        self.assertEqual(points[0].x, round(1919 * 0.94))
        self.assertLess(points[0].y, points[len(points) // 2].y)

    def test_runtime_discovers_only_explicit_amy_service(self) -> None:
        commands = {
            10: "/tmp/LB_Omnichord --amy-service --socket /tmp/a.sock",
            11: "/tmp/LB_Omnichord",
            12: "python something.py --amy-service-like",
        }
        original_ids = runtime.process_ids
        original_command = runtime.process_command
        try:
            runtime.process_ids = lambda _uid=None: list(commands)
            runtime.process_command = commands.__getitem__
            self.assertEqual(runtime.discover_amy_services(), [10])
        finally:
            runtime.process_ids = original_ids
            runtime.process_command = original_command

    def test_runtime_reads_frontend_parent(self) -> None:
        original_read = runtime._read
        try:
            runtime._read = lambda path: "Name:\ttest\nPPid:\t123\n"
            self.assertEqual(runtime.parent_pid(456), 123)
        finally:
            runtime._read = original_read

    def test_runtime_never_treats_init_as_a_frontend(self) -> None:
        original_parent = runtime.parent_pid
        original_command = runtime.process_command
        try:
            runtime.parent_pid = lambda _pid: 1
            runtime.process_command = lambda _pid: "/sbin/init"
            self.assertIsNone(runtime.frontend_parent_pid(456))

            runtime.parent_pid = lambda _pid: 123
            runtime.process_command = lambda _pid: "/tmp/LB_Omnichord --fullscreen"
            self.assertEqual(runtime.frontend_parent_pid(456), 123)

            runtime.process_command = lambda _pid: "/usr/lib/systemd/systemd"
            self.assertIsNone(runtime.frontend_parent_pid(456))
        finally:
            runtime.parent_pid = original_parent
            runtime.process_command = original_command

    def test_runtime_signature_changes_when_audio_processes_change(self) -> None:
        original_frontend = runtime.frontend_parent_pid
        original_tasks = runtime.task_ids
        original_pipewire = runtime.discover_pipewire
        original_read = runtime._read
        try:
            runtime.frontend_parent_pid = lambda _pid: 50
            runtime.task_ids = lambda pid: {60: [60, 61], 70: [70, 71]}[pid]
            runtime.discover_pipewire = lambda _uid=None: [70]
            runtime._read = lambda path: "data-loop.0" if path.parts[-2] == "71" else "other"
            first = runtime.runtime_signature(60)
            runtime.frontend_parent_pid = lambda _pid: 51
            second = runtime.runtime_signature(60)
            self.assertNotEqual(first, second)
        finally:
            runtime.frontend_parent_pid = original_frontend
            runtime.task_ids = original_tasks
            runtime.discover_pipewire = original_pipewire
            runtime._read = original_read

    def test_trace_parser_reports_wake_and_runtime_tail(self) -> None:
        sample = """\
 worker-9 [003] 1.000000: sched_wakeup: comm=audio pid=42 prio=50 target_cpu=003
 idle-0 [003] 1.000100: sched_switch: prev_comm=idle prev_pid=0 prev_prio=120 prev_state=R ==> next_comm=audio next_pid=42 next_prio=50
 audio-42 [003] 1.000900: sched_switch: prev_comm=audio prev_pid=42 prev_prio=50 prev_state=S ==> next_comm=idle next_pid=0 next_prio=120
 worker-9 [003] 2.000000: sched_wakeup: comm=audio pid=42 prio=50 target_cpu=003
 idle-0 [003] 2.000300: sched_switch: prev_comm=idle prev_pid=0 prev_prio=120 prev_state=R ==> next_comm=audio next_pid=42 next_prio=50
 audio-42 [003] 2.001100: sched_switch: prev_comm=audio prev_pid=42 prev_prio=50 prev_state=S ==> next_comm=idle next_pid=0 next_prio=120
"""
        result = trace.parse_trace(sample, 42)
        self.assertEqual(result["wake_to_run"]["samples"], 2)
        self.assertAlmostEqual(result["wake_to_run"]["max_ms"], 0.3)
        self.assertAlmostEqual(result["run_to_switch_out"]["median_ms"], 0.8)


if __name__ == "__main__":
    unittest.main()
