from __future__ import annotations

import hashlib
import json
import sys
import tomllib
import unittest
from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[1]
ACTIVE = FRONTEND.parent
CODE = FRONTEND / "code"
PROFILE = (
    ACTIVE
    / "controller_profiles"
    / "novation_flkey_mini"
    / "lb_omnichord_gm_drums.toml"
)
SYSEX = PROFILE.with_suffix(".syx")
CHECKSUMS = PROFILE.parent / "SHA256SUMS"
DEFAULT_BINDINGS = FRONTEND / "instruments" / "default_omni_midi_control_bindings.json"
OMNI_FACTORY_PRESETS = FRONTEND / "instruments" / "default_presets"

if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))

from gm_percussion import GM_PERCUSSION_NAMES  # noqa: E402


EXPECTED_NOTES = (
    49, 42, 44, 46, 50, 48, 51, 57,
    37, 39, 38, 36, 35, 45, 43, 41,
)


class ControllerProfileTests(unittest.TestCase):
    def test_every_factory_omni_preset_has_reviewed_controller_defaults(self) -> None:
        expected = json.loads(DEFAULT_BINDINGS.read_text(encoding="utf-8"))
        self.assertEqual(len(expected), 12)

        for number in range(1, 19):
            with self.subTest(preset=number):
                preset = json.loads(
                    (OMNI_FACTORY_PRESETS / f"p{number}.json").read_text(
                        encoding="utf-8"
                    )
                )
                self.assertEqual(preset.get("midi_control_bindings"), expected)

    def test_flkey_mini_profile_is_a_distinct_channel_ten_gm_kit(self) -> None:
        with PROFILE.open("rb") as handle:
            profile = tomllib.load(handle)

        self.assertEqual(profile["version"], 2)
        self.assertEqual(profile["device"], "flkey-mini-pads")
        pads = profile["pads"]
        self.assertEqual(set(pads), {str(index) for index in range(1, 17)})

        notes = tuple(pads[str(index)]["note"]["pitch"] for index in range(1, 17))
        channels = tuple(
            pads[str(index)]["note"]["channel"] for index in range(1, 17)
        )
        self.assertEqual(notes, EXPECTED_NOTES)
        self.assertEqual(len(set(notes)), 16)
        self.assertTrue(all(note in GM_PERCUSSION_NAMES for note in notes))
        self.assertEqual(channels, (10,) * 16)

    def test_committed_sysex_has_framing_and_reviewed_digest(self) -> None:
        data = SYSEX.read_bytes()
        self.assertGreater(len(data), 16)
        self.assertEqual(data[0], 0xF0)
        self.assertEqual(data[-1], 0xF7)

        digest = hashlib.sha256(data).hexdigest()
        expected_line = CHECKSUMS.read_text(encoding="utf-8").strip()
        self.assertEqual(
            expected_line,
            f"{digest}  {SYSEX.name}",
        )


if __name__ == "__main__":
    unittest.main()
