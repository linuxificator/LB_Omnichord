from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from frontend_config import (  # noqa: E402
    CURRENT_FRONTEND_CONFIG_REVISION,
    FrontendConfigError,
    load_frontend_config,
    resolve_frontend_config,
)
import user_data  # noqa: E402


class FrontendConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.path = ROOT / "config" / "frontend.json"
        cls.shipped = json.loads(cls.path.read_text(encoding="utf-8"))

    def resolve(self, value: object):
        return resolve_frontend_config(value, source_path=self.path)

    def test_shipped_config_is_small_typed_and_engine_neutral(self) -> None:
        config = load_frontend_config(self.path)
        self.assertEqual(config.revision, CURRENT_FRONTEND_CONFIG_REVISION)
        self.assertEqual(config.midi_voices_per_row, 4)
        self.assertEqual(config.layout.midi_row_buses, (4, 5, 6, 7, 8, 9))
        self.assertEqual(dict(config.layout.role_buses)["chord"], 3)
        text = self.path.read_text(encoding="utf-8").casefold()
        for forbidden in ("amy", "serial", "sequencer_tags", "oscillators"):
            self.assertNotIn(forbidden, text)

    def test_unknown_missing_and_future_fields_have_paths(self) -> None:
        unknown = copy.deepcopy(self.shipped)
        unknown["amy_max_oscs"] = 128
        with self.assertRaises(FrontendConfigError) as caught:
            self.resolve(unknown)
        self.assertEqual(caught.exception.issues[0].path, "$.amy_max_oscs")

        missing = copy.deepcopy(self.shipped)
        del missing["logical_buses"]
        with self.assertRaises(FrontendConfigError) as caught:
            self.resolve(missing)
        self.assertEqual(caught.exception.issues[0].path, "$.logical_buses")

        future = copy.deepcopy(self.shipped)
        future["config_revision"] = 99
        with self.assertRaises(FrontendConfigError) as caught:
            self.resolve(future)
        self.assertEqual(caught.exception.issues[0].path, "$.config_revision")

    def test_network_and_bus_invariants_are_validated(self) -> None:
        invalid_network = copy.deepcopy(self.shipped)
        invalid_network["osc_input"]["listen_address"] = "localhost"
        with self.assertRaises(FrontendConfigError) as caught:
            self.resolve(invalid_network)
        self.assertEqual(caught.exception.issues[0].path, "$.osc_input.listen_address")

        duplicate_bus = copy.deepcopy(self.shipped)
        duplicate_bus["logical_buses"]["midi_drums"] = 3
        with self.assertRaises(FrontendConfigError) as caught:
            self.resolve(duplicate_bus)
        self.assertEqual(caught.exception.issues[0].path, "$.logical_buses")

    def test_first_start_imports_only_relevant_legacy_user_settings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            user_root = Path(directory) / ".omnichord"
            config_dir = user_root / "config"
            config_dir.mkdir(parents=True)
            legacy = {
                "midi_input": copy.deepcopy(self.shipped["midi_input"]),
                "osc_input": copy.deepcopy(self.shipped["osc_input"]),
                "default_synths": {
                    "chord": "juno_004",
                    "strum": "juno_028",
                    "bass": "dx7_143",
                },
                "midi_player": {"voices_per_synth": 7},
                "rhythm": {
                    "chord_gate_beats": 0.8,
                    "bass_gate_beats": 0.4,
                    "max_rhythm_chord_notes": 5,
                    "tag_ranges": {"not": "imported"},
                },
                "performance": {"strum_tail_ms": 600, "synth_alloc_guard_ms": 99},
                "buses": copy.deepcopy(self.shipped["logical_buses"]),
                "amy_max_oscs": 999,
            }
            (config_dir / "amy_config.json").write_text(
                json.dumps(legacy), encoding="utf-8"
            )
            with patch.multiple(
                user_data,
                USER_ROOT=user_root,
                USER_CONFIG_DIR=config_dir,
                OMNI_PRESET_DIR=user_root / "omni_presets",
                MIDI_PRESET_DIR=user_root / "midi_presets",
            ):
                result = user_data.ensure_user_configs(ROOT / "config")

            loaded = json.loads((result / "frontend.json").read_text(encoding="utf-8"))
            self.assertEqual(
                loaded["default_programs"], self.shipped["default_programs"]
            )
            self.assertEqual(loaded["midi"]["voices_per_row"], 7)
            self.assertEqual(loaded["rhythm"]["max_chord_notes"], 5)
            self.assertEqual(loaded["performance"], {"strum_tail_ms": 600})
            self.assertNotIn("amy_max_oscs", loaded)
            self.assertNotIn("tag_ranges", loaded["rhythm"])


if __name__ == "__main__":
    unittest.main()
