from __future__ import annotations

import argparse
from collections.abc import Sequence
import hashlib
import json
from pathlib import Path
from pathlib import PurePosixPath
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
DEFAULT_SAMPLE_BRANCH = "lb-omnichord-runtime-v1"
DEFAULT_SAMPLE_COMMIT = "78b95e70efe4349eeb03855f7f7654cb81c8c62f"
LEGACY_SAMPLE_COMMIT = "440300901dfe9275fd84e0b7763af1f8443ae62e"
DEFAULT_SAMPLE_ROOT = "~/VSCO-2-CE"
LEGACY_SAMPLE_ROOT = "~/sample_lib/VSCO-2-CE-1.1.0"
SAMPLE_RECEIPT_NAME = "lb-omnichord-samples.json"


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


def _drum_catalogue_for_config(shipped_config: Path) -> Path:
    source = shipped_config.expanduser().resolve()
    candidate = source.parents[1] / "music" / "sc_expansion" / "sc_pcm_drumkits_v1.json"
    if candidate.is_file():
        return candidate
    raise SampleRepositoryError(
        f"could not locate the PCM drum catalogue beside {source}"
    )


def _runtime_sample_records(
    manifest: object,
    direct_sample_ids: set[str] | None = None,
) -> list[dict[str, object]]:
    """Select the source files reachable from the shipped playable regions."""

    if not isinstance(manifest, dict):
        raise SampleRepositoryError("VSCO content manifest must contain an object")
    raw_files = manifest.get("files")
    raw_regions = manifest.get("regions")
    if not isinstance(raw_files, list) or not isinstance(raw_regions, list):
        raise SampleRepositoryError(
            "VSCO content manifest must contain files and regions arrays"
        )

    files_by_id: dict[str, dict[str, object]] = {}
    ordered_files: list[dict[str, object]] = []
    for raw_record in raw_files:
        if not isinstance(raw_record, dict):
            raise SampleRepositoryError("VSCO manifest contains an invalid file record")
        sample_id = raw_record.get("id")
        relative = raw_record.get("relative_path")
        expected_hash = raw_record.get("sha256")
        if (
            not isinstance(sample_id, str)
            or not sample_id
            or not isinstance(relative, str)
            or not isinstance(expected_hash, str)
        ):
            raise SampleRepositoryError("VSCO manifest file identity is incomplete")
        relative_path = PurePosixPath(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise SampleRepositoryError(
                f"VSCO manifest contains an unsafe sample path: {relative!r}"
            )
        if sample_id in files_by_id:
            raise SampleRepositoryError(
                f"VSCO manifest contains duplicate sample id {sample_id!r}"
            )
        files_by_id[sample_id] = raw_record
        ordered_files.append(raw_record)

    used_ids: set[str] = set(direct_sample_ids or ())
    unknown_direct = used_ids.difference(files_by_id)
    if unknown_direct:
        raise SampleRepositoryError(
            "PCM catalogue refers to unknown VSCO sample id "
            f"{min(unknown_direct)!r}"
        )
    for raw_region in raw_regions:
        if not isinstance(raw_region, dict):
            raise SampleRepositoryError("VSCO manifest contains an invalid region record")
        sample_id = raw_region.get("sample_id")
        if not isinstance(sample_id, str) or not sample_id:
            raise SampleRepositoryError("VSCO manifest region has no sample identity")
        if sample_id not in files_by_id:
            raise SampleRepositoryError(
                f"VSCO manifest region refers to unknown sample id {sample_id!r}"
            )
        used_ids.add(sample_id)
    if not used_ids:
        raise SampleRepositoryError("VSCO content manifest has no playable samples")
    return [record for record in ordered_files if record["id"] in used_ids]


def _direct_drum_sample_ids(path: Path | None) -> tuple[set[str], bytes]:
    if path is None:
        return set(), b""
    try:
        encoded = path.read_bytes()
        catalogue = json.loads(encoded)
    except (OSError, json.JSONDecodeError) as exc:
        raise SampleRepositoryError(
            f"could not read PCM drum catalogue {path}: {exc}"
        ) from exc
    records = catalogue.get("sample_files") if isinstance(catalogue, dict) else None
    if not isinstance(records, list):
        raise SampleRepositoryError("PCM drum catalogue has no sample_files array")
    sample_ids: set[str] = set()
    for record in records:
        sample_id = record.get("source_sample_id") if isinstance(record, dict) else None
        if not isinstance(sample_id, str) or not sample_id:
            raise SampleRepositoryError(
                "PCM drum catalogue contains an incomplete source sample identity"
            )
        sample_ids.add(sample_id)
    return sample_ids, encoded


def _sample_inventory(
    root: Path, records: Sequence[object]
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


def _sample_receipt(
    records: list[dict[str, object]],
    *,
    manifest_hash: str,
    repository_url: str | None,
    branch: str | None,
    commit: str | None,
) -> dict[str, object]:
    return {
        "schema_revision": 1,
        "bank_id": "vsco-2-ce",
        "selection": "files referenced by playable regions or the PCM drum catalogue",
        "repository": repository_url,
        "branch": branch,
        "commit": commit,
        "content_manifest_sha256": manifest_hash,
        "file_count": len(records),
        "files": [
            {
                "relative_path": record["relative_path"],
                "sha256": record["sha256"],
            }
            for record in records
        ],
    }


def validate_sample_tree(
    path: Path,
    manifest_path: Path,
    *,
    cache_path: Path | None = None,
    repository_url: str | None = None,
    branch: str | None = None,
    commit: str | None = None,
    direct_reference_catalogue: Path | None = None,
) -> Path:
    """Validate the playable subset and maintain its installation receipt."""

    resolved = path.expanduser().resolve()
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
    except (OSError, json.JSONDecodeError) as exc:
        raise SampleRepositoryError(
            f"could not read VSCO content manifest {manifest_path}: {exc}"
        ) from exc
    direct_sample_ids, catalogue_bytes = _direct_drum_sample_ids(
        direct_reference_catalogue
    )
    records = _runtime_sample_records(manifest, direct_sample_ids)
    manifest_hash = hashlib.sha256(
        manifest_bytes + b"\0" + catalogue_bytes
    ).hexdigest()
    inventory_hash, files = _sample_inventory(resolved, records)
    receipt_path = resolved / SAMPLE_RECEIPT_NAME
    expected_receipt = _sample_receipt(
        records,
        manifest_hash=manifest_hash,
        repository_url=repository_url,
        branch=branch,
        commit=commit,
    )
    expected_cache = {
        "schema_revision": 1,
        "manifest_sha256": manifest_hash,
        "inventory_sha256": inventory_hash,
        "file_count": len(files),
    }
    if cache_path is not None:
        try:
            if (
                JsonStore(cache_path).read() == expected_cache
                and JsonStore(receipt_path).read() == expected_receipt
            ):
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
    JsonStore(receipt_path, mode=0o644).write(expected_receipt)
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
    branch: str = DEFAULT_SAMPLE_BRANCH,
    expected_commit: str = DEFAULT_SAMPLE_COMMIT,
    *,
    content_manifest: Path | None = None,
    direct_reference_catalogue: Path | None = None,
    validation_cache: Path | None = None,
) -> Path:
    destination = path.expanduser().resolve()
    if destination.exists():
        if content_manifest is not None:
            return validate_sample_tree(
                destination,
                content_manifest,
                cache_path=validation_cache,
                repository_url=repository_url,
                branch=branch,
                commit=expected_commit,
                direct_reference_catalogue=direct_reference_catalogue,
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
        f"Installing the LB Omnichord VSCO 2 CE sample subset in {destination}; "
        "this is a one-time download.",
        file=sys.stderr,
        flush=True,
    )
    try:
        porcelain.clone(
            repository_url,
            str(checkout),
            checkout=True,
            depth=1,
            branch=branch,
        )
        validate_sample_repository(checkout, repository_url, expected_commit)
        if content_manifest is not None:
            validate_sample_tree(
                checkout,
                content_manifest,
                cache_path=validation_cache,
                repository_url=repository_url,
                branch=branch,
                commit=expected_commit,
                direct_reference_catalogue=direct_reference_catalogue,
            )
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
    default_sample_branch: str,
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
    elif revision == 5 and server["gesture_voice_limit"] == 24:
        # Revision 5 briefly shipped on the development branch with a limit
        # below the natural overlap of the 450 ms strum tail. Upgrade only
        # that exact old default; preserve an explicitly chosen other value.
        server["gesture_voice_limit"] = default_gesture_voice_limit
        changed = True

    samples = migrated.get("samples")
    if not isinstance(samples, dict):
        raise SampleRepositoryError("SuperCollider config samples object is missing")
    if "commit" not in samples:
        samples["commit"] = default_sample_commit
        changed = True
    if "branch" not in samples:
        samples["branch"] = default_sample_branch
        changed = True
        if samples.get("commit") == LEGACY_SAMPLE_COMMIT:
            samples["commit"] = default_sample_commit

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
        default_sample_branch=shipped.samples.branch,
        default_sample_commit=shipped.samples.commit,
    )
    if changed:
        store.write(migrated)
    config = load_supercollider_config(target)
    if install_samples:
        ensure_sample_repository(
            config.samples.vsco_root,
            config.samples.repository,
            config.samples.branch,
            config.samples.commit,
            content_manifest=_sample_manifest_for_config(shipped_config),
            direct_reference_catalogue=_drum_catalogue_for_config(shipped_config),
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
