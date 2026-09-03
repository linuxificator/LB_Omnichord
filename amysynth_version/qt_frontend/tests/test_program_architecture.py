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
    def test_package_input_stimulus_is_not_generated_by_production_code(self) -> None:
        package_smoke = CODE / "package_smoke.py"
        tree = ast.parse(package_smoke.read_text(encoding="utf-8"))
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertNotIn("socket", imports)
        self.assertTrue(
            calls.isdisjoint(
                {"sendto", "injectControl", "injectButton", "injectOscControl"}
            )
        )
        self.assertTrue(
            (ROOT / "tests" / "support" / "external_input_peer.py").is_file()
        )

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
