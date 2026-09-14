from __future__ import annotations

import sys

from PySide6.QtGui import QGuiApplication


def resolve_midi_tech_profile(
    configured_profile: object,
    qpa_name: str,
    runtime_platform: str,
) -> str:
    """Resolve a MIDI adapter profile without encoding an OS in config."""

    configured = str(configured_profile or "").strip().casefold()
    if configured not in ("", "auto"):
        return configured

    qpa = str(qpa_name or "").strip().casefold()
    runtime = str(runtime_platform or "").strip().casefold()
    qpa_profiles = {
        "cocoa": "darwin",
        "windows": "win32",
        "android": "android",
    }
    if qpa in qpa_profiles:
        return qpa_profiles[qpa]

    if runtime.startswith("darwin"):
        return "darwin"
    if runtime.startswith(("win32", "cygwin", "msys")):
        return "win32"
    if runtime.startswith("android"):
        return "android"
    if runtime.startswith("linux"):
        return "linux"

    # XCB, Wayland, EGLFS and Linux framebuffer plugins identify a display
    # stack, not an operating system. They select Linux only when Python could
    # not provide a more specific supported runtime above.
    if qpa in ("xcb", "wayland", "eglfs", "linuxfb"):
        return "linux"
    return runtime or "unsupported"


def current_midi_tech_profile(configured_profile: object) -> str:
    """Resolve the current Qt/Python runtime into the portable profile key."""

    qpa = (
        str(QGuiApplication.platformName()).casefold()
        if QGuiApplication.instance() is not None
        else ""
    )
    return resolve_midi_tech_profile(configured_profile, qpa, sys.platform)
