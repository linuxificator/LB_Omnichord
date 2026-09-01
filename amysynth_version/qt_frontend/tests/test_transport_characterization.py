from __future__ import annotations

import sys
import threading
import unittest
from collections import deque
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from amy_transport import _SerialWriter  # noqa: E402


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
    @staticmethod
    def closed_writer() -> _SerialWriter:
        writer = _SerialWriter.__new__(_SerialWriter)
        writer.debug_log = None
        writer._high = deque()
        writer._low = deque()
        writer._lane_generation = {}
        writer._closed = True
        writer._condition = threading.Condition()
        return writer

    def test_high_priority_precedes_current_low_and_stale_low_is_dropped(self) -> None:
        writer = self.closed_writer()
        writer._high.append(("command", "high", 0.0))
        writer._low.extend(
            [
                ("rhythm", 1, "stale"),
                ("rhythm", 2, "current"),
            ]
        )
        writer._lane_generation["rhythm"] = 2
        emitted: list[tuple[str, str]] = []
        writer._write = lambda command, lane: emitted.append((lane, command))

        writer._run()

        self.assertEqual(emitted, [("HIGH", "high"), ("LOW", "current")])

    def test_close_is_idempotent_and_rejects_later_queue_work(self) -> None:
        serial_probe = _SerialProbe()
        with patch("amy_transport.serial.Serial", return_value=serial_probe):
            writer = _SerialWriter("probe", 1_000_000, 0.1)
            generation = writer.new_low_generation("rhythm")
            writer.close()
            writer.close()
            writer.high("after-close")
            writer.delay(0.1)
            writer.low("rhythm", generation, "after-close-low")

        self.assertEqual(serial_probe.close_count, 1)
        self.assertEqual(list(writer._high), [])
        self.assertEqual(list(writer._low), [])
        self.assertFalse(writer._thread.is_alive())

    def test_close_discards_pending_low_but_keeps_pending_high_for_drain(self) -> None:
        writer = self.closed_writer()
        writer._closed = False
        writer._high.append(("command", "safety", 0.0))
        writer._low.append(("rhythm", 1, "replaceable"))
        writer._lane_generation["rhythm"] = 1

        class ThreadProbe:
            join_count = 0

            def join(self, timeout: float) -> None:
                self.join_count += 1

        writer._thread = ThreadProbe()
        writer.serial = _SerialProbe()

        writer.close()

        self.assertEqual(list(writer._low), [])
        self.assertEqual(
            list(writer._high),
            [("command", "safety", 0.0)],
        )
        self.assertEqual(writer._lane_generation, {"rhythm": 2})
        self.assertEqual(writer._thread.join_count, 1)
        self.assertEqual(writer.serial.close_count, 1)

    def test_serial_constructor_and_write_errors_propagate_at_current_seams(self) -> None:
        with patch(
            "amy_transport.serial.Serial",
            side_effect=OSError("open failed"),
        ):
            with self.assertRaisesRegex(OSError, "open failed"):
                _SerialWriter("missing", 1_000_000, 0.1)

        writer = self.closed_writer()

        class FailingSerial:
            @staticmethod
            def write(_payload: bytes) -> int:
                raise OSError("write failed")

        writer.serial = FailingSerial()
        with self.assertRaisesRegex(OSError, "write failed"):
            writer._write("n60l1i1", "HIGH")

    def test_wire_line_is_ascii_lf_framed_with_exactly_one_terminator(self) -> None:
        self.assertEqual(_SerialWriter._line("n60l1i1"), b"n60l1i1Z\n")
        self.assertEqual(_SerialWriter._line(" n60l1i1Z "), b"n60l1i1Z\n")
        with self.assertRaises(UnicodeEncodeError):
            _SerialWriter._line("n♪l1i1")


if __name__ == "__main__":
    unittest.main()
