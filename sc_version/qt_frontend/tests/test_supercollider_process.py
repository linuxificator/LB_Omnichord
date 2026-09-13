from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from supercollider_config import load_supercollider_config  # noqa: E402
from supercollider_platform_adapter import (  # noqa: E402
    SuperColliderProcessError,
    SuperColliderSupervisor,
    locate_supercollider_runtime,
    pipewire_jack_prefix,
)


class SuperColliderProcessTests(unittest.TestCase):
    def test_pipewire_uses_distribution_jack_wrapper(self) -> None:
        active = Mock(returncode=0)
        with (
            patch(
                "supercollider_platform_adapter.subprocess.run",
                return_value=active,
            ),
            patch(
                "supercollider_platform_adapter.shutil.which",
                side_effect=lambda name: {
                    "systemctl": "/usr/bin/systemctl",
                    "pw-jack": "/usr/bin/pw-jack",
                }.get(name),
            ),
        ):
            self.assertEqual(pipewire_jack_prefix(), ("/usr/bin/pw-jack",))

    def test_pipewire_without_jack_wrapper_is_rejected(self) -> None:
        active = Mock(returncode=0)
        with (
            patch(
                "supercollider_platform_adapter.subprocess.run",
                return_value=active,
            ),
            patch(
                "supercollider_platform_adapter.shutil.which",
                side_effect=lambda name: (
                    "/usr/bin/systemctl" if name == "systemctl" else None
                ),
            ),
            self.assertRaisesRegex(
                SuperColliderProcessError, "pw-jack is unavailable"
            ),
        ):
            pipewire_jack_prefix(environment={})

    def test_bundled_runtime_is_resolved_as_one_complete_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in (
                root / "bin" / "sclang",
                root / "bin" / "scsynth",
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            (root / "share" / "SuperCollider" / "SCClassLibrary").mkdir(
                parents=True
            )
            (root / "lib" / "SuperCollider" / "plugins").mkdir(parents=True)

            runtime = locate_supercollider_runtime(root)

            self.assertEqual(runtime.sclang, root / "bin" / "sclang")
            self.assertEqual(runtime.scsynth, root / "bin" / "scsynth")
            self.assertEqual(
                runtime.class_library,
                root / "share" / "SuperCollider" / "SCClassLibrary",
            )

    def test_incomplete_bundled_runtime_is_rejected_before_launch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                SuperColliderProcessError, "runtime is incomplete"
            ):
                locate_supercollider_runtime(Path(directory))

    def test_supervisor_uses_exact_server_plugins_and_private_class_path(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            runtime = base / "runtime"
            engine = base / "engine"
            engine.mkdir()
            (engine / "bootstrap.scd").touch()
            for path in (
                runtime / "bin" / "sclang",
                runtime / "bin" / "scsynth",
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            class_library = runtime / "share" / "SuperCollider" / "SCClassLibrary"
            plugins = runtime / "lib" / "SuperCollider" / "plugins"
            class_library.mkdir(parents=True)
            plugins.mkdir(parents=True)
            config = load_supercollider_config(
                ROOT / "config" / "supercollider.json"
            )
            process = Mock()
            process.poll.return_value = 0
            with (
                patch(
                    "supercollider_platform_adapter.pipewire_jack_prefix",
                    return_value=(),
                ),
                patch(
                    "supercollider_platform_adapter.subprocess.Popen",
                    return_value=process,
                ) as popen,
            ):
                supervisor = SuperColliderSupervisor(
                    engine_root=engine,
                    config=config,
                    runtime_root=runtime,
                )
                supervisor.start()
                command = popen.call_args.args[0]
                environment = popen.call_args.kwargs["env"]
                language_config = Path(command[command.index("-l") + 1])
                self.assertIn(str(class_library), language_config.read_text())
                self.assertEqual(
                    environment["OMNICHORD_SC_SYNTH_PROGRAM"],
                    str(runtime / "bin" / "scsynth"),
                )
                self.assertEqual(
                    environment["OMNICHORD_SC_PLUGIN_PATH"], str(plugins)
                )
                self.assertEqual(command[-2:], ["-D", str(engine / "bootstrap.scd")])
                supervisor.stop()


if __name__ == "__main__":
    unittest.main()
