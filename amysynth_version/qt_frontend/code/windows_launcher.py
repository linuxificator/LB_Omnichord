from __future__ import annotations

import os
import sys


def prepare_windowed_console_streams() -> None:
    """Provide sinks for PyInstaller's Windows --windowed bootloader."""

    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
