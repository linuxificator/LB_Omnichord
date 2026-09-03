#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"

SUITES: dict[str, tuple[Path, ...]] = {
    "quality": (
        TESTS / "run_quality.py",
    ),
    # Every top-level test_*.py file is a dependency-free/unit contract. Auto
    # discovery prevents a new unit test from silently being omitted locally
    # and in CI, as happened with the MIDI engine and socket tests.
    "unit": tuple(sorted(TESTS.glob("test_*.py"))),
    "portable-input-processes": (
        TESTS / "contracts" / "test_external_input_processes.py",
    ),
    "platform-input-linux": (
        TESTS / "platform" / "linux" / "test_midi_input.py",
        TESTS / "platform" / "linux" / "test_source_package_smoke.py",
    ),
    "frontend": (
        TESTS / "integration" / "test_frontend.py",
    ),
    "serial": (
        TESTS / "integration" / "test_serial.py",
        TESTS / "integration" / "test_programs.py",
    ),
    "native-controls": (
        TESTS / "integration" / "test_native_controls.py",
    ),
    "native-rhythm": (
        TESTS / "integration" / "test_native_rhythm.py",
    ),
    "presets": (
        TESTS / "integration" / "test_presets.py",
    ),
}
ALL_ORDER = (
    "quality",
    "unit",
    "portable-input-processes",
    "platform-input-linux",
    "frontend",
    "serial",
    "presets",
    "native-controls",
    "native-rhythm",
)


@dataclass(frozen=True, slots=True)
class ScriptResult:
    suite: str
    script: str
    status: str
    returncode: int
    duration_seconds: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a logical subset of the LB Omnichord regression suite"
    )
    parser.add_argument(
        "--suite",
        default=os.environ.get("OMNICHORD_TEST_SUITE", "unit"),
        choices=tuple(SUITES) + ("all",),
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="print available suites and exit",
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        help="write the atomic machine-readable run report to this path",
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="collect branch coverage for navigation without enforcing a total",
    )
    return parser.parse_args()


def _artifact_root(env: dict[str, str]) -> Path:
    return Path(
        env.get(
            "OMNICHORD_TEST_ARTIFACT_DIR",
            str(ROOT / "test-artifacts"),
        )
    )


def _prepare_suite_artifacts(artifact_root: Path, suite: str) -> Path:
    suite_artifacts = artifact_root / suite
    shutil.rmtree(suite_artifacts, ignore_errors=True)
    suite_artifacts.mkdir(parents=True, exist_ok=True)
    return suite_artifacts


def _command_for_script(script: Path, coverage_directory: Path | None) -> list[str]:
    if coverage_directory is None:
        return [sys.executable, str(script)]
    return [
        sys.executable,
        "-m",
        "coverage",
        "run",
        "--rcfile",
        str(ROOT / ".coveragerc"),
        str(script),
    ]


def run_script(
    script: Path,
    *,
    suite: str,
    suite_artifacts: Path,
    coverage_directory: Path | None = None,
) -> ScriptResult:
    env = os.environ.copy()
    env["OMNICHORD_TEST_ARTIFACT_DIR"] = str(suite_artifacts)
    if coverage_directory is not None:
        env["COVERAGE_FILE"] = str(coverage_directory / ".coverage")
        env["COVERAGE_PROCESS_START"] = str(ROOT / ".coveragerc")

    print(f"\n=== {suite}: {script.relative_to(ROOT)} ===", flush=True)
    started = time.monotonic()
    completed = subprocess.run(
        _command_for_script(script, coverage_directory),
        cwd=ROOT,
        env=env,
        check=False,
    )
    duration = round(time.monotonic() - started, 6)
    return ScriptResult(
        suite=suite,
        script=str(script.relative_to(ROOT)),
        status="passed" if completed.returncode == 0 else "failed",
        returncode=completed.returncode,
        duration_seconds=duration,
    )


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _repository_commit() -> str:
    configured = os.environ.get("GITHUB_SHA")
    if configured:
        return configured
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def _amy_commit() -> str:
    manifest = ROOT / "packaging" / "release_inputs.json"
    value = json.loads(manifest.read_text(encoding="utf-8"))
    return str(value["amy"]["commit"])


def _finalize_coverage(directory: Path) -> ScriptResult:
    env = os.environ.copy()
    env["COVERAGE_FILE"] = str(directory / ".coverage")
    started = time.monotonic()
    commands = (
        [sys.executable, "-m", "coverage", "combine", "--keep", str(directory)],
        [
            sys.executable,
            "-m",
            "coverage",
            "json",
            "--show-contexts",
            "-o",
            str(directory / "coverage.json"),
        ],
    )
    returncode = 0
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            check=False,
        )
        if completed.returncode != 0:
            returncode = completed.returncode
            break
    return ScriptResult(
        suite="coverage",
        script="coverage combine/json",
        status="passed" if returncode == 0 else "failed",
        returncode=returncode,
        duration_seconds=round(time.monotonic() - started, 6),
    )


def main() -> int:
    args = parse_args()
    if args.list:
        print("Available suites:")
        for suite in SUITES:
            print(f"  {suite}")
        print("  all")
        return 0

    environment = os.environ.copy()
    artifact_root = _artifact_root(environment)
    artifact_root.mkdir(parents=True, exist_ok=True)
    report_path = args.report_json or artifact_root / f"test-report-{args.suite}.json"
    coverage_directory = (
        artifact_root / f"coverage-{args.suite}" if args.coverage else None
    )
    if coverage_directory is not None:
        shutil.rmtree(coverage_directory, ignore_errors=True)
        coverage_directory.mkdir(parents=True)

    selected = ALL_ORDER if args.suite == "all" else (args.suite,)
    started_wall = datetime.now(UTC)
    started = time.monotonic()
    results: list[ScriptResult] = []
    returncode = 0
    for suite in selected:
        suite_artifacts = _prepare_suite_artifacts(artifact_root, suite)
        for script in SUITES[suite]:
            result = run_script(
                script,
                suite=suite,
                suite_artifacts=suite_artifacts,
                coverage_directory=coverage_directory,
            )
            results.append(result)
            if result.returncode != 0:
                returncode = result.returncode
                break
        if returncode != 0:
            break
    if coverage_directory is not None:
        coverage_result = _finalize_coverage(coverage_directory)
        results.append(coverage_result)
        if returncode == 0:
            returncode = coverage_result.returncode

    report = {
        "schema_version": 1,
        "requested_suite": args.suite,
        "started_at": started_wall.isoformat(),
        "duration_seconds": round(time.monotonic() - started, 6),
        "status": "passed" if returncode == 0 else "failed",
        "repository_commit": _repository_commit(),
        "amy_commit": _amy_commit(),
        "coverage_report": (
            str(coverage_directory / "coverage.json")
            if coverage_directory is not None
            else None
        ),
        "scripts": [asdict(result) for result in results],
    }
    _write_json_atomic(report_path, report)
    print(f"\nMachine-readable report: {report_path}")
    if returncode == 0:
        print("All selected tests passed.")
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
