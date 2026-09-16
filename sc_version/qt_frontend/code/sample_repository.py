from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
import json
from pathlib import Path
from pathlib import PurePosixPath
import shutil
import sys
import tarfile
import tempfile
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

from json_store import JsonStore
from release_identity import release_user_root
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
SAMPLE_DOWNLOAD_TIMEOUT_SECONDS = 60.0


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


def _sample_archive_url(repository_url: str, commit: str) -> str:
    _host, owner, name = _repository_identity(repository_url)
    invalid_commit = len(commit) != 40 or any(
        character not in "0123456789abcdefABCDEF" for character in commit
    )
    if invalid_commit:
        raise SampleRepositoryError(f"invalid pinned sample commit: {commit!r}")
    return (
        "https://codeload.github.com/"
        f"{quote(owner, safe='')}/{quote(name, safe='')}/tar.gz/{commit.lower()}"
    )


def _install_sample_snapshot(
    destination: Path,
    repository_url: str,
    expected_commit: str,
    required: RequiredSampleList,
) -> None:
    """Stream only required files from a pinned GitHub tree snapshot.

    A Git clone duplicates every incompressible WAV in its object store. A
    codeload snapshot has the same pinned tree identity without history; files
    are copied directly from the response, so neither an archive nor `.git`
    remains on disk.
    """

    _host, _owner, repository_name = _repository_identity(repository_url)
    expected_archive_root = f"{repository_name}-{expected_commit}".casefold()
    archive_url = _sample_archive_url(repository_url, expected_commit)
    request = Request(
        archive_url,
        headers={
            "Accept": "application/x-gzip",
            "User-Agent": "LB-Omnichord-sample-installer/1",
        },
    )
    required_paths = set(required.files)
    installed: set[str] = set()
    try:
        with urlopen(request, timeout=SAMPLE_DOWNLOAD_TIMEOUT_SECONDS) as response:
            with tarfile.open(fileobj=response, mode="r|gz") as archive:
                for member in archive:
                    member_path = PurePosixPath(member.name)
                    if member_path.is_absolute() or ".." in member_path.parts:
                        raise SampleRepositoryError(
                            f"sample snapshot contains unsafe path {member.name!r}"
                        )
                    if len(member_path.parts) < 2:
                        continue
                    if member_path.parts[0].casefold() != expected_archive_root:
                        raise SampleRepositoryError(
                            "sample snapshot has an unexpected archive root: "
                            f"{member_path.parts[0]!r}"
                        )
                    relative = PurePosixPath(*member_path.parts[1:]).as_posix()
                    if relative not in required_paths:
                        continue
                    if relative in installed:
                        raise SampleRepositoryError(
                            f"sample snapshot repeats required path {relative!r}"
                        )
                    if not member.isfile():
                        raise SampleRepositoryError(
                            f"required sample is not a regular file: {relative!r}"
                        )
                    source = archive.extractfile(member)
                    if source is None:
                        raise SampleRepositoryError(
                            f"could not read required sample {relative!r}"
                        )
                    target = destination / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with source, target.open("wb") as output:
                        shutil.copyfileobj(source, output, length=1024 * 1024)
                    installed.add(relative)
    except (OSError, tarfile.TarError) as exc:
        raise SampleRepositoryError(
            f"could not download pinned sample snapshot {archive_url}: {exc}"
        ) from exc

    missing = sorted(required_paths - installed)
    if missing:
        example = missing[0]
        raise SampleRepositoryError(
            "pinned sample snapshot is incomplete; "
            f"missing {len(missing)} required file(s), including {example!r}"
        )


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
        if required_samples is None:
            raise SampleRepositoryError(
                "a required sample list is needed to validate the sample directory"
            )
        return validate_sample_tree(
            destination,
            required_samples,
            repository_url=repository_url,
            branch=branch,
            commit=expected_commit,
        )
    if required_samples is None:
        raise SampleRepositoryError(
            "a required sample list is needed to install the sample directory"
        )

    required = load_required_sample_list(required_samples)
    if _repository_identity(required.repository) != _repository_identity(
        repository_url
    ):
        raise SampleRepositoryError(
            "required sample list repository differs from the runtime config"
        )
    if required.branch != branch or required.commit != expected_commit:
        raise SampleRepositoryError(
            "required sample list branch or commit differs from the runtime config"
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_root = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.install-", dir=destination.parent)
    )
    snapshot = temporary_root / "snapshot"
    snapshot.mkdir()
    print(
        f"Installing {len(required.files)} LB Omnichord VSCO 2 CE samples in "
        f"{destination}; this is a one-time download without Git history.",
        file=sys.stderr,
        flush=True,
    )
    try:
        _install_sample_snapshot(
            snapshot,
            repository_url,
            expected_commit,
            required,
        )
        validate_sample_tree(
            snapshot,
            required_samples,
            repository_url=repository_url,
            branch=branch,
            commit=expected_commit,
        )
        snapshot.replace(destination)
    except SampleRepositoryError:
        raise
    except Exception as exc:
        raise SampleRepositoryError(
            f"could not install sample snapshot {repository_url} in {destination}: {exc}"
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

    root = (user_root or release_user_root()).expanduser().resolve()
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
