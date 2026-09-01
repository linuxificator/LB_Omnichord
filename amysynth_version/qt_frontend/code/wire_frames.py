from __future__ import annotations


# AMY's MAX_MESSAGE_LEN is 1024 including its terminating NUL. Local IPC may
# therefore carry at most 1023 request bytes, including the final wire `Z`.
MAX_WIRE_REQUEST_BYTES = 1023


class WireFrameError(ValueError):
    """A local AMY request violates the bounded wire framing contract."""


def validate_wire_request(payload: bytes) -> str:
    """Validate one packet/framed payload and return its AMY wire text."""

    if payload.endswith(b"\r"):
        payload = payload[:-1]
    if not payload:
        raise WireFrameError("empty AMY wire request")
    if len(payload) > MAX_WIRE_REQUEST_BYTES:
        raise WireFrameError(
            "AMY wire request exceeds "
            f"{MAX_WIRE_REQUEST_BYTES} bytes"
        )
    if any(byte < 0x20 or byte > 0x7E for byte in payload):
        raise WireFrameError("AMY wire request must contain printable ASCII")
    if payload[-1:] != b"Z":
        raise WireFrameError("AMY wire request must end in Z")
    return payload.decode("ascii")


class LfWireFrameParser:
    """Incrementally parse bounded LF/CRLF-framed AMY wire requests."""

    def __init__(self) -> None:
        self._buffer = bytearray()
        self._failed = False

    @property
    def buffered_bytes(self) -> int:
        return len(self._buffer)

    def _fail(self, message: str) -> None:
        self._failed = True
        self._buffer.clear()
        raise WireFrameError(message)

    def feed(self, chunk: bytes) -> tuple[str, ...]:
        if self._failed:
            raise WireFrameError("AMY wire parser is unusable after an error")

        requests: list[str] = []
        for byte in chunk:
            if byte > 0x7F:
                self._fail("AMY wire request must contain ASCII")
            if byte == 0x0A:
                payload = bytes(self._buffer)
                self._buffer.clear()
                if payload in (b"", b"\r"):
                    continue
                requests.append(validate_wire_request(payload))
                continue

            self._buffer.append(byte)
            allowed = MAX_WIRE_REQUEST_BYTES + (
                1 if self._buffer[-1:] == b"\r" else 0
            )
            if len(self._buffer) > allowed:
                self._fail(
                    "AMY wire request exceeds "
                    f"{MAX_WIRE_REQUEST_BYTES} bytes before LF"
                )
        return tuple(requests)

    def finish(self) -> None:
        """Reject a connection that closes in the middle of a record."""

        if self._failed:
            raise WireFrameError("AMY wire parser is unusable after an error")
        if self._buffer:
            self._fail("unterminated AMY wire request at end of stream")
