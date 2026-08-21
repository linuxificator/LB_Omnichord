from __future__ import annotations

import re
import unittest

from catalog import patch_for_index, synth_index
from harness import HeadlessApp


def parameter_signature(commands: list[str], prefix: str) -> list[str]:
    pattern = re.compile(re.escape(prefix) + r"([^A-Za-zZ]*)")
    values: list[str] = []
    for command in commands:
        values.extend(match.group(1) for match in pattern.finditer(command))
    return values


def normalized_chord_synth(commands: list[str]) -> list[str]:
    result: list[str] = []
    for command in commands:
        # Manual chords intentionally have 7 voices while rhythm chords have 4.
        # get_synth_commands() omits the synth number itself, so voice-pool size
        # is the only allocation difference to remove. Everything describing
        # the per-voice oscillator/timbre remains compared exactly.
        result.append(re.sub(r"iv\d+", "iv#", command, count=1))
    return result


class NativeControlTests(unittest.TestCase):
    def test_repeater_sustain_changes_only_amplitude_in_real_amy(self) -> None:
        repeater_index = synth_index("Repeater")
        patch = patch_for_index(repeater_index)

        with HeadlessApp(native_amy=True) as app:
            app.bridge.wait_idle(timeout=10.0)
            app.action("setChordSynthIndex", repeater_index)
            app.bridge.wait_for_lines(
                [f"K{patch}i3Z", f"K{patch}i4Z"],
                start=0,
                timeout=8.0,
            )
            app.bridge.wait_idle(timeout=8.0)

            before3 = app.bridge.synth_commands(3)
            before4 = app.bridge.synth_commands(4)
            self.assertEqual(
                normalized_chord_synth(before3),
                normalized_chord_synth(before4),
                "manual and rhythm chord timbres already differ before edit",
            )
            before_filter3 = (
                parameter_signature(before3, "F"),
                parameter_signature(before3, "R"),
            )
            before_filter4 = (
                parameter_signature(before4, "F"),
                parameter_signature(before4, "R"),
            )

            start = app.bridge.count()
            app.action("setChordSynthControl", "sustain", 0.42)
            app.bridge.wait_for_lines(
                ["v0A,,,0.42,,i3Z", "v0A,,,0.42,,i4Z"],
                start=start,
            )
            app.bridge.wait_idle(timeout=8.0)
            wire_delta = app.bridge.lines_since(start)
            self.assertFalse(
                any("F" in line or "R" in line for line in wire_delta),
                "Sustain edit resent filter/resonance commands:\n"
                + "\n".join(wire_delta),
            )

            after3 = app.bridge.synth_commands(3)
            after4 = app.bridge.synth_commands(4)
            self.assertEqual(
                before_filter3,
                (
                    parameter_signature(after3, "F"),
                    parameter_signature(after3, "R"),
                ),
                "native AMY filter state changed on manual Repeater synth",
            )
            self.assertEqual(
                before_filter4,
                (
                    parameter_signature(after4, "F"),
                    parameter_signature(after4, "R"),
                ),
                "native AMY filter state changed on rhythm Repeater synth",
            )
            self.assertEqual(
                normalized_chord_synth(after3),
                normalized_chord_synth(after4),
                "manual and rhythm chord timbres diverged after Sustain edit",
            )
            app.bridge.checkpoint("repeater-sustain")


    def test_cold_start_defines_all_five_synths_in_real_amy(self) -> None:
        with HeadlessApp(native_amy=True) as app:
            app.bridge.wait_idle(timeout=10.0)
            for synth in range(5):
                commands = app.bridge.synth_commands(synth)
                self.assertTrue(commands, f"native AMY synth {synth} is undefined after cold start")
            app.bridge.checkpoint("cold-start-all-synths", synths=(0, 1, 2, 3, 4))


if __name__ == "__main__":
    unittest.main()
