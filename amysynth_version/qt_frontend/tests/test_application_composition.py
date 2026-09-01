from __future__ import annotations

import ast
import copy
import json
import sys
import tempfile
import unittest
from argparse import Namespace
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
sys.path.insert(0, str(CODE))

from application_composition import (  # noqa: E402
    ApplicationDependencies,
    ApplicationResources,
    FrontendPaths,
    compose_application_graph,
    load_application_resources,
)
from config_loader import load_resolved_amy_config  # noqa: E402
from package_test_hooks import PackageTestHooks  # noqa: E402
from runtime_platform_adapters import RuntimeOverrides  # noqa: E402


ADDRESSES = (
    "chord_state",
    "chord_manual",
    "chord_amp",
    "strum_amp",
    "bass_amp",
    "percussion_amp",
    "reverb",
    "master_volume",
    "chord_synth",
    "chord_params",
    "strum_synth",
    "strum_params",
    "bass_synth",
    "bass_params",
    "bass_running",
    "strum_note",
    "rhythm_config",
    "rhythm_running",
    "rhythm_chord_enabled",
    "panic",
)


class FakeClient:
    def __init__(self, kind: str, kwargs: dict[str, Any]) -> None:
        self.kind = kind
        self.kwargs = kwargs
        self.messages: list[tuple[str, Any]] = []
        self.closed = False

    def send_message(self, address: str, value: Any) -> None:
        self.messages.append((address, value))

    def close(self) -> None:
        self.closed = True


def arguments(config: Path, **overrides: Any) -> Namespace:
    values: dict[str, Any] = {
        "amy_config": config,
        "serial_port": None,
        "serial_baud": None,
        "amy_socket": None,
        "amy_local_name": None,
        "debug": False,
        "debug_file": None,
    }
    values.update({f"{name}_address": f"/{name}" for name in ADDRESSES})
    values.update(overrides)
    return Namespace(**values)


