from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
from typing import Mapping

from supercollider_config import SuperColliderRuntimeConfig


class SuperColliderProcessError(RuntimeError):
    """Raised before the UI starts when its owned SC runtime is unusable."""


@dataclass(frozen=True, slots=True)
class SuperColliderExecutables:
    sclang: Path
    scsynth: Path
    supernova: Path
    class_library: Path | None
    plugins: Path | None


def locate_supercollider_runtime(
    runtime_root: Path | None = None,
) -> SuperColliderExecutables:
    """Resolve one bundled prefix or the host runtime without mixing them."""

    if runtime_root is not None:
        root = Path(runtime_root).expanduser().resolve()
        layouts = (
            # Linux installation prefix.
            (
                root / "bin" / "sclang",
                root / "bin" / "scsynth",
                root / "bin" / "supernova",
                root / "share" / "SuperCollider" / "SCClassLibrary",
                root / "lib" / "SuperCollider" / "plugins",
            ),
            # Official macOS application bundle.
            (
                root / "Contents" / "MacOS" / "sclang",
                root / "Contents" / "Resources" / "scsynth",
                root / "Contents" / "Resources" / "supernova",
                root / "Contents" / "Resources" / "SCClassLibrary",
                root / "Contents" / "Resources" / "plugins",
            ),
            # Official portable Windows archive.
            (
                root / "sclang.exe",
                root / "scsynth.exe",
                root / "supernova.exe",
                root / "SCClassLibrary",
                root / "plugins",
            ),
        )
        for sclang, scsynth, supernova, class_library, plugins in layouts:
            if all(
                path.exists()
                for path in (sclang, scsynth, supernova, class_library, plugins)
            ):
                return SuperColliderExecutables(
                    sclang, scsynth, supernova, class_library, plugins
                )
        raise SuperColliderProcessError(
            f"bundled SuperCollider runtime is incomplete or has an unsupported layout: {root}"
        )

    sclang_name = shutil.which("sclang")
    scsynth_name = shutil.which("scsynth")
    supernova_name = shutil.which("supernova")
    if not sclang_name or not scsynth_name or not supernova_name:
        raise SuperColliderProcessError(
            "SuperCollider sclang, scsynth and supernova are required"
        )
    return SuperColliderExecutables(
        Path(sclang_name).resolve(),
        Path(scsynth_name).resolve(),
        Path(supernova_name).resolve(),
        None,
        None,
    )


