#!/usr/bin/env python3
"""Static checks for the hardware-independent ESP32-P4 build contract."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parents[1]
FRONTEND = ROOT.parent / "qt_frontend"
sys.path.insert(0, str(ROOT))

from assemble_release import assemble
from release_flash_common import build_command


class FirmwareContractTests(unittest.TestCase):
    def test_release_is_gamma9001_and_immutable(self) -> None:
        release = json.loads(
            (FRONTEND / "packaging/release_inputs.json").read_text()
        )["amy"]
        self.assertEqual(release["pcm_bank"], "gamma9001")
        self.assertRegex(release["commit"], r"^[0-9a-f]{40}$")
        self.assertTrue(release["release_branch"].startswith("releases/"))

    def test_runtime_capacity_matches_frontend_contract(self) -> None:
        frontend = json.loads(
            (FRONTEND / "config/amy_config.json").read_text()
        )
        kconfig = (ROOT / "main/Kconfig.projbuild").read_text()
        expected = {
            "OMNICHORD_P4_MAX_OSCS": frontend["amy_max_oscs"],
            "OMNICHORD_P4_MAX_BUSES": frontend["amy_max_buses"],
            "OMNICHORD_P4_MAX_SEQUENCER_TAGS": frontend[
                "amy_max_sequencer_tags"
            ],
            "OMNICHORD_P4_MAX_SEQUENCE_EVENTS": frontend[
                "amy_max_sequence_events"
            ],
            "OMNICHORD_P4_MAX_SEQUENCE_EXECUTIONS": frontend[
                "amy_max_sequence_executions"
            ],
        }
        for symbol, value in expected.items():
            self.assertIn(f"config {symbol}", kconfig)
            self.assertIn(f"default {value}", kconfig)

    def test_retired_sequence_config_names_are_gone(self) -> None:
        source = (ROOT / "main/main.c").read_text()
        kconfig = (ROOT / "main/Kconfig.projbuild").read_text()
        for obsolete in (
            "max_patterns",
            "max_pattern_tags",
            "max_pattern_instances",
            "nested_sequencer",
        ):
            self.assertNotIn(obsolete, source)
        self.assertIn("config.max_sequencer_tags", source)
        for retired in (
            "max_sequence_groups",
            "max_sequence_group_tags",
            "max_sequence_group_executions",
        ):
            self.assertNotIn(retired, source)
            self.assertNotIn(retired.upper(), kconfig)

    def test_gamma_and_external_ram_are_explicit(self) -> None:
        prepare = (ROOT / "prepare_amy.sh").read_text()
        source = (ROOT / "main/main.c").read_text()
        self.assertIn("gamma9001-blob-c", prepare)
        self.assertIn("GAMMA9001=1", prepare)
        self.assertIn("amy_set_gamma9001_pcm(gamma9001_pcm_data)", source)
        self.assertIn("MALLOC_CAP_SPIRAM", source)
        self.assertIn("esp_psram_is_initialized", source)
        package = (ROOT / "package_firmware.sh").read_text()
        self.assertIn('audio_block_size=128', package)
        self.assertIn('i2s_dma_frames=64', package)
        self.assertIn('"audio_block_size=$audio_block_size"', package)
        self.assertIn('"i2s_dma_frames=$i2s_dma_frames"', package)

    def test_pins_are_build_configuration_not_main_constants(self) -> None:
        source = (ROOT / "main/main.c").read_text()
        shared = (ROOT / "main/lp_core/amy_uart_shared.h").read_text()
        for literal in ("GPIO_NUM_15", "config.i2s_lrc  = 16", "1000000"):
            self.assertNotIn(literal, source)
        self.assertIn("CONFIG_OMNICHORD_P4_UART_RX_GPIO", shared)
        self.assertIn("CONFIG_OMNICHORD_P4_UART_BAUD", shared)

    def test_silicon_abis_have_separate_profiles(self) -> None:
        old = (ROOT / "sdkconfig.defaults.v1").read_text()
        new = (ROOT / "sdkconfig.defaults.v3").read_text()
        self.assertIn("CONFIG_ESP32P4_SELECTS_REV_LESS_V3=y", old)
        self.assertIn("CONFIG_ESP32P4_REV_MIN_100=y", old)
        self.assertIn("CONFIG_ESP32P4_REV_MIN_301=y", new)
        self.assertIn("SELECTS_REV_LESS_V3 is not set", new)

    def test_flash_and_psram_are_sized_for_gamma9001(self) -> None:
        defaults = (ROOT / "sdkconfig.defaults").read_text()
        partitions = (ROOT / "partitions.csv").read_text()
        self.assertIn("CONFIG_ESPTOOLPY_FLASHSIZE_32MB=y", defaults)
        self.assertIn("CONFIG_SPIRAM=y", defaults)
        self.assertIn("factory,  app,  factory, 0x10000, 8M", partitions)

    def test_ci_supports_reuse_and_standalone_profiles(self) -> None:
        workflow = (REPO_ROOT / ".github/workflows/esp32p4-build.yml").read_text()
        self.assertIn("workflow_call:", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn('"v1","v3"', workflow)
        self.assertIn("package_firmware.sh", workflow)

    def test_release_flashers_cover_old_and_new_esptool_syntax(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package_root = Path(temporary)
            profile = package_root / "v1"
            (profile / "bootloader").mkdir(parents=True)
            (profile / "bootloader/bootloader.bin").write_bytes(b"boot")
            (profile / "app.bin").write_bytes(b"app")
            (profile / "flasher_args.json").write_text(
                json.dumps(
                    {
                        "flash_files": {
                            "0x2000": "bootloader/bootloader.bin",
                            "0x10000": "app.bin",
                        },
                        "flash_settings": {
                            "flash_mode": "dio",
                            "flash_freq": "80m",
                            "flash_size": "32MB",
                        },
                    }
                ),
                encoding="utf-8",
            )

            legacy, legacy_cwd = build_command(
                package_root=package_root,
                profile="v1",
                port="/dev/test",
                baud=921600,
                modern=False,
            )
            modern, modern_cwd = build_command(
                package_root=package_root,
                profile="v1",
                port="/dev/test",
                baud=921600,
                modern=True,
            )

        self.assertEqual(legacy_cwd, profile.resolve())
        self.assertEqual(modern_cwd, profile.resolve())
        self.assertIn("write_flash", legacy)
        self.assertIn("--flash_mode", legacy)
        self.assertIn("write-flash", modern)
        self.assertIn("--flash-mode", modern)
        self.assertLess(legacy.index("0x2000"), legacy.index("0x10000"))

    def test_release_zip_has_versioned_root_and_both_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profiles = {}
            for profile_name in ("v1", "v3"):
                profile = root / profile_name
                profiles[profile_name] = profile
                for relative in (
                    "BUILD_INFO",
                    "flasher_args.json",
                    "amy_p4_test.bin",
                    "bootloader/bootloader.bin",
                    "partition_table/partition-table.bin",
                ):
                    path = profile / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(profile_name.encode("ascii"))

            archive = assemble(
                release_name="R20260905T123456",
                v1=profiles["v1"],
                v3=profiles["v3"],
                output_dir=root / "out",
            )
            with zipfile.ZipFile(archive) as bundle:
                names = set(bundle.namelist())
            checksum_exists = archive.with_suffix(".zip.sha256").is_file()

        release_root = "LB_Omnichord.R20260905T123456.ESP32P4"
        self.assertIn(f"{release_root}/flash_esptool_v4.py", names)
        self.assertIn(f"{release_root}/flash_esptool_v5.py", names)
        self.assertIn(f"{release_root}/v1/amy_p4_test.bin", names)
        self.assertIn(f"{release_root}/v3/amy_p4_test.bin", names)
        self.assertTrue(all(name.startswith(f"{release_root}/") for name in names))
        self.assertTrue(checksum_exists)


if __name__ == "__main__":
    unittest.main()
