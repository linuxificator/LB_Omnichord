from __future__ import annotations

import sys
import queue
import threading
import time
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from amy_transport import (  # noqa: E402
    DEBUG_LOG_MAX_BYTES,
    _DebugLog,
    _SerialWriter,
)
from config_loader import DebugConfig  # noqa: E402
from transport_scheduler import (  # noqa: E402
    CommandScheduler,
    TransportFailed,
    encode_command,
)


class _SinkProbe:
    delimiter = b"\n"

    def __init__(self, *, block_first: bool = False, fail: bool = False) -> None:
        self.payloads: list[bytes] = []
        self.write_times: list[float] = []
        self.open_count = 0
        self.close_count = 0
        self.started = threading.Event()
        self.release = threading.Event()
        self.block_first = block_first
        self.fail = fail

    def open(self) -> None:
        self.open_count += 1

    def write(self, payload: bytes) -> None:
        self.payloads.append(payload)
        self.write_times.append(time.monotonic())
        self.started.set()
        if self.block_first and len(self.payloads) == 1:
            self.release.wait(2.0)
        if self.fail:
            raise OSError("write failed")

    def close(self) -> None:
        self.close_count += 1


class _SerialProbe:
    def __init__(self, *args: object, **kwargs: object) -> None:
        self.constructor_args = args
        self.constructor_kwargs = kwargs
        self.payloads: list[bytes] = []
        self.close_count = 0

    def write(self, payload: bytes) -> int:
        self.payloads.append(payload)
        return len(payload)

    def close(self) -> None:
        self.close_count += 1


