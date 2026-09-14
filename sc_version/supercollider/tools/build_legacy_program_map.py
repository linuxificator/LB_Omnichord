from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


CODE = Path(__file__).resolve().parents[2] / "qt_frontend" / "code"
sys.path.insert(0, str(CODE))

from supercollider_programs import build_legacy_program_map  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("legacy_catalog", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    migration = build_legacy_program_map(arguments.legacy_catalog.resolve())
    arguments.output.write_text(
        json.dumps(migration, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
