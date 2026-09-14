from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SC_ROOT = ROOT.parent / "supercollider"
TOOLS = ROOT.parent / "tools" / "banks"
sys.path.insert(0, str(TOOLS))

from bank_source_catalog import inventory_bank, load_source_catalog  # noqa: E402


class SampleBankSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = load_source_catalog(SC_ROOT / "sample-bank-sources.json")

    def test_all_bounded_sources_have_reproducible_authorities(self) -> None:
        git_banks = self.catalog["git_banks"]
        self.assertEqual(len(git_banks), 11)
        self.assertEqual(len(self.catalog["web_banks"]), 1)
        self.assertEqual(
            sum(int(item["expected_audio_files"]) for item in git_banks),
            23548,
        )
        self.assertEqual(
            {item["id"] for item in git_banks},
            {
                "vsco-2-ce",
                "vcsl",
                "salamander-grand-piano-v3",
                "black-and-green-guitars",
                "black-and-blue-basses",
                "meatbass",
                "emilyguitar",
                "bear-sax",
                "weresax",
                "virtuosity-drums",
                "swirly-drums",
            },
        )
        self.assertTrue(
            all(
                item["source_archive_url"].endswith(
                    f"/{item['commit']}.zip"
                )
                for item in git_banks
            )
        )

    def test_inventory_hashes_audio_and_rejects_lfs_placeholders(self) -> None:
        bank = self.catalog["git_banks"][0]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "tone.wav").write_bytes(b"real-audio-fixture")
            inventory = inventory_bank(bank, root)
            self.assertEqual(inventory["audio_file_count"], 1)
            self.assertEqual(inventory["source_bytes"], 18)
            self.assertEqual(len(inventory["files"][0]["sha256"]), 64)
            (root / "pointer.flac").write_text(
                "version https://git-lfs.github.com/spec/v1\n"
                "oid sha256:" + "a" * 64 + "\nsize 100\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Git LFS pointer"):
                inventory_bank(bank, root)

    def test_catalog_json_remains_machine_readable_without_derived_fields(self) -> None:
        raw = json.loads(
            (SC_ROOT / "sample-bank-sources.json").read_text(encoding="utf-8")
        )
        self.assertNotIn("source_archive_url", raw["git_banks"][0])


if __name__ == "__main__":
    unittest.main()
