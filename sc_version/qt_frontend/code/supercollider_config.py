from __future__ import annotations

import argparse
from dataclasses import dataclass
import ipaddress
import json
from pathlib import Path
from typing import Any


CURRENT_CONFIG_REVISION = 2


class SuperColliderConfigError(ValueError):
    """Raised when the dedicated audio-engine configuration is invalid."""


@dataclass(frozen=True, slots=True)
class SuperColliderLanguageConfig:
    host: str
    port: int
    startup_timeout_seconds: float
    message_payload_bytes: int


@dataclass(frozen=True, slots=True)
class SuperColliderServerConfig:
    sample_rate: int
    block_size: int
    latency_seconds: float
    max_nodes: int
    max_buffers: int
    realtime_memory_kib: int


@dataclass(frozen=True, slots=True)
class SuperColliderSampleConfig:
    vsco_root: Path
    repository: str
    ram_budget_mib: int


@dataclass(frozen=True, slots=True)
class SuperColliderRuntimeConfig:
    config_revision: int
    protocol_version: int
    language: SuperColliderLanguageConfig
    server: SuperColliderServerConfig
    samples: SuperColliderSampleConfig


def _mapping(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise SuperColliderConfigError(f"$.{key}: required object is missing")
    return value


def _integer(parent: dict[str, Any], key: str, path: str) -> int:
    value = parent.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise SuperColliderConfigError(f"{path}.{key}: expected integer")
    return value


def _number(parent: dict[str, Any], key: str, path: str) -> float:
    value = parent.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SuperColliderConfigError(f"{path}.{key}: expected number")
    return float(value)


def load_supercollider_config(path: Path) -> SuperColliderRuntimeConfig:
    """Load the SC-only config before opening a socket or audio process."""

    source = Path(path).expanduser().resolve()
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SuperColliderConfigError(f"could not read {source}: {exc}") from exc
    if not isinstance(raw, dict):
        raise SuperColliderConfigError("$: expected object")

    revision = _integer(raw, "config_revision", "$")
    if revision != CURRENT_CONFIG_REVISION:
        raise SuperColliderConfigError(
            "$.config_revision: unsupported revision "
            f"{revision}; expected {CURRENT_CONFIG_REVISION}"
        )
    protocol_version = _integer(raw, "protocol_version", "$")
    if protocol_version != 1:
        raise SuperColliderConfigError(
            f"$.protocol_version: unsupported version {protocol_version}; expected 1"
        )

    language = _mapping(raw, "language")
    host = language.get("host")
    if not isinstance(host, str):
        raise SuperColliderConfigError("$.language.host: expected IPv4 address")
    try:
        parsed_host = ipaddress.ip_address(host)
    except ValueError as exc:
        raise SuperColliderConfigError(
            "$.language.host: expected loopback IPv4 address"
        ) from exc
    if parsed_host.version != 4 or not parsed_host.is_loopback:
        raise SuperColliderConfigError(
            "$.language.host: internal engine control must use IPv4 loopback"
        )
    port = _integer(language, "port", "$.language")
    if not 1024 <= port <= 65535:
        raise SuperColliderConfigError("$.language.port: expected 1024..65535")
    startup_timeout = _number(
        language, "startup_timeout_seconds", "$.language"
    )
    if not 0.1 <= startup_timeout <= 60.0:
        raise SuperColliderConfigError(
            "$.language.startup_timeout_seconds: expected 0.1..60"
        )
    payload_bytes = _integer(
        language, "message_payload_bytes", "$.language"
    )
    if not 256 <= payload_bytes <= 65507:
        raise SuperColliderConfigError(
            "$.language.message_payload_bytes: expected 256..65507"
        )

    server = _mapping(raw, "server")
    sample_rate = _integer(server, "sample_rate", "$.server")
    if sample_rate not in (44100, 48000, 88200, 96000):
        raise SuperColliderConfigError(
            "$.server.sample_rate: expected a supported audio sample rate"
        )
    block_size = _integer(server, "block_size", "$.server")
    if block_size < 16 or block_size > 2048 or block_size & (block_size - 1):
        raise SuperColliderConfigError(
            "$.server.block_size: expected a power of two in 16..2048"
        )
    latency = _number(server, "latency_seconds", "$.server")
    if not 0.0 <= latency <= 1.0:
        raise SuperColliderConfigError(
            "$.server.latency_seconds: expected 0..1"
        )
    max_nodes = _integer(server, "max_nodes", "$.server")
    if not 256 <= max_nodes <= 1_000_000:
        raise SuperColliderConfigError("$.server.max_nodes: expected 256..1000000")
    max_buffers = _integer(server, "max_buffers", "$.server")
    if not 1024 <= max_buffers <= 1_000_000:
        raise SuperColliderConfigError(
            "$.server.max_buffers: expected 1024..1000000"
        )
    realtime_memory = _integer(
        server, "realtime_memory_kib", "$.server"
    )
    if not 8192 <= realtime_memory <= 4_194_304:
        raise SuperColliderConfigError(
            "$.server.realtime_memory_kib: expected 8192..4194304"
        )

    samples = _mapping(raw, "samples")
    vsco_root = samples.get("vsco_root")
    if not isinstance(vsco_root, str) or not vsco_root.strip():
        raise SuperColliderConfigError("$.samples.vsco_root: expected path string")
    repository = samples.get("repository")
    if not isinstance(repository, str) or not repository.strip():
        raise SuperColliderConfigError("$.samples.repository: expected URL string")
    ram_budget = _integer(samples, "ram_budget_mib", "$.samples")
    if not 64 <= ram_budget <= 1_048_576:
        raise SuperColliderConfigError(
            "$.samples.ram_budget_mib: expected 64..1048576"
        )

    return SuperColliderRuntimeConfig(
        config_revision=revision,
        protocol_version=protocol_version,
        language=SuperColliderLanguageConfig(
            host=host,
            port=port,
            startup_timeout_seconds=startup_timeout,
            message_payload_bytes=payload_bytes,
        ),
        server=SuperColliderServerConfig(
            sample_rate=sample_rate,
            block_size=block_size,
            latency_seconds=latency,
            max_nodes=max_nodes,
            max_buffers=max_buffers,
            realtime_memory_kib=realtime_memory,
        ),
        samples=SuperColliderSampleConfig(
            vsco_root=Path(vsco_root).expanduser(),
            repository=repository,
            ram_budget_mib=ram_budget,
        ),
    )


def _cli() -> int:
    parser = argparse.ArgumentParser(
        description="Read one validated LB Omnichord SuperCollider setting."
    )
    parser.add_argument("path", type=Path)
    parser.add_argument(
        "field",
        choices=(
            "language.host",
            "language.port",
            "server.sample_rate",
            "server.block_size",
            "server.max_nodes",
            "server.max_buffers",
            "server.realtime_memory_kib",
            "samples.vsco_root",
            "samples.repository",
            "samples.ram_budget_mib",
        ),
    )
    args = parser.parse_args()
    config = load_supercollider_config(args.path)
    section, field = args.field.split(".", 1)
    print(getattr(getattr(config, section), field))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
