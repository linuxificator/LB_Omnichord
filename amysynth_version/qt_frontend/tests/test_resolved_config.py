from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from config_loader import (  # noqa: E402
    CONFIG_SCHEMA_REVISION,
    ConfigValidationError,
    apply_transport_overrides,
    load_amy_config,
    load_resolved_amy_config,
)


class ResolvedConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.shipped_path = ROOT / "config" / "amy_config.json"
        cls.shipped = json.loads(cls.shipped_path.read_text(encoding="utf-8"))

    def write_config(self, root: Path, data: object) -> Path:
        path = root / "amy_config.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_shipped_config_becomes_frozen_typed_sections(self) -> None:
        resolved = load_resolved_amy_config(self.shipped_path)

        self.assertEqual(resolved.revision, CONFIG_SCHEMA_REVISION)
        self.assertEqual(resolved.transport.serial_baud, 1_000_000)
        self.assertEqual(resolved.midi_input.configured_profile, "auto")
        self.assertEqual(resolved.midi_input.profile_source, "runtime-adapter")
        self.assertTrue(resolved.osc_input.enabled)
        self.assertEqual(resolved.osc_input.listen_address, "0.0.0.0")
        self.assertEqual(resolved.osc_input.listen_port, 8000)
        self.assertTrue(resolved.osc_input.configured)
        self.assertEqual(resolved.capacities.voices.manual_chord, 7)
        self.assertEqual(resolved.capacities.max_sequencer_tags, 1280)
        self.assertEqual(resolved.capacities.max_sequence_events, 64)
        self.assertEqual(resolved.capacities.max_sequence_executions, 40)
        self.assertEqual(resolved.layout.midi_row_buses, (4, 5, 6, 7, 8, 9))
        self.assertEqual(
            resolved.layout.sequencer_tag_ranges,
            (("drums", 0, 56), ("bass", 56, 56), ("chords", 112, 140)),
        )
        self.assertEqual(
            resolved.layout.sequencer_sequence_ranges,
            (("fills", 256, 936), ("chords", 1192, 64), ("drum_bases", 1256, 24)),
        )
        self.assertEqual(resolved.provenance.source_kind, "shipped")
        self.assertEqual(
            resolved.provenance.platform_derived_paths,
            ("$.midi_input.tech_profile",),
        )
        with self.assertRaises(FrozenInstanceError):
            resolved.transport.serial_baud = 230_400  # type: ignore[misc]

    def test_compatibility_views_are_isolated_and_keep_legacy_patch_map(self) -> None:
        resolved = load_resolved_amy_config(self.shipped_path)
        first = resolved.compatibility_dict()
        second = resolved.compatibility_dict()

        self.assertEqual(len(first["synth_patches"]), 256)
        self.assertEqual(first["synth_patches"]["dx7_143"], 143)
        first["serial"]["baud"] = 1
        first["synth_patches"]["juno_000"] = 99
        self.assertEqual(second["serial"]["baud"], 1_000_000)
        self.assertEqual(second["synth_patches"]["juno_000"], 0)
        self.assertEqual(load_amy_config(self.shipped_path), second)

    def test_legacy_patch_extension_is_deterministic(self) -> None:
        old = copy.deepcopy(self.shipped)
        old["synth_patches"] = {"external_patch": 300}
        with tempfile.TemporaryDirectory() as directory:
            resolved = load_resolved_amy_config(
                self.write_config(Path(directory), old)
            )
        compatibility = resolved.compatibility_dict()
        self.assertEqual(compatibility["synth_patches"]["juno_127"], 127)
        self.assertEqual(compatibility["synth_patches"]["external_patch"], 300)

    def test_structural_errors_report_exact_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wrong_type = copy.deepcopy(self.shipped)
            wrong_type["serial"]["baud"] = "fast"
            with self.assertRaises(ConfigValidationError) as caught:
                load_resolved_amy_config(self.write_config(root, wrong_type))
            self.assertEqual(caught.exception.issues[0].path, "$.serial.baud")

            unknown = copy.deepcopy(self.shipped)
            unknown["serial"]["hardcoded_backup_baud"] = 115_200
            with self.assertRaises(ConfigValidationError) as caught:
                load_resolved_amy_config(self.write_config(root, unknown))
            self.assertEqual(
                caught.exception.issues[0].path,
                "$.serial.hardcoded_backup_baud",
            )
            self.assertEqual(caught.exception.issues[0].message, "unknown property")

    def test_missing_required_sections_are_reported_together(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_config(
                Path(directory),
                {"config_revision": CONFIG_SCHEMA_REVISION},
            )
            with self.assertRaises(ConfigValidationError) as caught:
                load_resolved_amy_config(path)
        paths = {issue.path for issue in caught.exception.issues}
        self.assertIn("$.serial", paths)
        self.assertIn("$.voices", paths)
        self.assertIn("$.buses", paths)
        self.assertGreater(len(paths), 10)

    def test_domain_invariants_aggregate_independent_path_errors(self) -> None:
        invalid = copy.deepcopy(self.shipped)
        invalid["osc_input"]["listen_address"] = "all interfaces"
        invalid["synth_ids"]["bass"] = invalid["synth_ids"]["drums"]
        invalid["voices"]["manual_chord"] = 4
        invalid["voices"]["rhythm_chord"] = 4
        invalid["midi_player"]["synth_ids"][0] = 0
        invalid["buses"]["bass"] = 0
        invalid["amy_max_buses"] = 10
        invalid["rhythm"]["tag_ranges"]["bass"]["start"] = 50
        invalid["rhythm"]["tag_ranges"]["chords"] = {
            "start": 1270,
            "count": 20,
        }
        invalid["amy_max_sequence_events"] = 63
        invalid["amy_max_sequence_executions"] = 33
        invalid["default_synths"]["chord"] = "does_not_exist"

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ConfigValidationError) as caught:
                load_resolved_amy_config(
                    self.write_config(Path(directory), invalid)
                )
        paths = {issue.path for issue in caught.exception.issues}
        self.assertTrue(
            {
                "$.osc_input.listen_address",
                "$.synth_ids",
                "$.voices.manual_chord",
                "$.voices.rhythm_chord",
                "$.midi_player",
                "$.buses",
                "$.amy_max_buses",
                "$.rhythm.tag_ranges.bass",
                "$.rhythm.tag_ranges.chords",
                "$.amy_max_sequence_events",
                "$.amy_max_sequence_executions",
                "$.default_synths.chord",
            }.issubset(paths),
            paths,
        )

    def test_sequence_ranges_must_be_disjoint_contiguous_and_end_at_capacity(self) -> None:
        invalid = copy.deepcopy(self.shipped)
        invalid["rhythm"]["sequence_ranges"]["chords"]["start"] = 1191
        invalid["amy_max_sequencer_tags"] = 1281

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ConfigValidationError) as caught:
                load_resolved_amy_config(
                    self.write_config(Path(directory), invalid)
                )

        paths = {issue.path for issue in caught.exception.issues}
        self.assertIn("$.rhythm.sequence_ranges.chords.start", paths)
        self.assertIn("$.rhythm.sequence_ranges.chords", paths)
        self.assertIn("$.rhythm.sequence_ranges.drum_bases.start", paths)
        self.assertIn("$.amy_max_sequencer_tags", paths)

    def test_absent_osc_endpoint_is_an_explicit_unconfigured_capability(self) -> None:
        unconfigured = copy.deepcopy(self.shipped)
        unconfigured["osc_input"] = {"enabled": True}

        with tempfile.TemporaryDirectory() as directory:
            resolved = load_resolved_amy_config(
                self.write_config(Path(directory), unconfigured)
            )

        self.assertTrue(resolved.osc_input.enabled)
        self.assertFalse(resolved.osc_input.configured)
        self.assertIsNone(resolved.osc_input.listen_address)
        self.assertIsNone(resolved.osc_input.listen_port)

    def test_bad_config_fails_before_transport_is_opened(self) -> None:
        invalid = copy.deepcopy(self.shipped)
        invalid["voices"]["manual_chord"] = 1
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_config(Path(directory), invalid)
            with patch("serial.Serial") as serial_open:
                with self.assertRaises(ConfigValidationError):
                    load_resolved_amy_config(path)
            serial_open.assert_not_called()

    def test_provenance_records_overrides_without_merging_them(self) -> None:
        changed = copy.deepcopy(self.shipped)
        changed["serial"]["baud"] = 230_400
        changed["midi_input"]["tech_profile"] = "linux"
        with tempfile.TemporaryDirectory() as directory:
            resolved = load_resolved_amy_config(
                self.write_config(Path(directory), changed),
                source_kind="user",
            )

        self.assertEqual(resolved.provenance.source_kind, "user")
        self.assertIn("$.serial.baud", resolved.provenance.user_override_paths)
        self.assertIn(
            "$.midi_input.tech_profile",
            resolved.provenance.user_override_paths,
        )
        self.assertEqual(resolved.provenance.platform_derived_paths, ())
        self.assertEqual(resolved.midi_input.profile_source, "explicit-override")
        self.assertEqual(resolved.transport.serial_baud, 230_400)

    def test_json_and_revision_errors_are_path_specific(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "amy_config.json"
            path.write_text('{"config_revision":', encoding="utf-8")
            with self.assertRaises(ConfigValidationError) as caught:
                load_resolved_amy_config(path)
            self.assertEqual(caught.exception.issues[0].path, "$")
            self.assertIn("line 1", caught.exception.issues[0].message)

            path.write_text(json.dumps({"config_revision": 99}), encoding="utf-8")
            with self.assertRaises(ConfigValidationError) as caught:
                load_resolved_amy_config(path)
            self.assertEqual(caught.exception.issues[0].path, "$.config_revision")
            self.assertIn("newer than supported", str(caught.exception))

    def test_cli_transport_overrides_are_typed_isolated_and_provenanced(self) -> None:
        original = load_resolved_amy_config(self.shipped_path)
        overridden = apply_transport_overrides(
            original,
            serial_port="COM7",
            serial_baud=230_400,
        )

        self.assertEqual(original.transport.serial_port, "/dev/serial0")
        self.assertEqual(original.transport.serial_baud, 1_000_000)
        self.assertEqual(overridden.transport.serial_port, "COM7")
        self.assertEqual(overridden.transport.serial_baud, 230_400)
        self.assertEqual(
            overridden.provenance.runtime_override_paths,
            ("$.serial.port", "$.serial.baud"),
        )
        compatibility = overridden.compatibility_dict()
        self.assertEqual(compatibility["serial"]["port"], "COM7")
        self.assertEqual(compatibility["serial"]["baud"], 230_400)

        with self.assertRaises(ConfigValidationError) as caught:
            apply_transport_overrides(original, serial_baud=300)
        self.assertEqual(caught.exception.issues[0].path, "$.serial.baud")


if __name__ == "__main__":
    unittest.main()
