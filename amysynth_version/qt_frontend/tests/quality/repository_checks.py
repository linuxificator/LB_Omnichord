from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote


class QualityError(ValueError):
    """A repository quality contract was violated."""


def parse_python(path: Path) -> ast.Module:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        raise QualityError(f"invalid Python syntax: {path}: {exc}") from exc


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise QualityError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> Any:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise QualityError(f"invalid shipped JSON: {path}: {exc}") from exc
    if not isinstance(value, (dict, list)):
        raise QualityError(f"shipped JSON must have an object/array root: {path}")
    return value


def check_shipped_json(frontend: Path) -> None:
    roots = tuple(frontend / name for name in ("config", "instruments", "music"))
    paths = sorted(path for root in roots for path in root.rglob("*.json"))
    if not paths:
        raise QualityError("no shipped JSON files found")
    for path in paths:
        load_json(path)


_MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def check_markdown_file(path: Path) -> None:
    for raw_target in _MARKDOWN_LINK.findall(path.read_text(encoding="utf-8")):
        target = raw_target.strip().strip("<>")
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        target = unquote(target.split("#", 1)[0])
        if target and not (path.parent / target).resolve().exists():
            raise QualityError(f"missing Markdown target: {path} -> {target}")


def markdown_files(repository: Path) -> list[Path]:
    candidates = [repository / "README.md", repository / "CODEX_HANDOFF.md"]
    candidates.extend((repository / "amysynth_version" / "design").rglob("*.md"))
    candidates.extend(
        (repository / "amysynth_version" / "qt_frontend").rglob("*.md")
    )
    return sorted(
        path
        for path in set(candidates)
        if path.is_file()
        and not {"build", "dist", "test-artifacts"}.intersection(path.parts)
    )


def check_markdown_links(repository: Path) -> None:
    for path in markdown_files(repository):
        check_markdown_file(path)


def check_document_status(repository: Path, relative_paths: list[str]) -> None:
    required = ("Status:", "Owner:", "Last verified:")
    for relative in relative_paths:
        path = repository / relative
        if not path.is_file():
            raise QualityError(f"active document is missing: {relative}")
        preamble = "\n".join(path.read_text(encoding="utf-8").splitlines()[:12])
        for field in required:
            if field not in preamble:
                raise QualityError(f"active document lacks {field} {relative}")


def check_document_routes(repository: Path) -> None:
    design = repository / "amysynth_version" / "design"
    route = design / "README.md"
    tokens = set(re.findall(r"`([^`\n]+\.md)`", route.read_text(encoding="utf-8")))
    for token in sorted(tokens):
        if any(marker in token for marker in ("<", ">", "*")):
            continue
        if not (design / token).resolve().is_file():
            raise QualityError(f"design route target is missing: {token}")


def imported_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def uses_direct_platform_access(tree: ast.AST) -> bool:
    restricted_attributes = {("sys", "platform"), ("os", "name")}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and (node.value.id, node.attr) in restricted_attributes
        ):
            return True
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and (node.func.value.id, node.func.attr)
            in {("platform", "system"), ("platform", "platform")}
        ):
            return True
    return False


def check_import_boundaries(code_dir: Path, policy: dict[str, Any]) -> None:
    amy_allowed = set(policy["amy_import_allowlist"])
    platform_allowed = {
        root: set(files)
        for root, files in policy["platform_import_allowlist"].items()
    }
    direct_platform_allowed = set(policy["direct_platform_access_allowlist"])
    for path in sorted(code_dir.glob("*.py")):
        tree = parse_python(path)
        roots = imported_roots(tree)
        if roots.intersection({"amy", "c_amy"}) and path.name not in amy_allowed:
            raise QualityError(f"AMY engine import outside service adapter: {path}")
        for root, allowed_files in platform_allowed.items():
            if root in roots and path.name not in allowed_files:
                raise QualityError(
                    f"platform import {root} outside declared adapter: {path}"
                )
        if uses_direct_platform_access(tree) and path.name not in direct_platform_allowed:
            raise QualityError(f"direct platform selection outside adapter: {path}")


def check_declared_third_party_imports(frontend: Path, manifest_path: Path) -> None:
    manifest = load_json(manifest_path)
    if not isinstance(manifest, dict):
        raise QualityError("dependency manifest must be an object")
    declared = set(manifest["direct_imports"])
    python_files = sorted(
        path
        for path in frontend.rglob("*.py")
        if not {"build", "dist", "deployment", ".venv"}.intersection(path.parts)
    )
    first_party = {path.stem for path in python_files}
    imported = set().union(*(imported_roots(parse_python(path)) for path in python_files))
    actual = imported - sys.stdlib_module_names - first_party
    if actual != declared:
        raise QualityError(
            "third-party import declaration drift: "
            f"undeclared={sorted(actual - declared)}, stale={sorted(declared - actual)}"
        )


def _joined_shell_lines(text: str) -> list[str]:
    return re.sub(r"\\\s*\n\s*", " ", text).splitlines()


def check_workflow_dependency_installs(workflows: list[Path]) -> None:
    package_literal = re.compile(r"(?<![/\w.-])[A-Za-z][A-Za-z0-9_.-]*==[0-9]")
    for path in workflows:
        text = path.read_text(encoding="utf-8")
        if package_literal.search(text):
            raise QualityError(f"workflow contains a package/version literal: {path}")
        for line in _joined_shell_lines(text):
            if "pip install" not in line:
                continue
            command = line.split("pip install", 1)[1].strip()
            allowed = (
                "-r " in command
                or command in {"--upgrade pip", "/tmp/amy-lb"}
                or command.endswith(" /tmp/amy-lb")
            )
            if not allowed:
                raise QualityError(f"undeclared workflow pip install: {path}: {line}")


def check_workflow_action_pins(workflows: list[Path]) -> None:
    action = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)", re.MULTILINE)
    for path in workflows:
        for reference in action.findall(path.read_text(encoding="utf-8")):
            if reference.startswith("./"):
                continue
            if "@" not in reference:
                raise QualityError(f"workflow action has no revision: {path}: {reference}")
            revision = reference.rsplit("@", 1)[1]
            if not _FULL_SHA.fullmatch(revision):
                raise QualityError(
                    f"workflow action is not pinned to a full SHA: {path}: {reference}"
                )


def load_policy(path: Path) -> dict[str, Any]:
    value = load_json(path)
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise QualityError(f"unsupported quality policy: {path}")
    return value


def run_repository_checks(repository: Path, frontend: Path, policy_path: Path) -> None:
    policy = load_policy(policy_path)
    check_shipped_json(frontend)
    check_markdown_links(repository)
    check_document_status(repository, policy["active_documents"])
    check_document_routes(repository)
    check_import_boundaries(frontend / "code", policy)
    check_declared_third_party_imports(
        frontend,
        frontend / "packaging" / "python_dependency_groups.json",
    )
    check_workflow_dependency_installs(
        sorted((repository / ".github" / "workflows").glob("*.yml"))
    )
    check_workflow_action_pins(
        sorted((repository / ".github" / "workflows").glob("*.yml"))
    )
