#!/usr/bin/env python3
"""Apply the measured Raspberry Pi audio policy to registered processes.

The privileged watcher never searches by executable name or command line.
AMY and frontend processes register a semantic role plus their common wire
endpoint. Linux ``SO_PEERCRED`` supplies the immutable PID/UID/GID, and the
open connection is the process-lifetime token.
"""

from __future__ import annotations

import argparse
import json
import os
import selectors
import socket
import stat
import struct
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, cast


PROTOCOL = "lb-omnichord-rt-v1"
RUNTIME_DIRECTORY = Path("/run/lb-omnichord-rt")
ROLES = frozenset(("amy-service", "frontend"))


@dataclass(frozen=True, slots=True)
class ThreadInfo:
    pid: int
    tid: int
    name: str
    command: str
    run_ns: int


@dataclass(slots=True)
class Registration:
    connection: socket.socket
    role: str
    endpoint: str
    pid: int
    uid: int
    gid: int


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        return ""


def process_command(pid: int) -> str:
    return _read(Path(f"/proc/{pid}/cmdline")).replace("\0", " ")


def process_ids(uid: int | None = None) -> list[int]:
    result: list[int] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if uid is not None and entry.stat().st_uid != uid:
                continue
        except (FileNotFoundError, PermissionError):
            continue
        result.append(int(entry.name))
    return sorted(result)


def task_ids(pid: int) -> list[int]:
    try:
        return sorted(int(path.name) for path in Path(f"/proc/{pid}/task").iterdir())
    except (FileNotFoundError, ProcessLookupError):
        return []


def thread_info(pid: int, tid: int) -> ThreadInfo | None:
    try:
        run_ns = int(
            Path(f"/proc/{pid}/task/{tid}/schedstat")
            .read_text(encoding="ascii")
            .split()[0]
        )
        name = _read(Path(f"/proc/{pid}/task/{tid}/comm"))
    except (FileNotFoundError, PermissionError, ProcessLookupError, ValueError):
        return None
    return ThreadInfo(pid, tid, name, process_command(pid), run_ns)


def snapshot_threads(pid: int) -> dict[int, ThreadInfo]:
    return {
        item.tid: item
        for tid in task_ids(pid)
        if (item := thread_info(pid, tid)) is not None
    }


def select_active_worker(pid: int, seconds: float = 0.35) -> ThreadInfo:
    before = snapshot_threads(pid)
    time.sleep(seconds)
    after = snapshot_threads(pid)
    candidates = [
        item
        for tid, item in after.items()
        if tid != pid and tid in before and item.run_ns > before[tid].run_ns
    ]
    if not candidates:
        raise RuntimeError(f"no active worker thread found in PID {pid}")
    return max(candidates, key=lambda item: item.run_ns - before[item.tid].run_ns)


def discover_pipewire(uid: int | None = None) -> list[int]:
    result = []
    for pid in process_ids(uid):
        command = process_command(pid)
        executable = Path(command.split(" ", 1)[0]).name if command else ""
        if executable in {"pipewire", "pipewire-pulse"}:
            result.append(pid)
    return result


def runtime_signature(
    service_pid: int,
    frontend_pid: int | None,
    uid: int | None = None,
) -> tuple[object, ...]:
    """Return exact identities whose replacement requires reapplication."""

    pipewire_loops = tuple(
        (pid, tid)
        for pid in discover_pipewire(uid)
        for tid in task_ids(pid)
        if _read(Path(f"/proc/{pid}/task/{tid}/comm")) == "data-loop.0"
    )
    return (
        service_pid,
        frontend_pid,
        tuple(task_ids(service_pid)),
        tuple(task_ids(frontend_pid)) if frontend_pid is not None else (),
        pipewire_loops,
    )


def set_thread_policy(tid: int, cpus: set[int], fifo_priority: int = 0) -> None:
    os.sched_setaffinity(tid, cpus)
    policy = os.SCHED_FIFO if fifo_priority else os.SCHED_OTHER
    os.sched_setscheduler(tid, policy, os.sched_param(fifo_priority))


def current_policy(tid: int) -> dict[str, object]:
    return {
        "tid": tid,
        "affinity": sorted(os.sched_getaffinity(tid)),
        "scheduler": os.sched_getscheduler(tid),
        "priority": os.sched_getparam(tid).sched_priority,
    }


def _policy_matches(
    tid: int,
    cpus: set[int],
    scheduler: int,
    priority: int,
) -> bool:
    policy = current_policy(tid)
    return (
        policy["affinity"] == sorted(cpus)
        and policy["scheduler"] == scheduler
        and policy["priority"] == priority
    )


