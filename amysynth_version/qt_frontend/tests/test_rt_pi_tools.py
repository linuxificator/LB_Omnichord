from __future__ import annotations

import importlib.util
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


if __name__ == "__main__":
    unittest.main()