def pipewire_jack_prefix(
    *,
    environment: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
    """Use the distribution's JACK compatibility layer on PipeWire Linux."""

    env = os.environ if environment is None else environment
    systemctl = shutil.which("systemctl")
    if not systemctl:
        return ()
    host_environment = dict(env)
    host_environment.pop("LD_LIBRARY_PATH", None)
    host_environment.pop("LD_PRELOAD", None)
    active = subprocess.run(
        [systemctl, "--user", "is-active", "--quiet", "pipewire.service"],
        env=host_environment,
        check=False,
    ).returncode == 0
    if not active:
        return ()
    wrapper = shutil.which("pw-jack")
    if wrapper:
        return (wrapper,)
    if env.get("OMNICHORD_SC_ALLOW_RAW_JACK") == "1":
        return ()
    raise SuperColliderProcessError(
        "PipeWire is active, but pw-jack is unavailable; install the "
        "distribution's PipeWire JACK compatibility package"
    )


def server_program_command(path: Path, *, platform: str | None = None) -> str:
    """Return the command string expected by SuperCollider's Server class."""

    target = str(Path(path).resolve())
    selected = sys.platform if platform is None else platform
    if selected.startswith("win"):
        return subprocess.list2cmdline([target])
    return f"exec {shlex.quote(target)}"


class SuperColliderSupervisor:
    """Own exactly one headless sclang process group and its supernova child."""

    def __init__(
        self,
        *,
        engine_root: Path,
        config: SuperColliderRuntimeConfig,
        runtime_root: Path | None = None,
    ) -> None:
        self.engine_root = Path(engine_root).resolve()
        self.config = config
        self.executables = locate_supercollider_runtime(runtime_root)
        self._temporary: tempfile.TemporaryDirectory[str] | None = None
        self.process: subprocess.Popen[bytes] | None = None

    def _language_config(self) -> Path | None:
        class_library = self.executables.class_library
        if class_library is None:
            return None
        self._temporary = tempfile.TemporaryDirectory(prefix="lb-omnichord-sc-")
        path = Path(self._temporary.name) / "sclang_conf.yaml"
        path.write_text(
            "includePaths:\n"
            f"  - {json_string(str(class_library))}\n"
            "excludePaths: []\n"
            "postInlineWarnings: false\n",
            encoding="utf-8",
        )
        return path

    def _launch_context(
        self, *, with_audio_wrapper: bool
    ) -> tuple[list[str], dict[str, str]]:
        bootstrap = self.engine_root / "bootstrap.scd"
        if not bootstrap.is_file():
            raise SuperColliderProcessError(f"SC bootstrap is missing: {bootstrap}")
        env = os.environ.copy()
        server = self.config.server
        samples = self.config.samples
        env.update(
            {
                "OMNICHORD_SC_PORT": str(self.config.language.port),
                "OMNICHORD_SC_SAMPLE_RATE": str(server.sample_rate),
                "OMNICHORD_SC_BLOCK_SIZE": str(server.block_size),
                "OMNICHORD_SC_MAX_NODES": str(server.max_nodes),
                "OMNICHORD_SC_MAX_BUFFERS": str(server.max_buffers),
                "OMNICHORD_SC_MEM_KIB": str(server.realtime_memory_kib),
                "OMNICHORD_SC_VSCO_ROOT": str(samples.vsco_root),
                "OMNICHORD_SC_SAMPLE_RAM_MIB": str(samples.ram_budget_mib),
                "OMNICHORD_SC_SYNTH_PROGRAM": server_program_command(
                    self.executables.supernova
                ),
            }
        )
        if self.executables.plugins is not None:
            env["OMNICHORD_SC_PLUGIN_PATH"] = str(self.executables.plugins)
        runtime_library = self.executables.sclang.parent.parent / "lib"
        if self.executables.class_library is not None and sys.platform.startswith("linux"):
            env["LD_LIBRARY_PATH"] = os.pathsep.join(
                part
                for part in (
                    str(runtime_library),
                    env.get("LD_LIBRARY_PATH", ""),
                )
                if part
            )
        prefix = pipewire_jack_prefix(environment=env) if with_audio_wrapper else ()
        command = [*prefix, str(self.executables.sclang)]
        language_config = self._language_config()
        if language_config is not None:
            # A relocated runtime may still remember its build prefix.  SC's
            # standalone mode excludes that default and all host extensions;
            # the private configuration then admits exactly one class tree.
            command.extend(("-a", "-l", str(language_config)))
        command.extend(("-D", str(bootstrap)))
        return command, env

    def validate_bootstrap(self, timeout: float = 20.0) -> None:
        """Execute the real bootstrap up to its no-audio validation boundary."""

        command, env = self._launch_context(with_audio_wrapper=False)
        env["OMNICHORD_SC_VALIDATE_ONLY"] = "1"
        try:
            result = subprocess.run(
                command,
                env=env,
                text=True,
                capture_output=True,
                check=False,
                timeout=timeout,
            )
        finally:
            if self._temporary is not None:
                self._temporary.cleanup()
                self._temporary = None
        output = result.stdout + result.stderr
        if result.returncode != 0 or "LB_OMNICHORD_SC_SYNTAX_OK" not in output:
            raise SuperColliderProcessError(
                "SuperCollider bootstrap validation failed:\n" + output
            )

    def start(self) -> None:
        if self.process is not None:
            raise SuperColliderProcessError("SuperCollider is already started")
        command, env = self._launch_context(with_audio_wrapper=True)
        self.process = subprocess.Popen(command, env=env, start_new_session=True)

    def stop(self, timeout: float = 4.0) -> None:
        process = self.process
        self.process = None
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=2.0)
        if self._temporary is not None:
            self._temporary.cleanup()
            self._temporary = None

    def __enter__(self) -> SuperColliderSupervisor:
        self.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.stop()


def json_string(value: str) -> str:
    """Return a YAML-compatible quoted scalar without adding a dependency."""

    import json

    return json.dumps(value)
