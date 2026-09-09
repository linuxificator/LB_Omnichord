from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from raspberry_pi_realtime import (
    prepare_realtime_startup,
    service_pid_from_environment,
)


@dataclass(frozen=True, slots=True)
class RuntimeOverrides:
    amy_socket: str | None
    amy_local_name: str | None
    startup_warnings: tuple[str, ...] = ()


def resolve_package_runtime(
    *,
    platform_name: str,
    private_files_dir: Path,
    amy_socket: str | None,
    amy_local_name: str | None,
) -> RuntimeOverrides:
    """Resolve package-native startup facts without changing application args."""

    socket = amy_socket
    local_name = amy_local_name
    if str(platform_name).casefold() != "android":
        if socket is None:
            return RuntimeOverrides(socket, local_name)
        realtime = prepare_realtime_startup(
            socket,
            service_pid=service_pid_from_environment(),
        )
        return RuntimeOverrides(socket, local_name, realtime.warnings)

    files_dir = Path(private_files_dir)
    if not socket and not local_name:
        socket = str(files_dir / "amy.sock")

    return RuntimeOverrides(socket, local_name)
