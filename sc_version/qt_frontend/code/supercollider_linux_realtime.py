from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Callable, Mapping, Sequence


RTKIT_SERVICE = "org.freedesktop.RealtimeKit1"
RTKIT_PATH = "/org/freedesktop/RealtimeKit1"
RTKIT_INTERFACE = "org.freedesktop.RealtimeKit1"
SCHED_FIFO = getattr(os, "SCHED_FIFO", 1)
SCHED_RR = getattr(os, "SCHED_RR", 2)
SCHED_RESET_ON_FORK = getattr(os, "SCHED_RESET_ON_FORK", 0)


@dataclass(frozen=True, slots=True)
class RealtimeSetupResult:
    status: str
    server_pid: int | None = None
    dsp_threads: int = 0
    promoted_threads: int = 0
    detail: str = ""

    @property
    def successful(self) -> bool:
        return self.status in {"not-applicable", "already-realtime", "promoted"}

    def summary(self) -> str:
        if self.status == "not-applicable":
            return self.detail
        prefix = (
            f"Supernova realtime DSP workers: {self.dsp_threads}/{self.dsp_threads}"
            if self.successful
            else "Supernova realtime DSP worker setup incomplete"
        )
        if self.detail:
            return f"{prefix} ({self.detail})"
        return prefix


def _process_session(path: Path) -> int | None:
    try:
        value = path.read_text(encoding="utf-8")
    except (FileNotFoundError, PermissionError, OSError):
        return None
    closing = value.rfind(")")
    if closing < 0:
        return None
    fields = value[closing + 2 :].split()
    if len(fields) < 4:
        return None
    try:
        return int(fields[3])
    except ValueError:
        return None


def _owned_server_pid(
    session_leader: int,
    expected_executable: Path,
    *,
    proc_root: Path,
) -> int | None:
    expected = expected_executable.resolve()
    matches: list[int] = []
    for process_dir in proc_root.iterdir():
        if not process_dir.name.isdecimal():
            continue
        if _process_session(process_dir / "stat") != session_leader:
            continue
        try:
            executable = (process_dir / "exe").resolve(strict=True)
        except (FileNotFoundError, PermissionError, OSError):
            continue
        if executable == expected:
            matches.append(int(process_dir.name))
    if len(matches) == 1:
        return matches[0]
    return None


def _dsp_threads(server_pid: int, *, proc_root: Path) -> dict[int, str]:
    threads: dict[int, str] = {}
    task_root = proc_root / str(server_pid) / "task"
    try:
        task_dirs = tuple(task_root.iterdir())
    except (FileNotFoundError, PermissionError, OSError):
        return threads
    for task_dir in task_dirs:
        if not task_dir.name.isdecimal():
            continue
        try:
            name = (task_dir / "comm").read_text(encoding="utf-8").strip()
        except (FileNotFoundError, PermissionError, OSError):
            continue
        if name.startswith("DSP Thread "):
            threads[int(task_dir.name)] = name
    return threads


def _scheduler(tid: int) -> tuple[int, int] | None:
    try:
        policy = os.sched_getscheduler(tid)
        priority = os.sched_getparam(tid).sched_priority
    except (AttributeError, PermissionError, ProcessLookupError, OSError):
        return None
    return policy, priority


def _is_realtime(scheduler: tuple[int, int] | None) -> bool:
    if scheduler is None:
        return False
    policy = scheduler[0] & ~SCHED_RESET_ON_FORK
    return policy in {SCHED_FIFO, SCHED_RR} and scheduler[1] > 0


def _wait_for_dsp_pool(
    session_leader: int,
    expected_executable: Path,
    *,
    proc_root: Path,
    timeout: float,
    monotonic: Callable[[], float],
    sleep: Callable[[float], None],
) -> tuple[int, dict[int, str]] | None:
    deadline = monotonic() + timeout
    previous: tuple[int, ...] = ()
    stable_samples = 0
    while monotonic() < deadline:
        server_pid = _owned_server_pid(
            session_leader,
            expected_executable,
            proc_root=proc_root,
        )
        if server_pid is not None:
            threads = _dsp_threads(server_pid, proc_root=proc_root)
            identities = tuple(sorted(threads))
            if len(identities) >= 1:
                if identities == previous:
                    stable_samples += 1
                else:
                    previous = identities
                    stable_samples = 0
                if stable_samples >= 2:
                    return server_pid, threads
        sleep(0.05)
    return None


