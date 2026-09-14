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
from frontend_config import load_frontend_config  # noqa: E402
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
    "pitch_bend",
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
        "frontend_config": config,
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
            load_frontend_config=load_frontend_config,
            load_defaults=unused,
            load_chords=lambda _path: (),
            load_synth_catalog=lambda _path: ([], 0, 0, 0),
            load_rhythm_catalog=lambda _path: (),
            load_bass_riffs=lambda *_args, **_kwargs: (),
            load_title_config=unused,
            load_intonation_table=lambda _path: (),
            client_factory=client_factory("supercollider"),
            midi_input_port=lambda _sink, _config: None,
            osc_input_port=lambda _sink, _config: None,
            private_files_dir=lambda: root / "private",
            resolve_package_runtime=lambda **_kwargs: RuntimeOverrides(),
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

    def test_graph_uses_user_frontend_config_and_one_engine_factory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_dir = root / "config"
            config_dir.mkdir()
            shipped = json.loads(
                (ROOT / "config" / "frontend.json").read_text(encoding="utf-8")
            )
            shipped_path = config_dir / "frontend.json"
            shipped_path.write_text(json.dumps(shipped), encoding="utf-8")
            user_dir = root / "user"
            user_dir.mkdir()
            user_config = copy.deepcopy(shipped)
            user_config["midi"]["voices_per_row"] = 6
            (user_dir / "frontend.json").write_text(
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
                arguments(shipped_path),
                dependencies,
                self.resources(),
                user_config_dir=user_dir,
            )

        self.assertEqual([kind for kind, _kwargs in calls], ["supercollider"])
        self.assertIs(graph.client, backend_calls[0]["client"])
        self.assertIs(
            backend_calls[0]["midi_input_port_factory"],
            dependencies.midi_input_port,
        )
        self.assertIs(
            backend_calls[0]["osc_input_port_factory"],
            dependencies.osc_input_port,
        )
        self.assertEqual(graph.frontend_config.midi_voices_per_row, 6)
        self.assertIs(
            calls[0][1]["frontend_config"],
            graph.frontend_config,
        )

    def test_graph_has_no_audio_transport_selection(self) -> None:
        calls: list[tuple[str, dict[str, Any]]] = []
        backend_calls: list[dict[str, Any]] = []
        dependencies = self.dependencies(
            root=ROOT,
            calls=calls,
            backend_calls=backend_calls,
        )
        with tempfile.TemporaryDirectory() as directory:
            user_dir = Path(directory)
            config = ROOT / "config" / "frontend.json"
            (user_dir / "frontend.json").write_text(
                config.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            graph = compose_application_graph(
                arguments(config),
                dependencies,
                self.resources(),
                user_config_dir=user_dir,
            )
        self.assertEqual([kind for kind, _data in calls], ["supercollider"])
        self.assertNotIn("socket_path", calls[0][1])
        self.assertNotIn("server_name", calls[0][1])
        self.assertIs(graph.client, backend_calls[0]["client"])

    def test_resource_loading_uses_injected_paths(self) -> None:
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
        warnings: list[tuple[str, str, str]] = []

        resources = load_application_resources(
            dependencies,
            user_config_dir=ROOT / "user-config",
            synth_fallback_notice=lambda *values: warnings.append(values),
        )

        self.assertEqual(resources.synths[0].key, "fallback")
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