def apply_split_policy(
    service_pid: int,
    uid: int | None = None,
    *,
    frontend_pid: int | None = None,
) -> dict[str, object]:
    """Keep general work on 0-1, PipeWire on 2 and AMY callback on 3."""

    frontend_threads = task_ids(frontend_pid) if frontend_pid is not None else []
    for tid in frontend_threads:
        set_thread_policy(tid, {0, 1})
    for tid in task_ids(service_pid):
        set_thread_policy(tid, {0, 1})
    audio = select_active_worker(service_pid)
    set_thread_policy(audio.tid, {3}, 70)

    pipewire_result = []
    priorities = {"pipewire": 80, "pipewire-pulse": 75}
    for pid in discover_pipewire(uid):
        command = process_command(pid)
        executable = Path(command.split(" ", 1)[0]).name
        for tid in task_ids(pid):
            name = _read(Path(f"/proc/{pid}/task/{tid}/comm"))
            if name == "data-loop.0":
                set_thread_policy(tid, {2}, priorities[executable])
                pipewire_result.append(
                    {
                        "process": executable,
                        "pid": pid,
                        "tid": tid,
                        "cpu": 2,
                        "fifo": priorities[executable],
                    }
                )
    if {str(item["process"]) for item in pipewire_result} != {
        "pipewire",
        "pipewire-pulse",
    }:
        raise RuntimeError("did not find both PipeWire data-loop.0 threads")

    result: dict[str, object] = {
        "amy": {**asdict(audio), "cpu": 3, "fifo": 70},
        "frontend": {
            "pid": frontend_pid,
            "threads": len(frontend_threads),
            "cpus": [0, 1],
        },
        "pipewire": pipewire_result,
        "housekeeping_cpus": [0, 1],
    }
    verify_applied_policy(result, require_frontend=frontend_pid is not None)
    return result


def verify_applied_policy(
    result: dict[str, object],
    *,
    require_frontend: bool,
) -> None:
    amy = cast(dict[str, object], result["amy"])
    if not _policy_matches(int(amy["tid"]), {3}, os.SCHED_FIFO, 70):
        raise RuntimeError("AMY callback realtime policy verification failed")

    frontend = cast(dict[str, object], result["frontend"])
    frontend_pid = frontend.get("pid")
    if require_frontend:
        if frontend_pid is None or not task_ids(int(frontend_pid)):
            raise RuntimeError("frontend registration disappeared during policy setup")
        for tid in task_ids(int(frontend_pid)):
            if not _policy_matches(tid, {0, 1}, os.SCHED_OTHER, 0):
                raise RuntimeError("frontend scheduling policy verification failed")

    processes = set()
    for entry in cast(list[dict[str, object]], result["pipewire"]):
        processes.add(str(entry["process"]))
        if not _policy_matches(
            int(entry["tid"]), {2}, os.SCHED_FIFO, int(entry["fifo"])
        ):
            raise RuntimeError("PipeWire realtime policy verification failed")
    if processes != {"pipewire", "pipewire-pulse"}:
        raise RuntimeError("PipeWire realtime policy is incomplete")


def verify(service_pid: int, uid: int | None = None) -> dict[str, object]:
    audio = select_active_worker(service_pid)
    return {
        "amy_candidate": current_policy(audio.tid),
        "pipewire": [
            {"name": _read(Path(f"/proc/{pid}/task/{tid}/comm")), **current_policy(tid)}
            for pid in discover_pipewire(uid)
            for tid in task_ids(pid)
            if _read(Path(f"/proc/{pid}/task/{tid}/comm")) == "data-loop.0"
        ],
    }


def registration_socket_path(
    uid: int,
    *,
    runtime_directory: Path = RUNTIME_DIRECTORY,
) -> Path:
    return runtime_directory / f"policy-{uid}.sock"


def peer_credentials(connection: socket.socket) -> tuple[int, int, int]:
    if not hasattr(socket, "SO_PEERCRED"):
        raise RuntimeError("Linux SO_PEERCRED support is required")
    size = struct.calcsize("3i")
    return struct.unpack(
        "3i",
        connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, size),
    )


