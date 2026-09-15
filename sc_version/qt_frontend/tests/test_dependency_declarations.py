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
        # The SC edition owns Python tooling beside qt_frontend as well (for
        # example the sample-bank compiler and inventory tools).  Those are
        # repository modules, not undeclared PyPI dependencies.
        first_party = {
            path.stem
            for path in REPOSITORY.rglob("*.py")
            if not {"build", "dist", "deployment", ".venv"}.intersection(path.parts)
        }
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
            resolved["portable"],
            {"fastjsonschema", "python-osc", "dulwich", "urllib3"},
        )
        self.assertEqual(
            resolved["runtime"],
            {
                "pyside6", "fastjsonschema", "python-osc",
                "zeroconf", "dulwich", "urllib3",
            },
        )
        self.assertEqual(
            resolved["source_runtime"],
            {
                "pyside6",
                "fastjsonschema",
                "python-osc",
                "zeroconf",
                "dulwich",
                "urllib3",
                "numpy",
                "soundfile",
            },
        )
        self.assertEqual(
            resolved["build"],
            {
                "pyside6",
                "fastjsonschema",
                "python-osc",
                "zeroconf",
                "dulwich",
                "urllib3",
                "pyinstaller",
            },
        )
        self.assertEqual(
            resolved["test_quality"],
            {
                "pyside6",
                "fastjsonschema",
                "python-osc",
                "zeroconf",
                "dulwich",
                "urllib3",
                "numpy",
                "ruff",
                "mypy",
                "coverage",
            },
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

        for dependency, record in self.manifest["transitive_dependencies"].items():
            owner = record["owner"]
            distribution = record["distribution"].casefold().replace("_", "-")
            self.assertIn(distribution, resolved[owner], dependency)

    def test_active_workflow_consumes_declared_sc_dependency_groups(self) -> None:
        release = (
            REPOSITORY / ".github" / "workflows" / "supercollider-release.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("requirements-test.txt", release)
        self.assertIn("requirements-source.txt", release)
        self.assertIn("requirements-build.txt", release)
        self.assertNotIn("pyinstaller==6.22.2", release.casefold())
        self.assertNotIn("requirements-android-host.txt", release)
        self.assertNotIn("packaging/release_inputs.py", release)
        self.assertNotIn("AMY_RELEASE_BRANCH:", release)


if __name__ == "__main__":
    unittest.main()
