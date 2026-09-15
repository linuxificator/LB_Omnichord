from __future__ import annotations

from collections.abc import Sequence
import os
from pathlib import Path
import sys

import main as frontend_main
from supercollider_client import SuperColliderUnavailable
from supercollider_config import load_supercollider_config
from supercollider_platform_adapter import (
    SuperColliderProcessError,
    SuperColliderSupervisor,
)


def run(arguments: Sequence[str] | None = None) -> int:
    """Run a source checkout through the production SC supervisor."""

    frontend_root = Path(__file__).resolve().parents[1]
    config_value = os.environ.get("OMNICHORD_SC_CONFIG")
    if not config_value:
        raise SuperColliderProcessError("OMNICHORD_SC_CONFIG is not configured")
    config = load_supercollider_config(Path(config_value))
    with SuperColliderSupervisor(
        engine_root=frontend_root.parent / "supercollider",
        config=config,
    ):
        return frontend_main.main(arguments, asset_root=frontend_root)


def main() -> int:
    try:
        return run(sys.argv[1:])
    except (SuperColliderProcessError, SuperColliderUnavailable) as exc:
        print(f"Cannot start LB Omnichord: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
