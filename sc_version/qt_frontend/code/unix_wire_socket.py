from __future__ import annotations

import socket
from pathlib import Path


def _wire_socket_types() -> tuple[int, ...]:
    """Prefer packet framing, with an LF-framed stream fallback."""

    candidates = (
        getattr(socket, "SOCK_SEQPACKET", None),
        socket.SOCK_STREAM,
    )
    return tuple(
        socket_type
        for index, socket_type in enumerate(candidates)
        if socket_type is not None
        and socket_type not in candidates[:index]
    )


def connect_unix_wire_socket(
    socket_path: str,
    *,
    timeout: float,
) -> tuple[socket.socket, bool]:
    """Connect using the first local socket mode supported by the service."""

    errors: list[OSError] = []
    for socket_type in _wire_socket_types():
        try:
            candidate = socket.socket(socket.AF_UNIX, socket_type)
        except OSError as exc:
            errors.append(exc)
            continue
        try:
            candidate.settimeout(timeout)
            candidate.connect(str(socket_path))
            candidate.settimeout(None)
        except OSError as exc:
            errors.append(exc)
            candidate.close()
            continue
        return candidate, socket_type == socket.SOCK_STREAM

    raise OSError(
        f"no supported Unix socket mode accepted {socket_path}"
    ) from errors[-1]


def listen_unix_wire_socket(
    socket_path: Path,
) -> tuple[socket.socket, bool]:
    """Bind using the best local socket mode supported by this system."""

    errors: list[OSError] = []
    for socket_type in _wire_socket_types():
        try:
            candidate = socket.socket(socket.AF_UNIX, socket_type)
        except OSError as exc:
            errors.append(exc)
            continue
        bound = False
        try:
            candidate.bind(str(socket_path))
            bound = True
            candidate.listen(1)
        except OSError as exc:
            errors.append(exc)
            candidate.close()
            if bound:
                socket_path.unlink(missing_ok=True)
            continue
        return candidate, socket_type == socket.SOCK_STREAM

    raise OSError(
        f"no supported Unix socket mode could bind {socket_path}"
    ) from errors[-1]