class TransportCharacterizationTests(unittest.TestCase):
    def test_high_precedes_queued_low_and_stale_generation_is_coalesced(self) -> None:
        sink = _SinkProbe(block_first=True)
        scheduler = CommandScheduler(sink, name="ordering-test")
        first = scheduler.new_low_generation("rhythm")
        scheduler.low("rhythm", first, "first")
        self.assertTrue(sink.started.wait(1.0))
        scheduler.low("rhythm", first, "stale")
        current = scheduler.new_low_generation("rhythm")
        scheduler.low("rhythm", current, "current")
        scheduler.high("safety")
        sink.release.set()
        deadline = time.monotonic() + 1.0
        while len(sink.payloads) < 3 and time.monotonic() < deadline:
            time.sleep(0.001)
        scheduler.close()

        self.assertEqual(
            sink.payloads,
            [b"firstZ\n", b"safetyZ\n", b"currentZ\n"],
        )
        self.assertGreaterEqual(scheduler.health.coalesced_stale, 1)

    def test_guard_separates_physical_sink_writes(self) -> None:
        sink = _SinkProbe()
        scheduler = CommandScheduler(sink, name="guard-test")
        scheduler.high("allocation")
        scheduler.delay(0.010)
        scheduler.high("post-allocation")
        scheduler.close()

        self.assertEqual(
            sink.payloads,
            [b"allocationZ\n", b"post-allocationZ\n"],
        )
        elapsed = sink.write_times[1] - sink.write_times[0]
        self.assertGreaterEqual(
            elapsed,
            0.008,
            f"guard separated sink writes by only {elapsed:.4f}s",
        )

    def test_critical_overload_is_explicit_and_replaceable_work_is_bounded(self) -> None:
        sink = _SinkProbe(block_first=True)
        scheduler = CommandScheduler(
            sink,
            name="bounds-test",
            high_capacity=2,
            low_capacity=2,
        )
        scheduler.high("block")
        self.assertTrue(sink.started.wait(1.0))
        scheduler.high("critical-1")
        scheduler.high("critical-2")
        with self.assertRaisesRegex(BufferError, "critical"):
            scheduler.high("must-not-disappear")

        generation = scheduler.new_low_generation("lane")
        for command in ("old-1", "old-2", "newest"):
            scheduler.low("lane", generation, command)
        self.assertEqual(scheduler.health.low_depth, 2)
        self.assertEqual(scheduler.health.dropped_replaceable, 1)
        sink.release.set()
        scheduler.close()
        self.assertEqual(scheduler.health.high_water, 2)
        self.assertEqual(sink.close_count, 1)

    def test_terminal_failure_is_visible_and_rejects_new_work(self) -> None:
        sink = _SinkProbe(fail=True)
        scheduler = CommandScheduler(sink, name="failure-test")
        scheduler.high("bad")
        deadline = time.monotonic() + 1.0
        while scheduler.health.lifecycle != "failed" and time.monotonic() < deadline:
            time.sleep(0.001)
        self.assertEqual(scheduler.health.lifecycle, "failed")
        self.assertIn("write failed", scheduler.health.terminal_error or "")
        with self.assertRaisesRegex(TransportFailed, "write failed"):
            scheduler.high("later")
        scheduler.close()
        self.assertEqual(sink.close_count, 1)

    def test_close_is_idempotent_and_does_not_close_sink_under_live_worker(self) -> None:
        sink = _SinkProbe(block_first=True)
        scheduler = CommandScheduler(
            sink,
            name="blocked-close-test",
            shutdown_timeout=0.01,
        )
        scheduler.high("blocked")
        self.assertTrue(sink.started.wait(1.0))
        scheduler.close()
        self.assertTrue(scheduler.worker_alive)
        self.assertTrue(scheduler.health.shutdown_timed_out)
        self.assertEqual(sink.close_count, 0)

        sink.release.set()
        scheduler.close()
        scheduler.close()
        self.assertFalse(scheduler.worker_alive)
        self.assertEqual(sink.close_count, 1)

    def test_serial_facade_opens_and_closes_sink_once(self) -> None:
        serial_probe = _SerialProbe()
        with patch("transport_sinks.serial.Serial", return_value=serial_probe):
            writer = _SerialWriter("probe", 1_000_000, 0.1)
            writer.high("n60l1i1")
            writer.close()
            writer.close()

        self.assertEqual(serial_probe.payloads, [b"n60l1i1Z\n"])
        self.assertEqual(serial_probe.close_count, 1)
        self.assertEqual(writer.health.lifecycle, "closed")

    def test_serial_open_failure_propagates_synchronously(self) -> None:
        with patch(
            "transport_sinks.serial.Serial",
            side_effect=OSError("open failed"),
        ):
            with self.assertRaisesRegex(TransportFailed, "open failed"):
                _SerialWriter("missing", 1_000_000, 0.1)

    def test_wire_line_is_ascii_lf_framed_with_exactly_one_terminator(self) -> None:
        self.assertEqual(_SerialWriter._line("n60l1i1"), b"n60l1i1Z\n")
        self.assertEqual(encode_command(" n60l1i1Z ", b"\n"), b"n60l1i1Z\n")
        with self.assertRaises(UnicodeEncodeError):
            _SerialWriter._line("n♪l1i1")

    def test_debug_log_rotates_and_reports_nonblocking_queue_loss(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "amy.log"
            with path.open("wb") as handle:
                handle.truncate(DEBUG_LOG_MAX_BYTES)
            log = _DebugLog(
                DebugConfig(
                    log_amy_commands=True,
                    amy_command_log=str(path),
                    log_logical_events=True,
                )
            )
            log.write("TEST", "one")
            log.close()
            self.assertTrue(path.with_suffix(".log.1").is_file())
            self.assertIn("TEST", path.read_text(encoding="utf-8"))

        probe = _DebugLog.__new__(_DebugLog)
        probe.enabled = True
        probe._queue = queue.Queue(maxsize=1)
        probe.dropped_records = 0
        probe.write("TEST", "one")
        probe.write("TEST", "two")
        self.assertEqual(probe.dropped_records, 1)

    def test_disabled_debug_log_never_creates_its_configured_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "amy.log"
            log = _DebugLog(
                DebugConfig(
                    log_amy_commands=False,
                    amy_command_log=str(path),
                    log_logical_events=True,
                )
            )

            log.write("TEST", "not persisted")
            log.close()

            self.assertFalse(path.exists())
            self.assertIsNone(log.path)


if __name__ == "__main__":
    unittest.main()
