#!/usr/bin/env python3
"""Generate the release-level SPDX 2.3 SBOM from the exact release manifest."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SPDX_VERSION = "SPDX-2.3"
DATA_LICENSE = "CC0-1.0"
REPOSITORY = "https://github.com/linuxificator/LB_Omnichord"
PLATFORM_PYSIDE = {
    "linux-x86_64": "6.10.3",
    "raspberrypi-aarch64": "6.7.3",
    "macos-arm64": "6.10.3",
    "windows-x86_64": "6.10.3",
    "android-arm64": "6.11.2",
}
DESKTOP_PLATFORMS = frozenset(PLATFORM_PYSIDE) - {"android-arm64"}


def _object(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    return value


def _list(value: Any, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{context} must be a list")
    return value


def _spdx_id(*parts: str) -> str:
    body = "-".join(parts)
    return "SPDXRef-" + re.sub(r"[^A-Za-z0-9.-]", "-", body)


def _created_from_stamp(stamp: str) -> str:
    if not re.fullmatch(r"R[0-9]{14}", stamp):
        raise ValueError("release stamp must look like RYYYYMMDDHHMMSS")
    instant = datetime.strptime(stamp[1:], "%Y%m%d%H%M%S").replace(
        tzinfo=timezone.utc
    )
    return instant.isoformat(timespec="seconds").replace("+00:00", "Z")


def _tag_from_stamp(stamp: str) -> str:
    _created_from_stamp(stamp)
    return f"{stamp[:9]}T{stamp[9:]}"


def _evidence_index(manifest: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    python = _object(manifest.get("python"), "python")
    evidence = _list(python.get("component_evidence"), "component_evidence")
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in evidence:
        component = _object(raw, "component evidence")
        name = str(component["name"])
        for version in _list(component.get("versions"), f"{name}.versions"):
            result[(name.casefold(), str(version))] = component
    return result


def _component_package(
    evidence: dict[tuple[str, str], dict[str, Any]],
    name: str,
    version: str,
) -> dict[str, Any]:
    try:
        record = evidence[(name.casefold(), version)]
    except KeyError as error:
        raise ValueError(f"missing component evidence for {name} {version}") from error
    return {
        "SPDXID": _spdx_id("Package", name, version),
        "name": name,
        "versionInfo": version,
        "downloadLocation": str(record["source"]),
        "filesAnalyzed": False,
        "licenseConcluded": "NOASSERTION",
        "licenseDeclared": str(record["license"]),
        "copyrightText": "NOASSERTION",
        "supplier": "NOASSERTION",
        "externalRefs": [
            {
                "referenceCategory": "PACKAGE-MANAGER",
                "referenceType": "purl",
                "referenceLocator": (
                    f"pkg:pypi/{name.casefold().replace('_', '-')}@{version}"
                ),
            }
        ],
    }


def create_spdx_sbom(manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported release manifest schema")
    stamp = str(manifest.get("release_stamp", ""))
    source_commit = str(manifest.get("source_commit", ""))
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("release manifest source_commit must be a full SHA")
    raw_packages = _list(manifest.get("packages"), "packages")
    if len(raw_packages) != 5:
        raise ValueError("release SBOM requires exactly five packages")
    platforms = {
        str(_object(item, "release package")["platform"]) for item in raw_packages
    }
    if platforms != set(PLATFORM_PYSIDE):
        raise ValueError("release SBOM platforms do not match the supported set")

    evidence = _evidence_index(manifest)
    packages: list[dict[str, Any]] = []
    relationships: list[dict[str, str]] = []
    dependency_keys: set[tuple[str, str]] = set()

    for raw in raw_packages:
        package = _object(raw, "release package")
        platform = str(package["platform"])
        file_name = str(package["file"])
        digest = str(package["sha256"])
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"invalid package SHA-256 for {file_name}")
        app_id = _spdx_id("Package", "LB-Omnichord", platform)
        packages.append(
            {
                "SPDXID": app_id,
                "name": f"LB Omnichord ({platform})",
                "versionInfo": stamp,
                "downloadLocation": (
                    f"{REPOSITORY}/releases/download/{_tag_from_stamp(stamp)}/{file_name}"
                ),
                "filesAnalyzed": False,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": "NOASSERTION",
                "copyrightText": "NOASSERTION",
                "supplier": "NOASSERTION",
                "checksums": [{"algorithm": "SHA256", "checksumValue": digest}],
            }
        )
        relationships.append(
            {
                "spdxElementId": "SPDXRef-DOCUMENT",
                "relationshipType": "DESCRIBES",
                "relatedSpdxElement": app_id,
            }
        )
        runtime_dependencies = (
            ("AMY", str(_object(manifest["amy"], "amy")["commit"])),
            ("PySide6", PLATFORM_PYSIDE[platform]),
            ("PySide6_Addons", PLATFORM_PYSIDE[platform]),
            ("PySide6_Essentials", PLATFORM_PYSIDE[platform]),
            ("shiboken6", PLATFORM_PYSIDE[platform]),
            ("pyserial", "3.5"),
            ("fastjsonschema", "2.22.2"),
        )
        for dependency in runtime_dependencies:
            dependency_keys.add(dependency)
            relationships.append(
                {
                    "spdxElementId": app_id,
                    "relationshipType": "DEPENDS_ON",
                    "relatedSpdxElement": _spdx_id("Package", *dependency),
                }
            )
        if platform in DESKTOP_PLATFORMS:
            dependency_keys.add(("PyInstaller", "6.22.2"))
            relationships.append(
                {
                    "spdxElementId": _spdx_id("Package", "PyInstaller", "6.22.2"),
                    "relationshipType": "BUILD_DEPENDENCY_OF",
                    "relatedSpdxElement": app_id,
                }
            )

    amy = _object(manifest["amy"], "amy")
    amy_commit = str(amy["commit"])
    packages.append(
        {
            "SPDXID": _spdx_id("Package", "AMY", amy_commit),
            "name": "AMY",
            "versionInfo": amy_commit,
            "downloadLocation": str(amy["repository"]),
            "filesAnalyzed": False,
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": "MIT",
            "copyrightText": "Copyright (c) 2022 Brian Whitman and Daniel PW Ellis",
            "supplier": "Organization: shorepine",
        }
    )
    dependency_keys.discard(("AMY", amy_commit))
    packages.extend(
        _component_package(evidence, name, version)
        for name, version in sorted(dependency_keys)
    )
    return {
        "spdxVersion": SPDX_VERSION,
        "dataLicense": DATA_LICENSE,
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"LB Omnichord {stamp} five-platform release",
        "documentNamespace": f"{REPOSITORY}/spdx/{stamp}/{source_commit}",
        "creationInfo": {
            "created": _created_from_stamp(stamp),
            "creators": ["Tool: LB_Omnichord release_sbom.py"],
        },
        "documentDescribes": [
            _spdx_id("Package", "LB-Omnichord", platform)
            for platform in sorted(platforms)
        ],
        "packages": packages,
        "relationships": relationships,
    }


def write_spdx_sbom(manifest_path: Path, output: Path) -> dict[str, Any]:
    manifest = _object(
        json.loads(manifest_path.read_text(encoding="utf-8")), str(manifest_path)
    )
    sbom = create_spdx_sbom(manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    temporary.write_text(
        json.dumps(sbom, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(output)
    return sbom


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    write_spdx_sbom(args.manifest, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
