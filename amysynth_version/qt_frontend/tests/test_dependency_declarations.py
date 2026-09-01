from __future__ import annotations

import ast
import json
import re
import sys
import unittest
from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[1]
REPOSITORY = FRONTEND.parents[1]
MANIFEST = FRONTEND / "packaging" / "python_dependency_groups.json"
SCAN_ROOTS = tuple(
    FRONTEND / name for name in ("code", "tests", "tools", "packaging")
)


def requirement_names(path: Path) -> set[str]:
    names: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("-r "):
            names.update(requirement_names(path.parent / line[3:].strip()))
            continue
        match = re.match(r"[A-Za-z0-9_.-]+", line)
        if match is None:
            raise AssertionError(f"unrecognized requirement in {path}: {raw_line}")
        names.add(match.group(0).casefold().replace("_", "-"))
    return names


class DependencyDeclarationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_every_direct_third_party_import_is_classified(self) -> None:
        python_files = sorted(
            path
            for root in SCAN_ROOTS
            for path in root.rglob("*.py")
            if not {"build", "deployment", ".venv"}.intersection(path.parts)
        )
        first_party = {path.stem for path in FRONTEND.rglob("*.py")}
        imported: set[str] = set()
        for path in python_files:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".", 1)[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".", 1)[0])

        third_party = imported - sys.stdlib_module_names - first_party
        self.assertEqual(
            third_party,
            set(self.manifest["direct_imports"]),
        )

    def test_requirement_groups_have_one_declared_owner(self) -> None:
        groups = self.manifest["requirement_groups"]
        resolved = {
            name: requirement_names(FRONTEND / relative)
            for name, relative in groups.items()
        }
        self.assertEqual(
            resolved["runtime"],
            {"pyside6", "pyserial", "fastjsonschema"},
        )
        self.assertEqual(
            resolved["build"],
            {"pyside6", "pyserial", "fastjsonschema", "pyinstaller"},
        )
        self.assertEqual(
            resolved["test_quality"],
            {
                "pyside6",
                "pyserial",
                "fastjsonschema",
                "numpy",
                "ruff",
                "mypy",
                "types-pyserial",
            },
        )
        self.assertEqual(
            resolved["android_host"],
            {"pyside6", "pyserial", "fastjsonschema", "cython"},
        )

        for import_root, record in self.manifest["direct_imports"].items():
            if "distribution" not in record:
                self.assertIn("component_exception", record, import_root)
                continue
            owner = record["owner"]
            distribution = record["distribution"].casefold().replace("_", "-")
            self.assertIn(distribution, resolved[owner], import_root)

        for tool, record in self.manifest["invoked_python_tools"].items():
            owner = record["owner"]
            distribution = record["distribution"].casefold().replace("_", "-")
            self.assertIn(distribution, resolved[owner], tool)

    def test_workflows_consume_declared_groups_and_shared_amy_pin(self) -> None:
        regression = (
            REPOSITORY / ".github" / "workflows" / "amy-regression.yml"
        ).read_text(encoding="utf-8")
        release = (
            REPOSITORY / ".github" / "workflows" / "desktop-release.yml"
        ).read_text(encoding="utf-8")
        esp32 = (
            REPOSITORY / ".github" / "workflows" / "esp32p4-build.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("requirements-test.txt", regression)
        self.assertIn("requirements-build.txt", release)
        self.assertIn("requirements-android-host.txt", release)
        self.assertNotIn("pyinstaller==6.22.2", release.casefold())
        self.assertNotIn("cython==0.29.36", release.casefold())

        amy = self.manifest["component_exceptions"]["lb_amy"]
        for workflow in (regression, release):
            self.assertIn(f"AMY_RELEASE_BRANCH: {amy['release_branch']}", workflow)
            self.assertIn(f"AMY_COMMIT: {amy['commit']}", workflow)
        self.assertIn(f"AMY_RELEASE_BRANCH: {amy['release_branch']}", esp32)
        self.assertIn(f"AMY_REF: {amy['commit']}", esp32)


if __name__ == "__main__":
    unittest.main()
