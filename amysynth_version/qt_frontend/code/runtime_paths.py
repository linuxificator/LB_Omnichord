from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths


ASSET_DIRECTORIES = ("config", "gui", "instruments", "music")


def resolve_frontend_asset_root(
    code_dir: Path,
    packaged_root: Path | None = None,
) -> Path:
    """Find assets in source, frozen, or a flat staged package layout."""

    candidate = Path(code_dir)
    if all((candidate / name).is_dir() for name in ASSET_DIRECTORIES):
        return candidate
    if packaged_root is not None:
        return Path(packaged_root)
    return candidate.parent


def production_frontend_asset_root(code_dir: Path) -> Path:
    raw_packaged = getattr(sys, "_MEIPASS", None)
    packaged = Path(str(raw_packaged)) if raw_packaged is not None else None
    return resolve_frontend_asset_root(code_dir, packaged)


def qt_private_files_dir() -> Path:
    """Resolve the package-private writable root through Qt's platform API."""

    return Path(
        QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.HomeLocation
        )
    )
