#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
DEFAULT_INPUTS = HERE / "release_inputs.json"
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class AmyInput:
    repository: str
    release_branch: str
    commit: str
    pcm_bank: str


@dataclass(frozen=True, slots=True)
class PackageInput:
    platform: str
    suffix: str


@dataclass(frozen=True, slots=True)
class ReleaseInputs:
    amy: AmyInput
    desktop_python: str
    direct_runtime: dict[str, str]
    desktop_runtime: dict[str, str]
    direct_build: dict[str, str]
    constraints: dict[str, str]
    component_evidence: tuple[dict[str, Any], ...]
    declared_input_hashes: dict[str, str]
    packages: tuple[PackageInput, ...]


def _object(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    return value


def load_release_inputs(path: Path = DEFAULT_INPUTS) -> ReleaseInputs:
    raw = _object(json.loads(Path(path).read_text(encoding="utf-8")), str(path))
    if raw.get("schema_version") != 1:
        raise ValueError("unsupported release-input schema")
    amy = _object(raw.get("amy"), "amy")
    python = _object(raw.get("python"), "python")
    commit = str(amy.get("commit", ""))
    if not SHA_PATTERN.fullmatch(commit):
        raise ValueError("amy.commit must be a lowercase full commit SHA")
    packages_raw = raw.get("release_packages")
    if not isinstance(packages_raw, list) or len(packages_raw) != 5:
        raise ValueError("release_packages must contain exactly five entries")
    packages = tuple(
        PackageInput(
            platform=str(_object(item, "release package")["platform"]),
            suffix=str(_object(item, "release package")["suffix"]),
        )
        for item in packages_raw
    )
    if len({item.platform for item in packages}) != 5:
        raise ValueError("release package platform names must be unique")
    if len({item.suffix for item in packages}) != 5:
        raise ValueError("release package suffixes must be unique")
    declared_hashes = {
        str(key): str(value)
        for key, value in _object(
            raw.get("declared_input_hashes"), "declared_input_hashes"
        ).items()
    }
    frontend = Path(path).resolve().parent.parent
    for relative, expected in declared_hashes.items():
        if not HASH_PATTERN.fullmatch(expected):
            raise ValueError(f"invalid declared input hash for {relative}")
        declared_path = frontend / relative
        if _sha256(declared_path) != expected:
            raise ValueError(f"declared release input hash drift: {relative}")
    evidence = python.get("component_evidence")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("python.component_evidence must be a non-empty list")
    return ReleaseInputs(
        amy=AmyInput(
            repository=str(amy["repository"]),
            release_branch=str(amy["release_branch"]),
            commit=commit,
            pcm_bank=str(amy["pcm_bank"]),
        ),
        desktop_python=str(python["desktop"]),
        direct_runtime={
            str(key): str(value)
            for key, value in _object(
                python.get("direct_runtime"), "python.direct_runtime"
            ).items()
        },
        desktop_runtime={
            str(key): str(value)
            for key, value in _object(
                python.get("desktop_runtime"), "python.desktop_runtime"
            ).items()
        },
        direct_build={
            str(key): str(value)
            for key, value in _object(
                python.get("direct_build"), "python.direct_build"
            ).items()
        },
        constraints={
            str(key): str(value)
            for key, value in _object(
                python.get("constraints"), "python.constraints"
            ).items()
        },
        component_evidence=tuple(
            _object(value, "python.component_evidence entry") for value in evidence
        ),
        declared_input_hashes=declared_hashes,
        packages=packages,
    )


def append_github_environment(path: Path, inputs: ReleaseInputs) -> None:
    values = {
        "AMY_REPO": inputs.amy.repository,
        "AMY_RELEASE_BRANCH": inputs.amy.release_branch,
        "AMY_COMMIT": inputs.amy.commit,
        "AMY_REF": inputs.amy.commit,
        "AMY_PCM_BANK": inputs.amy.pcm_bank,
    }
    with Path(path).open("a", encoding="utf-8", newline="\n") as stream:
        for key, value in values.items():
            if "\n" in value:
                raise ValueError(f"release input {key} contains a newline")
            stream.write(f"{key}={value}\n")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def create_release_manifest(
    directory: Path,
    *,
    release_stamp: str,
    source_commit: str,
    output: Path,
    inputs: ReleaseInputs,
) -> dict[str, Any]:
    if not SHA_PATTERN.fullmatch(source_commit):
        raise ValueError("source commit must be a lowercase full commit SHA")
    expected_packages = {
        f"LB_Omnichord.{release_stamp}.{item.suffix}": item
        for item in inputs.packages
    }
    expected_files = set(expected_packages)
    expected_files.update(f"{name}.sha256" for name in expected_packages)
    actual_files = {
        path.name for path in Path(directory).iterdir() if path.is_file()
    }
    missing = sorted(expected_files - actual_files)
    extra = sorted(actual_files - expected_files)
    if missing or extra:
        raise ValueError(f"release assets differ: missing={missing}, extra={extra}")

    packages: list[dict[str, Any]] = []
    for file_name, definition in expected_packages.items():
        package_path = Path(directory) / file_name
        checksum_path = Path(directory) / f"{file_name}.sha256"
        digest = _sha256(package_path)
        checksum_fields = checksum_path.read_text(encoding="utf-8").strip().split()
        if checksum_fields != [digest, file_name]:
            raise ValueError(f"non-canonical or incorrect checksum for {file_name}")
        packages.append(
            {
                "platform": definition.platform,
                "file": file_name,
                "size": package_path.stat().st_size,
                "sha256": digest,
                "checksum_file": checksum_path.name,
            }
        )
    manifest = {
        "schema_version": 1,
        "release_stamp": release_stamp,
        "source_commit": source_commit,
        "amy": {
            "repository": inputs.amy.repository,
            "release_branch": inputs.amy.release_branch,
            "commit": inputs.amy.commit,
            "pcm_bank": inputs.amy.pcm_bank,
        },
        "python": {
            "desktop": inputs.desktop_python,
            "direct_runtime": inputs.direct_runtime,
            "desktop_runtime": inputs.desktop_runtime,
            "direct_build": inputs.direct_build,
            "constraints": inputs.constraints,
            "component_evidence": list(inputs.component_evidence),
            "declared_input_hashes": inputs.declared_input_hashes,
        },
        "packages": packages,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    temporary.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Use exact LB release inputs")
    parser.add_argument("--inputs", type=Path, default=DEFAULT_INPUTS)
    subparsers = parser.add_subparsers(dest="command", required=True)
    github = subparsers.add_parser("github-env")
    github.add_argument("--output", type=Path, required=True)
    amy = subparsers.add_parser("amy-values")
    amy.add_argument(
        "--field",
        choices=("repository", "release_branch", "commit", "pcm_bank"),
        required=True,
    )
    manifest = subparsers.add_parser("release-manifest")
    manifest.add_argument("--directory", type=Path, required=True)
    manifest.add_argument("--release-stamp", required=True)
    manifest.add_argument("--source-commit", required=True)
    manifest.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    inputs = load_release_inputs(args.inputs)
    if args.command == "github-env":
        append_github_environment(args.output, inputs)
    elif args.command == "amy-values":
        print(getattr(inputs.amy, args.field))
    else:
        create_release_manifest(
            args.directory,
            release_stamp=args.release_stamp,
            source_commit=args.source_commit,
            output=args.output,
            inputs=inputs,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
