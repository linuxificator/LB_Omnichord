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
            "core_synthdefs.scd",
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

    def test_frozen_entry_uses_sc_supervision_and_contains_no_amy_service(self) -> None:
        entry = (ROOT / "packaging" / "sc_appimage_entry.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("SuperColliderSupervisor", entry)
        self.assertIn("supercollider.json", entry)
        self.assertNotIn("local_amy_service", entry)
        self.assertNotIn("--amy-service", entry)

    def test_sc_build_is_independent_and_release_is_explicit(self) -> None:
        workflow = (ROOT.parents[1] / ".github" / "workflows" / "supercollider-linux.yml")
        text = workflow.read_text(encoding="utf-8")
        builder = (ROOT / "packaging" / "build_sc_appimage.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("branches: [main, version/supercollider]", text)
        self.assertIn("description: Publish this tested SuperCollider Linux build", text)
        self.assertIn("if: github.event_name == 'workflow_dispatch' && inputs.release", text)
        self.assertIn("build_supercollider_runtime.sh", text)
        self.assertIn("--exclude-module c_amy", builder)
        self.assertIn("--add-data \"$sc_dir:supercollider\"", builder)

    def test_global_bend_reaches_bus_voices_and_native_sclork_voices(self) -> None:
        bootstrap = (SC_ROOT / "bootstrap.scd").read_text(encoding="utf-8")
        self.assertIn("~omniSetPitchBend =", bootstrap)
        self.assertIn("~omniBendBus.set(ratio)", bootstrap)
        self.assertIn("record[\\baseFrequency] * ratio", bootstrap)
        self.assertIn("frequency * (2 ** ~omniPitchBendOctaves)", bootstrap)


if __name__ == "__main__":
    unittest.main()
