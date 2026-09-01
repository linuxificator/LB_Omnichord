from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from wire_frames import (  # noqa: E402
    MAX_WIRE_REQUEST_BYTES,
    LfWireFrameParser,
    WireFrameError,
    validate_wire_request,
)


class WireFrameTests(unittest.TestCase):
    def test_empty_split_and_combined_stream_frames(self) -> None:
        parser = LfWireFrameParser()
        self.assertEqual(parser.feed(b"\n\r\nK215"), ())
        self.assertEqual(parser.buffered_bytes, 4)
        self.assertEqual(
            parser.feed(b"i5Z\nn60l1i5Z\r\n"),
            ("K215i5Z", "n60l1i5Z"),
        )
        self.assertEqual(parser.buffered_bytes, 0)
        parser.finish()

    def test_maximum_sized_request_is_valid(self) -> None:
        payload = b"a" * (MAX_WIRE_REQUEST_BYTES - 1) + b"Z"
        parser = LfWireFrameParser()
        self.assertEqual(parser.feed(payload + b"\n"), (payload.decode("ascii"),))
        self.assertEqual(validate_wire_request(payload), payload.decode("ascii"))

    def test_overlong_input_fails_before_an_lf_can_grow_the_buffer(self) -> None:
        parser = LfWireFrameParser()
        with self.assertRaisesRegex(WireFrameError, "exceeds 1023 bytes"):
            parser.feed(b"a" * (MAX_WIRE_REQUEST_BYTES + 1))
        self.assertEqual(parser.buffered_bytes, 0)
        with self.assertRaisesRegex(WireFrameError, "unusable"):
            parser.feed(b"n60l1i1Z\n")

    def test_non_ascii_and_non_printable_input_is_rejected(self) -> None:
        with self.assertRaisesRegex(WireFrameError, "ASCII"):
            LfWireFrameParser().feed(b"n60\xffZ\n")
        with self.assertRaisesRegex(WireFrameError, "printable ASCII"):
            LfWireFrameParser().feed(b"n60\x00Z\n")

    def test_missing_z_and_unterminated_input_are_rejected(self) -> None:
        with self.assertRaisesRegex(WireFrameError, "end in Z"):
            LfWireFrameParser().feed(b"n60l1i1\n")

        parser = LfWireFrameParser()
        self.assertEqual(parser.feed(b"n60l1i1Z"), ())
        with self.assertRaisesRegex(WireFrameError, "unterminated"):
            parser.finish()

    def test_packet_validation_uses_the_same_payload_contract(self) -> None:
        self.assertEqual(validate_wire_request(b"n60l1i1Z"), "n60l1i1Z")
        self.assertEqual(validate_wire_request(b"n60l1i1Z\r"), "n60l1i1Z")
        for payload in (b"", b"n60l1i1", b"a" * 1024):
            with self.subTest(length=len(payload)):
                with self.assertRaises(WireFrameError):
                    validate_wire_request(payload)

    def test_windows_service_enforces_the_same_amy_payload_limit(self) -> None:
        source = (
            ROOT / "packaging" / "windows" / "amy_service.c"
        ).read_text(encoding="utf-8")
        self.assertRegex(
            source,
            re.compile(r"#define SERVICE_MAX_LINE MAX_MESSAGE_LEN\b"),
        )
        self.assertIn("length >= MAX_MESSAGE_LEN", source)
        self.assertIn("line[length - 1] != 'Z'", source)


if __name__ == "__main__":
    unittest.main()
