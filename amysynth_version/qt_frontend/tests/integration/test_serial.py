from __future__ import annotations

import re
import time
import unittest

from catalog import control_default, patch_for_index, synth_index
from harness import HeadlessApp


_NOTE = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)"
CHORD_SEQUENCE_START = 1192
DRUM_BASE_SEQUENCE_START = 1256


def wire_float(value: float) -> str:
    return f"{float(value):.9g}"


def scheduled_note_ons(lines: list[str], synth: int) -> list[float]:
    direct_pattern = re.compile(
        rf"^H\d+,\d+n(?P<note>{_NOTE})l(?P<vel>{_NOTE})i{int(synth)}Z$"
    )
    definition_pattern = re.compile(
        rf"^H\d+,\d+,(?P<sequence>\d+)"
        rf"n(?P<note>{_NOTE})l(?P<vel>{_NOTE})i{int(synth)}Z$"
    )
    trigger_pattern = re.compile(
        r"^H\d+,\d+,\d+HC(?P<sequence>\d+),1,1Z$"
    )
    definitions: dict[int, list[float]] = {}
    notes: list[float] = []
    for line in lines:
        match = direct_pattern.match(line)
        if match and float(match.group("vel")) > 0.0:
            notes.append(float(match.group("note")))
            continue
        match = definition_pattern.match(line)
        if match and float(match.group("vel")) > 0.0:
            sequence = int(match.group("sequence"))
            note = float(match.group("note"))
            definitions.setdefault(sequence, []).append(note)
            # Bass notes live directly in the reusable root sequence. Chord
            # notes live in finite child sequences and are counted when their
            # root trigger is encountered below.
            if int(synth) == 1 and 56 <= sequence < 112:
                notes.append(note)
        match = trigger_pattern.match(line)
        if match:
            notes.extend(definitions.get(int(match.group("sequence")), []))
    return notes


