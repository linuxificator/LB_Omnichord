from __future__ import annotations

import math
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

import json_store  # noqa: E402
from json_store import JsonStore, JsonStoreError  # noqa: E402


class JsonStoreTests(unittest.TestCase):
    def test_replace_is_private_and_preserves_one_previous_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonStore(Path(directory) / "nested" / "state.json")
            store.write({"revision": 1})
            self.assertEqual(store.read(), {"revision": 1})
            self.assertEqual(stat.S_IMODE(store.path.stat().st_mode), 0o600)
            self.assertFalse(store.previous_path.exists())

            store.write({"revision": 2})
            self.assertEqual(store.read(), {"revision": 2})
            self.assertEqual(store.read_previous(), {"revision": 1})
            self.assertEqual(
                stat.S_IMODE(store.previous_path.stat().st_mode),
                0o600,
            )

    def test_corrupt_current_does_not_hide_recoverable_previous(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonStore(Path(directory) / "state.json")
            store.write({"safe": 1})
            store.write({"safe": 2})
            store.path.write_text('{"broken":', encoding="utf-8")

            with self.assertRaisesRegex(JsonStoreError, "cannot read JSON store"):
                store.read()
            self.assertEqual(store.read_previous(), {"safe": 1})

    def test_failed_final_replace_restores_old_current(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonStore(Path(directory) / "state.json")
            store.write({"safe": "old"})
            real_replace = json_store.os.replace
            calls = 0

            def fail_second_replace(source: object, target: object) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected final replacement failure")
                real_replace(source, target)

            with patch.object(json_store.os, "replace", fail_second_replace):
                with self.assertRaisesRegex(JsonStoreError, "atomically write"):
                    store.write({"safe": "new"})

            self.assertEqual(store.read(), {"safe": "old"})
            self.assertFalse(store.previous_path.exists())
            self.assertEqual(list(store.path.parent.glob("*.tmp")), [])

    def test_serialization_failure_leaves_current_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonStore(Path(directory) / "state.json")
            store.write({"safe": True})

            with self.assertRaisesRegex(JsonStoreError, "cannot serialize"):
                store.write({"invalid": math.nan})

            self.assertEqual(store.read(), {"safe": True})
            self.assertFalse(store.previous_path.exists())

    def test_read_error_contains_the_exact_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text("not-json", encoding="utf-8")
            with self.assertRaises(JsonStoreError) as caught:
                JsonStore(path).read()
            self.assertIn(str(path), str(caught.exception))


if __name__ == "__main__":
    unittest.main()
