from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SC_ROOT = ROOT.parent / "supercollider"
sys.path.insert(0, str(ROOT / "code"))

from sfz_manifest_compiler import COMPILER_VERSION, VSCO_SOURCE_PIN  # noqa: E402


class VscoManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            (SC_ROOT / "vsco-manifest.json").read_text(encoding="utf-8")
        )
        cls.opcode_coverage = json.loads(
            (SC_ROOT / "vsco-opcode-coverage.json").read_text(encoding="utf-8")
        )

    def test_inventory_and_mapping_counts_are_explicit(self) -> None:
        self.assertEqual(self.manifest["schema_revision"], 1)
        self.assertEqual(self.manifest["compiler_version"], COMPILER_VERSION)
        self.assertEqual(self.manifest["bank"]["source_pin"], VSCO_SOURCE_PIN)
        self.assertEqual(len(self.manifest["files"]), 3168)
        self.assertEqual(len(self.manifest["programs"]), 75)
        self.assertEqual(len(self.manifest["regions"]), 3163)
        self.assertEqual(len(self.manifest["coverage"]), 3168)

    def test_all_region_and_coverage_references_are_closed(self) -> None:
        file_ids = {item["id"] for item in self.manifest["files"]}
        region_ids = {item["id"] for item in self.manifest["regions"]}
        self.assertEqual(len(file_ids), 3168)
        self.assertEqual(len(region_ids), 3163)
        self.assertLessEqual(
            {item["sample_id"] for item in self.manifest["regions"]},
            file_ids,
        )
        self.assertEqual(
            {item["sample_id"] for item in self.manifest["coverage"]},
            file_ids,
        )
        self.assertEqual(
            {region_id for item in self.manifest["programs"] for region_id in item["region_ids"]},
            region_ids,
        )

    def test_unmapped_source_audio_is_reported_not_hidden(self) -> None:
        dispositions = [item["disposition"] for item in self.manifest["coverage"]]
        self.assertEqual(dispositions.count("mapped-region"), 2034)
        self.assertEqual(dispositions.count("unmapped-source-audio"), 1134)

    def test_embedded_sampler_metadata_is_accounted_without_looping_whole_files(self) -> None:
        looped = [item for item in self.manifest["files"] if item.get("embedded_loops")]
        self.assertEqual(len(looped), 6)
        for sample in looped:
            self.assertIsInstance(sample.get("embedded_root_key"), int)
            self.assertTrue(
                all(
                    loop["playback_disposition"] == "ignored-whole-file-loop"
                    and loop["start_frame"] == 0
                    and loop["end_frame_exclusive"] == sample["frames"]
                    for loop in sample["embedded_loops"]
                )
            )

    def test_opcode_surface_is_complete_and_every_classification_is_explicit(self) -> None:
        coverage = self.opcode_coverage
        self.assertEqual(coverage["compiler_version"], COMPILER_VERSION)
        self.assertEqual(coverage["mapping_count"], 75)
        self.assertTrue(coverage["complete"])
        self.assertEqual(coverage["unsupported_opcodes"], [])
        self.assertEqual(
            {item["classification"] for item in coverage["opcodes"]},
            {"compile-time-metadata", "implemented-runtime"},
        )
        self.assertEqual(
            {item["opcode"] for item in coverage["opcodes"]},
            {
                "ampeg_attack",
                "ampeg_dynamic",
                "ampeg_release",
                "default_path",
                "group_label",
                "hikey",
                "hirand",
                "hivel",
                "lokey",
                "lorand",
                "lovel",
                "pitch_keycenter",
                "sample",
                "seq_length",
                "seq_position",
                "sw_default",
                "sw_hikey",
                "sw_label",
                "sw_last",
                "sw_lokey",
                "tune",
                "volume",
            },
        )


if __name__ == "__main__":
    unittest.main()