def parse_registration(packet: bytes) -> tuple[str, str]:
    try:
        request = json.loads(packet.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid registration message") from exc
    if not isinstance(request, dict) or request.get("protocol") != PROTOCOL:
        raise ValueError("incompatible registration protocol")
    role = request.get("role")
    endpoint = request.get("endpoint")
    if role not in ROLES:
        raise ValueError("invalid registered role")
    if not isinstance(endpoint, str) or not endpoint or not Path(endpoint).is_absolute():
        raise ValueError("registered endpoint must be an absolute path")
    return str(role), str(Path(endpoint).resolve())


def _send_response(
    connection: socket.socket,
    *,
    accepted: bool,
    applied: bool,
    issue: str = "",
) -> None:
    response = {
        "protocol": PROTOCOL,
        "accepted": accepted,
        "applied": applied,
        "issue": issue,
    }
    connection.sendall(json.dumps(response, separators=(",", ":")).encode("utf-8"))


class RegistrationWatcher:
    def __init__(
        self,
        uid: int,
        *,
        runtime_directory: Path = RUNTIME_DIRECTORY,
        apply_policy: Callable[..., dict[str, object]] = apply_split_policy,
    ) -> None:
        self.uid = uid
        self.runtime_directory = runtime_directory
        self.path = registration_socket_path(uid, runtime_directory=runtime_directory)
        self.apply_policy = apply_policy
        self.registrations: dict[tuple[str, str], Registration] = {}
        self.signatures: dict[str, tuple[object, ...]] = {}
        self.results: dict[str, dict[str, object]] = {}
        self.process_fds: dict[int, int] = {}
        self.selector = selectors.DefaultSelector()
        self.server: socket.socket | None = None

    def open(self) -> None:
        self.runtime_directory.mkdir(parents=True, exist_ok=True)
        mode = self.path.lstat().st_mode if self.path.exists() else None
        if mode is not None:
            if not stat.S_ISSOCK(mode):
                raise RuntimeError(f"refusing to replace non-socket path: {self.path}")
            self.path.unlink()
        server = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        try:
            server.bind(str(self.path))
        except BaseException:
            server.close()
            raise
        if self.path.stat().st_uid != self.uid:
            os.chown(self.path, self.uid, -1)
        self.path.chmod(0o600)
        server.listen(8)
        server.setblocking(False)
        self.server = server
        self.selector.register(server, selectors.EVENT_READ, None)

    def close(self) -> None:
        for registration in tuple(self.registrations.values()):
            self._remove(registration)
        for pid in tuple(self.process_fds):
            self._remove_process_fd(pid)
        if self.server is not None:
            self.selector.unregister(self.server)
            self.server.close()
            self.server = None
        self.selector.close()
        try:
            if self.path.is_socket():
                self.path.unlink()
        except OSError:
            pass

    def _remove(self, registration: Registration) -> None:
        key = (registration.role, registration.endpoint)
        if self.registrations.get(key) is registration:
            self.registrations.pop(key, None)
        try:
            self.selector.unregister(registration.connection)
        except (KeyError, ValueError):
            pass
        registration.connection.close()
        self.signatures.pop(registration.endpoint, None)
        self.results.pop(registration.endpoint, None)

    def _remove_process_fd(self, pid: int) -> None:
        descriptor = self.process_fds.pop(pid, None)
        if descriptor is None:
            return
        try:
            self.selector.unregister(descriptor)
        except (KeyError, ValueError):
            pass
        os.close(descriptor)

    def _refresh_process_fds(self) -> None:
        wanted = set(discover_pipewire(self.uid))
        for pid in set(self.process_fds) - wanted:
            self._remove_process_fd(pid)
        if not hasattr(os, "pidfd_open"):
            return
        for pid in wanted - set(self.process_fds):
            try:
                descriptor = os.pidfd_open(pid)
                self.selector.register(
                    descriptor, selectors.EVENT_READ, ("pidfd", pid)
                )
            except (OSError, ProcessLookupError):
                continue
            self.process_fds[pid] = descriptor

    def _apply_endpoint(self, endpoint: str) -> dict[str, object]:
        service = self.registrations.get(("amy-service", endpoint))
        if service is None:
            raise RuntimeError("matching AMY service has not registered")
        frontend = self.registrations.get(("frontend", endpoint))
        result = self.apply_policy(
            service.pid,
            self.uid,
            frontend_pid=frontend.pid if frontend is not None else None,
        )
        self.signatures[endpoint] = runtime_signature(
            service.pid,
            frontend.pid if frontend is not None else None,
            self.uid,
        )
        self.results[endpoint] = result
        self._refresh_process_fds()
        return result

    def accept(self) -> Registration | None:
        assert self.server is not None
        connection, _address = self.server.accept()
        connection.settimeout(2.0)
        try:
            pid, uid, gid = peer_credentials(connection)
            if uid != self.uid:
                raise PermissionError(f"registration UID {uid} does not match {self.uid}")
            role, endpoint = parse_registration(connection.recv(65536))
            registration = Registration(connection, role, endpoint, pid, uid, gid)
            old = self.registrations.get((role, endpoint))
            if old is not None:
                self._remove(old)
            self.registrations[(role, endpoint)] = registration
            try:
                self._apply_endpoint(endpoint)
            except (OSError, RuntimeError, ProcessLookupError) as exc:
                _send_response(connection, accepted=True, applied=False, issue=str(exc))
            else:
                _send_response(connection, accepted=True, applied=True)
            connection.setblocking(False)
            self.selector.register(connection, selectors.EVENT_READ, registration)
            return registration
        except (OSError, ValueError, PermissionError) as exc:
            try:
                _send_response(connection, accepted=False, applied=False, issue=str(exc))
            except OSError:
                pass
            connection.close()
            return None

    def _retry_and_verify(self) -> None:
        endpoints = {endpoint for _role, endpoint in self.registrations}
        for endpoint in endpoints:
            service = self.registrations.get(("amy-service", endpoint))
            if service is None:
                continue
            frontend = self.registrations.get(("frontend", endpoint))
            signature = runtime_signature(
                service.pid,
                frontend.pid if frontend is not None else None,
                self.uid,
            )
            if self.signatures.get(endpoint) == signature:
                try:
                    verify_applied_policy(
                        self.results[endpoint],
                        require_frontend=frontend is not None,
                    )
                except (KeyError, OSError, RuntimeError, ProcessLookupError):
                    pass
                else:
                    continue
            try:
                result = self._apply_endpoint(endpoint)
            except (OSError, RuntimeError, ProcessLookupError) as exc:
                print(f"endpoint {endpoint}: {exc}", flush=True)
            else:
                print(json.dumps(result), flush=True)

    def run(self, interval: float) -> None:
        self.open()
        while True:
            registered_services = {
                endpoint
                for role, endpoint in self.registrations
                if role == "amy-service"
            }
            pending = registered_services - set(self.signatures)
            events = self.selector.select(timeout=2.0 if pending else interval)
            for key, _mask in events:
                registration = key.data
                if registration is None:
                    accepted = self.accept()
                    if accepted is not None:
                        print(
                            json.dumps(
                                {
                                    "registered": accepted.role,
                                    "endpoint": accepted.endpoint,
                                    "pid": accepted.pid,
                                    "uid": accepted.uid,
                                }
                            ),
                            flush=True,
                        )
                    continue
                if isinstance(registration, tuple) and registration[0] == "pidfd":
                    self._remove_process_fd(int(registration[1]))
                    self.signatures.clear()
                    self.results.clear()
                    continue
                assert isinstance(registration, Registration)
                try:
                    packet = registration.connection.recv(1)
                except (BlockingIOError, OSError):
                    packet = b""
                if not packet:
                    self._remove(registration)
                else:
                    self._remove(registration)
            self._retry_and_verify()


def _parse_uid(value: str) -> int:
    if value.isdigit():
        return int(value)
    import pwd

    return pwd.getpwnam(value).pw_uid


def _require_root() -> None:
    if os.geteuid() != 0:
        raise PermissionError("runtime scheduling changes must run as root")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inspect", "apply", "watch"))
    parser.add_argument("--user", default=str(os.getuid()))
    parser.add_argument("--service-pid", type=int)
    parser.add_argument("--frontend-pid", type=int)
    parser.add_argument("--interval", type=float, default=60.0)
    args = parser.parse_args()
    uid = _parse_uid(args.user)
    if args.command != "inspect":
        _require_root()

    if args.command == "inspect":
        path = registration_socket_path(uid)
        print(
            json.dumps(
                {
                    "registration_socket": str(path),
                    "watcher_available": path.is_socket(),
                    "pipewire": discover_pipewire(uid),
                },
                indent=2,
            )
        )
        return 0
    if args.command == "apply":
        if args.service_pid is None:
            raise RuntimeError("apply requires --service-pid; process-name discovery is disabled")
        result = apply_split_policy(
            args.service_pid,
            uid,
            frontend_pid=args.frontend_pid,
        )
        print(json.dumps(result, indent=2))
        return 0

    watcher = RegistrationWatcher(uid)
    try:
        watcher.run(args.interval)
    finally:
        watcher.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, PermissionError, ValueError) as exc:
        print(f"rt_pi_runtime: {exc}", file=sys.stderr)
        raise SystemExit(2)
