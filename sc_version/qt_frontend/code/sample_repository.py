from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from urllib.parse import urlsplit

from dulwich import porcelain
from dulwich.errors import NotGitRepository
from dulwich.repo import Repo

from json_store import JsonStore
from supercollider_config import (
    CURRENT_CONFIG_REVISION,
    SuperColliderRuntimeConfig,
    load_supercollider_config,
)


DEFAULT_REPOSITORY = "https://github.com/linuxificator/VSCO-2-CE.git"
DEFAULT_SAMPLE_ROOT = "~/VSCO-2-CE"
LEGACY_SAMPLE_ROOT = "~/sample_lib/VSCO-2-CE-1.1.0"


class SampleRepositoryError(RuntimeError):
    """Raised before audio startup when the configured sample clone is unsafe."""


def _repository_identity(value: str) -> tuple[str, str, str]:
    source = value.strip()
    if source.startswith("git@") and ":" in source:
        authority, path = source.split(":", 1)
        host = authority.split("@", 1)[1]
    else:
        parsed = urlsplit(source)
        host = parsed.hostname or ""
        path = parsed.path
    parts = [part for part in path.strip("/").split("/") if part]
    if len(parts) != 2 or host.lower() != "github.com":
        raise SampleRepositoryError(
            f"unsupported sample repository identity: {value!r}"
        )
    owner, name = parts
    if name.lower().endswith(".git"):
        name = name[:-4]
    return host.lower(), owner.lower(), name.lower()


def repository_origin(path: Path) -> str:
    try:
        config = Repo(str(path)).get_config()
        value = config.get((b"remote", b"origin"), b"url")
    except (KeyError, NotGitRepository, OSError, ValueError) as exc:
        raise SampleRepositoryError(
            f"sample directory is not a readable Git clone: {path}"
        ) from exc
    return bytes(value).decode("utf-8", errors="strict")


def validate_sample_repository(path: Path, expected_url: str) -> Path:
    resolved = path.expanduser().resolve()
    actual_url = repository_origin(resolved)
    if _repository_identity(actual_url) != _repository_identity(expected_url):
        raise SampleRepositoryError(
            "configured sample directory has the wrong Git origin: "
            f"expected {expected_url}, found {actual_url} in {resolved}"
        )
    return resolved


def ensure_sample_repository(path: Path, repository_url: str) -> Path:
    destination = path.expanduser().resolve()
    if destination.exists():
        return validate_sample_repository(destination, repository_url)

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_root = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.clone-", dir=destination.parent)
    )
    checkout = temporary_root / "repository"
    print(
        f"Installing VSCO 2 CE samples in {destination}; this is a large "
        "one-time download.",
        file=sys.stderr,
        flush=True,
    )
    try:
        porcelain.clone(repository_url, str(checkout), checkout=True)
        validate_sample_repository(checkout, repository_url)
        checkout.replace(destination)
    except BaseException as exc:
        raise SampleRepositoryError(
            f"could not clone sample repository {repository_url} to {destination}: {exc}"
        ) from exc
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)
    return destination


def _migrate_config(
    data: object,
    *,
    default_max_buffers: int,
) -> tuple[dict[str, object], bool]:
    if not isinstance(data, dict):
        raise SampleRepositoryError("SuperCollider config must contain an object")
    revision = data.get("config_revision")
    if revision not in (1, CURRENT_CONFIG_REVISION):
        raise SampleRepositoryError(
            f"unsupported SuperCollider config revision {revision!r}"
        )
    migrated = json.loads(json.dumps(data))
    changed = False

    if revision == 1:
        samples = migrated.get("samples")
        if not isinstance(samples, dict):
            raise SampleRepositoryError("SuperCollider config samples object is missing")
        if samples.get("vsco_root") == LEGACY_SAMPLE_ROOT:
            samples["vsco_root"] = DEFAULT_SAMPLE_ROOT
            changed = True
        if "repository" not in samples:
            samples["repository"] = DEFAULT_REPOSITORY
            changed = True
        migrated["config_revision"] = CURRENT_CONFIG_REVISION
        changed = True

    server = migrated.get("server")
    if not isinstance(server, dict):
        raise SampleRepositoryError("SuperCollider config server object is missing")
    if "max_buffers" not in server:
        server["max_buffers"] = default_max_buffers
        changed = True

    return migrated, changed


def prepare_user_runtime_config(
    shipped_config: Path,
    *,
    user_root: Path | None = None,
    install_samples: bool = True,
) -> tuple[Path, SuperColliderRuntimeConfig]:
    """Seed/migrate user config and ensure its external sample clone."""

    root = (user_root or (Path.home() / ".omnichord")).expanduser().resolve()
    target = root / "config" / "supercollider.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    shipped = load_supercollider_config(shipped_config)
    store = JsonStore(target)
    if not target.exists():
        source = JsonStore(shipped_config).read()
        store.write(source)
    migrated, changed = _migrate_config(
        store.read(),
        default_max_buffers=shipped.server.max_buffers,
    )
    if changed:
        store.write(migrated)
    config = load_supercollider_config(target)
    if install_samples:
        ensure_sample_repository(config.samples.vsco_root, config.samples.repository)
    return target, config


def _main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare the per-user SuperCollider sample configuration."
    )
    parser.add_argument("shipped_config", type=Path)
    parser.add_argument("--without-samples", action="store_true")
    args = parser.parse_args()
    path, _config = prepare_user_runtime_config(
        args.shipped_config,
        install_samples=not args.without_samples,
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
