from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


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
                selected = user_data.ensure_user_configs(shipped)
                target = selected / "amy_config.json"
                target.write_text('{"serial": 2}', encoding="utf-8")
                user_data.ensure_user_configs(shipped)
                self.assertEqual(json.loads(target.read_text())["serial"], 2)
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
