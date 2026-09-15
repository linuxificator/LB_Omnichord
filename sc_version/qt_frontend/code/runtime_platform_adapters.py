from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
@dataclass(frozen=True, slots=True)
class RuntimeOverrides:
    startup_warnings: tuple[str, ...] = ()


def resolve_package_runtime(
    *,
    platform_name: str,
    private_files_dir: Path,
) -> RuntimeOverrides:
    """Return platform facts without selecting or embedding an audio engine."""

    del platform_name, private_files_dir
    return RuntimeOverrides()
