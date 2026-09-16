from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys


RELEASE_NAME_ENV = "OMNICHORD_RELEASE_NAME"
DEFAULT_RELEASE_NAME = "development-SC"
_SAFE_RELEASE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


def validate_release_name(value: object) -> str:
    name = str(value)
    if not _SAFE_RELEASE_NAME.fullmatch(name) or name in {".", ".."}:
        raise ValueError(f"unsafe LB Omnichord release name: {name!r}")
    return name


def read_release_name(path: Path) -> str:
    source = Path(path)
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_revision") != 1:
        raise ValueError(f"{source} is not a supported release identity")
    return validate_release_name(data.get("release_name"))


def write_release_identity(path: Path, release_name: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {
                "release_name": validate_release_name(release_name),
                "schema_revision": 1,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def configure_release_environment(path: Path) -> str:
    name = read_release_name(path)
    existing = os.environ.get(RELEASE_NAME_ENV)
    if existing is not None and validate_release_name(existing) != name:
        raise RuntimeError(
            f"{RELEASE_NAME_ENV}={existing!r} disagrees with packaged release {name!r}"
        )
    os.environ[RELEASE_NAME_ENV] = name
    return name


def active_release_name() -> str:
    return validate_release_name(os.environ.get(RELEASE_NAME_ENV, DEFAULT_RELEASE_NAME))


def release_user_root(*, home: Path | None = None) -> Path:
    base = Path.home() if home is None else Path(home)
    return base / ".omnichord" / active_release_name()


def _main(arguments: list[str]) -> int:
    if len(arguments) == 3 and arguments[0] == "--write":
        write_release_identity(Path(arguments[1]), arguments[2])
        return 0
    if len(arguments) == 1:
        print(read_release_name(Path(arguments[0])))
        return 0
    raise SystemExit(
        "usage: release_identity.py RELEASE_IDENTITY_JSON | "
        "--write TARGET_JSON RELEASE_NAME"
    )


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
