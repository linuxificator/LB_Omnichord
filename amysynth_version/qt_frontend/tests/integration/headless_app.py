from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication


ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = ROOT / "code"
TEST_SUPPORT_DIR = ROOT / "tests" / "support"
sys.path.insert(0, str(CODE_DIR))
sys.path.insert(0, str(TEST_SUPPORT_DIR))

import main as omnichord  # noqa: E402
from application_composition import (  # noqa: E402
    compose_application_graph,
    load_application_resources,
)
from control_server import TestControlServer  # noqa: E402
from backend_control_surface import BackendControlSurface  # noqa: E402


def main() -> int:
    args = omnichord.parse_arguments()
    dependencies = omnichord.production_dependencies()
    resources = load_application_resources(
        dependencies,
        user_config_dir=omnichord.CONFIG_DIR,
    )

    app = QCoreApplication(sys.argv)
    app.setApplicationName("LB Omnichord headless integration test")
    graph = compose_application_graph(
        args,
        dependencies,
        resources,
        user_config_dir=omnichord.CONFIG_DIR,
    )
    amy_client = graph.client
    backend = graph.backend

    port = int(os.environ.get("OMNICHORD_TEST_API_PORT", "18765"))
    test_server = TestControlServer(BackendControlSurface(backend), port)
    print(
        f"TEST_API_PORT={test_server.port}",
        file=sys.stderr,
        flush=True,
    )

    backend.send_initial_state()
    try:
        return app.exec()
    finally:
        test_server.close()
        amy_client.close()


if __name__ == "__main__":
    raise SystemExit(main())
