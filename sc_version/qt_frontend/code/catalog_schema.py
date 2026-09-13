from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol, cast

import fastjsonschema  # type: ignore[import-untyped]


class SchemaValidator(Protocol):
    def __call__(self, value: Any) -> Any: ...


def _validator(schema_path: Path) -> SchemaValidator:
    path = Path(schema_path)
    schema = json.loads(path.read_text(encoding="utf-8"))
    return cast(SchemaValidator, fastjsonschema.compile(schema))


def read_versioned_catalog(
    path: Path,
    schema_name: str,
    *,
    schema_directory: Path,
) -> Mapping[str, Any]:
    """Read and shape-validate a catalogue before domain parsing begins."""
    source = Path(path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read catalogue {source}: {exc}") from exc
    try:
        validated = _validator(Path(schema_directory) / schema_name)(raw)
    except fastjsonschema.JsonSchemaException as exc:
        location = ".".join(str(part) for part in exc.path)
        raise ValueError(
            f"catalogue {source} violates {schema_name} at {location}: {exc.message}"
        ) from exc
    if not isinstance(validated, dict):
        raise ValueError(f"catalogue {source} must contain a JSON object")
    return cast(Mapping[str, Any], validated)
