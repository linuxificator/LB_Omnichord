from __future__ import annotations

import argparse
from pathlib import Path
import sys


CODE = Path(__file__).resolve().parents[2] / "qt_frontend" / "code"
sys.path.insert(0, str(CODE))

from sfz_manifest_compiler import compile_vsco_manifest, write_manifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bank_root", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    write_manifest(compile_vsco_manifest(arguments.bank_root), arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
