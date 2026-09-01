from __future__ import annotations

import ast
import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
sys.path.insert(0, str(CODE))

from PySide6.QtCore import QMetaMethod  # noqa: E402

import app_core  # noqa: E402
import amy_serial  # noqa: E402
import config_loader  # noqa: E402
import local_amy_service  # noqa: E402
import main  # noqa: E402
from midi_control import PITCH_BEND_CONTROLLER  # noqa: E402
from midi_integration import InstrumentBackend  # noqa: E402
from midi_player import (  # noqa: E402
    MidiPlayerBackend,
    _MidiByteStreamParser,
    _MidiInputTechManager,
)
from midi_platform_profile import resolve_midi_tech_profile  # noqa: E402


MANIFEST_PATH = Path(__file__).with_name("characterization_contracts.json")


def _digest(values: list[str]) -> str:
    payload = json.dumps(
        values,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _qobject_surface(cls: type[object]) -> dict[str, list[str]]:
    meta = cls.staticMetaObject
    properties = [
        meta.property(index).name()
        for index in range(1, meta.propertyCount())
    ]
    methods = []
    for index in range(5, meta.methodCount()):
        method = meta.method(index)
        signature = bytes(method.methodSignature()).decode("utf-8")
        if (
            method.methodType() in (QMetaMethod.Signal, QMetaMethod.Slot)
            and not signature.startswith("_")
        ):
            methods.append(signature)
    return {"properties": properties, "methods": methods}


class RefactorCharacterizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_intended_public_qobject_surface_is_frozen(self) -> None:
        classes = {
            "InstrumentBackend": InstrumentBackend,
            "MidiPlayerBackend": MidiPlayerBackend,
        }
        expected = self.manifest["public_qobject_surface"]
        for name, qobject_class in classes.items():
            with self.subTest(qobject=name):
                actual = _qobject_surface(qobject_class)
                self.assertEqual(
                    len(actual["properties"]),
                    expected[name]["property_count"],
                )
                self.assertEqual(
                    _digest(actual["properties"]),
                    expected[name]["property_sha256"],
                    actual["properties"],
                )
                self.assertEqual(
                    len(actual["methods"]),
                    expected[name]["method_count"],
                )
                self.assertEqual(
                    _digest(actual["methods"]),
                    expected[name]["method_sha256"],
                    actual["methods"],
                )

    def test_supported_python_entrypoints_share_one_loader_object(self) -> None:
        canonical = config_loader.load_amy_config
        self.assertIs(amy_serial.load_amy_config, canonical)
        self.assertIs(main.load_amy_config, canonical)
        self.assertIs(app_core.load_amy_config, canonical)
        self.assertIs(
            local_amy_service.load_resolved_amy_config,
            config_loader.load_resolved_amy_config,
        )

        expected = canonical(ROOT / "config" / "amy_config.json")
        for loader in (
            amy_serial.load_amy_config,
            main.load_amy_config,
            app_core.load_amy_config,
        ):
            with self.subTest(loader=loader.__module__):
                self.assertEqual(loader(ROOT / "config" / "amy_config.json"), expected)

    def test_headless_entrypoint_uses_the_shared_composition_graph(self) -> None:
        path = ROOT / "tests" / "integration" / "headless_app.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = {
            (node.module, alias.name)
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        self.assertIn(
            ("application_composition", "compose_application_graph"),
            imports,
        )
        self.assertIn(
            ("application_composition", "load_application_resources"),
            imports,
        )

    def test_unmodified_shipped_config_resolves_for_five_profiles(self) -> None:
        config = config_loader.load_amy_config(
            ROOT / "config" / "amy_config.json"
        )
        midi_config = config["midi_input"]
        expected = {
            ("wayland", "linux"): (
                "linux",
                ("alsa_raw", "alsa_seq", "oss_midi"),
            ),
            ("cocoa", "darwin"): ("darwin", ("coremidi",)),
            ("windows", "win32"): ("win32", ("winmm",)),
            ("android", "android"): ("android", ("android_midi",)),
            ("offscreen", "freebsd14"): ("freebsd14", ()),
        }
        original = copy.deepcopy(config)
        for (qpa, runtime), (profile, keys) in expected.items():
            with self.subTest(qpa=qpa, runtime=runtime):
                resolved = resolve_midi_tech_profile(
                    midi_config["tech_profile"],
                    qpa,
                    runtime,
                )
                self.assertEqual(resolved, profile)
                techs = _MidiInputTechManager.platform_techs(
                    midi_config,
                    resolved,
                )
                self.assertEqual(
                    tuple(str(item["key"]) for item in techs),
                    keys,
                )
                self.assertEqual(config, original)

    def test_midi_stream_normalization_is_characterized(self) -> None:
        notes: list[tuple[int, int, int, bool]] = []
        controls: list[tuple[int, int, int]] = []
        parser = _MidiByteStreamParser(
            lambda *event: notes.append(event),
            lambda *event: controls.append(event),
        )
        state: dict[str, object] = {}

        # Split packets, running status, Note On velocity zero, real-time bytes,
        # SysEx suppression, CC and 14-bit pitch bend are all common adapter
        # inputs. The normalized output is the portable behavior to preserve.
        parser._parse_stream(bytes([0x91, 60]), state)
        parser._parse_stream(bytes([100, 61, 0, 0xF8]), state)
        parser._parse_stream(bytes([0xF0, 1, 2, 0xF7]), state)
        parser._parse_stream(bytes([0xB2, 74, 99, 0xE2, 0, 64]), state)

        self.assertEqual(
            notes,
            [
                (2, 60, 100, True),
                (2, 61, 0, False),
            ],
        )
        self.assertEqual(
            controls,
            [
                (3, 74, 99),
                (3, PITCH_BEND_CONTROLLER, 8192),
            ],
        )

    def test_manifested_behavior_contracts_exist_as_real_tests(self) -> None:
        for category in ("wire_contract_tests", "slider_regression_tests"):
            for route in self.manifest[category]:
                with self.subTest(category=category, route=route):
                    file_name, symbol = route.split("::", 1)
                    class_name, method_name = symbol.split(".", 1)
                    path = ROOT / "tests" / file_name
                    tree = ast.parse(
                        path.read_text(encoding="utf-8"),
                        filename=str(path),
                    )
                    classes = {
                        node.name: node
                        for node in tree.body
                        if isinstance(node, ast.ClassDef)
                    }
                    self.assertIn(class_name, classes)
                    methods = {
                        node.name
                        for node in classes[class_name].body
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    }
                    self.assertIn(method_name, methods)


if __name__ == "__main__":
    unittest.main()
