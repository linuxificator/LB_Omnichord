"""Raspberry Pi realtime policy used by the existing Linux launch wrappers.

The installer grants the desktop user a standard ``RLIMIT_RTPRIO`` allowance.
The wrapper which starts AMY already owns its exact child PID, so it can apply
and verify the measured thread policy once without a daemon or process-name
lookup for AMY.
"""

from __future__ import annotations

import argparse
import os
import shlex
import time
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable


EXPECTED_BOOT_ARGUMENTS = frozenset(
    {
        "isolcpus=domain,managed_irq,2-3",
        "irqaffinity=0-1",
        "threadirqs",
    }
)
EXPECTED_ISOLATED_CPUS = frozenset({2, 3})
HOUSEKEEPING_CPUS = frozenset({0, 1})
PIPEWIRE_CPUS = frozenset({2})
AMY_AUDIO_CPUS = frozenset({3})
REQUIRED_RTPRIO = 80
AMY_AUDIO_PRIORITY = 70
PIPEWIRE_PRIORITIES = {"pipewire": 80, "pipewire-pulse": 75}
REALTIME_ASSET_PATTERN = (
    "LB_Omnichord.RYYYYMMDDHHMMSS.Pi4-Pi5-realtime-setup.sh"
)
SERVICE_PID_ENV = "OMNICHORD_AMY_SERVICE_PID"


@dataclass(frozen=True, slots=True)
class RealtimeFacts:
    model: str
    kernel_cmdline: str
    isolated_cpus: str
    governors: tuple[str, ...]
    rtprio_limit: int
    runtime_policy_active: bool = False
    runtime_policy_issue: str = ""


@dataclass(frozen=True, slots=True)
class RealtimeStatus:
    applicable: bool
    complete: bool
    missing: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PolicyApplication:
    applicable: bool
    applied: bool
    issue: str = ""
    amy_audio_tid: int | None = None


@dataclass(frozen=True, slots=True)
class RealtimeStartup:
    warnings: tuple[str, ...]


def is_supported_pi(model: str) -> bool:
    normalized = str(model).strip().casefold()
    return normalized.startswith("raspberry pi 4") or normalized.startswith(
        "raspberry pi 5"
    )


def parse_cpu_list(value: str) -> frozenset[int]:
    result: set[int] = set()
    for item in str(value).strip().split(","):
        if not item:
            continue
        if "-" in item:
            start_text, end_text = item.split("-", 1)
            start, end = int(start_text), int(end_text)
            if end < start:
                raise ValueError(f"descending CPU range: {item}")
            result.update(range(start, end + 1))
        else:
            result.add(int(item))
    return frozenset(result)


def evaluate_realtime(facts: RealtimeFacts) -> RealtimeStatus:
    if not is_supported_pi(facts.model):
        return RealtimeStatus(False, True, ())

    missing: list[str] = []
    if not EXPECTED_BOOT_ARGUMENTS <= set(shlex.split(facts.kernel_cmdline)):
        missing.append("isolated CPU and threaded-IRQ boot profile")
    try:
        isolated = parse_cpu_list(facts.isolated_cpus)
    except ValueError:
        isolated = frozenset()
    if not EXPECTED_ISOLATED_CPUS <= isolated:
        missing.append("CPU 2-3 isolation")
    if not facts.governors or any(
        governor != "performance" for governor in facts.governors
    ):
        missing.append("performance CPU governor")
    if facts.rtprio_limit < REQUIRED_RTPRIO:
        missing.append(f"user realtime-priority limit of at least {REQUIRED_RTPRIO}")
    if not facts.runtime_policy_active:
        policy = "verified AMY/frontend/PipeWire realtime policy"
        if facts.runtime_policy_issue:
            policy += f": {facts.runtime_policy_issue}"
        missing.append(policy)
    return RealtimeStatus(True, not missing, tuple(missing))


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip("\0\n")
    except (FileNotFoundError, PermissionError, OSError):
        return ""


def _rtprio_limit() -> int:
    try:
        import resource

        soft, _hard = resource.getrlimit(resource.RLIMIT_RTPRIO)
    except (ImportError, OSError, ValueError):
        return 0
    if soft == resource.RLIM_INFINITY:
        return REQUIRED_RTPRIO
    return max(0, int(soft))


def inspect_realtime_facts(
    *,
    root: Path = Path("/"),
    runtime_policy_active: bool = False,
    runtime_policy_issue: str = "",
) -> RealtimeFacts:
    model = _read_text(root / "proc" / "device-tree" / "model")
    if not is_supported_pi(model):
        return RealtimeFacts(model, "", "", (), 0)

    sys_root = root / "sys" / "devices" / "system" / "cpu"
    governors = tuple(
        _read_text(path / "scaling_governor")
        for path in sorted((sys_root / "cpufreq").glob("policy*"))
    )
    return RealtimeFacts(
        model=model,
        kernel_cmdline=_read_text(root / "proc" / "cmdline"),
        isolated_cpus=_read_text(sys_root / "isolated"),
        governors=governors,
        rtprio_limit=_rtprio_limit(),
        runtime_policy_active=runtime_policy_active,
        runtime_policy_issue=runtime_policy_issue,
    )


