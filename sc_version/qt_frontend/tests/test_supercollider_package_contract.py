from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SC_ROOT = ROOT.parent / "supercollider"


class SuperColliderPackageContractTests(unittest.TestCase):
    def test_source_launcher_owns_one_headless_engine_process_group(self) -> None:
        launcher = (ROOT / "run_local.sh").read_text(encoding="utf-8")
        self.assertIn('setsid "${sc_launcher[@]}" sclang -D', launcher)
        self.assertIn('trap cleanup EXIT INT TERM HUP', launcher)
        self.assertIn("pipewire-jack", launcher)

    def test_runtime_inventory_is_complete_and_versioned(self) -> None:
        required = {
            "bootstrap.scd",
            "sequencer.scd",
            "sclork_loader.scd",
            "acid_voices.scd",
            "sample_loader.scd",
            "protocol_runtime.scd",
            "sclork-programs.json",
            "vsco-manifest.json",
            "drum-key-map.json",
            "source-lock.json",
        }
        self.assertTrue(required.issubset({path.name for path in SC_ROOT.iterdir()}))
        config = json.loads(
            (ROOT / "config" / "supercollider.json").read_text(encoding="utf-8")
        )
        self.assertEqual(config["config_revision"], 1)
        self.assertEqual(config["protocol_version"], 1)

    def test_global_bend_reaches_bus_voices_and_native_sclork_voices(self) -> None:
        bootstrap = (SC_ROOT / "bootstrap.scd").read_text(encoding="utf-8")
        self.assertIn("~omniSetPitchBend =", bootstrap)
        self.assertIn("~omniBendBus.set(ratio)", bootstrap)
        self.assertIn("record[\\baseFrequency] * ratio", bootstrap)
        self.assertIn("frequency * (2 ** ~omniPitchBendOctaves)", bootstrap)


if __name__ == "__main__":
    unittest.main()
