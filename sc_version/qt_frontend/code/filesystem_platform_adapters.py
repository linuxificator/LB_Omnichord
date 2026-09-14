from __future__ import annotations

import os
from pathlib import Path


def set_descriptor_mode(descriptor: int, mode: int) -> None:
    """Apply Unix descriptor permissions when the platform exposes them.

    Windows has no ``os.fchmod``. Its newly created file inherits directory
    ACLs and the subsequent path-level chmod remains in the portable store.
    """

    fchmod = getattr(os, "fchmod", None)
    if callable(fchmod):
        fchmod(descriptor, mode)


def sync_directory(path: Path) -> None:
    """Flush directory metadata where the host supports directory handles."""

    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return
    try:
        try:
            os.fsync(descriptor)
        except OSError:
            pass
    finally:
        os.close(descriptor)
