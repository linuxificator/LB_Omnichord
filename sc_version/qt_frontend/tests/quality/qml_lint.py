from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any


WarningBucket = tuple[str, str]


def _tool_version(executable: str) -> str:
    completed = subprocess.run(
        [executable, "--version"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"qmllint version check failed: {completed.stderr.strip()}"
        )
    words = completed.stdout.strip().split()
    if len(words) != 2 or words[0] != "qmllint":
        raise RuntimeError(f"unexpected qmllint version output: {completed.stdout!r}")
    return words[1]


def normalize_report(raw: dict[str, Any], frontend: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for raw_file in raw.get("files", []):
        path = Path(str(raw_file["filename"])).resolve()
        try:
            relative = path.relative_to(frontend.resolve()).as_posix()
        except ValueError as exc:
            raise RuntimeError(f"qmllint reported a file outside the frontend: {path}") from exc
        warnings = [
            {
                "id": str(warning.get("id", "unknown")),
                "type": str(warning.get("type", "unknown")),
                "line": int(warning.get("line", 0)),
                "column": int(warning.get("column", 0)),
                "length": int(warning.get("length", 0)),
                "message": str(warning.get("message", "")),
            }
            for warning in raw_file.get("warnings", [])
        ]
        files.append(
            {
                "path": relative,
                "success": bool(raw_file.get("success", False)),
                "warnings": warnings,
            }
        )
    return {"schema_version": 1, "files": files}


def warning_buckets(report: dict[str, Any]) -> Counter[WarningBucket]:
    return Counter(
        (str(file_record["path"]), str(warning["id"]))
        for file_record in report["files"]
        for warning in file_record["warnings"]
    )


def baseline_buckets(baseline: dict[str, Any]) -> Counter[WarningBucket]:
    return Counter(
        {
            (str(record["path"]), str(record["id"])): int(record["count"])
            for record in baseline["warnings"]
        }
    )


def new_warning_buckets(
    report: dict[str, Any], baseline: dict[str, Any]
) -> Counter[WarningBucket]:
    return warning_buckets(report) - baseline_buckets(baseline)


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def run_qml_lint(frontend: Path, quality: Path) -> None:
    environment_tool = Path(sys.executable).with_name("pyside6-qmllint")
    executable = (
        str(environment_tool)
        if environment_tool.is_file()
        else shutil.which("pyside6-qmllint")
    )
    if executable is None:
        raise RuntimeError(
            "pyside6-qmllint is unavailable; install the declared test requirements"
        )
    baseline = json.loads(
        (quality / "qml_lint_baseline.json").read_text(encoding="utf-8")
    )
    version = _tool_version(executable)
    if version != baseline["tool_version"]:
        raise RuntimeError(
            "qmllint version does not match the reviewed baseline: "
            f"expected {baseline['tool_version']}, found {version}"
        )

    qml_files = sorted((frontend / "gui").rglob("*.qml"))
    completed = subprocess.run(
        [executable, "--json", "-", *(str(path) for path in qml_files)],
        cwd=frontend,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "qmllint execution failed:\n"
            f"{completed.stdout}\n{completed.stderr}"
        )
    try:
        report = normalize_report(json.loads(completed.stdout), frontend)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("qmllint returned an invalid JSON report") from exc

    artifact_root = Path(
        os.environ.get(
            "OMNICHORD_TEST_ARTIFACT_DIR",
            str(frontend / "test-artifacts" / "quality"),
        )
    )
    report["tool_version"] = version
    _write_json_atomic(artifact_root / "qml-lint.json", report)

    new_warnings = new_warning_buckets(report, baseline)
    actual = warning_buckets(report)
    allowed = baseline_buckets(baseline)
    if new_warnings or sum(actual.values()) > int(baseline["total_warnings"]):
        details = ", ".join(
            f"{path} [{warning_id}] +{count}"
            for (path, warning_id), count in sorted(new_warnings.items())
        )
        raise RuntimeError(f"QML lint baseline increased: {details or 'total'}")
    print(
        f"qml lint ratchet: {sum(actual.values())}/{sum(allowed.values())} "
        f"warnings with PySide {version}"
    )
