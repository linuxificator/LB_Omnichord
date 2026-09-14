from __future__ import annotations

import argparse
from pathlib import Path
import sys


CODE = Path(__file__).resolve().parents[2] / "qt_frontend" / "code"
sys.path.insert(0, str(CODE))

from sfz_manifest_compiler import audit_sfz_opcodes, write_manifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit the complete opcode surface of a pinned SFZ bank"
    )
    parser.add_argument("bank_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--bank-id")
    parser.add_argument("--source-pin")
    arguments = parser.parse_args()
    root = arguments.bank_root.resolve()
    mappings = tuple(
        sorted(path for path in root.rglob("*") if path.suffix.casefold() == ".sfz")
    )
    if not mappings:
        parser.error(f"no SFZ mappings found below {root}")
    if bool(arguments.bank_id) != bool(arguments.source_pin):
        parser.error("--bank-id and --source-pin must be supplied together")
    report = audit_sfz_opcodes(
        mappings,
        root=root,
        bank_id=arguments.bank_id,
        source_pin=arguments.source_pin,
    )
    write_manifest(report, arguments.output)
    return 0 if report["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
