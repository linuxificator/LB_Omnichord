#!/usr/bin/env python3
"""External DNS-SD publisher/browser used only by integration tests."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from zeroconf import IPVersion, ServiceBrowser, ServiceInfo, ServiceListener, Zeroconf


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))

from osc_discovery_zeroconf import OSC_DNS_SD_TYPE  # noqa: E402
from osc_discovery_platform_adapters import (  # noqa: E402
    production_osc_service_advertiser,
)
from osc_input import production_osc_input_port  # noqa: E402
from resolved_config import OscInputConfig  # noqa: E402


class _Listener(ServiceListener):
    def __init__(self, expected_name: str) -> None:
        self.expected_name = f"{expected_name}."
        self.name: str | None = None

    def add_service(self, zeroconf: Zeroconf, type_: str, name: str) -> None:
        del zeroconf, type_
        if name.startswith(self.expected_name):
            self.name = name

    def update_service(self, zeroconf: Zeroconf, type_: str, name: str) -> None:
        self.add_service(zeroconf, type_, name)

    def remove_service(self, zeroconf: Zeroconf, type_: str, name: str) -> None:
        del zeroconf, type_, name


def advertise(name: str, port: int, ready: Path, stop: Path) -> int:
    osc_port = production_osc_input_port(
        lambda _event: None,
        OscInputConfig(
            True,
            "0.0.0.0",
            port,
            advertise=True,
            service_name=name,
        ),
        advertiser_factory=production_osc_service_advertiser,
    )
    osc_port.start()
    if osc_port.lifecycle != "ready":
        raise RuntimeError(osc_port.failure_reason)
    ready.write_text(str(os.getpid()), encoding="utf-8")
    try:
        deadline = time.monotonic() + 12.0
        while not stop.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
    finally:
        osc_port.close()
    return 0


def browse(name: str, timeout: float) -> int:
    zeroconf = Zeroconf(ip_version=IPVersion.V4Only, use_asyncio=False)
    listener = _Listener(name)
    browser = ServiceBrowser(zeroconf, OSC_DNS_SD_TYPE, listener)
    try:
        deadline = time.monotonic() + timeout
        while listener.name is None and time.monotonic() < deadline:
            time.sleep(0.02)
        if listener.name is None:
            return 2
        info: ServiceInfo | None = zeroconf.get_service_info(
            OSC_DNS_SD_TYPE,
            listener.name,
            timeout=2000,
        )
        if info is None:
            return 3
        print(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "name": info.name,
                    "port": info.port,
                    "addresses": info.parsed_addresses(),
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 0
    finally:
        browser.cancel()
        zeroconf.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    publisher = commands.add_parser("advertise")
    publisher.add_argument("--name", required=True)
    publisher.add_argument("--port", required=True, type=int)
    publisher.add_argument("--ready", required=True, type=Path)
    publisher.add_argument("--stop", required=True, type=Path)
    discovery = commands.add_parser("browse")
    discovery.add_argument("--name", required=True)
    discovery.add_argument("--timeout", default=8.0, type=float)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "advertise":
        return advertise(args.name, args.port, args.ready, args.stop)
    if args.command == "browse":
        return browse(args.name, args.timeout)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
