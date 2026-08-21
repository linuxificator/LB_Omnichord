from __future__ import annotations

import atexit
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = ROOT / "code"
sys.path.insert(0, str(CODE_DIR))

import main as omnichord_main  # noqa: E402
from test_control import TestControlServer  # noqa: E402


OriginalBackend = omnichord_main.InstrumentBackend


class TestBackend(OriginalBackend):
    """Real application backend with a localhost-only CI control API."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        port = int(os.environ.get("OMNICHORD_TEST_API_PORT", "18765"))
        self._test_control_server = TestControlServer(self, port)
        print(
            f"Test control API: http://127.0.0.1:{self._test_control_server.port}",
            file=sys.stderr,
            flush=True,
        )
        atexit.register(self._test_control_server.close)


omnichord_main.InstrumentBackend = TestBackend


if __name__ == "__main__":
    raise SystemExit(omnichord_main.main())
