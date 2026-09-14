from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SC_ROOT = ROOT.parent / "supercollider"
SALAMANDER_PIN = "3382bf9496bba2486f5ab0de55a264d1dfc38404"


class SalamanderOpcodeAuditTests(unittest.TestCase):
    def test_pinned_mapping_gap_remains_explicit(self) -> None:
        report = json.loads(
            (SC_ROOT / "salamander-opcode-coverage.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(report["bank_id"], "salamander-grand-piano-v3")
        self.assertEqual(report["source_pin"], SALAMANDER_PIN)
        self.assertEqual(report["mapping_count"], 1)
        self.assertEqual(len(report["opcodes"]), 69)
        self.assertFalse(report["complete"])
        self.assertEqual(len(report["unsupported_opcodes"]), 49)
        self.assertLessEqual(
            {
                "rt_decay",
                "offset_oncc98",
                "on_locc64",
                "on_hicc64",
                "ampeg_release_oncc72",
            },
            set(report["unsupported_opcodes"]),
        )


if __name__ == "__main__":
    unittest.main()
