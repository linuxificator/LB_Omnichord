"""Raspberry Pi host-profile inspection outside the portable application core."""

from __future__ import annotations

import shlex
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

from rt_policy_registration import PolicyRegistration, register_policy_role


EXPECTED_BOOT_ARGUMENTS = frozenset(
    {
        "isolcpus=domain,managed_irq,2-3",
        "irqaffinity=0-1",
        "threadirqs",
    }
)
EXPECTED_ISOLATED_CPUS = frozenset({2, 3})
REALTIME_ASSET_PATTERN = (
    "LB_Omnichord.RYYYYMMDDHHMMSS.Pi4-Pi5-realtime-setup.sh"
)


@dataclass(frozen=True, slots=True)
class RealtimeFacts:
    model: str
    kernel_cmdline: str
    isolated_cpus: str
    governors: tuple[str, ...]
    runtime_policy_active: bool
    runtime_policy_issue: str = ""


@dataclass(frozen=True, slots=True)
class RealtimeStatus:
    applicable: bool
    complete: bool
    missing: tuple[str, ...]


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
    active_arguments = set(shlex.split(facts.kernel_cmdline))
    if not EXPECTED_BOOT_ARGUMENTS <= active_arguments:
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


def inspect_realtime_facts(
    *,
    root: Path = Path("/"),
    runtime_policy_active: bool = False,
    runtime_policy_issue: str = "",
) -> RealtimeFacts:
    model = _read_text(root / "proc" / "device-tree" / "model")
    if not is_supported_pi(model):
        return RealtimeFacts(model, "", "", (), False)

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
        runtime_policy_active=runtime_policy_active,
        runtime_policy_issue=runtime_policy_issue,
    )


@dataclass(slots=True)
class RealtimeStartup:
    warnings: tuple[str, ...]
    registration: PolicyRegistration | None = None

    def close(self) -> None:
        if self.registration is not None:
            self.registration.close()


def prepare_realtime_startup(
    amy_endpoint: str | Path,
    *,
    inspector: Callable[..., RealtimeFacts] = inspect_realtime_facts,
    register: Callable[..., PolicyRegistration] = register_policy_role,
) -> RealtimeStartup:
    static_facts = inspector()
    if not is_supported_pi(static_facts.model):
        return RealtimeStartup(())

    registration = register("frontend", amy_endpoint)
    facts = replace(
        static_facts,
        runtime_policy_active=registration.applied,
        runtime_policy_issue=registration.issue,
    )
    status = evaluate_realtime(facts)
    if not status.applicable or status.complete:
        return RealtimeStartup((), registration)
    missing = ", ".join(status.missing)
    return RealtimeStartup(
        (
            "The tested Raspberry Pi realtime audio profile is not fully active "
            f"({missing}). Audio can crackle under load. Download "
            f"{REALTIME_ASSET_PATTERN} from the same GitHub release, run it with "
            "sudo, and reboot when requested.",
        ),
        registration,
    )
