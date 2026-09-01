from __future__ import annotations

import ast
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
sys.path.insert(0, str(CODE))

import amy_serial  # noqa: E402
import amy_transport  # noqa: E402
import config_loader  # noqa: E402
import local_amy_service  # noqa: E402
import main  # noqa: E402


REQUIRED_SECTIONS = {
    "serial",
    "synth_ids",
    "voices",
    "default_synths",
    "buses",
    "drums",
    "rhythm",
    "performance",
    "midi_player",
    "midi_input",
    "amy_max_oscs",
    "amy_max_patterns",
    "amy_max_pattern_tags",
    "amy_max_pattern_instances",
    "amy_max_buses",
}


class ConfigAuthorityTests(unittest.TestCase):
    def test_obsolete_embedded_loader_and_dynamic_facade_are_absent(self) -> None:
        self.assertFalse(hasattr(amy_transport, "DEFAULT_CONFIG"))
        self.assertFalse(hasattr(amy_transport, "_deep_merge"))
        self.assertFalse(hasattr(amy_transport, "load_amy_config"))

        facade = ast.parse((CODE / "amy_serial.py").read_text(encoding="utf-8"))
        self.assertFalse(any(isinstance(node, (ast.For, ast.While)) for node in ast.walk(facade)))
        dynamic_calls = {
            node.func.id
            for node in ast.walk(facade)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertTrue({"vars", "globals"}.isdisjoint(dynamic_calls))
        self.assertIs(amy_serial.load_amy_config, config_loader.load_amy_config)

    def test_required_startup_sections_have_no_consumer_get_fallbacks(self) -> None:
        offenders: list[str] = []
        for name in (
            "amy_transport.py",
            "program_amy.py",
            "midi_player.py",
            "application_composition.py",
        ):
            path = CODE / name
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value in REQUIRED_SECTIONS
                    and ast.unparse(node.func.value)
                    in {
                        "config",
                        "self.config",
                        "client.config",
                        "self.client.config",
                        "cfg",
                        "midi_cfg",
                        "buses",
                    }
                ):
                    offenders.append(f"{name}:{node.lineno}:{node.args[0].value}")
        self.assertEqual(offenders, [])

    def test_pattern_layout_has_one_runtime_owner_and_independent_oracle(self) -> None:
        config = json.loads(
            (ROOT / "config" / "amy_config.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            config["rhythm"]["pattern_ranges"],
            {
                "fills": {"start": 0, "count": 936},
                "chords": {"start": 936, "count": 64},
                "drum_bases": {"start": 1000, "count": 24},
            },
        )
        transport = (CODE / "amy_transport.py").read_text(encoding="utf-8")
        for obsolete in (
            "CHORD_PATTERN_START",
            "CHORD_PATTERN_CAPACITY",
            "DRUM_BASE_PATTERN_START",
            "DRUM_PATTERN_CAPACITY",
        ):
            self.assertNotIn(obsolete, transport)

    def test_all_production_entrypoints_share_typed_resolution(self) -> None:
        dependencies = main.production_dependencies()
        self.assertIs(
            dependencies.load_resolved_config,
            config_loader.load_resolved_amy_config,
        )
        self.assertIs(
            local_amy_service.load_resolved_amy_config,
            config_loader.load_resolved_amy_config,
        )
        self.assertIs(
            amy_serial.load_resolved_amy_config,
            config_loader.load_resolved_amy_config,
        )


if __name__ == "__main__":
    unittest.main()
