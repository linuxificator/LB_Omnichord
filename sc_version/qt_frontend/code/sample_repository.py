from __future__ import annotations

import argparse
import hashlib
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
DEFAULT_SAMPLE_COMMIT = "440300901dfe9275fd84e0b7763af1f8443ae62e"
DEFAULT_SAMPLE_ROOT = "~/VSCO-2-CE"
LEGACY_SAMPLE_ROOT = "~/sample_lib/VSCO-2-CE-1.1.0"


class SampleRepositoryError(RuntimeError):
    """Raised before audio startup when the configured sample tree is unsafe."""


def _sample_manifest_for_config(shipped_config: Path) -> Path:
    source = shipped_config.expanduser().resolve()
    candidates = (
        source.parents[1] / "supercollider" / "vsco-manifest.json",
        source.parents[2] / "supercollider" / "vsco-manifest.json",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise SampleRepositoryError(
        f"could not locate the VSCO content manifest beside {source}"
    )


def _sample_inventory(
    root: Path, records: list[object]
) -> tuple[str, list[tuple[Path, str]]]:
    inventory = hashlib.sha256()
    files: list[tuple[Path, str]] = []
    for raw_record in records:
        if not isinstance(raw_record, dict):
            raise SampleRepositoryError("VSCO manifest contains an invalid file record")
        relative = raw_record.get("relative_path")
        expected_hash = raw_record.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected_hash, str):
            raise SampleRepositoryError("VSCO manifest file identity is incomplete")
        path = root / relative
        try:
            status = path.stat()
        except OSError as exc:
            raise SampleRepositoryError(
                f"sample collection is incomplete; missing {relative} in {root}"
            ) from exc
        if not path.is_file():
            raise SampleRepositoryError(
                f"sample collection is incomplete; {relative} is not a file"
            )
        inventory.update(relative.encode("utf-8"))
        inventory.update(b"\0")
        inventory.update(str(status.st_size).encode("ascii"))
        inventory.update(b"\0")
        inventory.update(str(status.st_mtime_ns).encode("ascii"))
        inventory.update(b"\0")
        inventory.update(str(status.st_ctime_ns).encode("ascii"))
        inventory.update(b"\n")
        files.append((path, expected_hash))
    return inventory.hexdigest(), files


def validate_sample_tree(
    path: Path,
    manifest_path: Path,
    *,
    cache_path: Path | None = None,
) -> Path:
    """Validate either a clone or an ordinary copy by its audio contents."""

    resolved = path.expanduser().resolve()
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
    except (OSError, json.JSONDecodeError) as exc:
        raise SampleRepositoryError(
            f"could not read VSCO content manifest {manifest_path}: {exc}"
        ) from exc
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), list):
        raise SampleRepositoryError("VSCO content manifest has no files array")

    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    inventory_hash, files = _sample_inventory(resolved, manifest["files"])
    expected_cache = {
        "schema_revision": 1,
        "sample_root": str(resolved),
        "manifest_sha256": manifest_hash,
        "inventory_sha256": inventory_hash,
        "file_count": len(files),
    }
    if cache_path is not None:
        try:
            if JsonStore(cache_path).read() == expected_cache:
                return resolved
        except (FileNotFoundError, OSError):
            pass

    for sample, expected_hash in files:
        try:
            with sample.open("rb") as handle:
                actual_hash = hashlib.file_digest(handle, "sha256").hexdigest()
        except OSError as exc:
            raise SampleRepositoryError(f"could not read sample file {sample}: {exc}") from exc
        if actual_hash != expected_hash:
            raise SampleRepositoryError(
                f"sample collection content differs from the supported set: {sample}"
            )
    if cache_path is not None:
        JsonStore(cache_path).write(expected_cache)
    return resolved


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


def repository_commit(path: Path) -> str:
    try:
        return bytes(Repo(str(path)).head()).decode("ascii")
    except (NotGitRepository, OSError, UnicodeDecodeError, ValueError) as exc:
        raise SampleRepositoryError(
            f"sample directory has no readable Git HEAD: {path}"
        ) from exc


def validate_sample_repository(
    path: Path,
    expected_url: str,
    expected_commit: str = DEFAULT_SAMPLE_COMMIT,
) -> Path:
    resolved = path.expanduser().resolve()
    actual_url = repository_origin(resolved)
    if _repository_identity(actual_url) != _repository_identity(expected_url):
        raise SampleRepositoryError(
            "configured sample directory has the wrong Git origin: "
            f"expected {expected_url}, found {actual_url} in {resolved}"
        )
    actual_commit = repository_commit(resolved)
    if actual_commit != str(expected_commit):
        raise SampleRepositoryError(
            "configured sample directory is at the wrong Git commit: "
            f"expected {expected_commit}, found {actual_commit} in {resolved}"
        )
    return resolved


def ensure_sample_repository(
    path: Path,
    repository_url: str,
    expected_commit: str = DEFAULT_SAMPLE_COMMIT,
    *,
    content_manifest: Path | None = None,
    validation_cache: Path | None = None,
) -> Path:
    destination = path.expanduser().resolve()
    if destination.exists():
        if content_manifest is not None:
            return validate_sample_tree(
                destination,
                content_manifest,
                cache_path=validation_cache,
            )
        return validate_sample_repository(
            destination, repository_url, expected_commit
        )

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
        porcelain.reset(checkout, "hard", expected_commit)
        validate_sample_repository(checkout, repository_url, expected_commit)
        if content_manifest is not None:
            validate_sample_tree(checkout, content_manifest)
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
    default_gesture_voice_limit: int,
    default_sample_commit: str,
) -> tuple[dict[str, object], bool]:
    if not isinstance(data, dict):
        raise SampleRepositoryError("SuperCollider config must contain an object")
    revision = data.get("config_revision")
    if (
        isinstance(revision, bool)
        or not isinstance(revision, int)
        or not 1 <= revision <= CURRENT_CONFIG_REVISION
    ):
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
    server = migrated.get("server")
    if not isinstance(server, dict):
        raise SampleRepositoryError("SuperCollider config server object is missing")
    if "max_buffers" not in server:
        server["max_buffers"] = default_max_buffers
        changed = True
    if "gesture_voice_limit" not in server:
        server["gesture_voice_limit"] = default_gesture_voice_limit
        changed = True

    samples = migrated.get("samples")
    if not isinstance(samples, dict):
        raise SampleRepositoryError("SuperCollider config samples object is missing")
    if "commit" not in samples:
        samples["commit"] = default_sample_commit
        changed = True

    if revision < CURRENT_CONFIG_REVISION:
        migrated["protocol_version"] = 2
        migrated["config_revision"] = CURRENT_CONFIG_REVISION
        changed = True

    return migrated, changed


def prepare_user_runtime_config(
    shipped_config: Path,
    *,
    user_root: Path | None = None,
    install_samples: bool = True,
) -> tuple[Path, SuperColliderRuntimeConfig]:
    """Seed/migrate user config and ensure its external sample collection."""

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
        default_gesture_voice_limit=shipped.server.gesture_voice_limit,
        default_sample_commit=shipped.samples.commit,
    )
    if changed:
        store.write(migrated)
    config = load_supercollider_config(target)
    if install_samples:
        ensure_sample_repository(
            config.samples.vsco_root,
            config.samples.repository,
            config.samples.commit,
            content_manifest=_sample_manifest_for_config(shipped_config),
            validation_cache=root / "cache" / "vsco-validation.json",
        )
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
