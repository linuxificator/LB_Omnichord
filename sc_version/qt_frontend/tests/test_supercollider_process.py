from __future__ import annotations

import json
from pathlib import Path
import shlex
import subprocess
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
    server_program_command,
)


class SuperColliderProcessTests(unittest.TestCase):
    def test_pipewire_uses_distribution_jack_wrapper(self) -> None:
        active = Mock(returncode=0)
        with (
            patch(
                "supercollider_platform_adapter.subprocess.run",
                return_value=active,
            ) as run,
            patch(
                "supercollider_platform_adapter.shutil.which",
                side_effect=lambda name: {
                    "systemctl": "/usr/bin/systemctl",
                    "pw-jack": "/usr/bin/pw-jack",
                }.get(name),
            ),
        ):
            self.assertEqual(
                pipewire_jack_prefix(
                    environment={
                        "PATH": "/usr/bin",
                        "LD_LIBRARY_PATH": "/packaged/lib",
                        "LD_PRELOAD": "/packaged/preload.so",
                    }
                ),
                ("/usr/bin/pw-jack",),
            )
            environment = run.call_args.kwargs["env"]
            self.assertEqual(environment, {"PATH": "/usr/bin"})
            self.assertEqual(run.call_args.args[0][0], "/usr/bin/systemctl")

    def test_server_program_command_is_shell_safe_on_each_platform(self) -> None:
        path = Path("/tmp/SC Runtime/bin/supernova")
        self.assertEqual(
            server_program_command(path, platform="linux"),
            f"exec {shlex.quote(str(path.resolve()))}",
        )
        self.assertEqual(
            server_program_command(path, platform="darwin"),
            f"exec {shlex.quote(str(path.resolve()))}",
        )
        self.assertEqual(
            server_program_command(path, platform="win32"),
            subprocess.list2cmdline([str(path.resolve())]),
        )

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
                root / "bin" / "supernova",
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            (root / "share" / "SuperCollider" / "SCClassLibrary").mkdir(
                parents=True
            )
            (root / "lib" / "SuperCollider" / "plugins").mkdir(parents=True)

            runtime = locate_supercollider_runtime(root)

            self.assertEqual(runtime.sclang, (root / "bin" / "sclang").resolve())
            self.assertEqual(runtime.scsynth, (root / "bin" / "scsynth").resolve())
            self.assertEqual(
                runtime.supernova, (root / "bin" / "supernova").resolve()
            )
            self.assertEqual(
                runtime.class_library,
                (root / "share" / "SuperCollider" / "SCClassLibrary").resolve(),
            )

    def test_incomplete_bundled_runtime_is_rejected_before_launch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                SuperColliderProcessError, "runtime is incomplete"
            ):
                locate_supercollider_runtime(Path(directory))

    def test_official_macos_bundle_layout_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "SuperCollider.app"
            paths = (
                root / "Contents" / "MacOS" / "sclang",
                root / "Contents" / "Resources" / "scsynth",
                root / "Contents" / "Resources" / "supernova",
                root / "Contents" / "Resources" / "SCClassLibrary",
                root / "Contents" / "Resources" / "plugins",
            )
            for path in paths[:3]:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            for path in paths[3:]:
                path.mkdir(parents=True)
            runtime = locate_supercollider_runtime(root)
            self.assertEqual(runtime.sclang, paths[0].resolve())
            self.assertEqual(runtime.scsynth, paths[1].resolve())
            self.assertEqual(runtime.supernova, paths[2].resolve())

    def test_official_windows_archive_layout_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("sclang.exe", "scsynth.exe", "supernova.exe"):
                (root / name).touch()
            (root / "SCClassLibrary").mkdir()
            (root / "plugins").mkdir()
            runtime = locate_supercollider_runtime(root)
            self.assertEqual(runtime.sclang, (root / "sclang.exe").resolve())
            self.assertEqual(runtime.scsynth, (root / "scsynth.exe").resolve())
            self.assertEqual(runtime.supernova, (root / "supernova.exe").resolve())

    def test_runtime_without_supernova_is_rejected_before_launch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in (root / "bin" / "sclang", root / "bin" / "scsynth"):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            (root / "share" / "SuperCollider" / "SCClassLibrary").mkdir(
                parents=True
            )
            (root / "lib" / "SuperCollider" / "plugins").mkdir(parents=True)
            with self.assertRaisesRegex(
                SuperColliderProcessError, "runtime is incomplete"
            ):
                locate_supercollider_runtime(root)

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
                runtime / "bin" / "supernova",
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
                self.assertIn("-a", command)
                self.assertIn(
                    json.dumps(str(class_library.resolve())),
                    language_config.read_text(),
                )
                self.assertEqual(
                    environment["OMNICHORD_SC_SYNTH_PROGRAM"],
                    server_program_command(runtime / "bin" / "supernova"),
                )
                self.assertEqual(
                    environment["OMNICHORD_SC_PLUGIN_PATH"],
                    str(plugins.resolve()),
                )
                self.assertEqual(
                    environment["OMNICHORD_SC_MAX_GESTURE_VOICES"],
                    "24",
                )
                self.assertEqual(
                    command[-2:], ["-D", str((engine / "bootstrap.scd").resolve())]
                )
                supervisor.stop()


if __name__ == "__main__":
    unittest.main()
