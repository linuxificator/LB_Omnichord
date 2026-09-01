from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ANDROID_SMOKE_ENABLE = "lb-android-package-smoke.enable"
ANDROID_SMOKE_STATUS = "lb-android-package-smoke.status"


@dataclass(frozen=True, slots=True)
class RuntimeOverrides:
    amy_socket: str | None
    amy_local_name: str | None
    package_smoke_test: bool
    smoke_status: Path | None = None


def resolve_package_runtime(
    *,
    platform_name: str,
    private_files_dir: Path,
    amy_socket: str | None,
    amy_local_name: str | None,
    package_smoke_test: bool,
) -> RuntimeOverrides:
    """Resolve package-native startup facts without changing application args."""

    socket = amy_socket
    local_name = amy_local_name
    smoke = bool(package_smoke_test)
    status: Path | None = None
    if str(platform_name).casefold() != "android":
        return RuntimeOverrides(socket, local_name, smoke)

    files_dir = Path(private_files_dir)
    if not socket and not local_name:
        socket = str(files_dir / "amy.sock")

    marker = files_dir / ANDROID_SMOKE_ENABLE
    if marker.is_file():
        marker.unlink()
        status = files_dir / ANDROID_SMOKE_STATUS
        status.unlink(missing_ok=True)
        smoke = True
    return RuntimeOverrides(socket, local_name, smoke, status)
