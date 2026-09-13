#!/usr/bin/env python3
"""Minimal separate-process implementation of the internal SC test boundary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import signal
import threading
from typing import Any

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--ready-file", type=Path)
    return parser.parse_args()


class FakeSuperColliderService:
    def __init__(self, port: int, log_path: Path) -> None:
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._reply_port: int | None = None
        dispatcher = Dispatcher()
        dispatcher.set_default_handler(self._accept)
        self.server = ThreadingOSCUDPServer(("127.0.0.1", port), dispatcher)

    def _record(self, address: str, arguments: tuple[Any, ...]) -> None:
        payload = {"address": address, "arguments": list(arguments)}
        with self._lock, self.log_path.open("a", encoding="utf-8") as output:
            output.write(json.dumps(payload, separators=(",", ":")) + "\n")
            output.flush()

    def _send(self, address: str, arguments: list[Any]) -> None:
        if self._reply_port is None:
            return
        client = SimpleUDPClient("127.0.0.1", self._reply_port)
        try:
            client.send_message(address, arguments)
        finally:
            client._sock.close()

    def _accept(self, address: str, *arguments: Any) -> None:
        self._record(address, arguments)
        if address == "/omni/v1/hello":
            self._reply_port = int(arguments[2])
            self._send(
                "/omni/v1/ready",
                ["fake-engine", 1, "fake-catalog", "ready"],
            )
        elif address == "/omni/v1/tx/commit":
            self._send(
                "/omni/v1/ack",
                [arguments[0], arguments[1], "applied", 1, 0.0, "ok"],
            )
        elif address == "/omni/v1/program/prepare":
            self._send(
                "/omni/v1/program/status",
                [arguments[0], arguments[3], arguments[4], "ready", "ok"],
            )
        elif address == "/omni/v1/shutdown":
            threading.Thread(target=self.server.shutdown, daemon=True).start()

    def run(self) -> None:
        self.server.serve_forever(poll_interval=0.05)
        self.server.server_close()


def main() -> int:
    args = parse_args()
    service = FakeSuperColliderService(args.port, args.log)

    def stop(_signum: int, _frame: object) -> None:
        threading.Thread(target=service.server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    if args.ready_file is not None:
        args.ready_file.parent.mkdir(parents=True, exist_ok=True)
        args.ready_file.touch()
    service.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
