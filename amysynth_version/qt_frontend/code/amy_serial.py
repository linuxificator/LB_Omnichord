from __future__ import annotations

"""Public AMY transport surface.

The stable transport implementation is isolated in amy_transport.py.
Configuration loading lives in config_loader.py so there is exactly one
runtime configuration source: config/amy_config.json.  Program-aware clients
are then layered on top of the stable transport.
"""

import amy_transport as _transport
from config_loader import load_amy_config

# Preserve the historical amy_serial import surface, including private helper
# names used by the regression harness, without re-exporting the retired
# embedded configuration loader/defaults.
for _name, _value in vars(_transport).items():
    if _name in {"DEFAULT_CONFIG", "load_amy_config", "_deep_merge"}:
        continue
    if _name.startswith("__"):
        continue
    globals()[_name] = _value

del _name, _value

# Override only the two client classes with the generalized program layer.
# program_amy imports amy_transport directly, so this does not form a cycle.
from program_amy import (  # noqa: E402
    ProgramAmySerialClient as AmySerialClient,
    ProgramAmySocketClient as AmySocketClient,
)
