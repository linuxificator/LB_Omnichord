#!/usr/bin/env python3
"""Create deterministic package-size/content evidence and enforce Qt policy."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from qt_runtime_policy import DEFAULT_MANIFEST, load_manifest


QT_TOKEN = re.compile(r"(?:lib)?(Qt(?:6)?[A-Za-z0-9]+)")


@dataclass(frozen=True)
class Member:
    path: str
    size: int
    compressed_size: int | None
    container: str


def tree_members(root: Path) -> list[Member]:
    return [
        Member(
            path.relative_to(root).as_posix(),
            path.stat().st_size,
            None,
            "tree",
        )
        for path in sorted(root.rglob("*"))
        if path.is_file() or path.is_symlink()
    ]


def zip_members(path: Path) -> list[Member]:
    members: list[Member] = []
    with zipfile.ZipFile(path) as archive:
        for info in sorted(archive.infolist(), key=lambda item: item.filename):
            if info.is_dir():
                continue
            members.append(
                Member(
                    info.filename,
                    info.file_size,
                    info.compress_size,
                    "zip",
                )
            )
    return members


def content_members(package: Path | None, tree: Path | None) -> list[Member]:
    members: list[Member] = []
    if tree is not None:
        members.extend(tree_members(tree))
    if package is not None and zipfile.is_zipfile(package):
        members.extend(zip_members(package))
    if not members:
        raise ValueError("audit needs a package ZIP or an extracted package tree")
    return members


def policy_violations(
    members: Iterable[Member],
    forbidden_fragments: Iterable[str],
    forbidden_basenames: Iterable[str] = (),
    exempt_prefixes: Iterable[str] = (),
) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    basenames = frozenset(forbidden_basenames)
    prefixes = tuple(
        prefix.replace("\\", "/").rstrip("/") + "/"
        for prefix in exempt_prefixes
    )
    for member in members:
        normalized_path = member.path.replace("\\", "/")
        if normalized_path.startswith(prefixes):
            continue
        if Path(member.path).name in basenames:
            violations.append(
                {"fragment": Path(member.path).name, "path": member.path}
            )
            continue
        for fragment in forbidden_fragments:
            if fragment in member.path:
                violations.append({"fragment": fragment, "path": member.path})
                break
    return violations


def qt_inventory(members: Iterable[Member]) -> list[str]:
    return sorted(
        {
            match.group(1)
            for member in members
            for match in QT_TOKEN.finditer(Path(member.path).name)
        }
    )


def audit(
    *,
    platform: str,
    output: Path,
    package: Path | None,
    tree: Path | None,
    max_package_bytes: int | None,
    manifest_path: Path = DEFAULT_MANIFEST,
    forbidden_runtime_exempt_prefixes: Iterable[str] = (),
) -> dict[str, object]:
    manifest = load_manifest(manifest_path)
    members = content_members(package, tree)
    violations = policy_violations(
        members,
        manifest["forbidden_runtime_fragments"],
        manifest.get("platform_forbidden_runtime_basenames", {}).get(platform, ()),
        forbidden_runtime_exempt_prefixes,
    )
    package_bytes = package.stat().st_size if package is not None else None
    configured_budget = manifest.get("package_size_budgets_bytes", {}).get(platform)
    budget = max_package_bytes if max_package_bytes is not None else configured_budget
    report: dict[str, object] = {
        "schema_version": 1,
        "platform": platform,
        "package": package.name if package is not None else None,
        "package_bytes": package_bytes,
        "package_budget_bytes": budget,
        "member_count": len(members),
        "member_bytes": sum(member.size for member in members),
        "qt_inventory": qt_inventory(members),
        "forbidden_runtime_matches": violations,
        "largest_members": [
            asdict(member)
            for member in sorted(
                members, key=lambda item: (item.size, item.path), reverse=True
            )[:30]
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if budget is not None:
        if package_bytes is None:
            raise ValueError("a compressed-size budget requires --package")
        if package_bytes > budget:
            raise ValueError(
                f"{package.name} is {package_bytes} bytes; budget is "
                f"{budget} bytes"
            )
    if violations:
        examples = ", ".join(
            f"{item['fragment']}:{item['path']}" for item in violations[:5]
        )
        raise ValueError(f"forbidden runtime content: {examples}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--package", type=Path)
    parser.add_argument("--tree", type=Path)
    parser.add_argument("--max-package-bytes", type=int)
    parser.add_argument(
        "--forbidden-runtime-exempt-prefix",
        action="append",
        default=[],
        help=(
            "Exclude one separately owned runtime subtree from forbidden-name "
            "matching; its bytes and inventory remain audited"
        ),
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    audit(
        platform=args.platform,
        output=args.output,
        package=args.package,
        tree=args.tree,
        max_package_bytes=args.max_package_bytes,
        manifest_path=args.manifest,
        forbidden_runtime_exempt_prefixes=args.forbidden_runtime_exempt_prefix,
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
