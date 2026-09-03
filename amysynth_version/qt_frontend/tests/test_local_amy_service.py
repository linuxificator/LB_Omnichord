from __future__ import annotations

import argparse
import signal
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

import local_amy_service  # noqa: E402
from wire_frames import WireFrameError  # noqa: E402


class _ClientProbe:
    def __init__(
        self,
        chunks: list[bytes],
        stop_callback: object,
    ) -> None:
        self._chunks = list(chunks)
        self._stop_callback = stop_callback

    def __enter__(self) -> _ClientProbe:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def settimeout(self, _seconds: float) -> None:
        return None

    def recv(self, _size: int) -> bytes:
        if self._chunks:
            return self._chunks.pop(0)
        callback = self._stop_callback
        assert callable(callback)
        callback(signal.SIGTERM, None)
        return b""


class _ServerProbe:
    def __init__(self, client: _ClientProbe) -> None:
        self.client = client
        self.close_count = 0

    def settimeout(self, _seconds: float) -> None:
        return None

    def accept(self) -> tuple[_ClientProbe, None]:
        return self.client, None

    def close(self) -> None:
        self.close_count += 1


class LocalAmyServiceTests(unittest.TestCase):
    def run_service(
        self,
        chunks: list[bytes],
        *,
        stream: bool,
    ) -> tuple[list[str], _ServerProbe, list[dict[str, int]]]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "amy_config.json"
            config_path.write_text(
                (ROOT / "config" / "amy_config.json").read_text(
                    encoding="utf-8"
                ),
                encoding="utf-8",
            )
            args = argparse.Namespace(
                socket=root / "amy.sock",
                config=config_path,
                max_buses=None,
                max_oscs=None,
            )
            callbacks: dict[int, object] = {}

            def install_handler(number: int, callback: object) -> None:
                callbacks[number] = callback

            client = _ClientProbe(
                chunks,
                lambda signum, frame: callbacks[signal.SIGTERM](signum, frame),
            )
            server = _ServerProbe(client)
            sent: list[str] = []
            live_calls: list[dict[str, int]] = []
            native = types.SimpleNamespace(stop=lambda: None)
            amy = types.SimpleNamespace(
                live=lambda **values: live_calls.append(values),
                send_wire=sent.append,
                _amy=native,
            )

            with (
                patch.object(local_amy_service, "parse_arguments", return_value=args),
                patch.object(
                    local_amy_service,
                    "listen_unix_wire_socket",
                    return_value=(server, stream),
                ),
                patch.object(Path, "chmod", return_value=None),
                patch.object(local_amy_service.signal, "signal", install_handler),
                patch.dict(sys.modules, {"amy": amy}),
            ):
                result = local_amy_service.main()

        self.assertEqual(result, 0)
        return sent, server, live_calls

    def test_stream_service_delivers_split_and_combined_valid_requests(self) -> None:
        sent, server, live_calls = self.run_service(
            [b"K215", b"i5Z\nn60l1i5Z\n"],
            stream=True,
        )
        self.assertEqual(sent, ["K215i5Z", "n60l1i5Z"])
        self.assertEqual(server.close_count, 1)
        self.assertEqual(live_calls[0]["max_sequence_groups"], 1024)
        self.assertEqual(live_calls[0]["max_sequence_group_executions"], 40)

    def test_packet_service_preserves_one_valid_request_per_packet(self) -> None:
        sent, _server, _live_calls = self.run_service(
            [b"K215i5Z", b"n60l1i5Z"],
            stream=False,
        )
        self.assertEqual(sent, ["K215i5Z", "n60l1i5Z"])

    def test_stream_service_rejects_an_overlong_unterminated_record(self) -> None:
        with self.assertRaisesRegex(WireFrameError, "exceeds 1023 bytes"):
            self.run_service([b"a" * 1024], stream=True)


if __name__ == "__main__":
    unittest.main()
