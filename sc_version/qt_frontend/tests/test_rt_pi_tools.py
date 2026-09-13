from __future__ import annotations

import importlib.util
import hashlib
import io
import subprocess
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "raspberry_pi"
sys.path.insert(0, str(ROOT / "code"))


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
    def test_runtime_boot_contract_matches_configuration_authority(self) -> None:
        self.assertEqual(
            realtime_status.EXPECTED_BOOT_ARGUMENTS,
            frozenset(config.PROFILES["audio-split"].boot_arguments),
        )

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

    def test_apply_is_idempotent_and_preserves_boot_file_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            boot = root / "cmdline.txt"
            state = root / "state"
            boot.write_text("root=/dev/mmcblk0 rootwait\n", encoding="utf-8")
            boot.chmod(0o640)
            with (
                mock.patch.object(config, "BOOT_CMDLINE", boot),
                mock.patch.object(config, "STATE_ROOT", state),
                mock.patch.object(config, "_require_root"),
            ):
                first, _updated = config.apply_profile("audio-split")
                latest = (state / "latest-snapshot").read_text(encoding="utf-8")
                second, _unchanged = config.apply_profile("audio-split")

            self.assertIsNotNone(first)
            self.assertIsNone(second)
            self.assertEqual(
                stat.S_IMODE(boot.stat().st_mode),
                0o640,
            )
            self.assertEqual((state / "latest-snapshot").read_text(), latest)

    def test_startup_status_is_silent_outside_pi_4_and_pi_5(self) -> None:
        status = realtime_status.evaluate_realtime(
            realtime_status.RealtimeFacts("generic arm64", "", "", (), 0)
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
                ("performance",),
                0,
            )
        )
        self.assertTrue(status.applicable)
        self.assertFalse(status.complete)
        self.assertEqual(len(status.missing), 5)
        self.assertIn("Raspberry Pi OS ondemand CPU governor", status.missing)

    def test_startup_status_accepts_the_measured_split_profile(self) -> None:
        status = realtime_status.evaluate_realtime(
            realtime_status.RealtimeFacts(
                "Raspberry Pi 4 Model B Rev 1.1",
                "rootwait isolcpus=domain,managed_irq,2-3 "
                "irqaffinity=0-1 threadirqs",
                "2-3",
                ("ondemand", "ondemand"),
                80,
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
        self.assertIn("install_realtime_profile.sh", source)
        self.assertNotIn("rt_pi_runtime.py", source)
        self.assertIn("sha256sum --check --status", source)
        for file_name, _mode in asset_builder.EMBEDDED_FILES:
            self.assertIn(asset_builder._encoded(TOOLS / file_name), source)
        self.assertEqual(fields[1], output.name)
        self.assertEqual(fields[0], hashlib.sha256(source.encode()).hexdigest())

    def test_release_setup_asset_has_valid_shell_and_verified_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output, _checksum = asset_builder.build(
                "R20260909153000", Path(temporary)
            )
            syntax = subprocess.run(
                ["bash", "-n", str(output)], capture_output=True, text=True
            )
            help_result = subprocess.run(
                ["bash", str(output), "--help"], capture_output=True, text=True
            )
        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("Usage:", help_result.stdout)

    def test_release_setup_asset_rejects_a_corrupted_embedded_helper(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output, _checksum = asset_builder.build(
                "R20260909153000", Path(temporary)
            )
            source = output.read_text(encoding="utf-8")
            marker = "__LB_OMNICHORD_INSTALL_REALTIME_PROFILE_SH__"
            start = source.index("\n", source.index(marker)) + 1
            replacement = "A" if source[start] != "A" else "B"
            output.write_text(
                source[:start] + replacement + source[start + 1 :],
                encoding="utf-8",
            )
            result = subprocess.run(
                ["bash", str(output), "--help"], capture_output=True, text=True
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("integrity check", result.stderr)

    def test_checkout_setup_script_is_the_release_asset_authority(self) -> None:
        installer = (TOOLS / "install_realtime_profile.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("apply --profile audio-split", installer)
        self.assertIn("set-governor ondemand", installer)
        self.assertIn(
            "disable --now lb-omnichord-performance.service",
            installer,
        )
        self.assertNotIn(
            "lb-omnichord-performance.service",
            {name for name, _mode in asset_builder.EMBEDDED_FILES},
        )
        self.assertIn("rtprio 80", installer)
        self.assertIn("pipewire.service.d", installer)
        self.assertIn("pipewire.conf.d", installer)
        self.assertNotIn("enable --now \"lb-omnichord-rt-policy", installer)
        self.assertIn("Raspberry Pi 4", installer)
        self.assertIn("Raspberry Pi 5", installer)
        self.assertIn(
            '("install_realtime_profile.sh", 0o755)',
            (ROOT / "packaging" / "build_rpi_realtime_setup.py").read_text(
                encoding="utf-8"
            ),
        )

    def test_startup_warning_keeps_checksum_details_out_of_the_ui(self) -> None:
        def inspect(**_overrides):
            return realtime_status.RealtimeFacts(
                "Raspberry Pi 4 Model B Rev 1.1",
                "rootwait",
                "",
                ("ondemand",),
                0,
            )

        result = realtime_status.prepare_realtime_startup(
            "/tmp/amy.sock",
            inspector=inspect,
        )
        warning = result.warnings[0]

        self.assertIn("run it with sudo", warning)
        self.assertNotIn("sha256", warning.casefold())
        self.assertNotIn("checksum", warning.casefold())

    def test_apply_reports_whether_the_running_kernel_needs_a_reboot(self) -> None:
        for active, expected in (
            (True, "profile is already active; reboot is not required"),
            (False, "reboot is required; verify after reconnecting"),
        ):
            with (
                self.subTest(active=active),
                mock.patch.object(
                    config, "apply_profile", return_value=(None, "rootwait\n")
                ),
                mock.patch.object(
                    config, "verify_profile", return_value=(active, {})
                ),
                mock.patch.object(
                    sys,
                    "argv",
                    ["rt_pi_config.py", "apply", "--profile", "audio-split"],
                ),
                redirect_stdout(output := io.StringIO()),
            ):
                self.assertEqual(config.main(), 0)
            self.assertIn(expected, output.getvalue())


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
