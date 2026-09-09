"""Optional Raspberry Pi realtime-policy registration client.

The application and AMY service identify only their semantic role and shared
wire endpoint.  The privileged watcher obtains PID, UID and GID from Linux
``SO_PEERCRED``; no caller-supplied process identity is trusted.
"""

from __future__ import annotations

import json
import os
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


PROTOCOL = "lb-omnichord-rt-v1"
RUNTIME_DIRECTORY = Path("/run/lb-omnichord-rt")
RegistrationRole = Literal["amy-service", "frontend"]


@dataclass(slots=True)
class PolicyRegistration:
    connection: socket.socket | None
    accepted: bool
    applied: bool
    issue: str = ""

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None


def registration_socket_path(
    uid: int | None = None,
    *,
    runtime_directory: Path = RUNTIME_DIRECTORY,
) -> Path:
    getuid = getattr(os, "getuid", None)
    if uid is None:
        if getuid is None:
            raise RuntimeError("numeric process identity is unavailable")
        effective_uid = int(getuid())
    else:
        effective_uid = int(uid)
    return runtime_directory / f"policy-{effective_uid}.sock"


def canonical_endpoint(endpoint: str | Path) -> str:
    return str(Path(endpoint).expanduser().resolve())


def _response(packet: bytes) -> dict[str, Any]:
    try:
        value = json.loads(packet.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("realtime watcher returned an invalid response") from exc
    if not isinstance(value, dict) or value.get("protocol") != PROTOCOL:
        raise RuntimeError("realtime watcher returned an incompatible response")
    return value


def register_policy_role(
    role: RegistrationRole,
    endpoint: str | Path,
    *,
    timeout: float = 2.0,
    runtime_directory: Path = RUNTIME_DIRECTORY,
) -> PolicyRegistration:
    """Register this process when the optional Linux watcher is installed.

    Absence of the host integration is an ordinary, non-fatal result.  A live
    connection is returned as the exact process-lifetime token and must remain
    open until that role stops.
    """

    if not hasattr(os, "getuid") or not hasattr(socket, "AF_UNIX"):
        return PolicyRegistration(None, False, False, "unsupported host")
    path = registration_socket_path(runtime_directory=runtime_directory)
    try:
        if not path.is_socket():
            return PolicyRegistration(None, False, False, "watcher is unavailable")
    except OSError:
        return PolicyRegistration(None, False, False, "watcher is unavailable")

    connection = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    connection.settimeout(timeout)
    request = {
        "protocol": PROTOCOL,
        "role": role,
        "endpoint": canonical_endpoint(endpoint),
    }
    try:
        connection.connect(str(path))
        connection.sendall(json.dumps(request, separators=(",", ":")).encode("utf-8"))
        response = _response(connection.recv(65536))
    except (OSError, RuntimeError) as exc:
        connection.close()
        return PolicyRegistration(None, False, False, str(exc))

    accepted = response.get("accepted") is True
    applied = response.get("applied") is True
    issue = str(response.get("issue", ""))
    if not accepted:
        connection.close()
        return PolicyRegistration(None, False, False, issue or "registration rejected")
    return PolicyRegistration(connection, True, applied, issue)
