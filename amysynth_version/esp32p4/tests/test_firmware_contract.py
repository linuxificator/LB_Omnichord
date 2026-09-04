#!/usr/bin/env python3
"""Static checks for the hardware-independent ESP32-P4 build contract."""

from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parents[1]
FRONTEND = ROOT.parent / "qt_frontend"


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
            "OMNICHORD_P4_MAX_SEQUENCE_GROUPS": frontend[
                "amy_max_sequence_groups"
            ],
            "OMNICHORD_P4_MAX_SEQUENCE_GROUP_TAGS": frontend[
                "amy_max_sequence_group_tags"
            ],
            "OMNICHORD_P4_MAX_SEQUENCE_GROUP_EXECUTIONS": frontend[
                "amy_max_sequence_group_executions"
            ],
        }
        for symbol, value in expected.items():
            self.assertIn(f"config {symbol}", kconfig)
            self.assertIn(f"default {value}", kconfig)

    def test_old_nested_pattern_config_names_are_gone(self) -> None:
        source = (ROOT / "main/main.c").read_text()
        for obsolete in (
            "max_patterns",
            "max_pattern_tags",
            "max_pattern_instances",
            "nested_sequencer",
        ):
            self.assertNotIn(obsolete, source)
        self.assertIn("config.max_sequence_groups", source)

    def test_gamma_and_external_ram_are_explicit(self) -> None:
        prepare = (ROOT / "prepare_amy.sh").read_text()
        source = (ROOT / "main/main.c").read_text()
        self.assertIn("gamma9001-blob-c", prepare)
        self.assertIn("GAMMA9001=1", prepare)
        self.assertIn("amy_set_gamma9001_pcm(gamma9001_pcm_data)", source)
        self.assertIn("MALLOC_CAP_SPIRAM", source)
        self.assertIn("esp_psram_is_initialized", source)

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


if __name__ == "__main__":
    unittest.main()
