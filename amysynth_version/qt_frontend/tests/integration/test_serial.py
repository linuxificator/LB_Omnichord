from __future__ import annotations

import re
import time
import unittest

from catalog import control_default, patch_for_index, synth_index
from harness import HeadlessApp


_NOTE = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)"


def wire_float(value: float) -> str:
    return f"{float(value):.9g}"


def scheduled_note_ons(lines: list[str], synth: int) -> list[float]:
    pattern = re.compile(
        rf"^H\d+,\d+n(?P<note>{_NOTE})l(?P<vel>{_NOTE})i{int(synth)}Z$"
    )
    notes: list[float] = []
    for line in lines:
        match = pattern.match(line)
        if match and float(match.group("vel")) > 0.0:
            notes.append(float(match.group("note")))
    return notes


def immediate_note_ons(lines: list[str], synth: int) -> list[float]:
    pattern = re.compile(
        rf"^n(?P<note>{_NOTE})l(?P<vel>{_NOTE})i{int(synth)}Z$"
    )
    notes: list[float] = []
    for line in lines:
        match = pattern.match(line)
        if match and float(match.group("vel")) > 0.0:
            notes.append(float(match.group("note")))
    return notes


def wait_for_immediate_note_ons(
    app: HeadlessApp,
    start: int,
    synth: int,
    *,
    minimum_count: int,
    timeout: float = 5.0,
) -> list[float]:
    """Wait for queued writer output instead of inferring it from idle age."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        notes = immediate_note_ons(app.bridge.lines_since(start), synth)
        if len(notes) >= minimum_count:
            return notes
        time.sleep(0.01)
    raise AssertionError(
        f"expected at least {minimum_count} note-ons for synth {synth}; "
        f"received:\n" + "\n".join(app.bridge.lines_since(start))
    )


def contains_fractional_pitch(notes: list[float]) -> bool:
    return any(abs(note - round(note)) > 1e-5 for note in notes)


class SerialIntegrationTests(unittest.TestCase):
    def test_preset7_rhythm_start_preserves_native_filter_until_user_override(self) -> None:
        """Fresh P7 must leave Chorus Vibes' complete native VCF model intact."""
        chorus_index = synth_index("Chorus Vibes")
        chorus_patch = patch_for_index(chorus_index)
        cutoff = control_default(chorus_index, "filter_hz")
        native_cutoff4 = f"v0F{wire_float(cutoff)}i4Z"

        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)
            app.action("selectPreset", 7)
            app.bridge.wait_idle(timeout=8.0)
            self.assertEqual(app.query("selectedPreset"), 7)
            self.assertEqual(app.query("selectedChordSynthIndex"), chorus_index)

            # The factory K66 command already installs F27.365 together with
            # note/envelope tracking. The host must not rewrite that native
            # base coefficient merely because it is visible in the UI.
            select_lines = app.bridge.lines_since(0)
            self.assertNotIn(native_cutoff4, select_lines)

            app.action("pressChord", 0, 0)
            app.action("releaseChord", 0, 0)
            app.bridge.wait_idle(timeout=8.0)

            start = app.bridge.count()
            if not bool(app.query("rhythmRunning")):
                app.action("toggleRhythm")
            app.bridge.wait_for_lines(["zY1Z"], start=start, timeout=8.0)
            app.bridge.wait_idle(timeout=8.0)
            lines = app.bridge.lines_since(start)
            self.assertNotIn(native_cutoff4, lines)
            self.assertNotIn(f"K{chorus_patch}i4Z", lines)
            self.assertTrue(
                any(line.startswith("H") and "i4Z" in line for line in lines),
                "no rhythm-chord events were scheduled",
            )

            # A real UI edit becomes an explicit engine override and is sent to
            # both manual and rhythm chord synths.
            edited_cutoff = max(500.0, cutoff + 250.0)
            edited3 = f"v0F{wire_float(edited_cutoff)}i3Z"
            edited4 = f"v0F{wire_float(edited_cutoff)}i4Z"
            edit_start = app.bridge.count()
            app.action("setChordSynthControl", "filter_hz", edited_cutoff)
            edit_lines = app.bridge.wait_for_lines(
                [edited3, edited4], start=edit_start, timeout=8.0
            )
            self.assertNotIn(f"K{chorus_patch}i3Z", edit_lines)
            self.assertNotIn(f"K{chorus_patch}i4Z", edit_lines)

    def test_every_note_path_follows_live_tuning_change(self) -> None:
        """EQ/HARM changes must reach manual, rhythm, bass and strum pitches."""
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)

            # Use a known C-major chord so HARM changes E/G while C remains the
            # reference. High accompaniment activity guarantees non-root notes
            # are represented in both rhythm-chord and bass schedules.
            app.action("setRowChordType", 0, 0)  # major = 0,4,7
            app.action("setTuningReference", 440)
            app.action("setTuningModeIndex", 1)  # EQ
            app.action("setRhythmChordActivity", 4.0)
            app.action("setRhythmBassActivity", 4.0)
            if not bool(app.query("bassRunning")):
                app.action("toggleBassRunning")
            app.action("selectChord", 0, 0)  # C major becomes the active chord
            app.bridge.wait_idle(timeout=8.0)

            eq_start = app.bridge.count()
            if not bool(app.query("rhythmRunning")):
                app.action("toggleRhythm")
            else:
                # Re-publish active pitch state and force a schedule rebuild in
                # the known EQ state.
                app.action("setTuningModeIndex", 0)
                app.action("setTuningModeIndex", 1)
            app.bridge.wait_for_lines(["zY1Z"], start=eq_start, timeout=8.0)
            app.bridge.wait_idle(timeout=8.0)
            eq_lines = app.bridge.lines_since(eq_start)
            eq_bass = scheduled_note_ons(eq_lines, 1)
            eq_rhythm_chords = scheduled_note_ons(eq_lines, 4)
            self.assertTrue(eq_bass, "EQ schedule contains no bass note-ons")
            self.assertTrue(
                eq_rhythm_chords,
                "EQ schedule contains no automatic chord note-ons",
            )

            # Changing only the tuning mode must rebuild both accompaniment
            # pitch lanes from the same newly tuned chord state.
            harm_start = app.bridge.count()
            app.action("setTuningModeIndex", 0)  # HARM
            app.bridge.wait_for_lines(
                ["S4096Z", "zY1Z"], start=harm_start, timeout=8.0
            )
            app.bridge.wait_idle(timeout=8.0)
            harm_lines = app.bridge.lines_since(harm_start)
            harm_bass = scheduled_note_ons(harm_lines, 1)
            harm_rhythm_chords = scheduled_note_ons(harm_lines, 4)
            self.assertTrue(harm_bass, "HARM rebuild contains no bass note-ons")
            self.assertTrue(
                harm_rhythm_chords,
                "HARM rebuild contains no automatic chord note-ons",
            )
            self.assertNotEqual(
                eq_bass,
                harm_bass,
                "bass schedule did not change pitch when EQ changed to HARM",
            )
            self.assertNotEqual(
                eq_rhythm_chords,
                harm_rhythm_chords,
                "rhythm-chord schedule did not change pitch when EQ changed to HARM",
            )
            self.assertTrue(
                contains_fractional_pitch(harm_bass),
                "HARM bass schedule contains no intonation-adjusted pitch",
            )
            self.assertTrue(
                contains_fractional_pitch(harm_rhythm_chords),
                "HARM rhythm-chord schedule contains no intonation-adjusted pitch",
            )

            # A physically held chord must retune in place through synth 3.
            press_start = app.bridge.count()
            app.action("pressChord", 0, 0)
            press_notes = wait_for_immediate_note_ons(
                app, press_start, 3, minimum_count=3
            )
            self.assertTrue(
                contains_fractional_pitch(press_notes),
                "held chord did not start with HARM intonation",
            )
            # The press also updates accompaniment gating/scheduling. Wait for
            # that transaction to finish so its HARM note-ons cannot leak into
            # the next EQ checkpoint.
            app.bridge.wait_for_lines(["zY1Z"], start=press_start, timeout=8.0)
            app.bridge.wait_idle(timeout=8.0)

            manual_eq_start = app.bridge.count()
            app.action("setTuningModeIndex", 1)  # back to EQ while held
            eq_manual = wait_for_immediate_note_ons(
                app, manual_eq_start, 3, minimum_count=3
            )
            self.assertFalse(
                contains_fractional_pitch(eq_manual),
                "equal-tempered C-major chord unexpectedly contains fractional pitches",
            )

            manual_harm_start = app.bridge.count()
            app.action("setTuningModeIndex", 0)
            harm_manual = wait_for_immediate_note_ons(
                app, manual_harm_start, 3, minimum_count=3
            )
            self.assertTrue(
                contains_fractional_pitch(harm_manual),
                "held chord did not acquire HARM intonation",
            )
            self.assertNotEqual(eq_manual, harm_manual)
            app.action("releaseChord", 0, 0)
            app.bridge.wait_idle(timeout=8.0)

            # Strum notes are generated at gesture time. The same touch
            # positions must therefore produce equal-tempered notes in EQ and
            # intonation-adjusted notes in HARM.
            app.action("setTuningModeIndex", 1)
            app.bridge.wait_idle(timeout=8.0)
            eq_strum_start = app.bridge.count()
            for y in (0.21, 0.37, 0.53, 0.69):
                app.action("strumTap", y)
            eq_strum = wait_for_immediate_note_ons(
                app, eq_strum_start, 2, minimum_count=4
            )

            app.action("setTuningModeIndex", 0)
            app.bridge.wait_idle(timeout=8.0)
            harm_strum_start = app.bridge.count()
            for y in (0.21, 0.37, 0.53, 0.69):
                app.action("strumTap", y)
            harm_strum = wait_for_immediate_note_ons(
                app, harm_strum_start, 2, minimum_count=4
            )
            self.assertEqual(len(eq_strum), len(harm_strum))
            self.assertNotEqual(
                eq_strum,
                harm_strum,
                "strum pitches did not follow the tuning change",
            )
            self.assertTrue(
                contains_fractional_pitch(harm_strum),
                "HARM strum contains no intonation-adjusted pitch",
            )

    def test_serial_framing_and_live_chord_patch_order(self) -> None:
        brass_index = synth_index("Brass Ensemble")
        other_index = synth_index("Orchestral Pad")
        brass_patch = patch_for_index(brass_index)
        other_patch = patch_for_index(other_index)

        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)

            # Real pyserial writes must be one complete AMY message per LF line.
            for line in app.bridge.lines_since(0):
                self.assertTrue(line.endswith("Z"), line)
                self.assertNotIn("\n", line)
                self.assertNotIn("\r", line)

            app.action("setChordSynthIndex", brass_index)
            app.bridge.wait_for_lines(
                [f"K{brass_patch}i3Z", f"K{brass_patch}i4Z"],
                start=0,
            )

            # Run actual rhythm chords before changing the sound.
            app.action("setRhythmChordActivity", 3.0)
            if not bool(app.query("rhythmRunning")):
                app.action("toggleRhythm")
            app.action("pressChord", 0, 0)
            app.action("releaseChord", 0, 0)
            app.bridge.wait_idle(timeout=8.0)

            switch_start = app.bridge.count()
            app.action("setChordSynthIndex", other_index)
            app.bridge.wait_for_lines(
                [f"K{other_patch}i3Z", f"K{other_patch}i4Z", "S4096Z"],
                start=switch_start,
                timeout=8.0,
            )
            app.bridge.wait_idle(timeout=8.0)
            lines = app.bridge.lines_since(switch_start)

            stop = lines.index("zY0Z")
            reset = lines.index("S4096Z")
            k3 = lines.index(f"K{other_patch}i3Z")
            k4 = lines.index(f"K{other_patch}i4Z")
            first_schedule = next(
                index for index, line in enumerate(lines) if line.startswith("H")
            )
            self.assertLess(stop, reset)
            self.assertLess(reset, k3)
            self.assertLess(k3, k4)
            self.assertLess(k4, first_schedule)

            # A live rhythm refresh must define chord events against the
            # dedicated rhythm chord synth 4, never manual synth 3.
            scheduled = [line for line in lines if line.startswith("H")]
            self.assertTrue(scheduled, "no sequencer events sent after switch")
            self.assertTrue(
                any("i4Z" in line for line in scheduled),
                "refreshed rhythm contains no synth-4 chord events",
            )

            # Once the new instrument switch begins, the old Brass patch may
            # not be reloaded into either chord synth by a stale host command.
            self.assertNotIn(f"K{brass_patch}i3Z", lines)
            self.assertNotIn(f"K{brass_patch}i4Z", lines)


if __name__ == "__main__":
    unittest.main()
