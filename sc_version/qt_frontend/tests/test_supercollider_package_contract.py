from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SC_ROOT = ROOT.parent / "supercollider"
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "packaging"))

from sc_appimage_entry import (  # noqa: E402
    packaged_runtime_root,
    verify_application_assets,
    verify_config_migrations,
)


class SuperColliderPackageContractTests(unittest.TestCase):
    def test_production_import_graph_cannot_reach_an_amy_runtime(self) -> None:
        code_root = ROOT / "code"
        packaging_root = ROOT / "packaging"
        forbidden = {
            "amy_serial",
            "amy_transport",
            "c_amy",
            "local_amy_service",
            "program_amy",
        }
        pending = [code_root / "main.py", packaging_root / "sc_appimage_entry.py"]
        visited: set[Path] = set()
        reached_modules: set[str] = set()
        while pending:
            path = pending.pop()
            if path in visited:
                continue
            visited.add(path)
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                modules: tuple[str, ...]
                if isinstance(node, ast.Import):
                    modules = tuple(alias.name.split(".", 1)[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    modules = (node.module.split(".", 1)[0],)
                else:
                    continue
                for module in modules:
                    reached_modules.add(module)
                    local = code_root / f"{module}.py"
                    if local.is_file():
                        pending.append(local)

        self.assertTrue(forbidden.isdisjoint(reached_modules))

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
            "program_registry.scd",
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
        self.assertEqual(config["config_revision"], 3)
        self.assertEqual(config["protocol_version"], 2)

    def test_frozen_entry_uses_sc_supervision_and_contains_no_amy_service(self) -> None:
        entry = (ROOT / "packaging" / "sc_appimage_entry.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("SuperColliderSupervisor", entry)
        self.assertIn("supercollider.json", entry)
        self.assertNotIn("local_amy_service", entry)
        self.assertNotIn("--amy-service", entry)

    def test_frozen_package_verifies_all_supported_config_migrations(self) -> None:
        verify_config_migrations(ROOT)

    def test_frozen_package_loads_its_production_instrument_catalogue(self) -> None:
        verify_application_assets(ROOT)

    def test_frozen_package_executes_the_real_engine_bootstrap(self) -> None:
        entry = (ROOT / "packaging" / "sc_appimage_entry.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(".validate_bootstrap()", entry)

    def test_bootstrap_configures_the_server_executable_on_server_class(self) -> None:
        bootstrap = (SC_ROOT / "bootstrap.scd").read_text(encoding="utf-8")
        self.assertIn(
            'Server.program = "OMNICHORD_SC_SYNTH_PROGRAM".getenv', bootstrap
        )
        self.assertNotIn("s.options.program", bootstrap)

    def test_sc_build_is_independent_and_release_is_explicit(self) -> None:
        workflow = (
            ROOT.parents[1] / ".github" / "workflows" / "supercollider-release.yml"
        )
        text = workflow.read_text(encoding="utf-8")
        builder = (ROOT / "packaging" / "build_sc_appimage.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("branches: [main, release/supercollider-multiplatform]", text)
        self.assertIn("Build and publish all tested SuperCollider packages", text)
        self.assertIn("if: github.event_name == 'workflow_dispatch' && inputs.release", text)
        self.assertIn("build_supercollider_runtime.sh", text)
        for platform in (
            "Linux-x86_64",
            "RaspberryPi-aarch64",
            "macOS-arm64",
            "Windows-x86_64",
        ):
            self.assertIn(platform, text)
        self.assertNotIn("Android-arm64.apk", text)
        self.assertNotIn("ESP32P4.zip", text)
        self.assertIn("--exclude-module c_amy", builder)
        self.assertIn("--add-data \"$sc_dir:supercollider\"", builder)
        macos_builder = (ROOT / "packaging" / "build_macos_dmg.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            '--forbidden-runtime-exempt-prefix "Contents/Resources/sc-runtime"',
            macos_builder,
        )
        windows_builder = (ROOT / "packaging" / "build_windows.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            '--forbidden-runtime-exempt-prefix "sc-runtime"', windows_builder
        )

    def test_macos_frozen_entry_finds_runtime_in_contents_resources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "LB_Omnichord_SC.app"
            executable = bundle / "Contents" / "MacOS" / "LB_Omnichord_SC"
            runtime = (
                bundle
                / "Contents"
                / "Resources"
                / "sc-runtime"
                / "SuperCollider.app"
            )
            executable.parent.mkdir(parents=True)
            executable.touch()
            for path in (
                runtime / "Contents" / "MacOS" / "sclang",
                runtime / "Contents" / "Resources" / "scsynth",
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            for path in (
                runtime / "Contents" / "Resources" / "SCClassLibrary",
                runtime / "Contents" / "Resources" / "plugins",
            ):
                path.mkdir(parents=True)

            with (
                patch("sc_appimage_entry.sys.executable", str(executable)),
                patch.dict(os.environ, {}, clear=True),
            ):
                # Windows may canonicalize an 8.3 temp-directory spelling and
                # macOS maps /var to /private/var. Compare canonical paths.
                self.assertEqual(
                    packaged_runtime_root().resolve(), runtime.resolve()
                )

    def test_raspberry_pi_sc_package_uses_host_cxx_runtime(self) -> None:
        builder = (ROOT / "packaging" / "build_sc_appimage.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn('if [[ "$platform_name" == "RaspberryPi-aarch64" ]]', builder)
        self.assertIn(
            '"$app_dir/usr/lib/LB_Omnichord/_internal/libstdc++.so.6"',
            builder,
        )
        self.assertIn(
            '"$app_dir/usr/lib/LB_Omnichord/sc-runtime/lib/libstdc++.so.6"',
            builder,
        )

    def test_global_bend_reaches_bus_voices_and_native_sclork_voices(self) -> None:
        bootstrap = (SC_ROOT / "bootstrap.scd").read_text(encoding="utf-8")
        self.assertIn("~omniSetPitchBend =", bootstrap)
        self.assertIn("~omniBendBus.set(ratio)", bootstrap)
        self.assertIn("record[\\baseFrequency] * ratio", bootstrap)
        self.assertIn("frequency * (2 ** ~omniPitchBendOctaves)", bootstrap)

    def test_natural_voice_lifetime_guards_server_node_updates(self) -> None:
        bootstrap = (SC_ROOT / "bootstrap.scd").read_text(encoding="utf-8")
        self.assertIn("record[\\sourceAlive] ? true", bootstrap)
        self.assertIn("record[\\releaseRequested] = true", bootstrap)
        self.assertIn("record[\\releaseRequested].not", bootstrap)
        self.assertIn("record[\\outputAlive] = false", bootstrap)
        self.assertIn("var voiceGroup = Group.tail(~omniSourceGroup)", bootstrap)
        self.assertIn("voiceGroup: voiceGroup", bootstrap)
        self.assertIn("voiceGroup.free", bootstrap)
        self.assertIn("record[\\voiceGroup].set(\\gate, 0)", bootstrap)
        self.assertIn("voiceGroup.set(\\gate, 0)", bootstrap)
        self.assertIn("record[\\voiceGroup].set(\\outputGain, value)", bootstrap)
        self.assertNotIn("record[\\outputNode].set(", bootstrap)
        self.assertNotIn("outputNode.set(", bootstrap)
        self.assertNotIn("sourceNode.free", bootstrap)

    def test_sample_release_and_retune_use_stable_control_buses(self) -> None:
        bootstrap = (SC_ROOT / "bootstrap.scd").read_text(encoding="utf-8")
        samples = (SC_ROOT / "sample_loader.scd").read_text(encoding="utf-8")
        self.assertIn("~omniGateSampleHandle.value(record)", bootstrap)
        self.assertIn("var gateBus = Bus.control(s, 1)", samples)
        self.assertIn("var rateScaleBus = Bus.control(s, 1)", samples)
        self.assertIn(
            "node.map(\\gateControl, gateBus, \\rateScale, rateScaleBus)",
            samples,
        )
        self.assertIn("record[\\gateBus].set(0)", samples)
        self.assertIn("record[\\rateScaleBus].set(", samples)
        self.assertNotIn("sampleNode[\\node].set(", samples)

    def test_sample_buffer_capacity_is_configured_before_server_boot(self) -> None:
        bootstrap = (SC_ROOT / "bootstrap.scd").read_text(encoding="utf-8")
        assignment = bootstrap.index("s.options.numBuffers = maxBuffers")
        boot = bootstrap.index("s.waitForBoot")
        self.assertLess(assignment, boot)

    def test_all_mix_and_room_outputs_cross_one_bounded_master_stage(self) -> None:
        bootstrap = (SC_ROOT / "bootstrap.scd").read_text(encoding="utf-8")
        core = (SC_ROOT / "core_synthdefs.scd").read_text(encoding="utf-8")
        self.assertIn("~omniMasterBus = Bus.audio(s, 2)", bootstrap)
        self.assertGreaterEqual(
            bootstrap.count("\\out, ~omniMasterBus.index"),
            2,
        )
        self.assertIn("Group.after(~omniFxGroup)", bootstrap)
        self.assertIn("Synth.tail(~omniOutputGroup, \\omniMasterOutput", bootstrap)
        self.assertIn("Limiter.ar(signal, ceiling.clip(0.1, 1), 0.005)", core)


if __name__ == "__main__":
    unittest.main()
