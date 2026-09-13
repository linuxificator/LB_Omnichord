from __future__ import annotations

from typing import Protocol


class OscServiceAdvertiser(Protocol):
    """Best-effort lifecycle for advertising one listening OSC endpoint."""

    def start(self, *, service_name: str, listen_address: str, port: int) -> None: ...

    def close(self) -> None: ...


class NullOscServiceAdvertiser:
    """Deliberate no-op used on unsupported platforms and in isolated tests."""

    def start(self, *, service_name: str, listen_address: str, port: int) -> None:
        del service_name, listen_address, port

    def close(self) -> None:
        pass


def null_osc_service_advertiser() -> OscServiceAdvertiser:
    return NullOscServiceAdvertiser()
