from __future__ import annotations

# Keep the historical `main` import surface stable while moving new
# performance-state behavior out of the already-large application core.
import app_core as _core
from app_core import *  # noqa: F401,F403
from performance_backend import InstrumentBackend

# app_core.main() resolves InstrumentBackend from its module globals when it
# constructs the backend.  Point that explicit construction seam at the
# performance subclass without duplicating the Qt/bootstrap code here.
_core.InstrumentBackend = InstrumentBackend


if __name__ == "__main__":
    raise SystemExit(_core.main())
