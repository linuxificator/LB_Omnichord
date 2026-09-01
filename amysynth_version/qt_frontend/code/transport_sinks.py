from __future__ import annotations

import time
from typing import Any

import serial

from unix_wire_socket import connect_unix_wire_socket


class SerialByteSink:
    delimiter = b"\n"

    def __init__(self, port: str, baud: int, write_timeout: float) -> None:
        self._port = str(port)
        self._baud = int(baud)
        self._write_timeout = float(write_timeout)
        self._serial: Any | None = None

    def open(self) -> None:
        self._serial = serial.Serial(
            port=self._port,
            baudrate=self._baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0,
            write_timeout=self._write_timeout,
        )

    def write(self, payload: bytes) -> None:
        if self._serial is None:
            raise ConnectionError("serial AMY sink is not open")
        written = self._serial.write(payload)
        if written is not None and int(written) != len(payload):
            raise OSError(f"short serial write: {written}/{len(payload)}")

    def close(self) -> None:
        if self._serial is not None:
            self._serial.close()
            self._serial = None


class UnixByteSink:
    delimiter = b""

    def __init__(self, path: str) -> None:
        self._path = str(path)
        self._socket: Any | None = None
        self._stream_transport = False

    def open(self) -> None:
        self._socket, self._stream_transport = connect_unix_wire_socket(
            self._path,
            timeout=5.0,
        )
        self.delimiter = b"\n" if self._stream_transport else b""

    def write(self, payload: bytes) -> None:
        if self._socket is None:
            raise ConnectionError("Unix AMY sink is not open")
        self._socket.sendall(payload)

    def close(self) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None


class QtLocalByteSink:
    delimiter = b"\n"

    def __init__(self, server_name: str) -> None:
        self._server_name = str(server_name)
        self._socket: Any | None = None

    def open(self) -> None:
        from PySide6.QtNetwork import QLocalSocket

        local_socket = QLocalSocket()
        local_socket.connectToServer(self._server_name)
        if not local_socket.waitForConnected(5000):
            raise ConnectionError(local_socket.errorString())
        self._socket = local_socket

    def write(self, payload: bytes) -> None:
        local_socket = self._socket
        if local_socket is None:
            raise ConnectionError("local AMY sink is not open")
        if local_socket.write(payload) != len(payload):
            raise OSError(local_socket.errorString())
        deadline = time.monotonic() + 5.0
        while local_socket.bytesToWrite() > 0:
            remaining_ms = max(1, int((deadline - time.monotonic()) * 1000))
            if time.monotonic() >= deadline or not local_socket.waitForBytesWritten(remaining_ms):
                raise TimeoutError(local_socket.errorString())

    def close(self) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None
