from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path

from package_test_hooks import PACKAGE_SMOKE_STATUS_ENV


def prepare_windowed_console_streams() -> None:
    """Provide sinks for PyInstaller's Windows --windowed bootloader."""

    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")


def guarded_package_main(run: Callable[[], int]) -> int:
    """Record otherwise invisible fatal errors during headless package smoke."""

    raw_status = os.environ.get(PACKAGE_SMOKE_STATUS_ENV)
    if not raw_status:
        return run()
    try:
        return run()
    except Exception as exc:
        status = Path(raw_status)
        with status.open("a", encoding="utf-8") as handle:
            handle.write(f"fatal-error {type(exc).__name__}: {exc}\n")
        return 1
