from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
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
                root / "share" / "SuperCollider" / "SCClassLibrary",
                root / "lib" / "SuperCollider" / "plugins",
            ),
            # Official macOS application bundle.
            (
                root / "Contents" / "MacOS" / "sclang",
                root / "Contents" / "Resources" / "scsynth",
                root / "Contents" / "Resources" / "SCClassLibrary",
                root / "Contents" / "Resources" / "plugins",
            ),
            # Official portable Windows archive.
            (
                root / "sclang.exe",
                root / "scsynth.exe",
                root / "SCClassLibrary",
                root / "plugins",
            ),
        )
        for sclang, scsynth, class_library, plugins in layouts:
            if all(path.exists() for path in (sclang, scsynth, class_library, plugins)):
                return SuperColliderExecutables(
                    sclang, scsynth, class_library, plugins
                )
        raise SuperColliderProcessError(
            f"bundled SuperCollider runtime is incomplete or has an unsupported layout: {root}"
        )

    sclang_name = shutil.which("sclang")
    scsynth_name = shutil.which("scsynth")
    if not sclang_name or not scsynth_name:
        raise SuperColliderProcessError(
            "SuperCollider sclang and scsynth are required"
        )
    return SuperColliderExecutables(
        Path(sclang_name).resolve(),
        Path(scsynth_name).resolve(),
        None,
        None,
    )


def pipewire_jack_prefix(
    *,
    environment: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
    """Use the distribution's JACK compatibility layer on PipeWire Linux."""

    env = os.environ if environment is None else environment
    if not shutil.which("systemctl"):
        return ()
    active = subprocess.run(
        ["systemctl", "--user", "is-active", "--quiet", "pipewire.service"],
        env=dict(env),
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


class SuperColliderSupervisor:
    """Own exactly one headless sclang process group and its scsynth child."""

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

    def start(self) -> None:
        if self.process is not None:
            raise SuperColliderProcessError("SuperCollider is already started")
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
                "OMNICHORD_SC_SYNTH_PROGRAM": str(self.executables.scsynth),
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
        command = [*pipewire_jack_prefix(environment=env), str(self.executables.sclang)]
        language_config = self._language_config()
        if language_config is not None:
            command.extend(("-l", str(language_config)))
        command.extend(("-D", str(bootstrap)))
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
