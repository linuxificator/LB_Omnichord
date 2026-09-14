#!/usr/bin/env python3
"""Create manifest and SPDX evidence for one tested SC Linux package."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any


REPOSITORY = "https://github.com/linuxificator/LB_Omnichord"


def _object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _release_instant(stamp: str) -> tuple[str, str]:
    if re.fullmatch(r"R[0-9]{14}", stamp) is None:
        raise ValueError("release stamp must look like RYYYYMMDDHHMMSS")
    instant = datetime.strptime(stamp[1:], "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    iso = instant.isoformat(timespec="seconds").replace("+00:00", "Z")
    tag = f"{stamp[:9]}T{stamp[9:]}-SC"
    return iso, tag


def _digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            result.update(chunk)
    return result.hexdigest()


def create_release_evidence(
    *,
    package: Path,
    release_stamp: str,
    source_commit: str,
    inputs: dict[str, Any],
    inputs_root: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    created, release_tag = _release_instant(release_stamp)
    if re.fullmatch(r"[0-9a-f]{40}", source_commit) is None:
        raise ValueError("source commit must be a full lowercase Git SHA")
    if inputs.get("schema_version") != 1:
        raise ValueError("unsupported SC release-input schema")
    supercollider = _object(inputs.get("supercollider"), "supercollider")
    sclork = _object(inputs.get("sclork_synths"), "sclork_synths")
    assets = _object(inputs.get("sample_assets"), "sample_assets")
    asset_evidence = dict(assets)
    if inputs_root is not None:
        for field in ("manifest", "source_catalog"):
            relative = asset_evidence.get(field)
            if not isinstance(relative, str) or not relative:
                raise ValueError(f"sample_assets.{field} must name an evidence file")
            evidence_path = (inputs_root / relative).resolve()
            if not evidence_path.is_file():
                raise ValueError(f"sample asset evidence is missing: {evidence_path}")
            asset_evidence[f"{field}_sha256"] = _digest(evidence_path)
    if supercollider.get("version") != "3.14.1":
        raise ValueError("SC release evidence requires pinned version 3.14.1")
    if int(sclork.get("definition_count", -1)) != 109:
        raise ValueError("SC release evidence requires all 109 SCLOrk definitions")
    if not package.is_file():
        raise ValueError(f"package is missing: {package}")
    package_sha = _digest(package)
    manifest = {
        "schema_version": 1,
        "edition": "supercollider",
        "release_stamp": release_stamp,
        "release_tag": release_tag,
        "created_utc": created,
        "source_commit": source_commit,
        "repository": REPOSITORY,
        "package": {
            "file": package.name,
            "platform": "linux-x86_64",
            "sha256": package_sha,
            "size_bytes": package.stat().st_size,
        },
        "runtime_inputs": {
            "supercollider": supercollider,
            "sclork_synths": sclork,
        },
        "external_sample_assets": asset_evidence,
    }
    app_id = "SPDXRef-Package-LB-Omnichord-SC-linux-x86-64"
    sc_id = "SPDXRef-Package-SuperCollider-3.14.1"
    sclork_id = "SPDXRef-Package-SCLOrkSynths"
    sbom = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"LB Omnichord SuperCollider {release_stamp}",
        "documentNamespace": (
            f"{REPOSITORY}/spdx/{release_tag}/{source_commit}"
        ),
        "creationInfo": {
            "created": created,
            "creators": [
                "Tool: LB_Omnichord supercollider_release_evidence.py"
            ],
        },
        "documentDescribes": [app_id],
        "packages": [
            {
                "SPDXID": app_id,
                "name": "LB Omnichord SuperCollider (linux-x86_64)",
                "versionInfo": release_stamp,
                "downloadLocation": (
                    f"{REPOSITORY}/releases/download/{release_tag}/{package.name}"
                ),
                "filesAnalyzed": False,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": "NOASSERTION",
                "copyrightText": "NOASSERTION",
                "checksums": [
                    {"algorithm": "SHA256", "checksumValue": package_sha}
                ],
            },
            {
                "SPDXID": sc_id,
                "name": "SuperCollider",
                "versionInfo": str(supercollider["version"]),
                "downloadLocation": str(supercollider["source_url"]),
                "filesAnalyzed": False,
                "licenseConcluded": str(supercollider["license"]),
                "licenseDeclared": str(supercollider["license"]),
                "copyrightText": "NOASSERTION",
                "checksums": [
                    {
                        "algorithm": "SHA256",
                        "checksumValue": str(supercollider["source_sha256"]),
                    }
                ],
            },
            {
                "SPDXID": sclork_id,
                "name": "SCLOrkSynths",
                "versionInfo": str(sclork["commit"]),
                "downloadLocation": (
                    "https://github.com/SCLOrkHub/SCLOrkSynths"
                ),
                "filesAnalyzed": False,
                "licenseConcluded": str(sclork["license"]),
                "licenseDeclared": str(sclork["license"]),
                "copyrightText": "NOASSERTION",
            },
        ],
        "relationships": [
            {
                "spdxElementId": "SPDXRef-DOCUMENT",
                "relationshipType": "DESCRIBES",
                "relatedSpdxElement": app_id,
            },
            {
                "spdxElementId": app_id,
                "relationshipType": "DEPENDS_ON",
                "relatedSpdxElement": sc_id,
            },
            {
                "spdxElementId": app_id,
                "relationshipType": "CONTAINS",
                "relatedSpdxElement": sclork_id,
            },
        ],
        "annotations": [
            {
                "annotationType": "OTHER",
                "annotator": "Tool: LB_Omnichord supercollider_release_evidence.py",
                "annotationDate": created,
                "annotatedElement": app_id,
                "comment": (
                    "VSCO 2 CE is an external CC0 sample bank and is not "
                    "contained in this package."
                ),
            }
        ],
    }
    return manifest, sbom


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--release-stamp", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--spdx", type=Path, required=True)
    args = parser.parse_args()
    inputs = _object(
        json.loads(args.inputs.read_text(encoding="utf-8")), str(args.inputs)
    )
    manifest, sbom = create_release_evidence(
        package=args.package,
        release_stamp=args.release_stamp,
        source_commit=args.source_commit,
        inputs=inputs,
        inputs_root=args.inputs.parent,
    )
    _write(args.manifest, manifest)
    _write(args.spdx, sbom)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
