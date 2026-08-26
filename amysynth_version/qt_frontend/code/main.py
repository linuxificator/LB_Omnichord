from __future__ import annotations

import os
import sys

# PyInstaller's Windows ``--windowed`` bootloader deliberately supplies no
# console streams.  The application and Qt diagnostics still write to them;
# install harmless sinks before importing the frontend so a native packaged
# launch cannot fail on ``None.write``.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

# Keep the historical `main` import surface stable while new architecture is
# layered around the already-large application core.
import app_core as _core
from app_core import *  # noqa: F401,F403

from catalog_extensions import load_synth_catalog as _extended_catalog
from config_loader import load_amy_config
from midi_integration import InstrumentBackend
from program_amy import (
    ProgramAmySerialClient,
    ProgramAmySocketClient,
    ProgramAmyTcpClient,
)


# app_core.main() resolves these names from its own module globals at runtime.
# These explicit seams let us modernize configuration/program handling without
# copying or forking the stable Qt/bootstrap/application core.
_original_catalog_loader = _core.load_synth_catalog


def load_synth_catalog(path):
    """Public catalogue loader including non-ROM synth programs."""
    return _extended_catalog(_original_catalog_loader, path)


_core.load_synth_catalog = load_synth_catalog
_core.load_amy_config = load_amy_config
_core.AmySerialClient = ProgramAmySerialClient
_core.AmySocketClient = ProgramAmySocketClient
_core.AmyTcpClient = ProgramAmyTcpClient
_core.InstrumentBackend = InstrumentBackend


if __name__ == "__main__":
    if os.environ.get("OMNICHORD_PACKAGE_SMOKE_STATUS"):
        try:
            _exit_code = _core.main()
        except Exception as _exc:
            # A --windowed PyInstaller executable otherwise displays an error
            # dialog that cannot be dismissed on a headless CI runner.
            from pathlib import Path

            _status = Path(os.environ["OMNICHORD_PACKAGE_SMOKE_STATUS"])
            with _status.open("a", encoding="utf-8") as _handle:
                _handle.write(
                    f"fatal-error {type(_exc).__name__}: {_exc}\n"
                )
            _exit_code = 1
        raise SystemExit(_exit_code)
    raise SystemExit(_core.main())
