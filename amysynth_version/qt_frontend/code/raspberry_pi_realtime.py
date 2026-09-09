"""Raspberry Pi host-profile inspection outside the portable application core."""

from __future__ import annotations

import os
import pwd
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


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
        missing.append("AMY/PipeWire realtime policy service")
    return RealtimeStatus(True, not missing, tuple(missing))


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip("\0\n")
    except (FileNotFoundError, PermissionError, OSError):
        return ""


def _runtime_watcher_in_processes(
    proc_root: Path,
    identities: frozenset[str],
) -> bool:
    try:
        entries: Iterable[Path] = proc_root.iterdir()
    except OSError:
        return False
    for entry in entries:
        if not entry.name.isdigit():
            continue
        raw = _read_text(entry / "cmdline")
        tokens = tuple(token for token in raw.split("\0") if token)
        if not tokens or "watch" not in tokens:
            continue
        if not any(Path(token).name == "rt_pi_runtime.py" for token in tokens):
            continue
        try:
            user_index = tokens.index("--user") + 1
        except (ValueError, IndexError):
            continue
        if user_index < len(tokens) and tokens[user_index] in identities:
            return True
    return False


def _systemd_policy_active(user: str) -> bool:
    try:
        result = subprocess.run(
            [
                "systemctl",
                "is-active",
                "--quiet",
                f"lb-omnichord-rt-policy@{user}.service",
            ],
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=1.0,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def inspect_realtime_facts(
    *,
    root: Path = Path("/"),
    uid: int | None = None,
    service_active: Callable[[str], bool] = _systemd_policy_active,
) -> RealtimeFacts:
    model = _read_text(root / "proc" / "device-tree" / "model")
    if not is_supported_pi(model):
        return RealtimeFacts(model, "", "", (), False)

    effective_uid = os.getuid() if uid is None else int(uid)
    try:
        user = pwd.getpwuid(effective_uid).pw_name
    except KeyError:
        user = str(effective_uid)
    identities = frozenset((user, str(effective_uid)))
    sys_root = root / "sys" / "devices" / "system" / "cpu"
    governors = tuple(
        _read_text(path / "scaling_governor")
        for path in sorted((sys_root / "cpufreq").glob("policy*"))
    )
    policy_active = service_active(user) or _runtime_watcher_in_processes(
        root / "proc",
        identities,
    )
    return RealtimeFacts(
        model=model,
        kernel_cmdline=_read_text(root / "proc" / "cmdline"),
        isolated_cpus=_read_text(sys_root / "isolated"),
        governors=governors,
        runtime_policy_active=policy_active,
    )


def startup_warning_messages() -> tuple[str, ...]:
    status = evaluate_realtime(inspect_realtime_facts())
    if not status.applicable or status.complete:
        return ()
    missing = ", ".join(status.missing)
    return (
        "The tested Raspberry Pi realtime audio profile is not fully active "
        f"({missing}). Audio can crackle under load. Download {REALTIME_ASSET_PATTERN} "
        "and its .sha256 file from the same GitHub release, verify it, then run "
        "the setup script with sudo and reboot when requested.",
    )
