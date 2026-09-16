from __future__ import annotations

import copy
from functools import partial
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
import frontend_config  # noqa: E402
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

    def test_osc_listener_can_be_deliberately_unconfigured(self) -> None:
        unconfigured = copy.deepcopy(self.shipped)
        del unconfigured["osc_input"]["listen_address"]
        del unconfigured["osc_input"]["listen_port"]

        config = self.resolve(unconfigured)

        self.assertFalse(config.osc_input.configured)
        self.assertIsNone(config.osc_input.listen_address)
        self.assertIsNone(config.osc_input.listen_port)

    def test_osc_listener_address_and_port_are_an_atomic_pair(self) -> None:
        missing_port = copy.deepcopy(self.shipped)
        del missing_port["osc_input"]["listen_port"]
        with self.assertRaises(FrontendConfigError) as caught:
            self.resolve(missing_port)
        self.assertEqual(caught.exception.issues[0].path, "$.osc_input.listen_port")

        missing_address = copy.deepcopy(self.shipped)
        del missing_address["osc_input"]["listen_address"]
        with self.assertRaises(FrontendConfigError) as caught:
            self.resolve(missing_address)
        self.assertEqual(
            caught.exception.issues[0].path,
            "$.osc_input.listen_address",
        )

    def test_new_release_seeds_defaults_without_importing_an_older_release(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            user_root = Path(directory) / ".omnichord"
            old_config_dir = user_root / "R20260901T120000-SC" / "config"
            old_config_dir.mkdir(parents=True)
            old_frontend = copy.deepcopy(self.shipped)
            old_frontend["midi"]["voices_per_row"] = 7
            (old_config_dir / "frontend.json").write_text(
                json.dumps(old_frontend), encoding="utf-8"
            )
            release_root = user_root / "R20260916T120000-SC"
            config_dir = release_root / "config"
            with patch.multiple(
                user_data,
                USER_ROOT=release_root,
                USER_CONFIG_DIR=config_dir,
                OMNI_PRESET_DIR=release_root / "omni_presets",
                MIDI_PRESET_DIR=release_root / "midi_presets",
            ):
                result = user_data.ensure_user_configs(ROOT / "config")

            loaded = json.loads((result / "frontend.json").read_text(encoding="utf-8"))
            self.assertEqual(loaded, self.shipped)
            self.assertEqual(old_frontend["midi"]["voices_per_row"], 7)

    def test_packaged_first_start_uses_the_explicit_asset_schema(self) -> None:
        """A copied user config must not derive schema location from __file__."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packaged_config = root / "package" / "_internal" / "config"
            packaged_config.mkdir(parents=True)
            for source in (ROOT / "config").glob("*.json"):
                (packaged_config / source.name).write_bytes(source.read_bytes())
            schema_dir = packaged_config / "schema"
            schema_dir.mkdir()
            schema = schema_dir / "frontend_v1.schema.json"
            schema.write_bytes(
                (ROOT / "config" / "schema" / schema.name).read_bytes()
            )
            user_config = (
                root / "home" / ".omnichord" / "R20260916T120000-SC" / "config"
            )
            loader = partial(frontend_config.load_frontend_config, schema_path=schema)

            # Model a frozen module beside the executable. There is no schema
            # at the source-layout fallback path used by an unfrozen module.
            with patch.object(
                frontend_config,
                "__file__",
                str(root / "package" / "frontend_config.py"),
            ):
                result = user_data.ensure_user_configs(
                    packaged_config,
                    user_config_dir=user_config,
                    frontend_config_loader=loader,
                )
                resolved = loader(result / "frontend.json")

            self.assertEqual(resolved.source_path, (result / "frontend.json").resolve())
            self.assertEqual(resolved.source_kind, "user")


if __name__ == "__main__":
    unittest.main()
