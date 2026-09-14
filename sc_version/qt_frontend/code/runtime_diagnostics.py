from __future__ import annotations

import os
from collections.abc import Mapping


def display_diagnostic_lines(
    qpa_platform: str,
    environment: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
    """Render platform/display diagnostics outside the portable Qt core."""

    values = os.environ if environment is None else environment

    def value(name: str, fallback: str) -> str:
        return str(values.get(name, fallback))

    return (
        "Qt Omnichord display diagnostics:",
        f"  QPA platform: {qpa_platform}",
        f"  XDG_SESSION_TYPE: {value('XDG_SESSION_TYPE', '<unset>')}",
        f"  WAYLAND_DISPLAY: {value('WAYLAND_DISPLAY', '<unset>')}",
        f"  DISPLAY: {value('DISPLAY', '<unset>')}",
        f"  QT_QPA_PLATFORM: {value('QT_QPA_PLATFORM', '<auto>')}",
        f"  QT_QUICK_BACKEND: {value('QT_QUICK_BACKEND', '<default>')}",
        f"  QSG_RHI_BACKEND: {value('QSG_RHI_BACKEND', '<default>')}",
    )