def chord_trigger(line: str) -> tuple[int, int] | None:
    match = re.match(
        r"^H\d+,\d+,(?P<tag>\d+)HC(?P<sequence>\d+),1,1Z$",
        line,
    )
    if match is None:
        return None
    tag = int(match.group("tag"))
    sequence_tag = int(match.group("sequence"))
    if not 112 <= tag < 252:
        return None
    if not CHORD_SEQUENCE_START <= sequence_tag < DRUM_BASE_SEQUENCE_START:
        return None
    return tag, sequence_tag


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
    def test_drum_library_is_preloaded_once_and_controls_send_only_deltas(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=12.0)
            startup = app.bridge.lines_since(0)
            self.assertIn("HR256Z", startup)
            self.assertTrue(
                "HR525Z" in startup,
                "last fill definition was not preloaded",
            )
            self.assertEqual(
                sum(
                    (match := re.match(r"^HR(\d+)Z$", line)) is not None
                    and 256 <= int(match.group(1)) < 1192
                    for line in startup
                ),
                270,
            )

            fill_start = app.bridge.count()
            app.action("toggleRhythmFill", 0)
            app.bridge.wait_for_line_match(
                lambda line: re.match(r"^H\d", line) is not None and "HC" in line,
                "updated fill root schedule",
                start=fill_start,
                timeout=8.0,
            )
            app.bridge.wait_idle(timeout=8.0)
            fill_lines = app.bridge.lines_since(fill_start)
            self.assertTrue(
                any(re.match(r"^H\d", line) and "HC" in line for line in fill_lines)
            )
            self.assertFalse(
                any(
                    (match := re.match(r"^H\d+,\d+,(\d+)", line)) is not None
                    and 256 <= int(match.group(1)) < 1192
                    for line in fill_lines
                ),
                "fill selection resent its stored event block",
            )

            activity_start = app.bridge.count()
            app.action("setRhythmBusyness", 5.0)
            app.bridge.wait_for_line_match(
                lambda line: line.startswith("HR125"),
                "replacement base-drum sequence definition",
                start=activity_start,
                timeout=8.0,
            )
            app.bridge.wait_idle(timeout=8.0)
            activity_lines = app.bridge.lines_since(activity_start)
            self.assertTrue(
                any(line.startswith("HR125") for line in activity_lines)
            )
            self.assertTrue(
                any(
                    (match := re.match(r"^H\d+,\d+,(\d+)", line)) is not None
                    and 1256 <= int(match.group(1)) < 1280
                    for line in activity_lines
                )
            )
            self.assertFalse(
                any(
                    (match := re.match(r"^HR(\d+)Z$", line)) is not None
                    and 256 <= int(match.group(1)) < 1192
                    for line in activity_lines
                ),
                "activity change rebuilt a preloaded fill",
            )

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
            app.action("toggleChordGate")
            app.bridge.wait_idle(timeout=8.0)

            start = app.bridge.count()
            if not bool(app.query("rhythmRunning")):
                app.action("toggleRhythm")
            app.bridge.wait_for_lines(["zY1Z"], start=start, timeout=8.0)
            app.bridge.wait_idle(timeout=8.0)
            lines = app.bridge.lines_since(start)
            self.assertNotIn(native_cutoff4, lines)
            self.assertNotIn(f"K{chorus_patch}i4if8Z", lines)
            self.assertTrue(
                any(chord_trigger(line) is not None for line in lines),
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
            self.assertNotIn(f"K{chorus_patch}i4if8Z", edit_lines)

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
            app.action("toggleChordGate")
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
            deadline = time.monotonic() + 8.0
            while time.monotonic() < deadline:
                harm_lines = app.bridge.lines_since(harm_start)
                if scheduled_note_ons(harm_lines, 1) and scheduled_note_ons(harm_lines, 4):
                    break
                time.sleep(0.01)
            else:
                self.fail("HARM tuning change did not replace bass/chord tagged events")
            app.bridge.wait_idle(timeout=8.0)
            harm_lines = app.bridge.lines_since(harm_start)
            self.assertNotIn("zY0Z", harm_lines)
            self.assertNotIn("S4096Z", harm_lines)
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

    def test_riff_selector_replaces_only_bass_and_live_transposition_keeps_timing(
        self,
    ) -> None:
        riff_pattern = re.compile(
            rf"^H(?P<tick>\d+),(?P<period>\d+),(?P<tag>\d+)"
            rf"n(?P<note>{_NOTE})l(?P<velocity>{_NOTE})i1Z$"
        )

        def riff_note_ons(
            lines: list[str],
        ) -> list[tuple[int, int, int, float, float]]:
            events = []
            for line in lines:
                match = riff_pattern.match(line)
                if match is None or float(match.group("velocity")) <= 0.0:
                    continue
                events.append((
                    int(match.group("tick")),
                    int(match.group("period")),
                    int(match.group("tag")),
                    float(match.group("note")),
                    float(match.group("velocity")),
                ))
            return events

        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)
            app.action("setRhythmIndex", 0)  # pop_8
            app.action("setTuningModeIndex", 1)  # EQ
            app.action("setRowChordType", 0, 0)  # major
            app.action("selectChord", 0, 0)  # C
            app.action("setRhythmBassActivity", 5.0)
            if not bool(app.query("bassRunning")):
                app.action("toggleBassRunning")
            start = app.bridge.count()
            app.action("toggleRhythm")
            app.bridge.wait_for_lines(["zY1Z"], start=start, timeout=8.0)
            app.bridge.wait_idle(timeout=8.0)

            selector_start = app.bridge.count()
            app.action("setBassRiffSelector", 4.0)
            deadline = time.monotonic() + 8.0
            while time.monotonic() < deadline:
                c_lines = app.bridge.lines_since(selector_start)
                c_events = riff_note_ons(c_lines)
                if len(c_events) >= 8:
                    break
                time.sleep(0.01)
            else:
                self.fail("riff selector did not install its own bass phrase")
            app.bridge.wait_idle(timeout=8.0)
            c_lines = app.bridge.lines_since(selector_start)
            c_events = riff_note_ons(c_lines)
            self.assertEqual(
                [event[3] for event in c_events],
                [36.0, 43.0, 48.0, 43.0, 36.0, 31.0, 36.0, 43.0],
            )
            self.assertTrue(c_events)
            for _tick, _period, tag, _note, _velocity in c_events:
                self.assertGreaterEqual(tag, 56)
                self.assertLess(tag, 112)
            self.assertNotIn("zY0Z", c_lines)
            self.assertNotIn("S4096Z", c_lines)

            transpose_start = app.bridge.count()
            app.action("selectChord", 0, 4)  # E major
            deadline = time.monotonic() + 8.0
            while time.monotonic() < deadline:
                e_lines = app.bridge.lines_since(transpose_start)
                e_events = riff_note_ons(e_lines)
                if len(e_events) >= 8:
                    break
                time.sleep(0.01)
            else:
                self.fail("chord change did not transpose the active riff")
            app.bridge.wait_idle(timeout=8.0)
            e_events = riff_note_ons(app.bridge.lines_since(transpose_start))
            self.assertEqual(
                [event[3] for event in e_events],
                [40.0, 47.0, 52.0, 47.0, 40.0, 35.0, 40.0, 47.0],
            )
            self.assertEqual(
                [
                    (tick, period, tag, velocity)
                    for tick, period, tag, _, velocity in c_events
                ],
                [
                    (tick, period, tag, velocity)
                    for tick, period, tag, _, velocity in e_events
                ],
            )
            self.assertEqual(
                str(app.query("selectedBassRiffId")),
                "riff_0004_pop_8_root_fifth",
            )

    def test_chord_arpeggio_uses_all_notes_and_only_the_chord_lane(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=8.0)
            startup_lines = app.bridge.lines_since(0)
            self.assertTrue(
                any("i4iv7iy3if8Z" in line for line in startup_lines)
            )
            self.assertFalse(
                any("i3" in line and "if8" in line for line in startup_lines)
            )
            app.action("setRhythmIndex", 0)  # pop_8
            app.action("setTuningModeIndex", 1)  # EQ
            app.action("setRowChordType", 0, 27)  # dominant13, seven notes
            app.action("selectChord", 0, 0)  # C3
            app.action("setRhythmChordActivity", 1.0)
            if int(app.query("chordGateState")) != 1:
                app.action("toggleChordGate")
            app.bridge.wait_idle(timeout=8.0)

            arpeggio_start = app.bridge.count()
            app.action("toggleChordArpeggio")
            app.bridge.wait_for_line_match(
                lambda line: chord_trigger(line) is not None,
                "ascending arpeggio chord tags",
                start=arpeggio_start,
                timeout=8.0,
            )
            app.bridge.wait_idle(timeout=8.0)
            arpeggio_lines = app.bridge.lines_since(arpeggio_start)
            self.assertEqual(
                scheduled_note_ons(arpeggio_lines, 4),
                [48.0, 52.0, 55.0, 58.0, 62.0, 65.0, 69.0],
            )
            for line in arpeggio_lines:
                trigger = chord_trigger(line)
                if trigger is None:
                    continue
                tag, _ = trigger
                self.assertGreaterEqual(tag, 112)
                self.assertLess(tag, 252)
            self.assertFalse(
                any(
                    line.startswith("H")
                    and ("i0Z" in line or "i1Z" in line)
                    for line in arpeggio_lines
                )
            )
            self.assertNotIn("zY0Z", arpeggio_lines)
            self.assertNotIn("zY1Z", arpeggio_lines)
            self.assertNotIn("S16384Z", arpeggio_lines)
            self.assertNotIn("S20480Z", arpeggio_lines)

            direction_start = app.bridge.count()
            app.action("toggleChordArpeggioDirection")
            app.bridge.wait_for_line_match(
                lambda line: chord_trigger(line) is not None,
                "descending arpeggio chord tags",
                start=direction_start,
                timeout=8.0,
            )
            app.bridge.wait_idle(timeout=8.0)
            self.assertEqual(
                scheduled_note_ons(app.bridge.lines_since(direction_start), 4),
                [69.0, 65.0, 62.0, 58.0, 55.0, 52.0, 48.0],
            )

            whole_chord_start = app.bridge.count()
            app.action("toggleChordArpeggio")
            app.bridge.wait_for_line_match(
                lambda line: chord_trigger(line) is not None,
                "whole-chord tags after arpeggio off",
                start=whole_chord_start,
                timeout=8.0,
            )
            app.bridge.wait_idle(timeout=8.0)
            self.assertEqual(
                sorted(set(scheduled_note_ons(
                    app.bridge.lines_since(whole_chord_start), 4
                ))),
                [48.0, 52.0, 55.0, 58.0],
            )

            inactive_start = app.bridge.count()
            app.action("setChordArpeggioRate", 2.0)
            app.action("toggleChordArpeggioDirection")
            time.sleep(0.05)
            self.assertFalse(
                any(
                    line.startswith("H")
                    for line in app.bridge.lines_since(inactive_start)
                ),
                "inactive lower-row controls changed the chord schedule",
            )

    def test_strum_patch_change_is_bus_isolated_from_chords(self) -> None:
        meow = synth_index("Meow Brass")
        sustainer = synth_index("Sustainer")
        other = synth_index("Orchestral Pad")
        meow_patch = patch_for_index(meow)
        sustainer_patch = patch_for_index(sustainer)
        other_patch = patch_for_index(other)

        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=10.0)
            app.action("setChordSynthIndex", meow)
            app.bridge.wait_for_lines(
                [f"K{meow_patch}i3Z", f"K{meow_patch}i4if8Z"],
                start=0,
                timeout=8.0,
            )
            app.action("setStrumSynthIndex", sustainer)
            app.bridge.wait_for_lines([f"K{sustainer_patch}i2Z"], start=0, timeout=8.0)
            app.bridge.wait_idle(timeout=8.0)

            start = app.bridge.count()
            app.action("setStrumSynthIndex", other)
            lines = app.bridge.wait_for_lines([f"K{other_patch}i2Z"], start=start, timeout=8.0)
            app.bridge.wait_idle(timeout=8.0)
            lines = app.bridge.lines_since(start)

            self.assertIn("i2iy2Z", lines)
            self.assertTrue(any(line.startswith("y2h") for line in lines), lines)
            self.assertFalse(any("i3" in line or "i4" in line for line in lines), lines)
            self.assertFalse(any(line.startswith("y3") for line in lines), lines)

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
                [f"K{brass_patch}i3Z", f"K{brass_patch}i4if8Z"],
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
                [f"K{other_patch}i3Z", f"K{other_patch}i4if8Z"],
                start=switch_start,
                timeout=8.0,
            )
            app.bridge.wait_idle(timeout=8.0)
            lines = app.bridge.lines_since(switch_start)

            self.assertNotIn("zY0Z", lines)
            self.assertNotIn("S4096Z", lines)
            self.assertNotIn("zY1Z", lines)
            self.assertLess(
                lines.index(f"K{other_patch}i3Z"),
                lines.index(f"K{other_patch}i4if8Z"),
            )

            # Once the new instrument switch begins, the old Brass patch may
            # not be reloaded into either chord synth by a stale host command.
            self.assertNotIn(f"K{brass_patch}i3Z", lines)
            self.assertNotIn(f"K{brass_patch}i4if8Z", lines)


    def test_cold_start_guards_synth4_and_reverb_zero_is_exact(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=10.0)
            lines = app.bridge.lines_since(0)

            # Four isolated buses: drums 0 are dry by default; bass/strum/chord
            # buses also start at user reverb level zero. Liveness/damping are
            # still defined at their neutral midpoint even while level is zero.
            for bus in range(4):
                self.assertIn(f"y{bus}h0,0.5,0.5Z", lines)
            self.assertFalse(any("h0.001" in line for line in lines))

            # The PTY may coalesce writes that were physically separated by a
            # scheduler delay when its reader thread is descheduled. Verify
            # the application's ordered transport decisions here; the
            # scheduler unit test measures the actual sink-write separation.
            allocation = next(
                line
                for line in lines
                if line.startswith("K")
                and "i4iv" in line
                and "iy3if8Z" in line
            )
            routed = "i4iy3Z"
            transport_log = app.wait_for_frontend_log(
                f"TX-HIGH      {routed}",
                timeout=5.0,
            )
            allocation_offset = transport_log.index(
                f"TX-HIGH      {allocation}"
            )
            guard_offset = transport_log.index(
                "GUARD        sleep 10.0 ms",
                allocation_offset,
            )
            routed_offset = transport_log.index(
                f"TX-HIGH      {routed}",
                allocation_offset,
            )
            self.assertLess(allocation_offset, guard_offset)
            self.assertLess(guard_offset, routed_offset)

            # User reverb applies to bass/strum/chords, never drums unless DRM
            # is explicitly enabled.
            start = app.bridge.count()
            app.action("setReverbLevel", 0.4)
            app.bridge.wait_for_lines(
                [
                    "y0h0,0.5,0.5Z",
                    "y1h0.4,0.5,0.5Z",
                    "y2h0.4,0.5,0.5Z",
                    "y3h0.4,0.5,0.5Z",
                ],
                start=start,
                timeout=5.0,
            )
            self.assertFalse(bool(app.query("reverbDrumsIncluded")))

            start = app.bridge.count()
            app.action("toggleReverbDrums")
            app.bridge.wait_for_lines(
                ["y0h0.4,0.5,0.5Z"], start=start, timeout=5.0
            )
            self.assertTrue(bool(app.query("reverbDrumsIncluded")))

            # Level zero is exact on every bus, including drums when DRM is on.
            start = app.bridge.count()
            app.action("setReverbLevel", 0.0)
            app.bridge.wait_for_lines(
                [
                    "y0h0,0.5,0.5Z",
                    "y1h0,0.5,0.5Z",
                    "y2h0,0.5,0.5Z",
                    "y3h0,0.5,0.5Z",
                ],
                start=start,
                timeout=5.0,
            )
            self.assertEqual(float(app.query("reverbLevel")), 0.0)

    def test_long_manual_chord_hold_only_edits_chord_tag_range(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=10.0)
            if not bool(app.query("rhythmRunning")):
                start = app.bridge.count()
                app.action("toggleRhythm")
                app.bridge.wait_for_lines(["zY1Z"], start=start, timeout=8.0)
                app.bridge.wait_idle(timeout=8.0)

            # First establish real bass/chord root events. The cancellation
            # assertion below is meaningful only for tags that were installed.
            seed = app.bridge.count()
            app.action("selectChord", 0, 0)
            app.action("toggleChordGate")
            if not bool(app.query("chordArpeggioEnabled")):
                app.action("toggleChordArpeggio")
            app.action("setChordArpeggioRate", 2.0)
            deadline = time.monotonic() + 8.0
            while time.monotonic() < deadline:
                seeded = app.bridge.lines_since(seed)
                if (
                    any(line.startswith("H") and "i1Z" in line for line in seeded)
                    and any(chord_trigger(line) is not None for line in seeded)
                ):
                    break
                time.sleep(0.01)
            else:
                self.fail("failed to seed bass and rhythm-chord tag ranges")
            time.sleep(0.75)  # allow one-shot chord release timer to drain
            app.bridge.wait_idle(timeout=8.0)
            seeded = app.bridge.lines_since(seed)
            chord_trigger_tags = {
                trigger[0]
                for line in seeded
                if (trigger := chord_trigger(line)) is not None
            }
            self.assertTrue(chord_trigger_tags, seeded)

            start = app.bridge.count()
            app.action("pressChord", 0, 0)
            app.action("promoteChordHold", 0, 0)
            # The localhost API returns before the asynchronous UART writer has
            # necessarily emitted anything. Wait for the actual manual press,
            # then for the targeted chord-sequence reset; an idle-age heuristic can
            # otherwise return while the output delta is still empty.
            app.bridge.wait_for_lines(["l0i3Z"], start=start, timeout=8.0)
            deadline = time.monotonic() + 8.0
            while time.monotonic() < deadline:
                delta = app.bridge.lines_since(start)
                cancellations = [line for line in delta if line == "HR112Z"]
                if cancellations:
                    break
                time.sleep(0.01)
            else:
                self.fail(
                    "manual chord hold did not clear the automatic-chord tag range; "
                    "received:\n" + "\n".join(app.bridge.lines_since(start))
                )
            app.bridge.wait_idle(timeout=8.0)
            delta = app.bridge.lines_since(start)

            # Finger-down starts synth 3 immediately. Promotion removes only
            # future child triggers. A child which already fired owns its
            # immutable note-off, so no root release tag needs retaining and
            # no immediate synth-4 all-off is allowed.
            self.assertNotIn("l0i4Z", delta)
            manual_note_pattern = re.compile(
                rf"^n{_NOTE}l(?P<vel>{_NOTE})i3Z$"
            )
            manual_note_indexes: list[int] = []
            for index, line in enumerate(delta):
                match = manual_note_pattern.match(line)
                if match and float(match.group("vel")) > 0.0:
                    manual_note_indexes.append(index)
            self.assertTrue(manual_note_indexes, delta)
            self.assertNotIn("zY0Z", delta)
            self.assertFalse(any(line.startswith("S") for line in delta), delta)
            self.assertNotIn("zY1Z", delta)
            self.assertNotIn("l0i0Z", delta)
            self.assertNotIn("l0i1Z", delta)
            cancellations = [line for line in delta if line == "HR112Z"]
            self.assertTrue(cancellations, delta)
            cancel_tags = {int(line[2:-1]) for line in cancellations}
            self.assertTrue(all(112 <= tag < 252 for tag in cancel_tags), cancel_tags)
            self.assertTrue(
                chord_trigger_tags <= cancel_tags,
                (chord_trigger_tags, cancel_tags),
            )
            self.assertFalse(
                any(
                    (match := re.match(r"^HR(\d+)Z$", line)) is not None
                    and int(match.group(1)) < 56
                    for line in delta
                ),
                delta,
            )
            self.assertTrue(bool(app.query("rhythmRunning")))

            time.sleep(1.0)
            self.assertTrue(bool(app.query("rhythmRunning")))

            release_start = app.bridge.count()
            app.action("releaseChord", 0, 0)
            deadline = time.monotonic() + 8.0
            while time.monotonic() < deadline:
                release_delta = app.bridge.lines_since(release_start)
                if any(
                    chord_trigger(line) is not None
                    for line in release_delta
                ):
                    break
                time.sleep(0.01)
            else:
                self.fail("release did not reinstall tagged rhythm chords")
            release_delta = app.bridge.lines_since(release_start)
            self.assertNotIn("zY0Z", release_delta)
            self.assertNotIn("S4096Z", release_delta)
            self.assertNotIn("zY1Z", release_delta)
            self.assertFalse(any("i0Z" in line for line in release_delta if line.startswith("H")))
            self.assertFalse(any("i1Z" in line for line in release_delta if line.startswith("H")))
            self.assertTrue(bool(app.query("rhythmRunning")))

    def test_arpeggio_rate_switch_keeps_running_note_gate_owned_by_old_rate(
        self,
    ) -> None:
        """Rate changes replace future data without truncating old releases."""
        reset_sequence = re.compile(r"^HR(?P<sequence>\d+)Z$")
        off_pattern = re.compile(
            rf"^H(?P<tick>\d+),0,(?P<sequence>\d+)"
            rf"n(?P<note>{_NOTE})l0i4Z$"
        )

        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=10.0)
            app.action("setRhythmIndex", 0)
            app.action("setTuningModeIndex", 1)
            app.action("setRowChordType", 0, 27)
            app.action("selectChord", 0, 0)
            app.action("setRhythmChordActivity", 4.0)
            if int(app.query("chordGateState")) != 1:
                app.action("toggleChordGate")
            if not bool(app.query("chordArpeggioEnabled")):
                app.action("toggleChordArpeggio")
            if not bool(app.query("rhythmRunning")):
                app.action("toggleRhythm")
            app.action("setChordArpeggioRate", 1.0)
            app.bridge.wait_idle(timeout=10.0)

            rate2_start = app.bridge.count()
            app.action("setChordArpeggioRate", 2.0)
            app.bridge.wait_for_line_match(
                lambda line: chord_trigger(line) is not None,
                "/2 child triggers",
                start=rate2_start,
                timeout=8.0,
            )
            app.bridge.wait_idle(timeout=10.0)
            rate2_lines = app.bridge.lines_since(rate2_start)
            rate2_sequences = {
                int(match.group("sequence"))
                for line in rate2_lines
                if (match := reset_sequence.match(line)) is not None
                and CHORD_SEQUENCE_START <= int(match.group("sequence")) < DRUM_BASE_SEQUENCE_START
            }
            rate2_offs = {
                (int(match.group("sequence")), int(match.group("tick"))): float(
                    match.group("note")
                )
                for line in rate2_lines
                if (match := off_pattern.match(line)) is not None
            }
            rate2_triggers = {
                trigger[1]
                for line in rate2_lines
                if (trigger := chord_trigger(line)) is not None
            }
            self.assertEqual(rate2_sequences, rate2_triggers)
            self.assertTrue(
                all(tag in rate2_sequences for tag, _tick in rate2_offs)
            )
            self.assertIn((1192, 161), rate2_offs)
            self.assertGreaterEqual(len(set(rate2_offs.values())), 7)

            rate4_start = app.bridge.count()
            app.action("setChordArpeggioRate", 4.0)
            app.bridge.wait_for_line_match(
                lambda line: chord_trigger(line) is not None,
                "/4 child triggers",
                start=rate4_start,
                timeout=8.0,
            )
            app.bridge.wait_idle(timeout=10.0)
            rate4_lines = app.bridge.lines_since(rate4_start)
            rate4_sequences = {
                int(match.group("sequence"))
                for line in rate4_lines
                if (match := reset_sequence.match(line)) is not None
                and CHORD_SEQUENCE_START <= int(match.group("sequence")) < DRUM_BASE_SEQUENCE_START
            }
            rate4_offs = {
                (int(match.group("sequence")), int(match.group("tick"))): float(
                    match.group("note")
                )
                for line in rate4_lines
                if (match := off_pattern.match(line)) is not None
            }
            rate4_triggers = {
                trigger[1]
                for line in rate4_lines
                if (trigger := chord_trigger(line)) is not None
            }
            self.assertEqual(rate4_sequences, rate4_triggers)
            self.assertTrue(
                all(tag in rate4_sequences for tag, _tick in rate4_offs)
            )
            self.assertIn((1192, 81), rate4_offs)
            # Sequence identity is stable. AMY's immutable definitions, covered by
            # its native tests, let already-running /2 notes retain releases.
            self.assertEqual(rate2_sequences, rate4_sequences)
            self.assertNotIn("l0i4Z", rate4_lines)
            self.assertNotIn("zY0Z", rate4_lines)
            self.assertNotIn("zY1Z", rate4_lines)
            self.assertFalse(any(line.startswith("S") for line in rate4_lines))

    def test_quick_chord_tap_never_drains_automatic_chord_lane(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=10.0)
            app.action("selectChord", 0, 0)
            if int(app.query("chordGateState")) != 1:
                app.action("toggleChordGate")
            if not bool(app.query("rhythmRunning")):
                app.action("toggleRhythm")
            app.bridge.wait_idle(timeout=8.0)

            start = app.bridge.count()
            # Use a different chord from the seeded accompaniment: a tap must
            # replace the pitches while leaving the lane continuously enabled.
            app.action("pressChord", 1, 9)
            app.action("releaseChord", 1, 9)
            app.bridge.wait_idle(timeout=8.0)
            delta = app.bridge.lines_since(start)

            self.assertTrue(immediate_note_ons(delta, 3), delta)
            self.assertGreaterEqual(delta.count("l0i3Z"), 2, delta)
            self.assertTrue(any(line.startswith("H") for line in delta), delta)
            self.assertIn("HR112Z", delta)
            self.assertTrue(
                any(re.match(r"^HC112,1,\d+Z$", line) for line in delta),
                delta,
            )
            self.assertNotIn("zY0Z", delta)
            self.assertNotIn("zY1Z", delta)
            self.assertEqual(int(app.query("activeRowIndex")), 1)
            self.assertEqual(int(app.query("activeRootSemitone")), 9)
            self.assertGreater(int(app.query("rhythmChordActivity")), 0)
            self.assertTrue(bool(app.query("rhythmRunning")))

    def test_stopping_rhythm_releases_sounding_accompaniment(self) -> None:
        """Stopping mid-pattern must not strand a synth-4 chord or bass note."""
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=10.0)
            app.action("setRhythmChordActivity", 4.0)
            app.action("setRhythmBassActivity", 4.0)
            if not bool(app.query("bassRunning")):
                app.action("toggleBassRunning")

            # Establish an active pitch state and let any one-shot manual chord
            # release drain before the stop checkpoint.
            app.action("selectChord", 0, 0)
            app.action("toggleChordGate")
            time.sleep(0.75)
            app.bridge.wait_idle(timeout=8.0)

            if not bool(app.query("rhythmRunning")):
                start = app.bridge.count()
                app.action("toggleRhythm")
                app.bridge.wait_for_lines(["zY1Z"], start=start, timeout=8.0)
            self.assertTrue(bool(app.query("rhythmRunning")))

            # The regression is the action call itself: the old implementation
            # raised AttributeError after zY0 because _silence_accompaniment was
            # missing, so the frontend never emitted rhythmStateChanged.
            stop_start = app.bridge.count()
            app.action("toggleRhythm")
            lines = app.bridge.wait_for_lines(
                ["zY0Z", "l0i0Z", "l0i1Z", "l0i4Z"],
                start=stop_start,
                timeout=8.0,
            )
            app.bridge.wait_idle(timeout=8.0)
            lines = app.bridge.lines_since(stop_start)

            self.assertFalse(bool(app.query("rhythmRunning")))
            self.assertLess(lines.index("zY0Z"), lines.index("l0i4Z"))
            self.assertLess(lines.index("zY0Z"), lines.index("l0i1Z"))
            self.assertNotIn(
                "l0i3Z",
                lines,
                "stopping rhythm must not release a manually held chord",
            )

    def test_tag_ranges_are_disjoint_and_lane_updates_do_not_cross(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=10.0)
            if not bool(app.query("rhythmRunning")):
                start = app.bridge.count()
                app.action("toggleRhythm")
                app.bridge.wait_for_lines(["zY1Z"], start=start, timeout=8.0)
                app.bridge.wait_idle(timeout=8.0)

            seed = app.bridge.count()
            app.action("selectChord", 0, 0)
            app.action("toggleChordGate")
            deadline = time.monotonic() + 8.0
            while time.monotonic() < deadline:
                seeded = app.bridge.lines_since(seed)
                if (
                    any(line.startswith("H") and "i1Z" in line for line in seeded)
                    and any(chord_trigger(line) is not None for line in seeded)
                ):
                    break
                time.sleep(0.01)
            else:
                self.fail("failed to seed tag ranges before isolation test")
            time.sleep(0.75)
            app.bridge.wait_idle(timeout=8.0)

            if bool(app.query("bassRunning")):
                start = app.bridge.count()
                app.action("toggleBassRunning")
                deadline = time.monotonic() + 8.0
                lines: list[str] = []
                while time.monotonic() < deadline:
                    lines = app.bridge.lines_since(start)
                    if "HC56,0,0Z" in lines and "HR56Z" in lines:
                        break
                    time.sleep(0.01)
                else:
                    self.fail(
                        "bass disable did not clear its tagged sequencer lane; received:\n"
                        + "\n".join(app.bridge.lines_since(start))
                    )
                app.bridge.wait_idle(timeout=8.0)
                lines = app.bridge.lines_since(start)
                self.assertFalse(
                    any(
                        (match := re.match(r"^HR(\d+)Z$", line)) is not None
                        and not 56 <= int(match.group(1)) < 112
                        for line in lines
                    ),
                    lines,
                )
                self.assertNotIn("zY0Z", lines)
                self.assertNotIn("S4096Z", lines)

            self.assertEqual(int(app.query("chordGateState")), 1)
            app.action("toggleChordGate")
            app.bridge.wait_idle(timeout=8.0)
            self.assertEqual(int(app.query("chordGateState")), 2)
            start = app.bridge.count()
            app.action("toggleChordGate")
            deadline = time.monotonic() + 8.0
            while time.monotonic() < deadline:
                lines = app.bridge.lines_since(start)
                if any(chord_trigger(line) is not None for line in lines):
                    break
                time.sleep(0.01)
            else:
                self.fail("chord lane was not reinstalled")
            self.assertEqual(int(app.query("chordGateState")), 1)
            chord_tags: list[int] = []
            for line in lines:
                trigger = chord_trigger(line)
                if trigger is not None:
                    chord_tags.append(trigger[0])
            self.assertTrue(chord_tags, lines)
            self.assertTrue(all(112 <= tag < 252 for tag in chord_tags), chord_tags)


if __name__ == "__main__":
    unittest.main()
