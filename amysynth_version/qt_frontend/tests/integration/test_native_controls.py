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
        # Ignore voice-allocation metadata and the automatic lane's diagnostic
        # flag when comparing timbre. Neither changes oscillator/program state.
        normalized = re.sub(r"iv\d+", "iv#", command, count=1)
        normalized = re.sub(r"if\d+", "", normalized)
        result.append(normalized)
    return result


class NativeControlTests(unittest.TestCase):
    def test_repeater_sustain_changes_only_amplitude_in_real_amy(self) -> None:
        repeater_index = synth_index("Repeater")
        patch = patch_for_index(repeater_index)

        with HeadlessApp(native_amy=True) as app:
            app.bridge.wait_idle(timeout=10.0)
            app.action("setChordSynthIndex", repeater_index)
            app.bridge.wait_for_lines(
                [f"K{patch}i3Z", f"K{patch}i4if8Z"],
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
            manual_chord = app.bridge.synth_commands(3)
            automatic_chord = app.bridge.synth_commands(4)
            self.assertFalse(any("if8" in command for command in manual_chord))
            self.assertTrue(any("if8" in command for command in automatic_chord))
            app.bridge.checkpoint("cold-start-all-synths", synths=(0, 1, 2, 3, 4))


    def test_strum_patch_change_cannot_change_chord_synth_or_bus(self) -> None:
        meow = synth_index("Meow Brass")
        sustainer = synth_index("Sustainer")
        other = synth_index("Orchestral Pad")

        def bus_line(state: str, bus: int) -> str:
            prefix = f"y{bus}"
            matches = [line for line in state.splitlines() if line.startswith(prefix)]
            self.assertEqual(len(matches), 1, state)
            return matches[0]

        with HeadlessApp(native_amy=True) as app:
            app.bridge.wait_idle(timeout=10.0)
            start = app.bridge.count()
            app.action("setChordSynthIndex", meow)
            app.action("setStrumSynthIndex", sustainer)
            # HTTP actions enqueue writer transactions.  Wait for evidence
            # that both transactions reached the independent serial peer
            # before using wait_idle() to settle their remaining commands.
            # Without this boundary, wait_idle() can observe the *previous*
            # idle interval before the writer has emitted its first byte.
            app.bridge.wait_for_lines(
                [
                    f"K{patch_for_index(meow)}i3Z",
                    f"K{patch_for_index(sustainer)}i2Z",
                ],
                start=start,
                timeout=8.0,
            )
            app.bridge.wait_idle(timeout=8.0)

            before3 = app.bridge.synth_commands(3)
            before4 = app.bridge.synth_commands(4)
            before_bus3 = bus_line(app.bridge.dump_state("before-strum-switch"), 3)

            start = app.bridge.count()
            app.action("setStrumSynthIndex", other)
            app.bridge.wait_for_lines(
                [f"K{patch_for_index(other)}i2Z"], start=start, timeout=8.0
            )
            app.bridge.wait_idle(timeout=8.0)

            after3 = app.bridge.synth_commands(3)
            after4 = app.bridge.synth_commands(4)
            after_bus3 = bus_line(app.bridge.dump_state("after-strum-switch"), 3)

            self.assertEqual(before3, after3, "strum patch switch changed manual chord synth")
            self.assertEqual(before4, after4, "strum patch switch changed rhythm chord synth")
            self.assertEqual(before_bus3, after_bus3, "strum patch switch changed chord bus FX")
            app.bridge.checkpoint("strum-isolated-from-chord", synths=(2, 3, 4))


if __name__ == "__main__":
    unittest.main()
