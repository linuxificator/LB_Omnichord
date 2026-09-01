from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[1]
QUALITY = FRONTEND / "tests" / "quality"
sys.path.insert(0, str(QUALITY))

from repository_checks import (  # noqa: E402
    QualityError,
    check_document_routes,
    check_document_status,
    check_declared_third_party_imports,
    check_import_boundaries,
    check_markdown_file,
    check_workflow_dependency_installs,
    check_workflow_action_pins,
    load_json,
    parse_python,
    run_repository_checks,
)


class QualityGuardrailFixtureTests(unittest.TestCase):
    def test_python_syntax_fixture_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.py"
            path.write_text("def broken(:\n", encoding="utf-8")
            with self.assertRaisesRegex(QualityError, "invalid Python syntax"):
                parse_python(path)

    def test_duplicate_json_key_fixture_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"value": 1, "value": 2}\n', encoding="utf-8")
            with self.assertRaisesRegex(QualityError, "duplicate JSON key"):
                load_json(path)

    def test_broken_markdown_link_fixture_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "contract.md"
            path.write_text("[missing](nowhere.md)\n", encoding="utf-8")
            with self.assertRaisesRegex(QualityError, "missing Markdown target"):
                check_markdown_file(path)

    def test_active_document_without_owner_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "contract.md"
            path.write_text(
                "# Contract\n\nStatus: active\nLast verified: 2026-09-01\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(QualityError, "lacks Owner"):
                check_document_status(root, ["contract.md"])

    def test_missing_design_route_fixture_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            design = root / "amysynth_version" / "design"
            design.mkdir(parents=True)
            (design / "README.md").write_text(
                "Read `missing.md`.\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(QualityError, "route target is missing"):
                check_document_routes(root)

    def test_amy_and_platform_import_fixtures_are_rejected(self) -> None:
        policy = {
            "amy_import_allowlist": ["service.py"],
            "platform_import_allowlist": {"ctypes": ["midi_adapter.py"]},
            "direct_platform_access_allowlist": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            code = Path(directory)
            (code / "core.py").write_text("import amy\n", encoding="utf-8")
            with self.assertRaisesRegex(QualityError, "AMY engine import"):
                check_import_boundaries(code, policy)
            (code / "core.py").write_text("import ctypes\n", encoding="utf-8")
            with self.assertRaisesRegex(QualityError, "platform import"):
                check_import_boundaries(code, policy)
            (code / "core.py").write_text(
                "import sys\nprint(sys.platform)\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(QualityError, "direct platform selection"):
                check_import_boundaries(code, policy)

    def test_undeclared_third_party_import_fixture_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            frontend = Path(directory)
            code = frontend / "code"
            code.mkdir()
            (code / "core.py").write_text("import surprise\n", encoding="utf-8")
            manifest = frontend / "dependencies.json"
            manifest.write_text('{"direct_imports": {}}\n', encoding="utf-8")
            with self.assertRaisesRegex(QualityError, "undeclared=.*surprise"):
                check_declared_third_party_imports(frontend, manifest)

    def test_workflow_package_literal_fixture_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workflow.yml"
            path.write_text(
                "run: python -m pip install surprise==1.2.3\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(QualityError, "package/version literal"):
                check_workflow_dependency_installs([path])

    def test_mutable_workflow_action_fixture_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workflow.yml"
            path.write_text(
                "steps:\n  - uses: actions/checkout@v4\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(QualityError, "not pinned to a full SHA"):
                check_workflow_action_pins([path])

            path.write_text(
                "steps:\n"
                "  - uses: actions/checkout@"
                "11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2\n"
                "  - uses: ./.github/workflows/local.yml\n",
                encoding="utf-8",
            )
            check_workflow_action_pins([path])

    def test_repository_baseline_passes(self) -> None:
        repository = FRONTEND.parents[1]
        run_repository_checks(
            repository,
            FRONTEND,
            QUALITY / "quality_policy.json",
        )
        baseline = json.loads(
            (QUALITY / "mypy_legacy_baseline.json").read_text(encoding="utf-8")
        )
        self.assertEqual(baseline["tool_version"], "2.3.1")
        self.assertEqual(baseline["total_errors"], 42)


if __name__ == "__main__":
    unittest.main()
