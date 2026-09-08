from __future__ import annotations

import os
import sys
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TextIO


LOCAL_AMY_FRONTEND_ENV = "LB_OMNICHORD_LOCAL_AMY_SERVICE"
RPI_MODEL_PATH = Path("/proc/device-tree/model")

AffinityRole = Literal["frontend", "service"]


@dataclass(frozen=True, slots=True)
class LocalAmyAffinityPlan:
    frontend_cpus: frozenset[int]
    service_cpus: frozenset[int]


def local_amy_affinity_plan(
    model: str,
    available_cpus: Iterable[int],
) -> LocalAmyAffinityPlan | None:
    """Partition a four-core-or-larger Raspberry Pi for local AMY audio."""

    cpus = tuple(sorted({int(cpu) for cpu in available_cpus}))
    if "raspberry pi" not in str(model).casefold() or len(cpus) < 4:
        return None
    return LocalAmyAffinityPlan(
        frontend_cpus=frozenset(cpus[:-1]),
        service_cpus=frozenset((cpus[-1],)),
    )


def read_device_model(path: Path = RPI_MODEL_PATH) -> str:
    try:
        return path.read_bytes().rstrip(b"\0").decode("utf-8", "replace")
    except OSError:
        return ""


def current_thread_ids(path: Path = Path("/proc/self/task")) -> tuple[int, ...]:
    try:
        return tuple(
            sorted(
                int(entry.name)
                for entry in path.iterdir()
                if entry.name.isdecimal()
            )
        )
    except OSError:
        return ()


def apply_local_amy_affinity(
    role: AffinityRole,
    *,
    model: str | None = None,
    get_affinity: Callable[[int], set[int]] | None = None,
    set_affinity: Callable[[int, set[int]], None] | None = None,
    thread_ids: Callable[[], Iterable[int]] | None = None,
    diagnostics: TextIO | None = None,
) -> LocalAmyAffinityPlan | None:
    """Apply the Pi local-service CPU partition, or safely keep OS defaults."""

    get_affinity = get_affinity or getattr(os, "sched_getaffinity", None)
    set_affinity = set_affinity or getattr(os, "sched_setaffinity", None)
    if get_affinity is None or set_affinity is None:
        return None

    output = diagnostics or sys.stderr
    thread_ids = thread_ids or current_thread_ids
    try:
        plan = local_amy_affinity_plan(
            read_device_model() if model is None else model,
            get_affinity(0),
        )
        if plan is None:
            return None
        selected = plan.service_cpus if role == "service" else plan.frontend_cpus
        set_affinity(0, set(selected))
        for thread_id in thread_ids():
            try:
                set_affinity(int(thread_id), set(selected))
            except ProcessLookupError:
                # A short-lived worker may disappear between /proc iteration
                # and sched_setaffinity; it cannot retain stale affinity.
                continue
    except OSError as exc:
        print(
            f"CPU affinity: keeping OS defaults ({exc})",
            file=output,
            flush=True,
        )
        return None

    cpu_list = ",".join(str(cpu) for cpu in sorted(selected))
    print(
        f"CPU affinity: local AMY {role} -> CPU(s) {cpu_list}",
        file=output,
        flush=True,
    )
    return plan


def frontend_uses_local_amy_service(
    environment: Mapping[str, str] | None = None,
) -> bool:
    values = os.environ if environment is None else environment
    return values.get(LOCAL_AMY_FRONTEND_ENV) == "1"
