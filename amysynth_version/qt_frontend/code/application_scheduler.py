from __future__ import annotations

import heapq
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass


APPLICATION_TIMER_CAPACITY = 512


@dataclass(frozen=True, slots=True)
class ApplicationSchedulerHealth:
    lifecycle: str
    pending: int
    high_water: int
    replaced: int
    callback_failures: int
    last_callback_error: str | None


@dataclass(order=True, frozen=True, slots=True)
class _ScheduledCall:
    deadline: float
    sequence: int
    key: str | None
    callback: Callable[[], None]


class MonotonicScheduler:
    """One bounded monotonic worker for non-Qt application callbacks."""

    def __init__(
        self,
        *,
        name: str = "omnichord-application-scheduler",
        capacity: int = APPLICATION_TIMER_CAPACITY,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if capacity <= 0:
            raise ValueError("application scheduler capacity must be positive")
        self._capacity = int(capacity)
        self._clock = clock
        self._condition = threading.Condition()
        self._pending: list[_ScheduledCall] = []
        self._next_sequence = 0
        self._closing = False
        self._closed = False
        self._high_water = 0
        self._replaced = 0
        self._callback_failures = 0
        self._last_callback_error: BaseException | None = None
        self._thread = threading.Thread(target=self._run, name=name, daemon=True)
        self._thread.start()

    def schedule(
        self,
        delay_seconds: float,
        callback: Callable[[], None],
        *,
        replace_key: str | None = None,
    ) -> int:
        if not callable(callback):
            raise TypeError("scheduled callback must be callable")
        key = None if replace_key is None else str(replace_key)
        with self._condition:
            if self._closing or self._closed:
                raise RuntimeError("application scheduler is closed")
            if key is not None:
                retained = [item for item in self._pending if item.key != key]
                self._replaced += len(self._pending) - len(retained)
                if len(retained) != len(self._pending):
                    self._pending = retained
                    heapq.heapify(self._pending)
            if len(self._pending) >= self._capacity:
                raise BufferError("application scheduler capacity exceeded")
            self._next_sequence += 1
            sequence = self._next_sequence
            heapq.heappush(
                self._pending,
                _ScheduledCall(
                    self._clock() + max(0.0, float(delay_seconds)),
                    sequence,
                    key,
                    callback,
                ),
            )
            self._high_water = max(self._high_water, len(self._pending))
            self._condition.notify_all()
            return sequence

    def _run(self) -> None:
        while True:
            with self._condition:
                while True:
                    if self._closing:
                        self._pending.clear()
                        self._closed = True
                        self._condition.notify_all()
                        return
                    if not self._pending:
                        self._condition.wait()
                        continue
                    remaining = self._pending[0].deadline - self._clock()
                    if remaining > 0:
                        self._condition.wait(timeout=remaining)
                        continue
                    call = heapq.heappop(self._pending)
                    break
            try:
                call.callback()
            except BaseException as exc:
                with self._condition:
                    self._callback_failures += 1
                    self._last_callback_error = exc

    def close(self) -> None:
        with self._condition:
            if not self._closing:
                self._closing = True
                self._pending.clear()
                self._condition.notify_all()
        self._thread.join(timeout=1.0)

    @property
    def health(self) -> ApplicationSchedulerHealth:
        with self._condition:
            return ApplicationSchedulerHealth(
                lifecycle="closed" if self._closed else "closing" if self._closing else "running",
                pending=len(self._pending),
                high_water=self._high_water,
                replaced=self._replaced,
                callback_failures=self._callback_failures,
                last_callback_error=None
                if self._last_callback_error is None
                else repr(self._last_callback_error),
            )
