#!/usr/bin/env python3
"""Validate and record LB Omnichord's deliberately small Qt/QML surface."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


PACKAGING_ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST = PACKAGING_ROOT / "qt_runtime_manifest.json"
QML_IMPORT = re.compile(r"^\s*import\s+([A-Za-z][A-Za-z0-9_.]*)", re.MULTILINE)


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError(f"unsupported Qt runtime manifest revision in {path}")
    for key in (
        "python_modules",
        "android_load_order",
        "source_qml_imports",
        "qml_modules",
        "forbidden_runtime_fragments",
    ):
        values = data.get(key)
        if not isinstance(values, list) or not all(
            isinstance(value, str) and value for value in values
        ):
            raise ValueError(f"{path}: {key} must be a non-empty string list")
        if values != sorted(set(values)) and key != "android_load_order":
            raise ValueError(f"{path}: {key} must be sorted and unique")
    if data.get("quick_controls_style") != "Basic":
        raise ValueError("LB Omnichord packages only the Basic controls style")
    return data


def source_qml_imports(qml_root: Path) -> tuple[str, ...]:
    imports: set[str] = set()
    for path in sorted(qml_root.rglob("*.qml")):
        imports.update(QML_IMPORT.findall(path.read_text(encoding="utf-8")))
    return tuple(sorted(imports))


def validate_source_imports(qml_root: Path, manifest: dict[str, Any]) -> None:
    actual = source_qml_imports(qml_root)
    expected = tuple(manifest["source_qml_imports"])
    if actual != expected:
        raise ValueError(
            "QML source imports differ from the reviewed package surface: "
            f"expected={expected}, actual={actual}"
        )


def run_qml_import_scanner(qml_root: Path) -> list[dict[str, Any]]:
    environment_scanner = Path(sys.executable).parent / (
        "pyside6-qmlimportscanner.exe"
        if sys.platform == "win32"
        else "pyside6-qmlimportscanner"
    )
    scanner = (
        str(environment_scanner)
        if environment_scanner.is_file()
        else shutil.which("pyside6-qmlimportscanner")
        or shutil.which("qmlimportscanner")
    )
    if scanner is None:
        raise FileNotFoundError("no Qt qmlimportscanner executable is installed")

    from PySide6.QtCore import QLibraryInfo

    qml_import_path = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.QmlImportsPath))
    completed = subprocess.run(
        [
            scanner,
            "-rootPath",
            str(qml_root.resolve()),
            "-importPath",
            str(qml_import_path.resolve()),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)
    if not isinstance(result, list):
        raise ValueError("qmlimportscanner did not return a JSON list")
    return result


def write_scanner_evidence(
    qml_root: Path,
    output: Path,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> None:
    manifest = load_manifest(manifest_path)
    validate_source_imports(qml_root, manifest)
    scanner_result = run_qml_import_scanner(qml_root)
    discovered = sorted(
        {
            item["name"]
            for item in scanner_result
            if isinstance(item, dict)
            and isinstance(item.get("name"), str)
            and item.get("type") == "module"
        }
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_imports": list(source_qml_imports(qml_root)),
                "reviewed_qml_modules": manifest["qml_modules"],
                "scanner_modules": discovered,
                "scanner_result": scanner_result,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qml-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    write_scanner_evidence(args.qml_root, args.output, args.manifest)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
