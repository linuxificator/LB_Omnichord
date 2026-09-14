#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from release_inputs import DEFAULT_INPUTS, load_release_inputs


def run(command: list[str], *, capture: bool = False) -> str:
    completed = subprocess.run(
        command,
        check=True,
        text=True,
        capture_output=capture,
    )
    return completed.stdout.strip() if capture else ""


def checkout_amy(destination: Path, *, inputs_path: Path = DEFAULT_INPUTS) -> str:
    inputs = load_release_inputs(inputs_path)
    destination = Path(destination)
    if destination.exists():
        raise ValueError(f"AMY checkout destination already exists: {destination}")
    run(
        [
            "git",
            "clone",
            "--filter=blob:none",
            "--no-checkout",
            inputs.amy.repository,
            str(destination),
        ]
    )
    run(
        [
            "git",
            "-C",
            str(destination),
            "fetch",
            "--no-tags",
            "origin",
            inputs.amy.commit,
            f"refs/heads/{inputs.amy.release_branch}:"
            f"refs/remotes/origin/{inputs.amy.release_branch}",
        ]
    )
    run(
        [
            "git",
            "-C",
            str(destination),
            "merge-base",
            "--is-ancestor",
            inputs.amy.commit,
            f"origin/{inputs.amy.release_branch}",
        ]
    )
    run(
        [
            "git",
            "-C",
            str(destination),
            "checkout",
            "--detach",
            inputs.amy.commit,
        ]
    )
    actual = run(
        ["git", "-C", str(destination), "rev-parse", "HEAD"],
        capture=True,
    )
    if actual != inputs.amy.commit:
        raise RuntimeError(f"AMY checkout resolved to {actual}, not {inputs.amy.commit}")
    print(f"AMY checkout verified: {actual}")
    return actual


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Checkout the exact LB AMY input")
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, default=DEFAULT_INPUTS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    checkout_amy(args.destination, inputs_path=args.inputs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
