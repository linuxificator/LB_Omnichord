#!/usr/bin/env python3
"""Validate package acceptance artifacts and emit one evidence manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SERVICE_SESSION = re.compile(
    r"AMY service session completed: ([1-9][0-9]*) wire commands, "
    r"([1-9][0-9]*) nonzero PCM samples"
)


@dataclass(frozen=True, slots=True)
class ScenarioEvidence:
    identifier: str
    evidence_class: str
    passed: bool
    detail: str
    sources: tuple[str, ...]


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _valid_png(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 1024 and path.read_bytes()[:8] == PNG_SIGNATURE


def _runtime_markers(platform: str, application_log: str) -> tuple[bool, str]:
    missing: list[str] = []
    if platform.startswith("Windows"):
        match = SERVICE_SESSION.search(application_log)
        if match is None:
            missing.append("AMY service session completed with wire and PCM output")
    elif platform.startswith("Android"):
        for marker in (
            "QPA platform: android",
            "AMY/Oboe started:",
            "AMY backend:",
        ):
            if marker not in application_log:
                missing.append(marker)
    else:
        for marker in (
            "QPA platform:",
            "AMY service ready:",
            "AMY backend:",
            "Captured ",
        ):
            if marker not in application_log:
                missing.append(marker)
    return not missing, "all runtime markers observed" if not missing else "missing: " + ", ".join(missing)


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    artifact = args.artifact.resolve()
    audit = _read_json(args.package_audit)
    qml = _read_json(args.qml_imports)
    application_log = args.application_log.read_text(encoding="utf-8", errors="replace")
    input_log = args.external_input_contract_log.read_text(
        encoding="utf-8", errors="replace"
    )
    screenshots = tuple(path.resolve() for path in args.screenshot)
    runtime_ok, runtime_detail = _runtime_markers(args.platform, application_log)

    package_policy_ok = (
        audit.get("platform") == args.platform
        and int(audit.get("package_bytes") or 0) > 0
        and audit.get("forbidden_runtime_matches") == []
    )
    qml_policy_ok = (
        qml.get("schema_version") == 1
        and (
            (
                bool(qml.get("source_imports"))
                and bool(qml.get("reviewed_qml_modules"))
                and isinstance(qml.get("scanner_result"), list)
            )
            or bool(qml.get("kept_qml_modules"))
        )
    )
    input_contract_ok = (
        "OK" in input_log
        and "FAILED" not in input_log
        and "Traceback (most recent call last)" not in input_log
    )
    scenarios = (
        ScenarioEvidence(
            "artifact-present",
            "package",
            artifact.is_file() and artifact.stat().st_size > 0,
            f"{artifact.name} is non-empty",
            (str(artifact),),
        ),
        ScenarioEvidence(
            "package-content-policy",
            "package",
            package_policy_ok,
            "package audit matches platform and has no forbidden runtime",
            (str(args.package_audit.resolve()),),
        ),
        ScenarioEvidence(
            "qml-import-policy",
            "package",
            qml_policy_ok,
            "reviewed QML imports and scanner evidence are present",
            (str(args.qml_imports.resolve()),),
        ),
        ScenarioEvidence(
            "external-input-process-contract",
            "portable-integration",
            input_contract_ok,
            "independent MIDI/OSC sender and receiver contract passed",
            (str(args.external_input_contract_log.resolve()),),
        ),
        ScenarioEvidence(
            "packaged-runtime",
            "package-integration",
            runtime_ok and "Traceback (most recent call last)" not in application_log,
            runtime_detail,
            (str(args.application_log.resolve()),),
        ),
        ScenarioEvidence(
            "rendered-ui",
            "package-integration",
            len(screenshots) >= 2 and all(_valid_png(path) for path in screenshots),
            f"{len(screenshots)} non-trivial PNG captures validated",
            tuple(str(path) for path in screenshots),
        ),
        ScenarioEvidence(
            "regression-prerequisite",
            "regression",
            args.regression_result == "success",
            f"upstream regression result: {args.regression_result}",
            (),
        ),
    )
    if args.audio_evidence is not None:
        audio = args.audio_evidence.resolve()
        scenarios += (
            ScenarioEvidence(
                "native-audio-evidence",
                "platform-native",
                audio.is_file() and audio.stat().st_size > 0,
                "platform-native audio validation produced evidence",
                (str(audio),),
            ),
        )

    manifest = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "platform": args.platform,
        "artifact": {
            "name": artifact.name,
            "bytes": artifact.stat().st_size if artifact.is_file() else 0,
            "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()
            if artifact.is_file()
            else None,
        },
        "passed": all(item.passed for item in scenarios),
        "scenarios": [asdict(item) for item in scenarios],
    }
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--package-audit", type=Path, required=True)
    parser.add_argument("--qml-imports", type=Path, required=True)
    parser.add_argument("--application-log", type=Path, required=True)
    parser.add_argument("--external-input-contract-log", type=Path, required=True)
    parser.add_argument("--screenshot", type=Path, action="append", required=True)
    parser.add_argument("--regression-result", choices=("success", "failure"), required=True)
    parser.add_argument("--audio-evidence", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = evaluate(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(args.output)
    if not manifest["passed"]:
        failures = [
            item["identifier"]
            for item in manifest["scenarios"]
            if not item["passed"]
        ]
        raise SystemExit("package evidence failed: " + ", ".join(failures))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
