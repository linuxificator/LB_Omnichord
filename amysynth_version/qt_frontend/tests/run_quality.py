#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any


FRONTEND = Path(__file__).resolve().parents[1]
REPOSITORY = FRONTEND.parents[1]
QUALITY = FRONTEND / "tests" / "quality"
sys.path.insert(0, str(QUALITY))

from repository_checks import run_repository_checks  # noqa: E402


def run(command: list[str], *, expected: set[int] = {0}) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=FRONTEND,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode not in expected:
        sys.stdout.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        raise SystemExit(completed.returncode)
    return completed


def compile_python() -> None:
    with tempfile.TemporaryDirectory(prefix="lb-compileall-") as directory:
        env = os.environ.copy()
        env["PYTHONPYCACHEPREFIX"] = directory
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "compileall",
                "-q",
                "code",
                "tests",
                "tools",
                "packaging",
                "instruments",
                "capture_screenshots.py",
            ],
            cwd=FRONTEND,
            env=env,
            check=False,
        )
        if completed.returncode != 0:
            raise SystemExit(completed.returncode)


def mypy_errors(output: str) -> Counter[tuple[str, str]]:
    errors: Counter[tuple[str, str]] = Counter()
    for line in output.splitlines():
        if not line.startswith("{"):
            continue
        record: dict[str, Any] = json.loads(line)
        if record.get("severity") == "error":
            errors[(str(record["file"]), str(record["code"]))] += 1
    return errors


def check_mypy_ratchet() -> None:
    baseline: dict[str, Any] = json.loads(
        (QUALITY / "mypy_legacy_baseline.json").read_text(encoding="utf-8")
    )
    version = run([sys.executable, "-m", "mypy", "--version"]).stdout
    if baseline["tool_version"] not in version:
        raise SystemExit(f"mypy version does not match baseline: {version.strip()}")

    run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--strict",
            "--follow-imports=skip",
            "tests/quality/repository_checks.py",
            "tests/run_quality.py",
        ]
    )

    completed = run(
        [sys.executable, "-m", "mypy", "-O", "json", "code"],
        expected={0, 1},
    )
    actual = mypy_errors(completed.stdout)
    allowed = Counter(
        {
            (str(record["file"]), str(record["code"])): int(record["count"])
            for record in baseline["errors"]
        }
    )
    new_errors = actual - allowed
    if new_errors or sum(actual.values()) > int(baseline["total_errors"]):
        for (path, code), count in sorted(new_errors.items()):
            print(f"new mypy error: {path} [{code}] x{count}", file=sys.stderr)
        raise SystemExit("mypy legacy error baseline increased")

    known = set(str(path) for path in baseline["known_production_modules"])
    current = {
        path.relative_to(FRONTEND).as_posix()
        for path in (FRONTEND / "code").glob("*.py")
    }
    new_modules = sorted(current - known)
    if new_modules:
        run(
            [
                sys.executable,
                "-m",
                "mypy",
                "--strict",
                "--follow-imports=skip",
                *new_modules,
            ]
        )

    print(
        f"mypy ratchet: {sum(actual.values())}/{baseline['total_errors']} "
        f"legacy errors; {len(new_modules)} new modules strict"
    )


def main() -> int:
    compile_python()
    run_repository_checks(
        REPOSITORY,
        FRONTEND,
        QUALITY / "quality_policy.json",
    )
    run([sys.executable, "-m", "ruff", "check", "."])
    check_mypy_ratchet()
    print("All quality guardrails passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
