from __future__ import annotations

import ast
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))

from config_loader import load_amy_config, load_resolved_amy_config  # noqa: E402
from synth_programs import resolve_program  # noqa: E402


class ProgramArchitectureTests(unittest.TestCase):
    @staticmethod
    def _class_method(
        tree: ast.Module,
        class_name: str,
        method_name: str,
    ) -> ast.FunctionDef:
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for child in node.body:
                    if isinstance(child, ast.FunctionDef) and child.name == method_name:
                        return child
        raise AssertionError(f"missing {class_name}.{method_name}")

    def test_package_input_stimulus_is_not_generated_by_production_code(self) -> None:
        self.assertFalse((CODE / "package_smoke.py").exists())
        self.assertFalse((CODE / "package_test_hooks.py").exists())
        self.assertTrue(
            (ROOT / "tests" / "support" / "external_input_peer.py").is_file()
        )

    def test_synthetic_input_hooks_exist_only_in_test_support(self) -> None:
        forbidden = (
            "injectMidiControl",
            "injectMidiPitchBend",
            "injectMidiButton",
            "injectMidiNote",
            "injectOscControl",
            "OMNICHORD_TEST_MIDI_CC_LOG",
            "testCcLogging",
            "testLogControl",
        )
        for path in CODE.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            for marker in forbidden:
                with self.subTest(path=path.name, marker=marker):
                    self.assertNotIn(marker, source)
        adapter = ROOT / "tests" / "support" / "backend_control_surface.py"
        self.assertTrue(adapter.is_file())
        self.assertIn("injectMidiControl", adapter.read_text(encoding="utf-8"))

    def test_shipped_launchers_contain_no_test_mode_or_assertions(self) -> None:
        shipped = (
            ROOT / "packaging" / "appimage_entry.py",
            ROOT / "packaging" / "windows" / "run_windows.ps1",
            ROOT / "packaging" / "windows" / "amy_service.c",
        )
        forbidden = (
            "package-smoke-test",
            "OMNICHORD_PACKAGE_SMOKE",
            "lb-android-package-smoke",
            "run_self_test",
            '"--self-test"',
            "requiredCheckpoints",
        )
        for path in shipped:
            source = path.read_text(encoding="utf-8")
            for marker in forbidden:
                with self.subTest(path=path.name, marker=marker):
                    self.assertNotIn(marker, source)

    def test_package_scenarios_have_one_test_side_owner(self) -> None:
        workflow = (
            ROOT.parents[1] / ".github" / "workflows" / "desktop-release.yml"
        ).read_text(encoding="utf-8")
        android = (
            ROOT / "packaging" / "android" / "test_android_apk.sh"
        ).read_text(encoding="utf-8")
        evidence = (
            ROOT / "tests" / "support" / "package_evidence.py"
        ).read_text(encoding="utf-8")
        self.assertGreaterEqual(workflow.count("package_evidence.py"), 3)
        self.assertIn("package_evidence.py", android)
        self.assertNotIn("for checkpoint", workflow)
        self.assertNotIn("requiredCheckpoints", workflow)
        for scenario in (
            "artifact-present",
            "package-content-policy",
            "qml-import-policy",
            "external-input-process-contract",
            "packaged-runtime",
            "rendered-ui",
            "regression-prerequisite",
        ):
            with self.subTest(scenario=scenario):
                self.assertEqual(evidence.count(f'"{scenario}"'), 1)

    def test_portable_input_contract_has_no_platform_branches(self) -> None:
        contract = (
            ROOT / "tests" / "contracts" / "test_external_input_processes.py"
        ).read_text(encoding="utf-8")
        for platform_probe in (
            "sys.platform",
            "os.name",
            "platform.system",
            "platform.machine",
            "runner.os",
        ):
            with self.subTest(platform_probe=platform_probe):
                self.assertNotIn(platform_probe, contract)

        runner = (ROOT / "tests" / "run_tests.py").read_text(encoding="utf-8")
        self.assertIn('"portable-input-processes"', runner)
        self.assertIn('"platform-input-linux"', runner)

    def test_shipped_json_is_the_authoritative_config(self) -> None:
        raw = json.loads(
            (ROOT / "config" / "amy_config.json").read_text(encoding="utf-8")
        )
        self.assertNotIn("synth_patches", raw)
        self.assertIn("synth_programs", raw)

        public_transport = (CODE / "amy_serial.py").read_text(encoding="utf-8")
        self.assertNotIn("DEFAULT_CONFIG", public_transport.split("for _name", 1)[0])
        self.assertIn("from config_loader import load_amy_config", public_transport)

    def test_sequencer_execution_mechanics_remain_owned_by_amy(self) -> None:
        transport_source = (CODE / "amy_transport.py").read_text(encoding="utf-8")
        planner_source = (CODE / "rhythm_command_plan.py").read_text(
            encoding="utf-8"
        )
        transport_tree = ast.parse(transport_source)
        planner_tree = ast.parse(planner_source)

        # Persistent fill definitions are authored at construction only. A
        # transport Start resets runtime state and must not resend the static
        # catalogue.
        preload_owners: list[str] = []
        for method in (
            node
            for class_node in transport_tree.body
            if isinstance(class_node, ast.ClassDef)
            and class_node.name == "AmySerialClient"
            for node in class_node.body
            if isinstance(node, ast.FunctionDef)
        ):
            if any(
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr == "_preload_drum_library"
                for call in ast.walk(method)
            ):
                preload_owners.append(method.name)
        self.assertEqual(preload_owners, ["__init__"])

        # Beat-accurate phrases are pure wire plans. Host scheduling remains
        # valid for manual strum/tail ownership, but not for rhythm sequences.
        self.assertFalse(any(
            isinstance(node, (ast.Import, ast.ImportFrom))
            and any(alias.name in {"time", "threading"} for alias in node.names)
            for node in planner_tree.body
        ))
        rhythm_methods = (
            "_chord_sequence_plan",
            "_drum_activity_commands",
            "_fill_schedule_commands",
            "_drum_commands",
            "_replace_drums",
            "_start_rhythm",
        )
        for method_name in rhythm_methods:
            method = self._class_method(
                transport_tree,
                "AmySerialClient",
                method_name,
            )
            with self.subTest(method=method_name):
                self.assertFalse(any(
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in {"schedule", "singleShot"}
                    for node in ast.walk(method)
                ))

        # AMY owns sequence definitions, execution phase, revisions and note
        # lifetime. LB emits reset/definition/control transactions and keeps
        # none of that runtime state (including no authoring high-water mark).
        for forbidden in (
            "high_water",
            "current_amy_tick",
            "amy_sequencer_tick",
            "sequence_execution_generation",
            "active_sequence_revision",
            "sequence_end_tick",
        ):
            self.assertNotIn(forbidden, transport_source)
            self.assertNotIn(forbidden, planner_source)

        # Repeating ordinary H tags is AMY's cumulative definition syntax.
        # Keeping this guard prevents the retired HA adapter from returning.
        self.assertNotIn('f"HA', planner_source)

    def test_frontend_sequencer_path_is_wire_only(self) -> None:
        for filename in (
            "amy_serial.py",
            "amy_transport.py",
            "program_amy.py",
            "rhythm_command_plan.py",
        ):
            tree = ast.parse((CODE / filename).read_text(encoding="utf-8"))
            imported_modules = {
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, (ast.Import, ast.ImportFrom))
                for alias in node.names
            }
            with self.subTest(filename=filename):
                self.assertNotIn("amy", imported_modules)

    def test_missing_config_is_an_error_not_a_hidden_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                load_amy_config(Path(directory) / "missing.json")

    def test_chord_voice_pools_cannot_underallocate_seven_note_arpeggios(self) -> None:
        config = json.loads(
            (ROOT / "config" / "amy_config.json").read_text(encoding="utf-8")
        )
        config["voices"]["rhythm_chord"] = 4
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "amy_config.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(
                ValueError,
                r"voices\.rhythm_chord must be at least 7",
            ):
                load_amy_config(path)

    def test_rom_programs_are_derived_from_stable_keys(self) -> None:
        config = load_resolved_amy_config(ROOT / "config" / "amy_config.json")
        juno = resolve_program("juno_036", config)
        dx7 = resolve_program("dx7_143", config)
        self.assertIsNotNone(juno)
        self.assertIsNotNone(dx7)
        self.assertEqual((juno.kind, juno.patch, juno.oscs_per_voice), ("rom_patch", 36, 6))
        self.assertEqual((dx7.kind, dx7.patch, dx7.oscs_per_voice), ("rom_patch", 143, 8))

    def test_physical_strings_is_a_real_karplus_strong_program(self) -> None:
        config = load_resolved_amy_config(ROOT / "config" / "amy_config.json")
        program = resolve_program("physical_strings", config)
        self.assertIsNotNone(program)
        self.assertEqual(program.kind, "karplus_strong")
        self.assertEqual(program.wave, 6)
        self.assertEqual(program.oscs_per_voice, 1)
        self.assertGreater(program.feedback, 0.9)
        self.assertLess(program.feedback, 1.0)


if __name__ == "__main__":
    unittest.main()
