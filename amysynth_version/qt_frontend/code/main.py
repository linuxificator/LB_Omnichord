from __future__ import annotations

from pathlib import Path

# Keep the historical `main` import surface stable while new architecture is
# layered around the already-large application core.
import app_core as _core
from app_core import *  # noqa: F401,F403

from catalog_extensions import load_synth_catalog as _extended_catalog
from config_loader import load_amy_config
from gated_backend import InstrumentBackend
from program_amy import ProgramAmyLocalClient, ProgramAmySerialClient


# app_core.main() resolves these names from its own module globals at runtime.
# These explicit seams let us modernize configuration/program handling without
# copying or forking the stable Qt/bootstrap/application core.
_original_catalog_loader = _core.load_synth_catalog


def _load_synth_catalog(path):
    return _extended_catalog(_original_catalog_loader, path)


_core.load_synth_catalog = _load_synth_catalog
_core.load_amy_config = load_amy_config
_core.AmySerialClient = ProgramAmySerialClient
_core.AmyLocalClient = ProgramAmyLocalClient
_core.InstrumentBackend = InstrumentBackend
_core.GUI_DIR = Path(__file__).resolve().parents[1] / "gui_extended"


if __name__ == "__main__":
    raise SystemExit(_core.main())
