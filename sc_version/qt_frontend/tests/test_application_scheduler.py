from __future__ import annotations

import sys
import threading
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from application_scheduler import MonotonicScheduler  # noqa: E402
from amy_transport import AmySerialClient  # noqa: E402


class ApplicationSchedulerTests(unittest.TestCase):
    def test_callbacks_are_ordered_on_one_worker_and_replace_by_key(self) -> None:
        scheduler = MonotonicScheduler(capacity=4, name="app-order-test")
        calls: list[tuple[str, int]] = []
        complete = threading.Event()
        scheduler.schedule(0.2, lambda: calls.append(("replaced", 0)), replace_key="tail")
        scheduler.schedule(0.01, lambda: calls.append(("first", threading.get_ident())))
        scheduler.schedule(
            0.02,
            lambda: (
                calls.append(("tail", threading.get_ident())),
                complete.set(),
            ),
            replace_key="tail",
        )
        self.assertTrue(complete.wait(1.0))
        scheduler.close()

        self.assertEqual([name for name, _ in calls], ["first", "tail"])
        self.assertEqual(len({thread_id for _, thread_id in calls}), 1)
        self.assertEqual(scheduler.health.replaced, 1)

    def test_capacity_is_explicit_and_close_cancels_pending_work(self) -> None:
        scheduler = MonotonicScheduler(capacity=2, name="app-bound-test")
        calls: list[str] = []
        scheduler.schedule(10.0, lambda: calls.append("one"))
        scheduler.schedule(10.0, lambda: calls.append("two"))
        with self.assertRaisesRegex(BufferError, "capacity"):
            scheduler.schedule(10.0, lambda: calls.append("three"))
        self.assertEqual(scheduler.health.high_water, 2)
        scheduler.close()
        scheduler.close()
        self.assertEqual(calls, [])
        self.assertEqual(scheduler.health.lifecycle, "closed")
        with self.assertRaisesRegex(RuntimeError, "closed"):
            scheduler.schedule(0, lambda: None)

    def test_callback_failure_is_visible_without_killing_scheduler(self) -> None:
        scheduler = MonotonicScheduler(name="app-failure-test")
        complete = threading.Event()

        def fail() -> None:
            raise ValueError("callback failed")

        scheduler.schedule(0, fail)
        scheduler.schedule(0.01, complete.set)
        self.assertTrue(complete.wait(1.0))
        deadline = time.monotonic() + 1.0
        while scheduler.health.callback_failures == 0 and time.monotonic() < deadline:
            time.sleep(0.001)
        self.assertEqual(scheduler.health.callback_failures, 1)
        self.assertIn("callback failed", scheduler.health.last_callback_error or "")
        scheduler.close()

    def test_product_code_creates_no_per_event_threading_timer(self) -> None:
        for filename in ("amy_transport.py", "midi_player.py"):
            source = (ROOT / "code" / filename).read_text(encoding="utf-8")
            self.assertNotIn("threading.Timer", source, filename)

    def test_delayed_note_off_retains_synth_generation_cancellation(self) -> None:
        scheduled: list[tuple[float, object]] = []
        emitted: list[str] = []

        class ManualScheduler:
            @staticmethod
            def schedule(delay: float, callback: object) -> int:
                scheduled.append((delay, callback))
                return len(scheduled)

        client = AmySerialClient.__new__(AmySerialClient)
        client.application_scheduler = ManualScheduler()
        client._synth_generation = {3: 4}
        client._wire = emitted.append
        client._note_off_later(3, 60.0, 25.0)
        self.assertEqual(scheduled[0][0], 0.025)
        callback = scheduled[0][1]
        self.assertTrue(callable(callback))
        client._synth_generation[3] = 5
        callback()
        self.assertEqual(emitted, [])

        client._note_off_later(3, 60.0, 25.0)
        callback = scheduled[1][1]
        self.assertTrue(callable(callback))
        callback()
        self.assertEqual(emitted, ["n60l0i3Z"])


if __name__ == "__main__":
    unittest.main()