def task_ids(pid: int) -> tuple[int, ...]:
    try:
        return tuple(
            sorted(int(path.name) for path in Path(f"/proc/{pid}/task").iterdir())
        )
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        return ()


def _thread_run_ns(pid: int, tid: int) -> int | None:
    try:
        return int(
            Path(f"/proc/{pid}/task/{tid}/schedstat")
            .read_text(encoding="ascii")
            .split()[0]
        )
    except (FileNotFoundError, PermissionError, ProcessLookupError, ValueError):
        return None


def select_active_worker(pid: int, seconds: float = 0.35) -> int:
    before = {
        tid: value
        for tid in task_ids(pid)
        if tid != pid and (value := _thread_run_ns(pid, tid)) is not None
    }
    time.sleep(seconds)
    deltas = {
        tid: after - before[tid]
        for tid in task_ids(pid)
        if tid in before
        and (after := _thread_run_ns(pid, tid)) is not None
        and after > before[tid]
    }
    if not deltas:
        raise RuntimeError(f"no active worker thread found in AMY PID {pid}")
    return max(deltas, key=deltas.__getitem__)


def _process_ids(uid: int) -> tuple[int, ...]:
    result: list[int] = []
    try:
        entries = Path("/proc").iterdir()
    except OSError:
        return ()
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            if entry.stat().st_uid == uid:
                result.append(int(entry.name))
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
    return tuple(sorted(result))


def _process_executable(pid: int) -> str:
    try:
        return Path(os.readlink(f"/proc/{pid}/exe")).name
    except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
        return ""


def _thread_name(pid: int, tid: int) -> str:
    return _read_text(Path(f"/proc/{pid}/task/{tid}/comm"))


def discover_pipewire_loops(uid: int) -> dict[str, int]:
    loops: dict[str, int] = {}
    for pid in _process_ids(uid):
        executable = _process_executable(pid)
        process_name = _thread_name(pid, pid)
        # pipewire-pulse is normally an alternate invocation of the pipewire
        # binary, so /proc/PID/exe resolves to "pipewire" for both services.
        # Require that native binary and use the kernel's exact main-thread
        # name to distinguish the two standard services.
        if (
            executable not in PIPEWIRE_PRIORITIES
            or process_name not in PIPEWIRE_PRIORITIES
        ):
            continue
        matching = [
            tid for tid in task_ids(pid) if _thread_name(pid, tid) == "data-loop.0"
        ]
        if len(matching) == 1:
            loops[process_name] = matching[0]
    return loops


def _owned_process(pid: int, uid: int) -> bool:
    try:
        return Path(f"/proc/{pid}").stat().st_uid == uid
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        return False


def set_thread_policy(
    tid: int,
    cpus: frozenset[int],
    fifo_priority: int = 0,
) -> None:
    os.sched_setaffinity(tid, cpus)
    scheduler = os.SCHED_FIFO if fifo_priority else os.SCHED_OTHER
    os.sched_setscheduler(tid, scheduler, os.sched_param(fifo_priority))


def _policy_matches(
    tid: int,
    cpus: frozenset[int],
    scheduler: int,
    priority: int,
) -> bool:
    try:
        return (
            os.sched_getaffinity(tid) == cpus
            and os.sched_getscheduler(tid) == scheduler
            and os.sched_getparam(tid).sched_priority == priority
        )
    except (OSError, ProcessLookupError):
        return False


def verify_runtime_policy(
    service_pid: int,
    *,
    frontend_pid: int | None = None,
    uid: int | None = None,
) -> tuple[bool, str]:
    owner = os.getuid() if uid is None else uid
    if not _owned_process(service_pid, owner):
        return False, "the exact AMY child process is absent or has another owner"

    amy_threads = task_ids(service_pid)
    callbacks = [
        tid
        for tid in amy_threads
        if _policy_matches(tid, AMY_AUDIO_CPUS, os.SCHED_FIFO, AMY_AUDIO_PRIORITY)
    ]
    if len(callbacks) != 1:
        return False, "AMY does not have exactly one verified realtime audio thread"
    if any(
        not _policy_matches(tid, HOUSEKEEPING_CPUS, os.SCHED_OTHER, 0)
        for tid in amy_threads
        if tid not in callbacks
    ):
        return False, "one or more non-audio AMY threads have the wrong policy"

    if frontend_pid is not None:
        frontend_threads = task_ids(frontend_pid)
        if not frontend_threads or any(
            not _policy_matches(tid, HOUSEKEEPING_CPUS, os.SCHED_OTHER, 0)
            for tid in frontend_threads
        ):
            return False, "the frontend is not confined to housekeeping CPUs"

    loops = discover_pipewire_loops(owner)
    if set(loops) != set(PIPEWIRE_PRIORITIES):
        return False, "both PipeWire data-loop.0 threads were not found"
    for executable, priority in PIPEWIRE_PRIORITIES.items():
        if not _policy_matches(
            loops[executable], PIPEWIRE_CPUS, os.SCHED_FIFO, priority
        ):
            return False, f"{executable} data-loop.0 has the wrong policy"
    return True, ""


