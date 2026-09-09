#!/usr/bin/env python3
"""Inspect and safely prepare Raspberry Pi realtime scheduling profiles.

This is host-integration tooling.  It deliberately does not import or alter the
LB Omnichord application or AMY; the audio processes keep their normal process
boundary and wire protocol.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shlex
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


BOOT_CMDLINE = Path("/boot/firmware/cmdline.txt")
STATE_ROOT = Path("/var/lib/lb-omnichord-rt")
MANAGED_ARGUMENTS = ("isolcpus", "irqaffinity")
MANAGED_FLAGS = ("threadirqs",)


@dataclass(frozen=True, slots=True)
class CpuProfile:
    name: str
    housekeeping: str
    amy_audio: str | None
    audio_support: str | None
    boot_arguments: tuple[str, ...]


PROFILES = {
    "stock": CpuProfile("stock", "0-3", None, None, ()),
    "audio-one": CpuProfile(
        "audio-one",
        "0-2",
        "3",
        "3",
        ("isolcpus=domain,managed_irq,3", "irqaffinity=0-2", "threadirqs"),
    ),
    "audio-split": CpuProfile(
        "audio-split",
        "0-1",
        "3",
        "2",
        ("isolcpus=domain,managed_irq,2-3", "irqaffinity=0-1", "threadirqs"),
    ),
}


def _argument_name(argument: str) -> str:
    return argument.split("=", 1)[0]


def update_kernel_cmdline(text: str, profile: CpuProfile) -> str:
    """Return one canonical cmdline, replacing only arguments we own."""

    tokens = shlex.split(text.strip())
    retained = [
        token
        for token in tokens
        if _argument_name(token) not in MANAGED_ARGUMENTS
        and token not in MANAGED_FLAGS
    ]
    return " ".join((*retained, *profile.boot_arguments)) + "\n"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, PermissionError, OSError):
        return None


def _kernel_config() -> dict[str, str]:
    path = Path(f"/boot/firmware/config-{platform.release()}")
    if not path.exists():
        path = Path(f"/boot/config-{platform.release()}")
    result: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return result
    wanted = {
        "CONFIG_CPU_ISOLATION",
        "CONFIG_IRQ_FORCED_THREADING",
        "CONFIG_NO_HZ_FULL",
        "CONFIG_PREEMPT",
        "CONFIG_PREEMPT_RT",
        "CONFIG_RCU_NOCB_CPU",
    }
    for line in lines:
        if "=" in line and line.split("=", 1)[0] in wanted:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def inspect() -> dict[str, object]:
    governors: dict[str, str | None] = {}
    for policy in sorted(Path("/sys/devices/system/cpu/cpufreq").glob("policy*")):
        governors[policy.name] = _read(policy / "scaling_governor")
    return {
        "model": _read(Path("/proc/device-tree/model")),
        "kernel": platform.release(),
        "kernel_cmdline": _read(Path("/proc/cmdline")),
        "boot_cmdline": _read(BOOT_CMDLINE),
        "isolated_cpus": _read(Path("/sys/devices/system/cpu/isolated")),
        "nohz_full_cpus": _read(Path("/sys/devices/system/cpu/nohz_full")),
        "governors": governors,
        "kernel_config": _kernel_config(),
    }


def _require_root() -> None:
    if os.geteuid() != 0:
        raise PermissionError("this operation must run as root")


def _atomic_write(path: Path, value: bytes, mode: int) -> None:
    temporary = path.with_name(f".{path.name}.lb-omnichord.tmp")
    temporary.write_bytes(value)
    os.chmod(temporary, mode)
    temporary.replace(path)


def snapshot_boot_cmdline(profile: str) -> Path:
    _require_root()
    original = BOOT_CMDLINE.read_bytes()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    snapshot = STATE_ROOT / "snapshots" / stamp
    snapshot.mkdir(parents=True, exist_ok=False)
    (snapshot / "cmdline.txt").write_bytes(original)
    manifest = {
        "created_utc": datetime.now(UTC).isoformat(),
        "profile_requested": profile,
        "source": str(BOOT_CMDLINE),
        "sha256": sha256_bytes(original),
    }
    (snapshot / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    latest = STATE_ROOT / "latest-snapshot"
    latest.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(latest, (str(snapshot) + "\n").encode(), 0o600)
    return snapshot


def apply_profile(name: str) -> tuple[Path, str]:
    _require_root()
    profile = PROFILES[name]
    original = BOOT_CMDLINE.read_text(encoding="utf-8")
    updated = update_kernel_cmdline(original, profile)
    snapshot = snapshot_boot_cmdline(name)
    if updated != original:
        _atomic_write(BOOT_CMDLINE, updated.encode(), 0o755)
    return snapshot, updated


def rollback(snapshot: Path | None) -> Path:
    _require_root()
    if snapshot is None:
        latest = (STATE_ROOT / "latest-snapshot").read_text(encoding="utf-8")
        snapshot = Path(latest.strip())
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    original = (snapshot / "cmdline.txt").read_bytes()
    if sha256_bytes(original) != manifest["sha256"]:
        raise RuntimeError(f"snapshot checksum mismatch: {snapshot}")
    _atomic_write(BOOT_CMDLINE, original, 0o755)
    return snapshot


def set_governor(name: str) -> dict[str, str]:
    _require_root()
    changed: dict[str, str] = {}
    for policy in sorted(Path("/sys/devices/system/cpu/cpufreq").glob("policy*")):
        available = (policy / "scaling_available_governors").read_text().split()
        if name not in available:
            raise ValueError(f"{name!r} is unavailable for {policy.name}: {available}")
        target = policy / "scaling_governor"
        target.write_text(name, encoding="ascii")
        changed[policy.name] = name
    return changed


def verify_profile(name: str) -> tuple[bool, dict[str, object]]:
    profile = PROFILES[name]
    evidence = inspect()
    running = str(evidence["kernel_cmdline"] or "")
    expected = set(profile.boot_arguments)
    active = set(shlex.split(running))
    checks = {
        "boot_arguments_active": expected <= active,
        "isolated_cpus": evidence["isolated_cpus"],
        "governors": evidence["governors"],
    }
    if name == "stock":
        checks["boot_arguments_active"] = not any(
            _argument_name(token) in MANAGED_ARGUMENTS or token in MANAGED_FLAGS
            for token in active
        )
    return bool(checks["boot_arguments_active"]), checks


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    inspect_parser = sub.add_parser("inspect")
    inspect_parser.add_argument("--json", action="store_true")
    for command in ("plan", "apply", "verify"):
        child = sub.add_parser(command)
        child.add_argument("--profile", choices=tuple(PROFILES), required=True)
    rollback_parser = sub.add_parser("rollback")
    rollback_parser.add_argument("--snapshot", type=Path)
    governor = sub.add_parser("set-governor")
    governor.add_argument("name", choices=("ondemand", "performance"))
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command == "inspect":
        result = inspect()
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.command == "plan":
        current = BOOT_CMDLINE.read_text(encoding="utf-8")
        print(update_kernel_cmdline(current, PROFILES[args.profile]), end="")
        return 0
    if args.command == "apply":
        snapshot, updated = apply_profile(args.profile)
        print(f"snapshot: {snapshot}")
        print(f"next boot: {updated}", end="")
        active, _checks = verify_profile(args.profile)
        if active:
            print("profile is already active; reboot is not required")
        else:
            print("reboot is required; verify after reconnecting")
        return 0
    if args.command == "rollback":
        print(f"restored: {rollback(args.snapshot)}")
        print("reboot is required")
        return 0
    if args.command == "set-governor":
        print(json.dumps(set_governor(args.name), sort_keys=True))
        return 0
    if args.command == "verify":
        ok, result = verify_profile(args.profile)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if ok else 1
    raise AssertionError(args.command)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, PermissionError) as exc:
        print(f"rt_pi_config: {exc}", file=sys.stderr)
        raise SystemExit(2)