class ApplicationCompositionTests(unittest.TestCase):
    def dependencies(
        self,
        *,
        root: Path,
        calls: list[tuple[str, dict[str, Any]]],
        backend_calls: list[dict[str, Any]],
    ) -> ApplicationDependencies:
        def client_factory(kind: str):
            def create(**kwargs: Any) -> FakeClient:
                calls.append((kind, kwargs))
                return FakeClient(kind, kwargs)

            return create

        def backend_factory(**kwargs: Any) -> SimpleNamespace:
            backend_calls.append(kwargs)
            return SimpleNamespace(
                initialize=lambda: None,
                send_initial_state=lambda: None,
            )

        unused = lambda _path: {}  # noqa: E731
        return ApplicationDependencies(
            paths=FrontendPaths.from_root(root),
            load_resolved_config=load_resolved_amy_config,
            load_defaults=unused,
            load_chords=lambda _path: (),
            load_synth_catalog=lambda _path: ([], 0, 0, 0),
            load_rhythm_catalog=lambda _path: (),
            load_bass_riffs=lambda *_args, **_kwargs: (),
            load_title_config=unused,
            load_intonation_table=lambda _path: (),
            serial_client=client_factory("serial"),
            socket_client=client_factory("socket"),
            local_client=client_factory("local"),
            midi_input_port=lambda _sink, _config: None,
            private_files_dir=lambda: root / "private",
            resolve_package_runtime=lambda **kwargs: RuntimeOverrides(
                kwargs["amy_socket"],
                kwargs["amy_local_name"],
                kwargs["package_smoke_test"],
            ),
            package_test_hooks=lambda enabled: PackageTestHooks(enabled, None),
            display_diagnostics=lambda qpa: (f"QPA {qpa}",),
            backend=backend_factory,
        )

    @staticmethod
    def resources() -> ApplicationResources:
        return ApplicationResources(
            defaults={},
            chords=(),
            synths=(),
            rhythms=(),
            bass_riffs=(),
            title={},
            intonation_eq=(),
            intonation_harm=(),
            intonation_jv=(),
            default_chord_synth_index=0,
            default_strum_synth_index=0,
            default_bass_synth_index=0,
        )

    def test_same_graph_accepts_fake_ports_and_records_cli_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_dir = root / "config"
            config_dir.mkdir()
            shipped = json.loads(
                (ROOT / "config" / "amy_config.json").read_text(encoding="utf-8")
            )
            shipped_path = config_dir / "amy_config.json"
            shipped_path.write_text(json.dumps(shipped), encoding="utf-8")
            user_dir = root / "user"
            user_dir.mkdir()
            user_config = copy.deepcopy(shipped)
            user_config["serial"]["baud"] = 460_800
            (user_dir / "amy_config.json").write_text(
                json.dumps(user_config), encoding="utf-8"
            )
            calls: list[tuple[str, dict[str, Any]]] = []
            backend_calls: list[dict[str, Any]] = []
            dependencies = self.dependencies(
                root=root,
                calls=calls,
                backend_calls=backend_calls,
            )

            graph = compose_application_graph(
                arguments(
                    shipped_path,
                    serial_port="COM7",
                    serial_baud=230_400,
                ),
                dependencies,
                self.resources(),
                user_config_dir=user_dir,
            )

        self.assertEqual([kind for kind, _kwargs in calls], ["serial"])
        self.assertIs(graph.client, backend_calls[0]["client"])
        self.assertIs(
            backend_calls[0]["midi_input_port_factory"],
            dependencies.midi_input_port,
        )
        self.assertEqual(graph.resolved_config.transport.serial_port, "COM7")
        self.assertEqual(graph.resolved_config.transport.serial_baud, 230_400)
        self.assertEqual(
            graph.resolved_config.provenance.runtime_override_paths,
            ("$.serial.port", "$.serial.baud"),
        )
        self.assertIsNone(calls[0][1]["config"])
        self.assertIs(
            calls[0][1]["resolved_config"],
            graph.resolved_config,
        )

    def test_transport_selection_constructs_only_the_selected_fake_port(self) -> None:
        calls: list[tuple[str, dict[str, Any]]] = []
        backend_calls: list[dict[str, Any]] = []
        dependencies = self.dependencies(
            root=ROOT,
            calls=calls,
            backend_calls=backend_calls,
        )
        with tempfile.TemporaryDirectory() as directory:
            user_dir = Path(directory)
            config = ROOT / "config" / "amy_config.json"
            (user_dir / "amy_config.json").write_text(
                config.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            for kwargs, expected, endpoint_key in (
                ({"amy_socket": "~/amy.sock"}, "socket", "socket_path"),
                ({"amy_local_name": "lb-amy"}, "local", "server_name"),
            ):
                with self.subTest(expected=expected):
                    calls.clear()
                    backend_calls.clear()
                    graph = compose_application_graph(
                        arguments(config, **kwargs),
                        dependencies,
                        self.resources(),
                        user_config_dir=user_dir,
                    )
                    self.assertEqual(graph.client_selection.kind, expected)
                    self.assertEqual([kind for kind, _data in calls], [expected])
                    self.assertIn(endpoint_key, calls[0][1])

            with self.assertRaisesRegex(ValueError, "select either"):
                compose_application_graph(
                    arguments(config, amy_socket="a", amy_local_name="b"),
                    dependencies,
                    self.resources(),
                    user_config_dir=user_dir,
                )

    def test_resource_loading_uses_injected_paths_and_preserves_checkpoint_order(self) -> None:
        calls: list[tuple[str, Path]] = []
        client_calls: list[tuple[str, dict[str, Any]]] = []
        backend_calls: list[dict[str, Any]] = []
        dependencies = self.dependencies(
            root=ROOT,
            calls=client_calls,
            backend_calls=backend_calls,
        )
        synths = [SimpleNamespace(key="fallback", label="Fallback")]
        rhythms = (SimpleNamespace(key="r1"),)
        chords = (SimpleNamespace(suffix="major"),)
        dependencies = replace(
            dependencies,
            load_defaults=lambda path: (
                calls.append(("defaults", path)) or {"synths": {}}
            ),
            load_chords=lambda path: calls.append(("chords", path)) or chords,
            load_synth_catalog=lambda path: (
                calls.append(("synths", path)) or (synths, 0, 0, 0)
            ),
            load_rhythm_catalog=lambda path: (
                calls.append(("rhythms", path)) or rhythms
            ),
            load_bass_riffs=lambda path, **_kwargs: (
                calls.append(("bass", path)) or ()
            ),
            load_title_config=lambda path: calls.append(("title", path)) or {},
            load_intonation_table=lambda path: (
                calls.append(("intonation", path)) or ()
            ),
        )
        checkpoints: list[str] = []
        warnings: list[tuple[str, str, str]] = []

        resources = load_application_resources(
            dependencies,
            user_config_dir=ROOT / "user-config",
            checkpoint=checkpoints.append,
            synth_fallback_notice=lambda *values: warnings.append(values),
        )

        self.assertEqual(resources.synths[0].key, "fallback")
        self.assertEqual(checkpoints[-1], "startup-synths-selected")
        self.assertEqual(len(warnings), 3)
        self.assertEqual(calls[0][1], ROOT / "user-config" / "defaults.json")
        self.assertEqual(calls[1][1], ROOT / "music" / "chords.csv")

    def test_entrypoint_contains_no_wildcard_or_module_monkey_patch(self) -> None:
        tree = ast.parse((CODE / "main.py").read_text(encoding="utf-8"))
        wildcard_imports = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and any(alias.name == "*" for alias in node.names)
        ]
        module_assignments = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            for target in (
                node.targets if isinstance(node, ast.Assign) else [node.target]
            )
            if isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "app_core"
        ]
        self.assertEqual(wildcard_imports, [])
        self.assertEqual(module_assignments, [])


if __name__ == "__main__":
    unittest.main()
