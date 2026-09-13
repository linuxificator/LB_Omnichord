from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

FRONTEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRONTEND_DIR / "code"))

from supercollider_config import (  # noqa: E402
    SuperColliderConfigError,
    load_supercollider_config,
)


class SuperColliderConfigTests(unittest.TestCase):
    def test_shipped_configuration_is_valid_and_loopback_only(self) -> None:
        config = load_supercollider_config(
            FRONTEND_DIR / "config" / "supercollider.json"
        )
        self.assertEqual(config.protocol_version, 1)
        self.assertEqual(config.language.host, "127.0.0.1")
        self.assertEqual(config.server.sample_rate, 48000)

    def test_non_loopback_control_listener_is_rejected(self) -> None:
        source = FRONTEND_DIR / "config" / "supercollider.json"
        data = json.loads(source.read_text(encoding="utf-8"))
        data["language"]["host"] = "0.0.0.0"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "supercollider.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(SuperColliderConfigError, "loopback"):
                load_supercollider_config(path)


if __name__ == "__main__":
    unittest.main()
