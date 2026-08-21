#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"

SUITES: dict[str, tuple[Path, ...]] = {
    "unit-controls": (
        TESTS / "test_instrument_defaults.py",
        TESTS / "test_static_contracts.py",
    ),
    "frontend": (
        TESTS / "integration" / "test_frontend.py",
    ),
    "serial": (
        TESTS / "integration" / "test_serial.py",
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
    "unit-controls",
    "frontend",
    "serial",
    "presets",
    "native-controls",
    "native-rhythm",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a logical subset of the LB Omnichord regression suite"
    )
    parser.add_argument(
        "--suite",
        default=os.environ.get("OMNICHORD_TEST_SUITE", "unit-controls"),
        choices=tuple(SUITES) + ("all",),
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="print available suites and exit",
    )
    return parser.parse_args()


def run_script(script: Path, *, suite: str) -> None:
    env = os.environ.copy()
    artifact_root = Path(
        env.get(
            "OMNICHORD_TEST_ARTIFACT_DIR",
            str(ROOT / "test-artifacts"),
        )
    )
    suite_artifacts = artifact_root / suite
    suite_artifacts.mkdir(parents=True, exist_ok=True)
    env["OMNICHORD_TEST_ARTIFACT_DIR"] = str(suite_artifacts)

    print(f"\n=== {suite}: {script.relative_to(ROOT)} ===", flush=True)
    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=ROOT,
        env=env,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def main() -> int:
    args = parse_args()
    if args.list:
        print("Available suites:")
        for suite in SUITES:
            print(f"  {suite}")
        print("  all")
        return 0

    selected = ALL_ORDER if args.suite == "all" else (args.suite,)
    for suite in selected:
        for script in SUITES[suite]:
            run_script(script, suite=suite)
    print("\nAll selected tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