def apply_runtime_policy(
    service_pid: int,
    *,
    pin_caller: bool = False,
    inspector: Callable[..., RealtimeFacts] = inspect_realtime_facts,
) -> PolicyApplication:
    facts = inspector()
    if not is_supported_pi(facts.model):
        return PolicyApplication(False, False)
    static_status = evaluate_realtime(replace(facts, runtime_policy_active=True))
    if not static_status.complete:
        return PolicyApplication(True, False, ", ".join(static_status.missing))

    uid = os.getuid()
    if service_pid <= 0 or not _owned_process(service_pid, uid):
        return PolicyApplication(
            True,
            False,
            "the exact AMY child PID is absent or is not owned by this user",
        )
    try:
        loops = discover_pipewire_loops(uid)
        if set(loops) != set(PIPEWIRE_PRIORITIES):
            raise RuntimeError("both PipeWire data-loop.0 threads were not found")
        audio_tid = select_active_worker(service_pid)

        if pin_caller:
            for tid in task_ids(os.getpid()):
                set_thread_policy(tid, HOUSEKEEPING_CPUS)
        for tid in task_ids(service_pid):
            set_thread_policy(tid, HOUSEKEEPING_CPUS)
        set_thread_policy(audio_tid, AMY_AUDIO_CPUS, AMY_AUDIO_PRIORITY)

        for executable, priority in PIPEWIRE_PRIORITIES.items():
            set_thread_policy(loops[executable], PIPEWIRE_CPUS, priority)

        verified, issue = verify_runtime_policy(
            service_pid,
            frontend_pid=os.getpid() if pin_caller else None,
            uid=uid,
        )
        if not verified:
            raise RuntimeError(issue)
    except (OSError, RuntimeError, ValueError) as exc:
        return PolicyApplication(True, False, str(exc))
    return PolicyApplication(True, True, amy_audio_tid=audio_tid)


def service_pid_from_environment(
    environment: Mapping[str, str] | None = None,
) -> int | None:
    source = os.environ if environment is None else environment
    value = source.get(SERVICE_PID_ENV, "").strip()
    try:
        pid = int(value)
    except ValueError:
        return None
    return pid if pid > 0 else None


def prepare_realtime_startup(
    _amy_endpoint: str | Path,
    *,
    service_pid: int | None = None,
    inspector: Callable[..., RealtimeFacts] = inspect_realtime_facts,
) -> RealtimeStartup:
    facts = inspector()
    if not is_supported_pi(facts.model):
        return RealtimeStartup(())
    pid = service_pid if service_pid is not None else service_pid_from_environment()
    if pid is None:
        verified, issue = False, "the launch wrapper did not supply its AMY child PID"
    else:
        verified, issue = verify_runtime_policy(pid, frontend_pid=os.getpid())
    status = evaluate_realtime(
        replace(
            facts,
            runtime_policy_active=verified,
            runtime_policy_issue=issue,
        )
    )
    if status.complete:
        return RealtimeStartup(())
    missing = ", ".join(status.missing)
    return RealtimeStartup(
        (
            "The tested Raspberry Pi realtime audio profile is not fully active "
            f"({missing}). Audio can crackle under load. From a source checkout "
            "run tools/raspberry_pi/install_realtime_profile.sh with sudo, or "
            f"download {REALTIME_ASSET_PATTERN} from the same GitHub release, "
            "run it with sudo, and reboot when requested.",
        )
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--service-pid", type=int, required=True)
    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("--service-pid", type=int)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command == "apply":
        result = apply_runtime_policy(args.service_pid)
        if not result.applicable:
            return 3
        if not result.applied:
            print(f"Raspberry Pi realtime policy not applied: {result.issue}")
            return 2
        print(
            "Raspberry Pi realtime policy applied to exact AMY child "
            f"{args.service_pid}, audio thread {result.amy_audio_tid}."
        )
        return 0
    facts = inspect_realtime_facts()
    pid = args.service_pid
    verified, issue = (
        verify_runtime_policy(pid, frontend_pid=os.getpid())
        if pid is not None and is_supported_pi(facts.model)
        else (False, "")
    )
    status = evaluate_realtime(
        replace(facts, runtime_policy_active=verified, runtime_policy_issue=issue)
    )
    print("complete" if status.complete else "; ".join(status.missing))
    return 0 if status.complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
