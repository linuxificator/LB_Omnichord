from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from filesystem_platform_adapters import set_descriptor_mode, sync_directory


class JsonStoreError(OSError):
    """A JSON store operation failed without discarding the prior value."""


@dataclass(frozen=True, slots=True)
class JsonStore:
    path: Path
    mode: int = 0o600

    @property
    def previous_path(self) -> Path:
        return self.path.with_suffix(self.path.suffix + ".previous")

    def read(self) -> Any:
        return self._read_path(self.path)

    def read_previous(self) -> Any:
        return self._read_path(self.previous_path)

    @staticmethod
    def _read_path(path: Path) -> Any:
        try:
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except FileNotFoundError:
            raise
        except (OSError, json.JSONDecodeError) as exc:
            raise JsonStoreError(f"cannot read JSON store {path}: {exc}") from exc

    def write(self, value: Any) -> None:
        try:
            encoded = (
                json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)
                + "\n"
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise JsonStoreError(
                f"cannot serialize JSON store {self.path}: {exc}"
            ) from exc

        descriptor = -1
        temporary_path: Path | None = None
        moved_previous = False
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            descriptor, raw_path = tempfile.mkstemp(
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                dir=self.path.parent,
            )
            temporary_path = Path(raw_path)
            set_descriptor_mode(descriptor, self.mode)
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = -1
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())

            if self.path.exists():
                os.replace(self.path, self.previous_path)
                moved_previous = True
                os.chmod(self.previous_path, self.mode)
            os.replace(temporary_path, self.path)
            temporary_path = None
            os.chmod(self.path, self.mode)
            self._sync_directory()
        except OSError as exc:
            if moved_previous and not self.path.exists() and self.previous_path.exists():
                try:
                    os.replace(self.previous_path, self.path)
                    self._sync_directory()
                except OSError as restore_exc:
                    raise JsonStoreError(
                        f"cannot write {self.path}; previous value remains at "
                        f"{self.previous_path}; restore also failed: {restore_exc}"
                    ) from exc
            raise JsonStoreError(
                f"cannot atomically write JSON store {self.path}: {exc}"
            ) from exc
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def _sync_directory(self) -> None:
        sync_directory(self.path.parent)
