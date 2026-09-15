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

    def test_sc_source_tree_contains_no_amy_runtime_or_firmware_copy(self) -> None:
        for module in (
            "amy_serial.py",
            "amy_transport.py",
            "local_amy_service.py",
            "program_amy.py",
            "wire_frames.py",
        ):
            self.assertFalse((ROOT / "code" / module).exists(), module)
        self.assertFalse((ROOT / "config" / "amy_config.json").exists())
        self.assertFalse((ROOT.parent / "esp32p4" / "CMakeLists.txt").exists())
        old_pi_tools = ROOT / "tools" / "raspberry_pi"
        self.assertFalse(
            any(
                path.is_file() and path.suffix in {".py", ".sh", ".conf"}
                for path in old_pi_tools.rglob("*")
            )
            if old_pi_tools.exists()
            else False
        )
        firmware_main = ROOT.parent / "esp32p4" / "main"
        self.assertFalse(
            any(path.is_file() for path in firmware_main.rglob("*"))
            if firmware_main.exists()
            else False
        )
        self.assertTrue((ROOT / "config" / "frontend.json").is_file())

    def test_source_launcher_owns_one_headless_engine_process_group(self) -> None:
        launcher = (ROOT / "run_local.sh").read_text(encoding="utf-8")
        self.assertIn('setsid "${sc_launcher[@]}" sclang -D', launcher)
        self.assertIn('trap cleanup EXIT INT TERM HUP', launcher)
        self.assertIn("pipewire-jack", launcher)
        self.assertIn('command -v supernova', launcher)
        self.assertIn('OMNICHORD_SC_SYNTH_PROGRAM="exec ', launcher)
        self.assertIn("supercollider_linux_realtime.py", launcher)
        self.assertIn("it is not a runtime watcher", launcher)

    def test_endurance_driver_uses_the_production_audio_server(self) -> None:
        endurance = (
            ROOT / "tests" / "endurance" / "sc_endurance.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"OMNICHORD_SC_SYNTH_PROGRAM"', endurance)
        self.assertIn("runtime.supernova", endurance)

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
        self.assertTrue((SC_ROOT / "tests" / "supernova_graph_nrt.scd").is_file())
        config = json.loads(
            (ROOT / "config" / "supercollider.json").read_text(encoding="utf-8")
        )
        self.assertEqual(config["config_revision"], 7)
        self.assertEqual(config["protocol_version"], 2)
        self.assertEqual(config["server"]["gesture_voice_limit"], 64)
        self.assertEqual(
            config["samples"]["commit"],
            "78b95e70efe4349eeb03855f7f7654cb81c8c62f",
        )
        self.assertEqual(
            config["samples"]["branch"], "lb-omnichord-runtime-v1"
        )
        release_inputs = json.loads(
            (ROOT / "packaging" / "supercollider_release_inputs.json").read_text(
                encoding="utf-8"
            )
        )
        drum_catalogue = json.loads(
            (ROOT / "music" / "sc_expansion" / "sc_pcm_drumkits_v1.json")
            .read_text(encoding="utf-8")
        )
        repositories = {
            config["samples"]["repository"],
            release_inputs["sample_assets"]["repository"],
            drum_catalogue["sample_repository"],
        }
        self.assertEqual(
            {str(value).removesuffix(".git") for value in repositories},
            {"https://github.com/linuxificator/VSCO-2-CE"},
        )
        self.assertEqual(
            {
                config["samples"]["branch"],
                release_inputs["sample_assets"]["branch"],
            },
            {"lb-omnichord-runtime-v1"},
        )
        self.assertEqual(
            {
                config["samples"]["commit"],
                release_inputs["sample_assets"]["commit"],
                drum_catalogue["sample_commit"],
            },
            {"78b95e70efe4349eeb03855f7f7654cb81c8c62f"},
        )

    def test_runtime_sample_selection_covers_every_playback_reference(self) -> None:
        manifest = json.loads(
            (SC_ROOT / "vsco-manifest.json").read_text(encoding="utf-8")
        )
        drums = json.loads(
            (ROOT / "music" / "sc_expansion" / "sc_pcm_drumkits_v1.json")
            .read_text(encoding="utf-8")
        )
        source_ids = {record["id"] for record in manifest["files"]}
        melodic_ids = {region["sample_id"] for region in manifest["regions"]}
        drum_ids = {
            record["source_sample_id"] for record in drums["sample_files"]
        }
        selected_ids = melodic_ids | drum_ids

        self.assertTrue(selected_ids.issubset(source_ids))
        self.assertEqual(len(melodic_ids), 2034)
        self.assertEqual(len(drum_ids - melodic_ids), 132)
        self.assertEqual(len(selected_ids), 2166)
        self.assertEqual(len(source_ids - selected_ids), 1002)

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
        runtime_builder = (
            ROOT.parent / "packaging" / "build_supercollider_runtime.sh"
        ).read_text(encoding="utf-8")
        self.assertIn("-DSUPERNOVA=ON", runtime_builder)
        self.assertIn('"$install_prefix/bin/supernova" -v', runtime_builder)
        self.assertGreaterEqual(text.count("supernova -v"), 3)
        for platform in (
            "Linux-x86_64",
            "RaspberryPi-aarch64",
            "macOS-arm64",
            "Windows-x86_64",
        ):
            self.assertIn(platform, text)
        self.assertNotIn("Android-arm64.apk", text)
        self.assertNotIn("ESP32P4.zip", text)
        self.assertNotIn("--exclude-module amy", builder)
        self.assertNotIn("--exclude-module c_amy", builder)
        self.assertIn("--add-data \"$sc_dir:supercollider\"", builder)
        self.assertIn('"$runtime_prefix/bin/supernova"', builder)
        macos_builder = (ROOT / "packaging" / "build_macos_dmg.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            '--forbidden-runtime-exempt-prefix "Contents/Resources/sc-runtime"',
            macos_builder,
        )
        self.assertIn('Contents/Resources/supernova', macos_builder)
        windows_builder = (ROOT / "packaging" / "build_windows.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            '--forbidden-runtime-exempt-prefix "sc-runtime"', windows_builder
        )
        self.assertIn('"supernova.exe"', windows_builder)

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
                runtime / "Contents" / "Resources" / "supernova",
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
        self.assertIn("var outputControlBus = Bus.control(s, 2)", bootstrap)
        self.assertIn(
            "outputNode.map(\\gateControl, outputControlBus.index)",
            bootstrap,
        )
        self.assertIn(
            "outputNode.map(\\release, outputControlBus.index + 1)",
            bootstrap,
        )
        self.assertIn("record[\\outputControlBus].set(0)", bootstrap)
        self.assertIn("outputControlBus.set(0)", bootstrap)
        self.assertIn("outputControlBus.free", bootstrap)
        self.assertIn("record[\\voiceGroup].set(\\outputGain, value)", bootstrap)
        self.assertNotIn("record[\\outputNode].set(", bootstrap)
        self.assertNotIn("outputNode.set(", bootstrap)
        self.assertNotIn("sourceNode.free", bootstrap)

    def test_gesture_voices_are_bounded_inside_the_engine(self) -> None:
        bootstrap = (SC_ROOT / "bootstrap.scd").read_text(encoding="utf-8")
        launcher = (ROOT / "run_local.sh").read_text(encoding="utf-8")
        config = json.loads(
            (ROOT / "config" / "supercollider.json").read_text(encoding="utf-8")
        )
        self.assertEqual(config["server"]["gesture_voice_limit"], 64)
        self.assertIn("OMNICHORD_SC_MAX_GESTURE_VOICES", bootstrap)
        self.assertIn("handles: List.new", bootstrap)
        self.assertIn(
            "state[\\handles].size >= maxGestureVoices",
            bootstrap,
        )
        self.assertIn("state[\\handles].removeAt(0)", bootstrap)
        self.assertIn("gestureStealRelease", bootstrap)
        self.assertIn("record[\\outputControlBus].setn([", bootstrap)
        self.assertIn("forcedRelease.asFloat.max(0.05)", bootstrap)
        self.assertIn("server.gesture_voice_limit", launcher)
        self.assertIn("export OMNICHORD_SC_MAX_GESTURE_VOICES", launcher)

    def test_supernova_graph_parallelizes_only_independent_stages(self) -> None:
        bootstrap = (SC_ROOT / "bootstrap.scd").read_text(encoding="utf-8")
        self.assertIn("~omniSourceGroup = ParGroup.head(s)", bootstrap)
        self.assertIn(
            "~omniMixGroup = ParGroup.after(~omniSourceGroup)", bootstrap
        )
        self.assertIn("~omniFxGroup = ParGroup.after(~omniMixGroup)", bootstrap)
        self.assertIn("~omniOutputGroup = Group.after(~omniFxGroup)", bootstrap)
        self.assertIn("var voiceGroup = Group.tail(~omniSourceGroup)", bootstrap)

    def test_native_voice_adapter_contains_non_finite_source_output(self) -> None:
        core = (SC_ROOT / "core_synthdefs.scd").read_text(encoding="utf-8")
        self.assertIn("var input = Sanitize.ar(In.ar(in, 2))", core)

    def test_pcm_drum_chokes_use_stable_control_buses(self) -> None:
        samples = (SC_ROOT / "sample_loader.scd").read_text(encoding="utf-8")
        self.assertIn("var gateBus = Bus.control(s, 1)", samples)
        self.assertIn("node.map(\\chokeControl, gateBus)", samples)
        self.assertIn("~omniDrumChokes[chokeKey][\\gateBus].set(0)", samples)
        self.assertNotIn("~omniDrumChokes[chokeKey].set(", samples)

    def test_legacy_vsco_drum_key_uses_resolved_pad_not_gate_role(self) -> None:
        bootstrap = (SC_ROOT / "bootstrap.scd").read_text(encoding="utf-8")
        self.assertIn(
            "var resolvedKey = ~omniMapDrumKey.value(padId, note)", bootstrap
        )
        self.assertIn("resolvedKey.midicps", bootstrap)
        self.assertNotIn("~omniMapDrumKey.value(role, note)", bootstrap)

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
