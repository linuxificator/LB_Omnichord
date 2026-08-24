#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import signal
import socket
import stat
import sys
from pathlib import Path


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Standalone Linux AMY audio service for LB Omnichord"
    )
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--max-buses", type=int, default=None)
    parser.add_argument("--max-oscs", type=int, default=None)
    return parser.parse_args()


def remove_stale_socket(path: Path) -> None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return
    if not stat.S_ISSOCK(mode):
        raise RuntimeError(f"refusing to remove non-socket path: {path}")
    path.unlink()


def main() -> int:
    args = parse_arguments()
    with args.config.expanduser().open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    max_buses = int(
        config.get("amy_max_buses", 11)
        if args.max_buses is None
        else args.max_buses
    )
    max_oscs = int(
        config.get("amy_max_oscs", 336)
        if args.max_oscs is None
        else args.max_oscs
    )
    if max_buses < 11:
        raise ValueError("LB Omnichord requires at least 11 AMY buses")
    args.socket = args.socket.expanduser().resolve()
    args.socket.parent.mkdir(parents=True, exist_ok=True)
    remove_stale_socket(args.socket)

    try:
        import amy  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "AMY is not installed in this Python environment; install the "
            "local amyfork first"
        ) from exc

    amy.live(
        default_synths=0,
        max_buses=max_buses,
        max_oscs=max_oscs,
    )

    running = True

    def stop(_signum: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    stream_transport = sys.platform == "darwin"
    socket_type = socket.SOCK_STREAM if stream_transport else socket.SOCK_SEQPACKET
    server = socket.socket(socket.AF_UNIX, socket_type)
    try:
        server.bind(str(args.socket))
        args.socket.chmod(0o600)
        server.listen(1)
        server.settimeout(0.25)
        print(f"AMY service ready: {args.socket}", flush=True)

        while running:
            try:
                client, _ = server.accept()
            except TimeoutError:
                continue
            with client:
                client.settimeout(0.25)
                buffered = b""
                while running:
                    try:
                        packet = client.recv(4096)
                    except TimeoutError:
                        continue
                    if not packet:
                        break
                    if not stream_transport:
                        amy.send_wire(packet.decode("ascii"))
                        continue
                    buffered += packet
                    while b"\n" in buffered:
                        request, buffered = buffered.split(b"\n", 1)
                        if request:
                            amy.send_wire(request.decode("ascii"))
    finally:
        server.close()
        remove_stale_socket(args.socket)
        stop_native = getattr(getattr(amy, "_amy", None), "stop", None)
        if callable(stop_native):
            stop_native()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"AMY service error: {exc}", file=sys.stderr, flush=True)
        raise
