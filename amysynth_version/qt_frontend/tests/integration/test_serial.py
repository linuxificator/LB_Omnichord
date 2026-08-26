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
        rf"^H\d+,\d+,\d+n(?P<note>{_NOTE})l(?P<vel>{_NOTE})i{int(synth)}Z$"
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
                [f"K{meow_patch}i3Z", f"K{meow_patch}i4Z"],
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
                [f"K{other_patch}i3Z", f"K{other_patch}i4Z"],
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
                lines.index(f"K{other_patch}i4Z"),
            )

            # Once the new instrument switch begins, the old Brass patch may
            # not be reloaded into either chord synth by a stale host command.
            self.assertNotIn(f"K{brass_patch}i3Z", lines)
            self.assertNotIn(f"K{brass_patch}i4Z", lines)


    def test_cold_start_guards_synth4_and_reverb_zero_is_exact(self) -> None:
        with HeadlessApp(native_amy=False) as app:
            app.bridge.wait_idle(timeout=10.0)
            records = app.bridge.timed_lines()
            lines = [line for line, _ in records]

            # Four isolated buses: drums 0 are dry by default; bass/strum/chord
            # buses also start at user reverb level zero. Liveness/damping are
            # still defined at their neutral midpoint even while level is zero.
            for bus in range(4):
                self.assertIn(f"y{bus}h0,0.5,0.5Z", lines)
            self.assertFalse(any("h0.001" in line for line in lines))

            k4_index = next(
                i for i, line in enumerate(lines)
                if line.startswith("K") and "i4iv" in line and "iy3Z" in line
            )
            next_synth4_index = next(
                i for i in range(k4_index + 1, len(lines))
                if "i4" in lines[i]
            )
            elapsed = records[next_synth4_index][1] - records[k4_index][1]
            self.assertGreaterEqual(
                elapsed,
                0.008,
                f"synth 4 post-allocation command arrived after only {elapsed:.4f}s",
            )

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

            # First establish real bass/chord tagged patterns. The cancellation
            # assertion below is meaningful only for tags that were installed.
            seed = app.bridge.count()
            app.action("selectChord", 0, 0)
            deadline = time.monotonic() + 8.0
            while time.monotonic() < deadline:
                seeded = app.bridge.lines_since(seed)
                if (
                    any(line.startswith("H") and "i1Z" in line for line in seeded)
                    and any(line.startswith("H") and "i4Z" in line for line in seeded)
                ):
                    break
                time.sleep(0.01)
            else:
                self.fail("failed to seed bass and rhythm-chord tag ranges")
            time.sleep(0.75)  # allow one-shot chord release timer to drain
            app.bridge.wait_idle(timeout=8.0)

            start = app.bridge.count()
            app.action("pressChord", 0, 0)
            # The localhost API returns before the asynchronous UART writer has
            # necessarily emitted anything. Wait for the actual manual press,
            # then for the targeted chord-tag clears; an idle-age heuristic can
            # otherwise return while the output delta is still empty.
            app.bridge.wait_for_lines(["l0i3Z"], start=start, timeout=8.0)
            deadline = time.monotonic() + 8.0
            while time.monotonic() < deadline:
                delta = app.bridge.lines_since(start)
                cancellations = [
                    line for line in delta if line.startswith("H0,0,")
                ]
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

            # Finger-down closes the automatic-chord gate before synth 3 is
            # triggered.  l0 is AMY's ordinary velocity-zero note-off for all
            # active voices of synth 4, so the selected patch keeps its normal
            # release instead of an orphaned sequencer chord sustaining.
            self.assertIn("l0i4Z", delta)
            manual_note_pattern = re.compile(
                rf"^n{_NOTE}l(?P<vel>{_NOTE})i3Z$"
            )
            manual_note_indexes: list[int] = []
            for index, line in enumerate(delta):
                match = manual_note_pattern.match(line)
                if match and float(match.group("vel")) > 0.0:
                    manual_note_indexes.append(index)
            self.assertTrue(manual_note_indexes, delta)
            self.assertLess(delta.index("l0i4Z"), min(manual_note_indexes))
            self.assertNotIn("zY0Z", delta)
            self.assertFalse(any(line.startswith("S") for line in delta), delta)
            self.assertNotIn("zY1Z", delta)
            self.assertNotIn("l0i0Z", delta)
            self.assertNotIn("l0i1Z", delta)
            cancellations = [line for line in delta if line.startswith("H0,0,")]
            self.assertTrue(cancellations, delta)
            cancel_tags = {int(line.split(",", 2)[2][:-1]) for line in cancellations}
            self.assertTrue(all(112 <= tag < 252 for tag in cancel_tags), cancel_tags)
            self.assertFalse(
                any(
                    line.startswith("H0,0,")
                    and int(line.split(",", 2)[2][:-1]) < 56
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
                if any(line.startswith("H") and "i4Z" in line for line in release_delta):
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
            deadline = time.monotonic() + 8.0
            while time.monotonic() < deadline:
                seeded = app.bridge.lines_since(seed)
                if (
                    any(line.startswith("H") and "i1Z" in line for line in seeded)
                    and any(line.startswith("H") and "i4Z" in line for line in seeded)
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
                tags: set[int] = set()
                lines: list[str] = []
                while time.monotonic() < deadline:
                    lines = app.bridge.lines_since(start)
                    tags = {
                        int(line.split(",", 2)[2][:-1])
                        for line in lines
                        if line.startswith("H0,0,")
                        and 56 <= int(line.split(",", 2)[2][:-1]) < 112
                    }
                    if tags:
                        break
                    time.sleep(0.01)
                else:
                    self.fail(
                        "bass disable did not clear its tagged sequencer lane; received:\n"
                        + "\n".join(app.bridge.lines_since(start))
                    )
                app.bridge.wait_idle(timeout=8.0)
                lines = app.bridge.lines_since(start)
                self.assertTrue(all(56 <= tag < 112 for tag in tags), tags)
                self.assertNotIn("zY0Z", lines)
                self.assertNotIn("S4096Z", lines)

            app.action("setRhythmChordActivity", 0.0)
            app.bridge.wait_idle(timeout=8.0)
            start = app.bridge.count()
            app.action("setRhythmChordActivity", 3.0)
            deadline = time.monotonic() + 8.0
            while time.monotonic() < deadline:
                lines = app.bridge.lines_since(start)
                if any(line.startswith("H") and "i4Z" in line for line in lines):
                    break
                time.sleep(0.01)
            else:
                self.fail("chord lane was not reinstalled")
            chord_tags = []
            for line in lines:
                if not line.startswith("H") or "i4Z" not in line:
                    continue
                header = line[1:].split("i", 1)[0]
                parts = header.split(",", 3)
                if len(parts) >= 3:
                    tag_text = re.match(r"(\d+)", parts[2])
                    if tag_text:
                        chord_tags.append(int(tag_text.group(1)))
            self.assertTrue(chord_tags, lines)
            self.assertTrue(all(112 <= tag < 252 for tag in chord_tags), chord_tags)


if __name__ == "__main__":
    unittest.main()