def configure_owned_supernova_realtime(
    session_leader: int,
    expected_executable: Path,
    *,
    timeout: float = 15.0,
    proc_root: Path = Path("/proc"),
    platform: str | None = None,
    environment: Mapping[str, str] | None = None,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    which: Callable[[str], str | None] = shutil.which,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> RealtimeSetupResult:
    """Give one owned Supernova DSP pool the audio thread's RT priority.

    PipeWire's JACK bridge can promote its callback through RealtimeKit, but
    Supernova creates additional DSP workers itself. On a normal desktop with
    ``RLIMIT_RTPRIO == 0`` those helpers otherwise remain SCHED_OTHER. This
    one-shot startup adapter applies the system RealtimeKit policy to the
    complete DSP pool and exits after verifying the already-owned, exact
    Supernova process. It is not a process-name watcher and it never changes
    unrelated threads.
    """

    selected_platform = sys.platform if platform is None else platform
    if not selected_platform.startswith("linux"):
        return RealtimeSetupResult("not-applicable", detail="non-Linux host")

    ready = _wait_for_dsp_pool(
        int(session_leader),
        Path(expected_executable),
        proc_root=Path(proc_root),
        timeout=max(0.0, float(timeout)),
        monotonic=monotonic,
        sleep=sleep,
    )
    if ready is None:
        return RealtimeSetupResult(
            "server-not-found",
            detail="owned Supernova DSP pool did not appear before timeout",
        )

    server_pid, threads = ready
    pending = [tid for tid in sorted(threads) if not _is_realtime(_scheduler(tid))]
    if not pending:
        return RealtimeSetupResult(
            "already-realtime",
            server_pid=server_pid,
            dsp_threads=len(threads),
        )

    busctl = which("busctl")
    if not busctl:
        return RealtimeSetupResult(
            "rtkit-unavailable",
            server_pid=server_pid,
            dsp_threads=len(threads),
            detail="busctl is unavailable",
        )

    host_environment = dict(os.environ if environment is None else environment)
    host_environment.pop("LD_LIBRARY_PATH", None)
    host_environment.pop("LD_PRELOAD", None)
    priority_result = run(
        [
            busctl,
            "--system",
            "get-property",
            RTKIT_SERVICE,
            RTKIT_PATH,
            RTKIT_INTERFACE,
            "MaxRealtimePriority",
        ],
        env=host_environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=2.0,
    )
    priority_fields = priority_result.stdout.split()
    if priority_result.returncode != 0 or len(priority_fields) != 2:
        detail = (priority_result.stderr or priority_result.stdout).strip()
        return RealtimeSetupResult(
            "rtkit-unavailable",
            server_pid=server_pid,
            dsp_threads=len(threads),
            detail=detail or "could not query RealtimeKit priority policy",
        )
    try:
        priority = int(priority_fields[1])
    except ValueError:
        priority = 0
    if priority <= 0:
        return RealtimeSetupResult(
            "rtkit-unavailable",
            server_pid=server_pid,
            dsp_threads=len(threads),
            detail="RealtimeKit reported no usable realtime priority",
        )
    failures: list[str] = []
    for tid in pending:
        result = run(
            [
                busctl,
                "--system",
                "call",
                RTKIT_SERVICE,
                RTKIT_PATH,
                RTKIT_INTERFACE,
                "MakeThreadRealtimeWithPID",
                "ttu",
                str(server_pid),
                str(tid),
                str(priority),
            ],
            env=host_environment,
            text=True,
            capture_output=True,
            check=False,
            timeout=2.0,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            failures.append(f"{tid}: {detail or 'RealtimeKit rejected request'}")

    verification_deadline = monotonic() + 1.0
    remaining = [tid for tid in threads if not _is_realtime(_scheduler(tid))]
    while remaining and monotonic() < verification_deadline:
        sleep(0.05)
        remaining = [tid for tid in threads if not _is_realtime(_scheduler(tid))]
    promoted = sum(_is_realtime(_scheduler(tid)) for tid in pending)
    if failures or remaining:
        detail_parts: list[str] = []
        if failures:
            detail_parts.append(failures[0])
        if remaining:
            detail_parts.append(
                "non-realtime thread IDs: " + ",".join(map(str, sorted(remaining)))
            )
        return RealtimeSetupResult(
            "promotion-failed",
            server_pid=server_pid,
            dsp_threads=len(threads),
            promoted_threads=promoted,
            detail="; ".join(detail_parts),
        )

    return RealtimeSetupResult(
        "promoted",
        server_pid=server_pid,
        dsp_threads=len(threads),
        promoted_threads=promoted,
        detail=f"{promoted} helpers promoted through RealtimeKit",
    )


def main(arguments: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Configure one owned Supernova DSP pool through RealtimeKit"
    )
    parser.add_argument("session_leader", type=int)
    parser.add_argument("supernova", type=Path)
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args(arguments)
    result = configure_owned_supernova_realtime(
        args.session_leader,
        args.supernova,
        timeout=args.timeout,
    )
    stream = sys.stdout if result.successful else sys.stderr
    print(result.summary(), file=stream, flush=True)
    # Host policy must not silently substitute another audio backend or keep
    # the UI from opening. The warning is explicit; release qualification can
    # enforce stronger host guarantees separately.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
