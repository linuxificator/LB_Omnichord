from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Protocol


# Startup authors more than 700 persistent fill groups. Keep the queue finite while
# admitting that characterized burst even when a 1-Mbaud target drains slowly.
HIGH_QUEUE_CAPACITY = 65536
LOW_QUEUE_CAPACITY = 4096
SHUTDOWN_TIMEOUT_SECONDS = 5.0


class ByteSink(Protocol):
    delimiter: bytes

    def open(self) -> None: ...

    def write(self, payload: bytes) -> None: ...

    def close(self) -> None: ...


class TransportRecorder(Protocol):
    def write(self, kind: str, text: str) -> None: ...


class TransportFailed(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TransportHealth:
    lifecycle: str
    high_depth: int
    low_depth: int
    high_water: int
    low_water: int
    dropped_replaceable: int
    coalesced_stale: int
    terminal_error: str | None
    shutdown_timed_out: bool


@dataclass(frozen=True, slots=True)
class _HighItem:
    command: str | None
    delay_seconds: float


@dataclass(frozen=True, slots=True)
class _LowItem:
    lane: str
    generation: int
    command: str


def encode_command(command: str, delimiter: bytes) -> bytes:
    text = str(command).strip()
    if not text.endswith("Z"):
        text += "Z"
    return text.encode("ascii") + delimiter


class CommandScheduler:
    """Bounded priority scheduler composed with one worker-owned byte sink."""

    def __init__(
        self,
        sink: ByteSink,
        *,
        name: str,
        recorder: TransportRecorder | None = None,
        high_capacity: int = HIGH_QUEUE_CAPACITY,
        low_capacity: int = LOW_QUEUE_CAPACITY,
        shutdown_timeout: float = SHUTDOWN_TIMEOUT_SECONDS,
        open_timeout: float = 5.5,
    ) -> None:
        if high_capacity <= 0 or low_capacity <= 0:
            raise ValueError("transport queue capacities must be positive")
        self._sink = sink
        self._recorder = recorder
        self._high_capacity = int(high_capacity)
        self._low_capacity = int(low_capacity)
        self._shutdown_timeout = max(0.01, float(shutdown_timeout))
        self._high: deque[_HighItem] = deque()
        self._low: deque[_LowItem] = deque()
        self._lane_generation: dict[str, int] = {}
        self._condition = threading.Condition()
        self._ready = threading.Event()
        self._closing = False
        self._closed = False
        self._sink_open = False
        self._terminal_error: BaseException | None = None
        self._high_water = 0
        self._low_water = 0
        self._dropped_replaceable = 0
        self._coalesced_stale = 0
        self._shutdown_timed_out = False
        self._thread = threading.Thread(
            target=self._run,
            name=str(name),
            daemon=True,
        )
        self._thread.start()
        if not self._ready.wait(max(0.01, float(open_timeout))):
            self.close()
            raise TimeoutError("timed out opening AMY transport sink")
        self._raise_if_failed()

    def _raise_if_failed(self) -> None:
        if self._terminal_error is not None:
            raise TransportFailed(str(self._terminal_error)) from self._terminal_error

    def _accepting(self) -> bool:
        self._raise_if_failed()
        return not self._closing and not self._closed

    def new_low_generation(self, lane: str) -> int:
        lane_name = str(lane)
        with self._condition:
            if not self._accepting():
                return self._lane_generation.get(lane_name, 0)
            generation = self._lane_generation.get(lane_name, 0) + 1
            self._lane_generation[lane_name] = generation
            self._discard_stale_locked()
            self._condition.notify_all()
            return generation

    def invalidate_all_low(self) -> None:
        with self._condition:
            if not self._accepting():
                return
            for lane in tuple(self._lane_generation):
                self._lane_generation[lane] += 1
            self._coalesced_stale += len(self._low)
            self._low.clear()
            self._condition.notify_all()

    def high(self, command: str) -> None:
        self._enqueue_high(_HighItem(str(command), 0.0))

    def high_many(self, commands: list[str] | tuple[str, ...]) -> None:
        """Admit one ordered critical batch under a single queue lock."""

        items = tuple(_HighItem(str(command), 0.0) for command in commands)
        with self._condition:
            if not self._accepting():
                return
            if len(self._high) + len(items) > self._high_capacity:
                raise BufferError(
                    "critical AMY transport queue is full; batch was rejected"
                )
            self._high.extend(items)
            self._high_water = max(self._high_water, len(self._high))
            self._condition.notify()

    def delay(self, delay_seconds: float) -> None:
        self._enqueue_high(_HighItem(None, max(0.0, float(delay_seconds))))

    def _enqueue_high(self, item: _HighItem) -> None:
        with self._condition:
            if not self._accepting():
                return
            if len(self._high) >= self._high_capacity:
                raise BufferError("critical AMY transport queue is full; command was rejected")
            self._high.append(item)
            self._high_water = max(self._high_water, len(self._high))
            self._condition.notify()

    def low(self, lane: str, generation: int, command: str) -> None:
        item = _LowItem(str(lane), int(generation), str(command))
        with self._condition:
            if not self._accepting():
                return
            if item.generation != self._lane_generation.get(item.lane, 0):
                self._coalesced_stale += 1
                return
            self._discard_stale_locked()
            if len(self._low) >= self._low_capacity:
                self._low.popleft()
                self._dropped_replaceable += 1
            self._low.append(item)
            self._low_water = max(self._low_water, len(self._low))
            self._condition.notify()

    def _discard_stale_locked(self) -> None:
        if not self._low:
            return
        retained = deque(
            item for item in self._low if item.generation == self._lane_generation.get(item.lane, 0)
        )
        self._coalesced_stale += len(self._low) - len(retained)
        self._low = retained

    def _next_item(self) -> tuple[str, _HighItem | _LowItem] | None:
        with self._condition:
            while True:
                if self._high:
                    return "HIGH", self._high.popleft()
                self._discard_stale_locked()
                if self._low and not self._closing:
                    return "LOW", self._low.popleft()
                if self._closing:
                    return None
                self._condition.wait()

    def _run(self) -> None:
        try:
            self._sink.open()
            self._sink_open = True
            self._ready.set()
            while True:
                selected = self._next_item()
                if selected is None:
                    break
                lane, item = selected
                if isinstance(item, _HighItem):
                    if item.command is None:
                        if self._recorder is not None:
                            self._recorder.write(
                                "GUARD",
                                f"sleep {item.delay_seconds * 1000.0:.1f} ms",
                            )
                        time.sleep(item.delay_seconds)
                        continue
                    command = item.command
                else:
                    command = item.command
                if self._recorder is not None:
                    self._recorder.write(f"TX-{lane}", command.strip())
                self._sink.write(encode_command(command, self._sink.delimiter))
        except BaseException as exc:
            with self._condition:
                self._terminal_error = exc
                self._high.clear()
                self._low.clear()
                self._closing = True
                self._condition.notify_all()
        finally:
            self._ready.set()
            if self._sink_open:
                try:
                    self._sink.close()
                except BaseException as exc:
                    if self._terminal_error is None:
                        self._terminal_error = exc
            with self._condition:
                self._closed = True
                self._condition.notify_all()

    def close(self) -> None:
        with self._condition:
            if not self._closing:
                self._closing = True
                for lane in tuple(self._lane_generation):
                    self._lane_generation[lane] += 1
                self._coalesced_stale += len(self._low)
                self._low.clear()
                self._condition.notify_all()
        self._thread.join(timeout=self._shutdown_timeout)
        if self._thread.is_alive():
            with self._condition:
                self._shutdown_timed_out = True

    @property
    def health(self) -> TransportHealth:
        with self._condition:
            lifecycle = (
                "failed"
                if self._terminal_error is not None
                else "closed"
                if self._closed
                else "closing"
                if self._closing
                else "running"
            )
            return TransportHealth(
                lifecycle=lifecycle,
                high_depth=len(self._high),
                low_depth=len(self._low),
                high_water=self._high_water,
                low_water=self._low_water,
                dropped_replaceable=self._dropped_replaceable,
                coalesced_stale=self._coalesced_stale,
                terminal_error=None if self._terminal_error is None else repr(self._terminal_error),
                shutdown_timed_out=self._shutdown_timed_out,
            )

    @property
    def worker_alive(self) -> bool:
        return self._thread.is_alive()
