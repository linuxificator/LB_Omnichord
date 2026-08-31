from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

import app_core  # noqa: E402
import midi_player  # noqa: E402
from midi_control import MidiControlState  # noqa: E402
import user_data  # noqa: E402
import instrument_balance  # noqa: E402


class SoundBalanceFeatureTests(unittest.TestCase):
    @staticmethod
    def _strum_backend(
        suffix: str,
        intervals: tuple[int, ...],
        *,
        root: int = 0,
        ladder: bool = False,
    ) -> app_core.InstrumentBackend:
        backend = app_core.InstrumentBackend.__new__(
            app_core.InstrumentBackend
        )
        backend._active_row = 0
        backend._active_root_semitone = root
        backend._row_chord_indexes = [0]
        backend._strum_ladder_mode = ladder
        backend._chords = (
            app_core.ChordType(
                suffix,
                suffix,
                intervals,
                (intervals,),
            ),
        )
        return backend

    def test_balance_plan_covers_every_omni_instrument_and_register(self) -> None:
        plan = instrument_balance.build_plan()
        self.assertEqual(len(plan), 124)
        self.assertEqual({entry["note"] for entry in plan[0]["notes"]}, {40, 60, 84})
    def test_old_user_layout_migrates_without_overwriting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_midi = root / "midi"
            old_midi.mkdir()
            (root / "p1.json").write_text('{"old": 1}', encoding="utf-8")
            (old_midi / "m1.json").write_text('{"midi": 1}', encoding="utf-8")
            original = (user_data.USER_ROOT, user_data.OMNI_PRESET_DIR,
                        user_data.MIDI_PRESET_DIR, user_data.USER_CONFIG_DIR)
            try:
                user_data.USER_ROOT = root
                user_data.OMNI_PRESET_DIR = root / "omni_presets"
                user_data.MIDI_PRESET_DIR = root / "midi_presets"
                user_data.USER_CONFIG_DIR = root / "config"
                user_data.migrate_user_layout()
                self.assertTrue((root / "omni_presets" / "p1.json").is_file())
                self.assertTrue((root / "midi_presets" / "m1.json").is_file())
            finally:
                (user_data.USER_ROOT, user_data.OMNI_PRESET_DIR,
                 user_data.MIDI_PRESET_DIR, user_data.USER_CONFIG_DIR) = original

    def test_user_config_is_seeded_once_and_then_wins(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shipped = root / "shipped"
            shipped.mkdir()
            (shipped / "amy_config.json").write_text('{"serial": 1}', encoding="utf-8")
            original = user_data.USER_CONFIG_DIR
            try:
                user_data.USER_CONFIG_DIR = root / "user"
                with mock.patch.object(
                    user_data.shutil,
                    "copy2",
                    side_effect=AssertionError("metadata copy is not portable"),
                ):
                    selected = user_data.ensure_user_configs(shipped)
                target = selected / "amy_config.json"
                self.assertEqual(json.loads(target.read_text())["serial"], 1)
                target.write_text('{"serial": 2}', encoding="utf-8")
                user_data.ensure_user_configs(shipped)
                self.assertEqual(json.loads(target.read_text())["serial"], 2)
            finally:
                user_data.USER_CONFIG_DIR = original

    def test_old_arpeggio_voice_default_is_migrated_without_losing_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shipped = root / "shipped"
            shipped.mkdir()
            (shipped / "amy_config.json").write_text(
                json.dumps({
                    "config_revision": 1,
                    "serial": {"baud": 1_000_000},
                    "voices": {"manual_chord": 7, "rhythm_chord": 7},
                }),
                encoding="utf-8",
            )
            original = user_data.USER_CONFIG_DIR
            try:
                user_data.USER_CONFIG_DIR = root / "user"
                user_data.USER_CONFIG_DIR.mkdir()
                target = user_data.USER_CONFIG_DIR / "amy_config.json"
                target.write_text(
                    json.dumps({
                        "serial": {"baud": 230_400},
                        "voices": {
                            "manual_chord": 7,
                            "rhythm_chord": 4,
                        },
                        "custom": "preserved",
                    }),
                    encoding="utf-8",
                )

                user_data.ensure_user_configs(shipped)
                migrated = json.loads(target.read_text(encoding="utf-8"))
                self.assertEqual(migrated["config_revision"], 1)
                self.assertEqual(migrated["voices"]["rhythm_chord"], 7)
                self.assertEqual(migrated["serial"]["baud"], 230_400)
                self.assertEqual(migrated["custom"], "preserved")

                # The revision makes the migration idempotent: later edits
                # are authoritative and are never repeatedly rewritten.
                migrated["voices"]["rhythm_chord"] = 8
                target.write_text(json.dumps(migrated), encoding="utf-8")
                user_data.ensure_user_configs(shipped)
                self.assertEqual(
                    json.loads(target.read_text())["voices"]["rhythm_chord"],
                    8,
                )
            finally:
                user_data.USER_CONFIG_DIR = original

    def test_ipmidi_default_is_migrated_without_overwriting_user_values(self) -> None:
        default_ipmidi = {
            "enabled": True,
            "listeners": [
                {
                    "address": "225.0.0.37",
                    "port": 21928,
                    "interface": "0.0.0.0",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shipped = root / "shipped"
            shipped.mkdir()
            (shipped / "amy_config.json").write_text(
                json.dumps(
                    {
                        "config_revision": 2,
                        "midi_input": {"ipmidi": default_ipmidi},
                    }
                ),
                encoding="utf-8",
            )
            original = user_data.USER_CONFIG_DIR
            try:
                user_data.USER_CONFIG_DIR = root / "user"
                user_data.USER_CONFIG_DIR.mkdir()
                target = user_data.USER_CONFIG_DIR / "amy_config.json"
                target.write_text(
                    json.dumps(
                        {
                            "config_revision": 1,
                            "midi_input": {"tech_profile": "linux"},
                        }
                    ),
                    encoding="utf-8",
                )

                user_data.ensure_user_configs(shipped)
                migrated = json.loads(target.read_text(encoding="utf-8"))
                self.assertEqual(migrated["config_revision"], 2)
                self.assertEqual(migrated["midi_input"]["ipmidi"], default_ipmidi)
                self.assertNotIn("tech_profile", migrated["midi_input"])

                custom_ipmidi = {
                    "enabled": False,
                    "listeners": [
                        {
                            "address": "239.1.2.3",
                            "port": 23000,
                            "interface": "192.0.2.20",
                        }
                    ],
                }
                target.write_text(
                    json.dumps(
                        {
                            "config_revision": 1,
                            "midi_input": {
                                "tech_profile": "win32",
                                "ipmidi": custom_ipmidi,
                            },
                        }
                    ),
                    encoding="utf-8",
                )
                user_data.ensure_user_configs(shipped)
                migrated = json.loads(target.read_text(encoding="utf-8"))
                self.assertEqual(
                    migrated["midi_input"]["ipmidi"],
                    custom_ipmidi,
                )
                self.assertEqual(
                    migrated["midi_input"]["tech_profile"],
                    "win32",
                )
            finally:
                user_data.USER_CONFIG_DIR = original

    def test_midi_running_status_parses_control_changes(self) -> None:
        notes = []
        controls = []
        reader = midi_player._LinuxRawMidiReader.__new__(midi_player._LinuxRawMidiReader)
        reader._callback = lambda *args: notes.append(args)
        reader._control_callback = lambda *args: controls.append(args)
        state = {}
        reader._parse_stream(bytes([0xB2, 7, 10, 74, 99]), state)
        self.assertEqual(controls, [(3, 7, 10), (3, 74, 99)])
        self.assertEqual(notes, [])

    def test_midi_channel_status_without_cc_data_adds_no_indicator(self) -> None:
        controls = []
        reader = midi_player._LinuxRawMidiReader.__new__(midi_player._LinuxRawMidiReader)
        reader._callback = lambda *_args: None
        reader._control_callback = lambda *args: controls.append(args)
        state = {}
        reader._parse_stream(bytes([0xB0, 0xB1, 0xB2]), state)
        self.assertEqual(controls, [])

    def test_midi_indicators_fill_capacity_before_lru_replacement(self) -> None:
        state = MidiControlState(capacity=17)
        for controller in range(17):
            state.observe(1, controller, controller)
            state.observe(1, controller, controller + 1)
        self.assertEqual(len(state.controls), 17)
        self.assertTrue(all(item["replaced"] == 0 for item in state.controls))

        state.observe(2, 99, 64)
        self.assertEqual(len(state.controls), 17)
        state.observe(2, 99, 65)
        self.assertEqual(len(state.controls), 17)
        self.assertEqual(state.controls[0]["channel"], 2)
        self.assertEqual(state.controls[0]["controller"], 99)
        self.assertGreater(state.controls[0]["replaced"], 0)

    def test_midi_cc_snapshot_needs_a_value_change_before_indicator(self) -> None:
        state = MidiControlState(capacity=4)

        state.observe(1, 7, 80)
        state.observe(1, 10, 64)
        state.observe(2, 7, 80)
        state.observe(2, 10, 64)
        self.assertEqual(state.controls, [])

        state.observe(2, 7, 81)
        self.assertEqual(
            [(item["channel"], item["controller"]) for item in state.controls],
            [(2, 7)],
        )

    def test_midi_lru_replaces_exactly_the_oldest_changed_control(self) -> None:
        state = MidiControlState(capacity=3)

        for controller in (10, 11, 12):
            state.observe(1, controller, 0)
            state.observe(1, controller, 1)
        state.observe(1, 10, 2)
        state.observe(1, 13, 0)
        state.observe(1, 13, 1)

        keys = {
            (item["channel"], item["controller"])
            for item in state.controls
        }
        self.assertEqual(keys, {(1, 10), (1, 12), (1, 13)})

    def test_ladder_mode_uses_expected_consonant_scale_families(self) -> None:
        backend = self._strum_backend("5", (0, 7), ladder=True)
        self.assertEqual(
            {note % 12 for note in backend._ladder_notes()},
            {0, 2, 4, 7, 9},
        )

    def test_every_chord_has_an_audited_ladder_with_all_chord_tones(self) -> None:
        chords = app_core.load_chords(ROOT / "music" / "chords.csv")
        expected_intervals = {
            "major": (0, 2, 4, 7, 9),
            "minor": (0, 3, 5, 7, 10),
            "diminished": (0, 2, 3, 5, 6, 8, 9, 11),
            "augmented": (0, 2, 4, 6, 8, 10),
            "sus2": (0, 2, 5, 7, 9),
            "sus4": (0, 2, 5, 7, 9),
            "5": (0, 2, 4, 7, 9),
            "major6": (0, 2, 4, 7, 9),
            "minor6": (0, 2, 3, 7, 9),
            "6_9": (0, 2, 4, 7, 9),
            "add9": (0, 2, 4, 7, 9),
            "minor_add9": (0, 2, 3, 5, 7, 10),
            "dominant7": (0, 2, 4, 7, 9, 10),
            "major7": (0, 2, 4, 7, 9, 11),
            "minor7": (0, 3, 5, 7, 10),
            "minor_major7": (0, 2, 3, 7, 9, 11),
            "minor7_flat5": (0, 2, 3, 5, 6, 8, 10),
            "diminished7": (0, 2, 3, 5, 6, 8, 9, 11),
            "augmented7": (0, 2, 4, 8, 10),
            "augmented_major7": (0, 2, 4, 6, 8, 9, 11),
            "7_sus4": (0, 2, 5, 7, 9, 10),
            "dominant9": (0, 2, 4, 7, 9, 10),
            "major9": (0, 2, 4, 7, 9, 11),
            "minor9": (0, 2, 3, 5, 7, 10),
            "dominant11": (0, 2, 4, 5, 7, 9, 10),
            "major11": (0, 2, 4, 5, 7, 9, 11),
            "minor11": (0, 2, 3, 5, 7, 10),
            "dominant13": (0, 2, 4, 5, 7, 9, 10),
            "major13": (0, 2, 4, 5, 7, 9, 11),
            "minor13": (0, 2, 3, 5, 7, 9, 10),
            "dominant7_flat5": (0, 2, 4, 6, 10),
            "dominant7_sharp5": (0, 2, 4, 8, 10),
            "dominant7_flat9": (0, 1, 4, 7, 10),
            "dominant7_sharp9": (0, 3, 4, 7, 10),
            "dominant7_sharp11": (0, 2, 4, 6, 7, 9, 10),
            "dominant7_flat13": (0, 2, 4, 7, 8, 10),
        }

        self.assertEqual(
            set(expected_intervals),
            {chord.suffix for chord in chords},
        )
        self.assertEqual(
            set(app_core.CHORD_LADDER_PATTERNS),
            set(expected_intervals),
        )
        for chord in chords:
            ladder_intervals, degree_offsets = app_core.ladder_pattern(
                chord.suffix
            )
            self.assertEqual(
                ladder_intervals,
                expected_intervals[chord.suffix],
                chord.suffix,
            )
            self.assertEqual(
                len(ladder_intervals),
                len(degree_offsets),
                chord.suffix,
            )
            self.assertTrue(
                {interval % 12 for interval in chord.intervals}
                <= {interval % 12 for interval in ladder_intervals},
                chord.suffix,
            )

    def test_minor_major7_ladder_uses_melodic_minor_colours_without_flat7(self) -> None:
        g_minor_major7 = self._strum_backend(
            "minor_major7",
            (0, 3, 7, 11),
            root=7,
            ladder=True,
        )
        self.assertEqual(
            g_minor_major7._strum_note_names(),
            ["G", "A", "B♭", "D", "E", "F♯"],
        )
        self.assertNotIn("F", g_minor_major7._strum_note_names())

    def test_ladder_lookup_rejects_unaudited_new_chord_types(self) -> None:
        with self.assertRaisesRegex(ValueError, "No audited LDR pattern"):
            app_core.ladder_pattern("future_chord")

    def test_apg_note_guide_uses_musical_chord_spelling(self) -> None:
        major = self._strum_backend("major", (0, 4, 7))
        minor = self._strum_backend("minor", (0, 3, 7))
        sharp_dominant = self._strum_backend(
            "dominant7",
            (0, 4, 7, 10),
            root=6,
        )

        self.assertEqual(major._strum_note_names(), ["C", "E", "G"])
        self.assertEqual(minor._strum_note_names(), ["C", "E♭", "G"])
        self.assertEqual(
            sharp_dominant._strum_note_names(),
            ["F♯", "A♯", "C♯", "E"],
        )

    def test_ldr_note_guide_keeps_scale_accidentals_consistent(self) -> None:
        d_major = self._strum_backend(
            "major",
            (0, 4, 7),
            root=2,
            ladder=True,
        )
        eb_minor = self._strum_backend(
            "minor",
            (0, 3, 7),
            root=3,
            ladder=True,
        )

        self.assertEqual(
            d_major._strum_note_names(),
            ["D", "E", "F♯", "A", "B"],
        )
        self.assertEqual(
            eb_minor._strum_note_names(),
            ["E♭", "G♭", "A♭", "B♭", "D♭"],
        )

    def test_octatonic_note_guide_uses_its_musical_mixed_spelling(self) -> None:
        diminished = self._strum_backend(
            "diminished",
            (0, 3, 6),
            ladder=True,
        )
        self.assertEqual(
            diminished._strum_note_names(),
            ["C", "D", "E♭", "F", "G♭", "A♭", "A", "B"],
        )

    def test_note_guide_is_empty_without_an_active_chord(self) -> None:
        backend = self._strum_backend("major", (0, 4, 7))
        backend._active_row = -1
        backend._active_root_semitone = -1
        self.assertEqual(backend._strum_note_names(), [])


if __name__ == "__main__":
    unittest.main()
