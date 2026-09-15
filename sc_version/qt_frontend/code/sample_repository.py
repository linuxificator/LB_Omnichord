from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
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


def _required_sample_list_for_config(shipped_config: Path) -> Path:
    source = shipped_config.expanduser().resolve()
    candidates = (
        source.parents[1] / "supercollider" / "required-samples.json",
        source.parents[2] / "supercollider" / "required-samples.json",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise SampleRepositoryError(
        f"could not locate the required sample list beside {source}"
    )


@dataclass(frozen=True, slots=True)
class RequiredSampleList:
    bank_id: str
    repository: str
    branch: str
    commit: str
    files: frozenset[str]

    def as_json(self) -> dict[str, object]:
        return {
            "schema_revision": 1,
            "bank_id": self.bank_id,
            "repository": self.repository,
            "branch": self.branch,
            "commit": self.commit,
            "file_count": len(self.files),
            "files": sorted(self.files),
        }


def _required_sample_list(data: object, source: str) -> RequiredSampleList:
    if not isinstance(data, dict) or data.get("schema_revision") != 1:
        raise SampleRepositoryError(f"{source} has no supported schema revision")
    expected_keys = {
        "schema_revision",
        "bank_id",
        "repository",
        "branch",
        "commit",
        "file_count",
        "files",
    }
    if set(data) != expected_keys:
        raise SampleRepositoryError(f"{source} has unexpected sample-list fields")
    bank_id = data.get("bank_id")
    repository = data.get("repository")
    branch = data.get("branch")
    commit = data.get("commit")
    raw_files = data.get("files")
    if not isinstance(bank_id, str) or not bank_id:
        raise SampleRepositoryError(f"{source} has incomplete sample identity")
    if not isinstance(repository, str) or not repository:
        raise SampleRepositoryError(f"{source} has incomplete sample identity")
    if not isinstance(branch, str) or not branch:
        raise SampleRepositoryError(f"{source} has incomplete sample identity")
    if not isinstance(commit, str) or not commit:
        raise SampleRepositoryError(f"{source} has incomplete sample identity")
    if not isinstance(raw_files, list) or not raw_files:
        raise SampleRepositoryError(f"{source} has no required sample files")
    files: set[str] = set()
    for relative in raw_files:
        if not isinstance(relative, str) or not relative:
            raise SampleRepositoryError(f"{source} contains an invalid sample path")
        relative_path = PurePosixPath(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise SampleRepositoryError(
                f"{source} contains an unsafe sample path: {relative!r}"
            )
        if relative in files:
            raise SampleRepositoryError(
                f"{source} contains duplicate sample path {relative!r}"
            )
        files.add(relative)
    file_count = data.get("file_count")
    if file_count != len(files):
        raise SampleRepositoryError(
            f"{source} file_count does not match its sample list"
        )
    return RequiredSampleList(
        bank_id=bank_id,
        repository=repository,
        branch=branch,
        commit=commit,
        files=frozenset(files),
    )


def load_required_sample_list(path: Path) -> RequiredSampleList:
    try:
        data = JsonStore(path).read()
    except (FileNotFoundError, OSError) as exc:
        raise SampleRepositoryError(
            f"could not read required sample list {path}: {exc}"
        ) from exc
    return _required_sample_list(data, str(path))


def validate_sample_tree(
    path: Path,
    required_samples_path: Path,
    *,
    repository_url: str | None = None,
    branch: str | None = None,
    commit: str | None = None,
) -> Path:
    """Compare semantic sample lists and verify every listed path exists."""

    resolved = path.expanduser().resolve()
    required = load_required_sample_list(required_samples_path)
    if repository_url is not None and _repository_identity(
        required.repository
    ) != _repository_identity(repository_url):
        raise SampleRepositoryError(
            "required sample list repository differs from the runtime config"
        )
    if branch is not None and required.branch != branch:
        raise SampleRepositoryError(
            "required sample list branch differs from the runtime config"
        )
    if commit is not None and required.commit != commit:
        raise SampleRepositoryError(
            "required sample list commit differs from the runtime config"
        )

    receipt_path = resolved / SAMPLE_RECEIPT_NAME
    receipt: RequiredSampleList | None = None
    try:
        receipt = _required_sample_list(
            JsonStore(receipt_path).read(), str(receipt_path)
        )
    except (FileNotFoundError, OSError, SampleRepositoryError):
        pass

    for relative in required.files:
        sample = resolved / relative
        if not sample.is_file():
            raise SampleRepositoryError(
                "sample collection is incomplete; missing "
                f"{relative!r} in {resolved}"
            )
    if receipt != required:
        JsonStore(receipt_path, mode=0o644).write(required.as_json())
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
    required_samples: Path | None = None,
) -> Path:
    destination = path.expanduser().resolve()
    if destination.exists():
        if required_samples is not None:
            return validate_sample_tree(
                destination,
                required_samples,
                repository_url=repository_url,
                branch=branch,
                commit=expected_commit,
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
        if required_samples is not None:
            validate_sample_tree(
                checkout,
                required_samples,
                repository_url=repository_url,
                branch=branch,
                commit=expected_commit,
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
    sample_root_override: Path | None = None,
    sample_root_selector: Callable[[Path], Path | None] | None = None,
) -> tuple[Path, SuperColliderRuntimeConfig]:
    """Seed/migrate user config and ensure its external sample collection."""

    root = (user_root or (Path.home() / ".omnichord")).expanduser().resolve()
    target = root / "config" / "supercollider.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    shipped = load_supercollider_config(shipped_config)
    store = JsonStore(target)
    if not target.exists():
        source = JsonStore(shipped_config).read()
        if sample_root_override is not None:
            samples = source.get("samples") if isinstance(source, dict) else None
            if not isinstance(samples, dict):
                raise SampleRepositoryError(
                    "shipped SuperCollider config has no samples object"
                )
            samples["vsco_root"] = str(sample_root_override.expanduser().resolve())
        elif install_samples and sample_root_selector is not None:
            samples = source.get("samples") if isinstance(source, dict) else None
            if not isinstance(samples, dict):
                raise SampleRepositoryError(
                    "shipped SuperCollider config has no samples object"
                )
            configured_root = samples.get("vsco_root")
            if not isinstance(configured_root, str):
                raise SampleRepositoryError(
                    "shipped SuperCollider config has no sample location"
                )
            default_root = Path(configured_root).expanduser()
            if not default_root.exists():
                selected_root = sample_root_selector(default_root)
                if selected_root is None:
                    raise SampleRepositoryError(
                        "sample location selection was cancelled; "
                        "no samples were downloaded"
                    )
                samples["vsco_root"] = str(selected_root.expanduser().resolve())
        store.write(source)
    elif sample_root_override is not None:
        source = store.read()
        samples = source.get("samples") if isinstance(source, dict) else None
        if not isinstance(samples, dict):
            raise SampleRepositoryError(
                "user SuperCollider config has no samples object"
            )
        samples["vsco_root"] = str(sample_root_override.expanduser().resolve())
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
            required_samples=_required_sample_list_for_config(shipped_config),
        )
    return target, config


def _main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare the per-user SuperCollider sample configuration."
    )
    parser.add_argument("shipped_config", type=Path)
    parser.add_argument("--without-samples", action="store_true")
    parser.add_argument(
        "--sample-root",
        type=Path,
        help="use this exact sample-library path instead of the first-run chooser",
    )
    args = parser.parse_args()
    selector: Callable[[Path], Path | None] | None = None
    if not args.without_samples:
        if args.sample_root is None:
            from sample_location_dialog import choose_sample_root

            selector = choose_sample_root
    path, _config = prepare_user_runtime_config(
        args.shipped_config,
        install_samples=not args.without_samples,
        sample_root_override=args.sample_root,
        sample_root_selector=selector,
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
