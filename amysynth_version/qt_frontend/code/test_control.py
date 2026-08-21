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
    requested = Signal(str, str, object, object)

    def __init__(self, backend: QObject) -> None:
        super().__init__()
        self._backend = backend
        self.requested.connect(self._dispatch)

    @staticmethod
    def _public_name(name: str) -> str:
        if not name or name.startswith("_"):
            raise ValueError("private backend members are not exposed")
        return name

    @Slot(str, str, object, object)
    def _dispatch(
        self,
        operation: str,
        name: str,
        args: object,
        request: object,
    ) -> None:
        req = request
        try:
            name = self._public_name(name)
            target = getattr(self._backend, name, None)
            if operation == "action":
                if target is None or not callable(target):
                    raise ValueError(f"unknown backend action: {name}")
                if not isinstance(args, list):
                    raise ValueError("args must be a JSON array")
                value = target(*args)
            elif operation == "query":
                if target is None:
                    raise ValueError(f"unknown backend value: {name}")
                if callable(target):
                    raise ValueError("query targets must be values, not methods")
                value = target
            else:
                raise ValueError(f"unknown operation: {operation}")
            req.result = {"ok": True, "result": value}
        except Exception as exc:
            req.result = {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
        finally:
            req.done.set()


class TestControlServer:
    """Localhost-only HTTP bridge for headless integration tests.

    It deliberately exposes only public backend members.  Calls are marshalled
    onto the Qt thread so the test drives exactly the same slots/properties QML
    uses without constructing a display/QML engine.
    """

    def __init__(self, backend: QObject, port: int = 0) -> None:
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

            def _read_json(self) -> dict[str, Any]:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length) if length else b"{}"
                value = json.loads(raw.decode("utf-8"))
                if not isinstance(value, dict):
                    raise ValueError("request body must be a JSON object")
                return value

            def _dispatch_request(
                self,
                operation: str,
                name: str,
                args: object,
            ) -> None:
                req = _Request()
                bridge.requested.emit(operation, name, args, req)
                if not req.done.wait(timeout=5.0):
                    self._reply(
                        504,
                        {"ok": False, "error": "Qt request timed out"},
                    )
                    return
                self._reply(
                    200 if req.result.get("ok") else 400,
                    req.result,
                )

            def do_GET(self) -> None:  # noqa: N802
                if self.path == "/health":
                    self._reply(200, {"ok": True})
                    return
                self._reply(404, {"ok": False, "error": "not found"})

            def do_POST(self) -> None:  # noqa: N802
                try:
                    data = self._read_json()
                    if self.path == "/action":
                        self._dispatch_request(
                            "action",
                            str(data["action"]),
                            data.get("args", []),
                        )
                        return
                    if self.path == "/query":
                        self._dispatch_request(
                            "query",
                            str(data["name"]),
                            [],
                        )
                        return
                    self._reply(404, {"ok": False, "error": "not found"})
                except Exception as exc:
                    self._reply(
                        400,
                        {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                    )

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
