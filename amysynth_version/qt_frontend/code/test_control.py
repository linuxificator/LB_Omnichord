from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot


class _Request:
    def __init__(self) -> None:
        self.done = threading.Event()
        self.result: dict[str, Any] = {}


class _Bridge(QObject):
    requested = Signal(str, object, object)

    def __init__(self, backend: QObject) -> None:
        super().__init__()
        self._backend = backend
        self.requested.connect(self._dispatch)

    @Slot(str, object, object)
    def _dispatch(self, action: str, args: object, request: object) -> None:
        req = request
        try:
            if action.startswith("_"):
                raise ValueError("private backend actions are not exposed")
            target = getattr(self._backend, action, None)
            if target is None or not callable(target):
                raise ValueError(f"unknown backend action: {action}")
            if not isinstance(args, list):
                raise ValueError("args must be a JSON array")
            value = target(*args)
            req.result = {"ok": True, "result": value}
        except Exception as exc:
            req.result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        finally:
            req.done.set()


class TestControlServer:
    """Localhost-only HTTP bridge for CI/integration tests."""

    def __init__(self, backend: QObject, port: int) -> None:
        self._bridge = _Bridge(backend)
        bridge = self._bridge

        class Handler(BaseHTTPRequestHandler):
            def _reply(self, status: int, payload: dict[str, Any]) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:  # noqa: N802
                if self.path == "/health":
                    self._reply(200, {"ok": True})
                else:
                    self._reply(404, {"ok": False, "error": "not found"})

            def do_POST(self) -> None:  # noqa: N802
                if self.path != "/action":
                    self._reply(404, {"ok": False, "error": "not found"})
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    data = json.loads(self.rfile.read(length).decode("utf-8"))
                    action = str(data["action"])
                    args = data.get("args", [])
                except Exception as exc:
                    self._reply(400, {"ok": False, "error": str(exc)})
                    return

                req = _Request()
                bridge.requested.emit(action, args, req)
                if not req.done.wait(timeout=5.0):
                    self._reply(504, {"ok": False, "error": "Qt action timed out"})
                    return
                self._reply(200 if req.result.get("ok") else 400, req.result)

            def log_message(self, _format: str, *_args: object) -> None:
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", int(port)), Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="omnichord-test-api",
            daemon=True,
        )
        self._thread.start()

    @property
    def port(self) -> int:
        return int(self._server.server_port)

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2.0)
