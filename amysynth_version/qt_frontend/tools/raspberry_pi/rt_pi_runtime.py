#!/usr/bin/env python3
"""Apply the measured Raspberry Pi audio thread policy from outside the app.

The helper deliberately discovers live processes and the active AMY callback
thread.  It neither imports application code nor changes the AMY wire protocol.
Run it as root after LB Omnichord starts, or use ``watch`` to handle restarts.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ThreadInfo:
    pid: int
    tid: int
    name: str
    command: str
    run_ns: int


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        return ""


def process_command(pid: int) -> str:
    return _read(Path(f"/proc/{pid}/cmdline")).replace("\0", " ")


def process_ids(uid: int | None = None) -> list[int]:
    result: list[int] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if uid is not None and entry.stat().st_uid != uid:
                continue
        except (FileNotFoundError, PermissionError):
            continue
        result.append(int(entry.name))
    return sorted(result)


def task_ids(pid: int) -> list[int]:
    try:
        return sorted(int(path.name) for path in Path(f"/proc/{pid}/task").iterdir())
    except (FileNotFoundError, ProcessLookupError):
        return []


def thread_info(pid: int, tid: int) -> ThreadInfo | None:
    try:
        run_ns = int(
            Path(f"/proc/{pid}/task/{tid}/schedstat")
            .read_text(encoding="ascii")
            .split()[0]
        )
        name = _read(Path(f"/proc/{pid}/task/{tid}/comm"))
    except (FileNotFoundError, PermissionError, ProcessLookupError, ValueError):
        return None
    return ThreadInfo(pid, tid, name, process_command(pid), run_ns)


def snapshot_threads(pid: int) -> dict[int, ThreadInfo]:
    return {
        item.tid: item
        for tid in task_ids(pid)
        if (item := thread_info(pid, tid)) is not None
    }


def parent_pid(pid: int) -> int | None:
    status = _read(Path(f"/proc/{pid}/status"))
    match = next(
        (line for line in status.splitlines() if line.startswith("PPid:")),
        None,
    )
    if match is None:
        return None
    value = int(match.split(":", 1)[1])
    return value or None


def select_active_worker(pid: int, seconds: float = 0.35) -> ThreadInfo:
    before = snapshot_threads(pid)
    time.sleep(seconds)
    after = snapshot_threads(pid)
    candidates = [
        item
        for tid, item in after.items()
        if tid != pid and tid in before and item.run_ns > before[tid].run_ns
    ]
    if not candidates:
        raise RuntimeError(f"no active worker thread found in PID {pid}")
    return max(candidates, key=lambda item: item.run_ns - before[item.tid].run_ns)


def discover_amy_services(uid: int | None = None) -> list[int]:
    return [
        pid
        for pid in process_ids(uid)
        if "--amy-service" in process_command(pid).split()
    ]


def discover_pipewire(uid: int | None = None) -> list[int]:
    result = []
    for pid in process_ids(uid):
        command = process_command(pid)
        executable = Path(command.split(" ", 1)[0]).name if command else ""
        if executable in {"pipewire", "pipewire-pulse"}:
            result.append(pid)
    return result


def set_thread_policy(tid: int, cpus: set[int], fifo_priority: int = 0) -> None:
    os.sched_setaffinity(tid, cpus)
    policy = os.SCHED_FIFO if fifo_priority else os.SCHED_OTHER
    os.sched_setscheduler(tid, policy, os.sched_param(fifo_priority))


def apply_split_policy(service_pid: int, uid: int | None = None) -> dict[str, object]:
    """Keep general work on 0-1, PipeWire on 2 and AMY callback on 3."""

    frontend_pid = parent_pid(service_pid)
    frontend_threads = task_ids(frontend_pid) if frontend_pid is not None else []
    for tid in frontend_threads:
        set_thread_policy(tid, {0, 1})
    for tid in task_ids(service_pid):
        set_thread_policy(tid, {0, 1})
    audio = select_active_worker(service_pid)
    set_thread_policy(audio.tid, {3}, 70)

    pipewire_result = []
    priorities = {"pipewire": 80, "pipewire-pulse": 75}
    for pid in discover_pipewire(uid):
        command = process_command(pid)
        executable = Path(command.split(" ", 1)[0]).name
        for tid in task_ids(pid):
            name = _read(Path(f"/proc/{pid}/task/{tid}/comm"))
            if name == "data-loop.0":
                set_thread_policy(tid, {2}, priorities[executable])
                pipewire_result.append(
                    {"process": executable, "pid": pid, "tid": tid,
                     "cpu": 2, "fifo": priorities[executable]}
                )
    if len(pipewire_result) < 2:
        raise RuntimeError("did not find both PipeWire data-loop.0 threads")
    return {
        "amy": {**asdict(audio), "cpu": 3, "fifo": 70},
        "frontend": {
            "pid": frontend_pid,
            "threads": len(frontend_threads),
            "cpus": [0, 1],
        },
        "pipewire": pipewire_result,
        "housekeeping_cpus": [0, 1],
    }


def current_policy(tid: int) -> dict[str, object]:
    return {
        "tid": tid,
        "affinity": sorted(os.sched_getaffinity(tid)),
        "scheduler": os.sched_getscheduler(tid),
        "priority": os.sched_getparam(tid).sched_priority,
    }


def verify(service_pid: int, uid: int | None = None) -> dict[str, object]:
    audio = select_active_worker(service_pid)
    return {
        "amy_candidate": current_policy(audio.tid),
        "pipewire": [
            {"name": _read(Path(f"/proc/{pid}/task/{tid}/comm")), **current_policy(tid)}
            for pid in discover_pipewire(uid)
            for tid in task_ids(pid)
            if _read(Path(f"/proc/{pid}/task/{tid}/comm")) == "data-loop.0"
        ],
    }


def _parse_uid(value: str) -> int:
    if value.isdigit():
        return int(value)
    import pwd

    return pwd.getpwnam(value).pw_uid


def _require_root() -> None:
    if os.geteuid() != 0:
        raise PermissionError("runtime scheduling changes must run as root")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inspect", "apply", "watch"))
    parser.add_argument("--user", default=str(os.getuid()))
    parser.add_argument("--service-pid", type=int)
    parser.add_argument("--interval", type=float, default=0.5)
    args = parser.parse_args()
    uid = _parse_uid(args.user)
    if args.command != "inspect":
        _require_root()

    def services() -> list[int]:
        return [args.service_pid] if args.service_pid else discover_amy_services(uid)

    if args.command == "inspect":
        print(json.dumps({"amy_services": services(), "pipewire": discover_pipewire(uid)}, indent=2))
        return 0
    if args.command == "apply":
        found = services()
        if len(found) != 1:
            raise RuntimeError(f"expected one AMY service, found {found}")
        result = apply_split_policy(found[0], uid)
        result["verification"] = verify(found[0], uid)
        print(json.dumps(result, indent=2))
        return 0

    applied: set[int] = set()
    while True:
        live = set(services())
        applied.intersection_update(live)
        for pid in sorted(live - applied):
            try:
                result = apply_split_policy(pid, uid)
            except (OSError, RuntimeError, ProcessLookupError) as exc:
                print(f"PID {pid}: {exc}", flush=True)
            else:
                applied.add(pid)
                print(json.dumps(result), flush=True)
        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, PermissionError, ValueError) as exc:
        print(f"rt_pi_runtime: {exc}", file=os.sys.stderr)
        raise SystemExit(2)
