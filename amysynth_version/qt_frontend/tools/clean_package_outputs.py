#!/usr/bin/env python3
"""Report or remove only the ignored Qt frontend package output roots."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[1]
OUTPUT_NAMES = ("build", "dist")


def output_roots(frontend: Path) -> tuple[Path, ...]:
    root = Path(frontend).resolve()
    return tuple(root / name for name in OUTPUT_NAMES)


def output_stats(path: Path) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    if path.is_symlink() or not path.is_dir():
        raise ValueError(f"refusing non-directory package output {path}")
    files = tuple(item for item in path.rglob("*") if item.is_file())
    return len(files), sum(item.stat().st_size for item in files)


def clean(frontend: Path, *, delete: bool) -> tuple[tuple[Path, int, int], ...]:
    results = []
    for path in output_roots(frontend):
        count, size = output_stats(path)
        results.append((path, count, size))
        if delete and path.exists():
            shutil.rmtree(path)
    return tuple(results)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frontend", type=Path, default=FRONTEND)
    parser.add_argument(
        "--delete",
        action="store_true",
        help="remove the exact ignored build/ and dist/ roots; default is dry-run",
    )
    args = parser.parse_args()
    for path, count, size in clean(args.frontend, delete=args.delete):
        action = "removed" if args.delete and count else "would remove"
        print(f"{action}: {path} ({count} files, {size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
