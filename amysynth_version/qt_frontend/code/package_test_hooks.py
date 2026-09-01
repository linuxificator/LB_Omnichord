from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path


PACKAGE_SMOKE_STATUS_ENV = "OMNICHORD_PACKAGE_SMOKE_STATUS"


@dataclass(frozen=True, slots=True)
class PackageTestHooks:
    enabled: bool
    status: Path | None

    @classmethod
    def from_environment(cls, enabled: bool) -> PackageTestHooks:
        raw = os.environ.get(PACKAGE_SMOKE_STATUS_ENV)
        return cls(bool(enabled), Path(raw) if raw else None)

    def redirected(self, *, enabled: bool, status: Path | None) -> PackageTestHooks:
        return replace(
            self,
            enabled=bool(enabled),
            status=status if status is not None else self.status,
        )

    def checkpoint(self, label: str) -> None:
        if not self.enabled or self.status is None:
            return
        self.status.parent.mkdir(parents=True, exist_ok=True)
        with self.status.open("a", encoding="utf-8") as handle:
            handle.write(f"{label}\n")
            handle.flush()
