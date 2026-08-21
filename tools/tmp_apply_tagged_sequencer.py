#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "amysynth_version" / "qt_frontend"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one occurrence, found {count}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_regex(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    new, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"{path}: regex did not match exactly once: {pattern[:120]!r}")
    path.write_text(new, encoding="utf-8")


# ---------------------------------------------------------------------------
# Config: reserve non-overlapping AMY user tag ranges sized from the complete
# rhythm catalogue audit. Current AMY defaults to max_sequencer_tags=256.
# ---------------------------------------------------------------------------
cfg_path = F / "config" / "amy_config.json"
cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
rhythm_cfg = cfg.setdefault("rhythm", {})
rhythm_cfg["max_sequencer_tags"] = 256
rhythm_cfg["tag_ranges"] = {
    "drums": {"start": 0, "count": 56},
    "bass": {"start": 56, "count": 56},
    "chords": {"start": 112, "count": 140},
}
# The old item budget described anonymous entries. Tagged lanes are bounded by
# their configured ranges instead.
rhythm_cfg.pop("max_sequencer_items", None)
cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


amy = F / "code" / "amy_serial.py"

# ---------------------------------------------------------------------------
# Writer: low-priority traffic is generation-cancelled PER LANE. A chord edit
# can therefore invalidate queued chord definitions without discarding bass or
# drum definitions. High-priority performance commands still preempt all low
# sequencer traffic.
# ---------------------------------------------------------------------------
writer_block = r'''class _SerialWriter:
    """Priority UART writer with independently cancelable low-priority lanes."""

    def __init__(self, port: str, baud: int, write_timeout: float, debug_log: _DebugLog | None = None) -> None:
        from collections import deque

        self.debug_log = debug_log
        self.serial = serial.Serial(
            port=port,
            baudrate=int(baud),
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0,
            write_timeout=float(write_timeout),
        )
        self._high = deque()
        self._low = deque()
        self._lane_generation: dict[str, int] = {}
        self._closed = False
        self._condition = threading.Condition()
        self._thread = threading.Thread(
            target=self._run,
            name="amy-uart-writer",
            daemon=True,
        )
        self._thread.start()

    @staticmethod
    def _line(command: str) -> bytes:
        command = command.strip()
        if not command.endswith("Z"):
            command += "Z"
        return (command + "\n").encode("ascii")

    def new_low_generation(self, lane: str) -> int:
        lane = str(lane)
        with self._condition:
            generation = self._lane_generation.get(lane, 0) + 1
            self._lane_generation[lane] = generation
            self._condition.notify_all()
            return generation

    def invalidate_all_low(self) -> None:
        with self._condition:
            for lane in list(self._lane_generation):
                self._lane_generation[lane] += 1
            self._low.clear()
            self._condition.notify_all()

    def high(self, command: str) -> None:
        with self._condition:
            if self._closed:
                return
            self._high.append(("command", command, 0.0))
            self._condition.notify()

    def delay(self, delay_seconds: float) -> None:
        """Insert a host-side guard before later high-priority commands."""
        with self._condition:
            if self._closed:
                return
            self._high.append((
                "delay",
                None,
                max(0.0, float(delay_seconds)),
            ))
            self._condition.notify()

    def low(self, lane: str, generation: int, command: str) -> None:
        with self._condition:
            if self._closed:
                return
            self._low.append((str(lane), int(generation), command))
            self._condition.notify()

    def _write(self, command: str, lane: str) -> None:
        if self.debug_log is not None:
            self.debug_log.write(f"TX-{lane}", command.strip())
        self.serial.write(self._line(command))

    def _run(self) -> None:
        while True:
            item_kind: str | None = None
            command: str | None = None
            delay_seconds = 0.0
            output_lane = "HIGH"

            with self._condition:
                while True:
                    if self._closed and not self._high and not self._low:
                        return

                    if self._high:
                        item_kind, command, delay_seconds = self._high.popleft()
                        break

                    # Drop stale lane generations without touching UART. This
                    # scan is intentionally cheap: there are only three rhythm
                    # lanes plus the occasional full-rhythm transaction lane.
                    while self._low:
                        low_lane, generation, low_command = self._low.popleft()
                        if generation != self._lane_generation.get(low_lane, 0):
                            continue
                        item_kind = "command"
                        command = low_command
                        output_lane = "LOW"
                        break

                    if item_kind is not None:
                        break

                    self._condition.wait()

            if item_kind == "delay":
                if self.debug_log is not None:
                    self.debug_log.write(
                        "GUARD", f"sleep {delay_seconds * 1000.0:.1f} ms"
                    )
                time.sleep(delay_seconds)
                continue

            if item_kind == "command" and command is not None:
                self._write(command, output_lane)

    def close(self) -> None:
        with self._condition:
            if self._closed:
                return
            self.invalidate_all_low()
            self._closed = True
            self._condition.notify_all()

        self._thread.join(timeout=1.0)
        self.serial.close()


class _TaggedSequencerLane:
    """One logical AMY sequencer lane backed by a reserved user-tag range.

    AMY tags are one-to-one with stored events. Reusing a tag replaces the
    previous event; H0,0,<tag> clears exactly that event. A lane therefore owns
    a contiguous range and assigns one deterministic tag to every scheduled
    event.  The high-water mark is intentionally monotonic: if a queued update
    is superseded halfway through, the next update still clears every tag that
    could contain an older definition.
    """

    def __init__(
        self,
        name: str,
        start: int,
        count: int,
        writer: _SerialWriter,
    ) -> None:
        self.name = str(name)
        self.start = int(start)
        self.count = int(count)
        self.writer = writer
        self.high_water = 0
        if self.start < 0 or self.count <= 0:
            raise ValueError(f"invalid sequencer tag range for {self.name}")

    @property
    def end(self) -> int:
        return self.start + self.count

    def commands(
        self,
        events: list[tuple[int, int, str]],
    ) -> list[str]:
        if len(events) > self.count:
            raise ValueError(
                f"sequencer lane {self.name} requires {len(events)} tags; "
                f"range capacity is {self.count}"
            )

        previous_high_water = self.high_water
        self.high_water = max(self.high_water, len(events))
        commands: list[str] = []

        for index, (tick, period, body) in enumerate(events):
            tag = self.start + index
            body = str(body)
            if body.endswith("Z"):
                body = body[:-1]
            commands.append(
                f"H{max(0, int(tick))},{max(1, int(period))},{tag}{body}Z"
            )

        # Clear tags no longer used by the new pattern. Keep using the maximum
        # ever occupied slot so an interrupted earlier update cannot leave a
        # stale event beyond the current event count.
        for index in range(len(events), max(previous_high_water, self.high_water)):
            commands.append(f"H0,0,{self.start + index}Z")

        return commands

    def enqueue(self, events: list[tuple[int, int, str]]) -> None:
        generation = self.writer.new_low_generation(self.name)
        for command in self.commands(events):
            self.writer.low(self.name, generation, command)

    def clear(self) -> None:
        self.enqueue([])


class AmySerialClient:'''
replace_regex(
    amy,
    r'class _SerialWriter:.*?\n\nclass AmySerialClient:',
    writer_block,
)

# ---------------------------------------------------------------------------
# Construct/validate tag lanes. 252 of the 256 current AMY user tags are used;
# four remain deliberately unallocated.
# ---------------------------------------------------------------------------
replace_once(
    amy,
    '''        self._scheduled_rhythm_id: str | None = None\n        self._configured_synths: set[int] = set()\n''',
    '''        self._scheduled_rhythm_id: str | None = None\n\n        tag_config = config.get("rhythm", {}).get("tag_ranges", {})\n        max_tags = int(config.get("rhythm", {}).get("max_sequencer_tags", 256))\n        self._sequencer_lanes: dict[str, _TaggedSequencerLane] = {}\n        occupied: set[int] = set()\n        for lane_name in ("drums", "bass", "chords"):\n            raw_range = tag_config.get(lane_name, {})\n            lane = _TaggedSequencerLane(\n                lane_name,\n                int(raw_range.get("start", -1)),\n                int(raw_range.get("count", 0)),\n                self.writer,\n            )\n            if lane.end > max_tags:\n                raise ValueError(\n                    f"sequencer lane {lane_name} ends at tag {lane.end - 1}, "\n                    f"but max_sequencer_tags is {max_tags}"\n                )\n            tags = set(range(lane.start, lane.end))\n            overlap = tags & occupied\n            if overlap:\n                raise ValueError(\n                    f"sequencer tag ranges overlap at {min(overlap)}"\n                )\n            occupied |= tags\n            self._sequencer_lanes[lane_name] = lane\n\n        self._configured_synths: set[int] = set()\n''',
)

# _wire only needs high-priority operation now; tagged lanes enqueue directly.
replace_once(
    amy,
    '''    def _wire(self, command: str, *, low_generation: int | None = None) -> None:\n        if low_generation is None:\n            self.writer.high(command)\n        else:\n            self.writer.low(low_generation, command)\n''',
    '''    def _wire(self, command: str) -> None:\n        self.writer.high(command)\n''',
)

# Chord patch changes no longer stop/reset/reinstall the whole sequencer. The
# tagged synth-4 events already point at the same physical synth and therefore
# automatically use the newly loaded patch on their next firing.
replace_once(
    amy,
    '''        rhythm_generation: int | None = None\n        rhythm_config: dict[str, Any] | None = None\n        if role == "chord" and patch_required and self.rhythm_running:\n            rhythm_generation, rhythm_config = self._prepare_rhythm_rebuild(\n                reset_phase=False\n            )\n\n''',
    '''        if role == "chord" and patch_required:\n            # Silence only the currently sounding automatic chord. Tagged\n            # synth-4 events remain scheduled and use the new patch when they\n            # next fire; drums, bass and transport are untouched.\n            self._wire(f"l0i{self.synth_id['rhythm_chord']}Z")\n\n''',
)
replace_once(
    amy,
    '''        if rhythm_generation is not None and rhythm_config is not None:\n            self.writer.delay(self._rhythm_guard_seconds())\n            self._install_rhythm_schedule(rhythm_generation, rhythm_config)\n\n''',
    '',
)

# ---------------------------------------------------------------------------
# Replace the complete old reset/rebuild sequencer implementation with tagged
# per-lane pattern generation and targeted replacement.
# ---------------------------------------------------------------------------
sequencer_section = r'''    # ------------------------------------------------------------------
    # AMY tagged sequencer lanes
    # ------------------------------------------------------------------

    def _rhythm_period_ticks(self) -> int:
        config = self.rhythm_config
        if not config:
            return AMY_PPQ
        return max(1, round(float(config["length_beats"]) * AMY_PPQ))

    def _lane_events(self, lane_name: str) -> list[tuple[int, int, str]]:
        config = self.rhythm_config
        if not config:
            return []

        period = self._rhythm_period_ticks()
        rhythm_cfg = self.config["rhythm"]
        events: list[tuple[int, int, str]] = []

        if lane_name == "drums":
            drum_synth = self.synth_id["drums"]
            sample_map = self.config["drums"]["sample_map"]
            drum_gain = max(
                0.0,
                float(self.config["drums"].get("velocity_gain", 5.0)),
            )
            for event in config.get("percussion_events", []):
                sample = str(event.get("sample", ""))
                if sample not in sample_map:
                    continue
                tick = round(float(event.get("time", 0.0)) * AMY_PPQ)
                velocity = max(0.0, min(1.0, float(event.get("amp", 1.0))))
                hit = sample_map[sample]
                events.append((
                    tick,
                    period,
                    f"p{int(hit['preset'])}n{self._f(float(hit['note']))}"
                    f"l{self._f(velocity * drum_gain)}i{drum_synth}",
                ))
            return events

        if lane_name == "bass":
            if not self.bass_running or not self.bass_notes:
                return []
            bass_synth = self.synth_id["bass"]
            gate = max(
                1,
                round(float(rhythm_cfg["bass_gate_beats"]) * AMY_PPQ),
            )
            for event in config.get("bass_events", []):
                degree = int(event.get("degree", 0))
                note = self.bass_notes[degree % len(self.bass_notes)]
                tick = round(float(event.get("time", 0.0)) * AMY_PPQ)
                velocity = max(0.0, min(1.0, float(event.get("amp", 1.0))))
                events.append((
                    tick,
                    period,
                    f"n{self._f(note)}l{self._f(velocity)}i{bass_synth}",
                ))
                events.append((
                    tick + gate,
                    period,
                    f"n{self._f(note)}l0i{bass_synth}",
                ))
            return events

        if lane_name == "chords":
            if not self.rhythm_chord_enabled or not self.chord_notes:
                return []
            chord_synth = self.synth_id["rhythm_chord"]
            max_notes = max(
                1,
                int(rhythm_cfg.get("max_rhythm_chord_notes", 4)),
            )
            rhythm_notes = self.chord_notes[:max_notes]
            gate = max(
                1,
                round(float(rhythm_cfg["chord_gate_beats"]) * AMY_PPQ),
            )
            for event in config.get("chord_events", []):
                tick = round(float(event.get("time", 0.0)) * AMY_PPQ)
                velocity = max(0.0, min(1.0, float(event.get("amp", 1.0))))
                for note in rhythm_notes:
                    events.append((
                        tick,
                        period,
                        f"n{self._f(note)}l{self._f(velocity)}i{chord_synth}",
                    ))
                events.append((tick + gate, period, f"l0i{chord_synth}"))
            return events

        raise KeyError(lane_name)

    def _invalidate_full_rhythm_transaction(self) -> None:
        self.writer.new_low_generation("rhythm-full")

    def _replace_lane(self, lane_name: str) -> None:
        # A targeted lane edit supersedes any still-queued full-pattern install.
        self._invalidate_full_rhythm_transaction()
        lane = self._sequencer_lanes[lane_name]
        try:
            lane.enqueue(self._lane_events(lane_name))
        except ValueError as exc:
            print(f"AMY rhythm warning: {exc}", flush=True)

    def _replace_all_lanes(self, *, resume_transport: bool) -> None:
        # Cancel queued per-lane edits, then serialize all three ranges into one
        # low-priority transaction.  If transport is being started/restarted,
        # zY1 is the final command in the same FIFO and therefore cannot overtake
        # the tag definitions.
        for lane_name in self._sequencer_lanes:
            self.writer.new_low_generation(lane_name)
        generation = self.writer.new_low_generation("rhythm-full")

        commands: list[str] = []
        for lane_name in ("drums", "bass", "chords"):
            lane = self._sequencer_lanes[lane_name]
            try:
                commands.extend(lane.commands(self._lane_events(lane_name)))
            except ValueError as exc:
                print(f"AMY rhythm warning: {exc}", flush=True)
                return

        if resume_transport:
            commands.append("zY1Z")
        for command in commands:
            self.writer.low("rhythm-full", generation, command)

    def _cancel_queued_rhythm_updates(self) -> None:
        self.writer.new_low_generation("rhythm-full")
        for lane_name in self._sequencer_lanes:
            self.writer.new_low_generation(lane_name)

    def _set_rhythm_config(self, payload_text: str) -> None:
        try:
            new_config = json.loads(str(payload_text))
        except json.JSONDecodeError:
            return
        if not isinstance(new_config, dict):
            return

        old_id = (
            str(self.rhythm_config.get("id", ""))
            if isinstance(self.rhythm_config, dict)
            else ""
        )
        new_id = str(new_config.get("id", ""))
        style_changed = bool(old_id) and old_id != new_id
        self.rhythm_config = new_config
        self._scheduled_rhythm_id = new_id
        self._wire(f"j{self._f(float(new_config.get('tempo', 108.0)))}Z")

        if style_changed and self.rhythm_running:
            # A whole style change deliberately starts the new bar cleanly.
            # This is the only ordinary rhythm edit which stops transport.
            self._cancel_queued_rhythm_updates()
            self._wire("zY0Z")
            self._silence_accompaniment()
            self._wire(f"S{RESET_TIMEBASE}Z")
            self._replace_all_lanes(resume_transport=True)
        else:
            # Activity/tempo/event edits replace tags in place without touching
            # transport. This may update all three ranges, but each tag write is
            # atomic inside AMY and no unrelated lane is globally reset.
            self._replace_all_lanes(resume_transport=False)

    def _start_rhythm(self) -> None:
        if self.rhythm_running:
            return
        self.rhythm_running = True
        self._wire(f"S{RESET_TIMEBASE}Z")
        self._replace_all_lanes(resume_transport=True)

    def _stop_rhythm(self) -> None:
        if not self.rhythm_running:
            return
        self.rhythm_running = False
        self._cancel_queued_rhythm_updates()
        self._wire("zY0Z")
        self._silence_accompaniment()
        # Tagged definitions remain installed while stopped. They are replaced
        # by config/tuning changes and reused on the next explicit Start.

    def _cancel_strum_tail'''
replace_regex(
    amy,
    r'    # ------------------------------------------------------------------\n    # AMY sequencer\n    # ------------------------------------------------------------------.*?    def _cancel_strum_tail',
    sequencer_section,
)

# Chord/bass pitch updates become targeted tag-range replacements.
replace_once(
    amy,
    '''        # Both accompaniment chords AND bass derive their pitch from this\n        # chord state.  Rebuild if either lane is active.\n        if self.rhythm_running and (\n            self.rhythm_chord_enabled or self.bass_running\n        ):\n            self._rebuild_rhythm(reset_phase=False)\n''',
    '''        # Chord and bass are independent tagged sequencer lanes. Updating\n        # tuning/chord pitch replaces only those ranges; percussion and\n        # sequencer transport remain untouched.\n        if self.bass_running:\n            self._replace_lane("bass")\n        self._replace_lane("chords")\n''',
)

# Panic/close must invalidate every low lane, not one obsolete global generation.
text = amy.read_text(encoding="utf-8")
text = text.replace('self.writer.new_low_generation()\n', 'self.writer.invalidate_all_low()\n')
amy.write_text(text, encoding="utf-8")

# Replace rhythm-related send_message branches.
replace_once(
    amy,
    '''        elif address == a["bass_running"]:\n            self.bass_running = bool(int(value))\n            if not self.bass_running:\n                self._wire(f"l0i{self.synth_id['bass']}Z")\n            if self.rhythm_running:\n                self._rebuild_rhythm(reset_phase=False)\n        elif address == a["rhythm_config"]:\n            try:\n                self.rhythm_config = json.loads(str(value))\n            except json.JSONDecodeError:\n                return\n            if self.rhythm_running:\n                self._rebuild_rhythm(reset_phase=False)\n            else:\n                tempo = float(self.rhythm_config.get("tempo", 108.0))\n                self._wire(f"j{self._f(tempo)}Z")\n        elif address == a["rhythm_chord_enabled"]:\n            enabled = bool(int(value))\n            if self.rhythm_chord_enabled == enabled:\n                return\n            self.rhythm_chord_enabled = enabled\n            if not enabled:\n                self._wire(f"l0i{self.synth_id['rhythm_chord']}Z")\n            if self.rhythm_running:\n                self._rebuild_rhythm(\n                    reset_phase=False,\n                    resync_chord=enabled,\n                )\n        elif address == a["rhythm_running"]:\n            new_state = bool(int(value))\n            if new_state:\n                self.rhythm_running = True\n                self._rebuild_rhythm(\n                    reset_phase=True,\n                    resync_chord=True,\n                )\n            else:\n                self.rhythm_running = False\n                self.writer.invalidate_all_low()\n                self._silence_accompaniment()\n                self._wire("zY0Z")\n                self._wire(f"S{RESET_SEQUENCER}Z")\n''',
    '''        elif address == a["bass_running"]:\n            enabled = bool(int(value))\n            if self.bass_running == enabled:\n                return\n            self.bass_running = enabled\n            if not enabled:\n                self._wire(f"l0i{self.synth_id['bass']}Z")\n            self._replace_lane("bass")\n        elif address == a["rhythm_config"]:\n            self._set_rhythm_config(str(value))\n        elif address == a["rhythm_chord_enabled"]:\n            enabled = bool(int(value))\n            if self.rhythm_chord_enabled == enabled:\n                return\n            self.rhythm_chord_enabled = enabled\n            if not enabled:\n                self._wire(f"l0i{self.synth_id['rhythm_chord']}Z")\n            else:\n                # Ensure the rhythm synth has the same explicit overrides as\n                # manual chords before tagged events are reintroduced.\n                self._sync_synth_params(\n                    "chord",\n                    (self.synth_id["rhythm_chord"],),\n                )\n            self._replace_lane("chords")\n        elif address == a["rhythm_running"]:\n            new_state = bool(int(value))\n            if new_state:\n                self._start_rhythm()\n            else:\n                self._stop_rhythm()\n''',
)

# Close no longer needs RESET_SEQUENCER because process shutdown follows; panic
# still performs the full reset. Leaving tagged definitions while merely
# stopping is intentional.
replace_once(
    amy,
    '''            self.writer.invalidate_all_low()\n            self._cancel_strum_tail()\n            self._wire("zY0Z")\n            for synth in self.synth_id.values():\n                self._wire(f"l0i{synth}Z")\n            self._wire(f"S{RESET_SEQUENCER}Z")\n''',
    '''            self.writer.invalidate_all_low()\n            self._cancel_strum_tail()\n            self._wire("zY0Z")\n            for synth in self.synth_id.values():\n                self._wire(f"l0i{synth}Z")\n''',
)

# ---------------------------------------------------------------------------
# Frontend semantics: chord-lane enable describes musical intent, not transport
# state. Transport is orthogonal and only Start/Stop controls zY.
# ---------------------------------------------------------------------------
main = F / "code" / "main.py"
replace_once(
    main,
    '''        enabled = (\n            self._rhythm_running\n            and self._effective_chord_activity() > 0\n        )\n''',
    '''        enabled = self._effective_chord_activity() > 0\n''',
)
replace_once(
    main,
    '''            "rhythm_chord_enabled": bool(\n                self._rhythm_running\n                and self._effective_chord_activity() > 0\n            ),\n''',
    '''            "rhythm_chord_enabled": bool(\n                self._effective_chord_activity() > 0\n            ),\n''',
)

# ---------------------------------------------------------------------------
# Tests: tagged H format, no whole-sequencer rebuild for tuning, timbre changes
# or held chords.  Verify lane tag ranges and independence explicitly.
# ---------------------------------------------------------------------------
serial = F / "tests" / "integration" / "test_serial.py"
text = serial.read_text(encoding="utf-8")
text = text.replace(
    'rf"^H\\d+,\\d+n(?P<note>{_NOTE})l(?P<vel>{_NOTE})i{int(synth)}Z$"',
    'rf"^H\\d+,\\d+,\\d+n(?P<note>{_NOTE})l(?P<vel>{_NOTE})i{int(synth)}Z$"',
)
# Tuning change no longer resets/stops transport; wait for tagged bass/chord
# events to appear and assert reset/transport commands are absent.
text = text.replace(
    '''            app.action("setTuningModeIndex", 0)  # HARM\n            app.bridge.wait_for_lines(\n                ["S4096Z", "zY1Z"], start=harm_start, timeout=8.0\n            )\n            app.bridge.wait_idle(timeout=8.0)\n            harm_lines = app.bridge.lines_since(harm_start)\n''',
    '''            app.action("setTuningModeIndex", 0)  # HARM\n            deadline = time.monotonic() + 8.0\n            while time.monotonic() < deadline:\n                harm_lines = app.bridge.lines_since(harm_start)\n                if scheduled_note_ons(harm_lines, 1) and scheduled_note_ons(harm_lines, 4):\n                    break\n                time.sleep(0.01)\n            else:\n                self.fail("HARM tuning change did not replace bass/chord tagged events")\n            app.bridge.wait_idle(timeout=8.0)\n            harm_lines = app.bridge.lines_since(harm_start)\n            self.assertNotIn("zY0Z", harm_lines)\n            self.assertNotIn("S4096Z", harm_lines)\n''',
)
# Held chord transaction no longer emits zY1 after the press.
text = text.replace(
    '''            app.bridge.wait_for_lines(["zY1Z"], start=press_start, timeout=8.0)\n            app.bridge.wait_idle(timeout=8.0)\n''',
    '''            app.bridge.wait_idle(timeout=8.0)\n''',
    1,
)
# Live instrument switch: patch only, no transport/reset or schedule rebuild.
old_switch = '''            app.bridge.wait_for_lines(\n                [f"K{other_patch}i3Z", f"K{other_patch}i4Z", "S4096Z"],\n                start=switch_start,\n                timeout=8.0,\n            )\n            app.bridge.wait_idle(timeout=8.0)\n            lines = app.bridge.lines_since(switch_start)\n\n            stop = lines.index("zY0Z")\n            reset = lines.index("S4096Z")\n            k3 = lines.index(f"K{other_patch}i3Z")\n            k4 = lines.index(f"K{other_patch}i4Z")\n            first_schedule = next(\n                index for index, line in enumerate(lines) if line.startswith("H")\n            )\n            self.assertLess(stop, reset)\n            self.assertLess(reset, k3)\n            self.assertLess(k3, k4)\n            self.assertLess(k4, first_schedule)\n\n            # A live rhythm refresh must define chord events against the\n            # dedicated rhythm chord synth 4, never manual synth 3.\n            scheduled = [line for line in lines if line.startswith("H")]\n            self.assertTrue(scheduled, "no sequencer events sent after switch")\n            self.assertTrue(\n                any("i4Z" in line for line in scheduled),\n                "refreshed rhythm contains no synth-4 chord events",\n            )\n'''
new_switch = '''            app.bridge.wait_for_lines(\n                [f"K{other_patch}i3Z", f"K{other_patch}i4Z"],\n                start=switch_start,\n                timeout=8.0,\n            )\n            app.bridge.wait_idle(timeout=8.0)\n            lines = app.bridge.lines_since(switch_start)\n\n            self.assertNotIn("zY0Z", lines)\n            self.assertNotIn("S4096Z", lines)\n            self.assertNotIn("zY1Z", lines)\n            self.assertLess(\n                lines.index(f"K{other_patch}i3Z"),\n                lines.index(f"K{other_patch}i4Z"),\n            )\n'''
if old_switch not in text:
    raise RuntimeError("serial live switch block not found")
text = text.replace(old_switch, new_switch, 1)

# Replace long-hold assertions with tag-range independence.
start = text.index('    def test_long_manual_chord_hold_keeps_rhythm_transport_and_percussion_alive')
end = text.index('\n\nif __name__ == "__main__":', start)
new_hold = '''    def test_long_manual_chord_hold_only_edits_chord_tag_range(self) -> None:\n        with HeadlessApp(native_amy=False) as app:\n            app.bridge.wait_idle(timeout=10.0)\n            if not bool(app.query("rhythmRunning")):\n                start = app.bridge.count()\n                app.action("toggleRhythm")\n                app.bridge.wait_for_lines(["zY1Z"], start=start, timeout=8.0)\n                app.bridge.wait_idle(timeout=8.0)\n\n            start = app.bridge.count()\n            app.action("pressChord", 0, 0)\n            app.bridge.wait_idle(timeout=8.0)\n            delta = app.bridge.lines_since(start)\n\n            self.assertNotIn("zY0Z", delta)\n            self.assertNotIn("S4096Z", delta)\n            self.assertNotIn("zY1Z", delta)\n            # Chord tags occupy 112..251. Holding a manual chord clears them,\n            # while drum tags 0..55 must not be touched. Bass may be replaced\n            # because the newly selected chord changes its pitches.\n            cancellations = [line for line in delta if line.startswith("H0,0,")]\n            self.assertTrue(cancellations, delta)\n            cancel_tags = {int(line.split(",", 2)[2][:-1]) for line in cancellations}\n            self.assertTrue(all(112 <= tag < 252 for tag in cancel_tags), cancel_tags)\n            self.assertFalse(any(line.startswith("H") and ",0" in line[:8] and "i0Z" in line for line in delta))\n            self.assertTrue(bool(app.query("rhythmRunning")))\n\n            time.sleep(1.0)\n            self.assertTrue(bool(app.query("rhythmRunning")))\n\n            release_start = app.bridge.count()\n            app.action("releaseChord", 0, 0)\n            deadline = time.monotonic() + 8.0\n            while time.monotonic() < deadline:\n                release_delta = app.bridge.lines_since(release_start)\n                if any(line.startswith("H") and "i4Z" in line for line in release_delta):\n                    break\n                time.sleep(0.01)\n            else:\n                self.fail("release did not reinstall tagged rhythm chords")\n            release_delta = app.bridge.lines_since(release_start)\n            self.assertNotIn("zY0Z", release_delta)\n            self.assertNotIn("S4096Z", release_delta)\n            self.assertNotIn("zY1Z", release_delta)\n            self.assertFalse(any("i0Z" in line for line in release_delta if line.startswith("H")))\n            self.assertFalse(any("i1Z" in line for line in release_delta if line.startswith("H")))\n            self.assertTrue(bool(app.query("rhythmRunning")))\n\n    def test_tag_ranges_are_disjoint_and_lane_updates_do_not_cross(self) -> None:\n        with HeadlessApp(native_amy=False) as app:\n            app.bridge.wait_idle(timeout=10.0)\n            if not bool(app.query("rhythmRunning")):\n                start = app.bridge.count()\n                app.action("toggleRhythm")\n                app.bridge.wait_for_lines(["zY1Z"], start=start, timeout=8.0)\n                app.bridge.wait_idle(timeout=8.0)\n\n            # Bass off clears only tags 56..111.\n            if bool(app.query("bassRunning")):\n                start = app.bridge.count()\n                app.action("toggleBassRunning")\n                app.bridge.wait_idle(timeout=8.0)\n                lines = app.bridge.lines_since(start)\n                tags = {\n                    int(line.split(",", 2)[2][:-1])\n                    for line in lines\n                    if line.startswith("H0,0,")\n                }\n                self.assertTrue(tags)\n                self.assertTrue(all(56 <= tag < 112 for tag in tags), tags)\n                self.assertNotIn("zY0Z", lines)\n                self.assertNotIn("S4096Z", lines)\n\n            # Disabling automatic chords clears only tags 112..251.\n            app.action("setRhythmChordActivity", 0.0)\n            app.bridge.wait_idle(timeout=8.0)\n            start = app.bridge.count()\n            app.action("setRhythmChordActivity", 3.0)\n            app.bridge.wait_idle(timeout=8.0)\n            lines = app.bridge.lines_since(start)\n            chord_tags = []\n            for line in lines:\n                if not line.startswith("H") or "i4Z" not in line:\n                    continue\n                header = line[1:].split("i", 1)[0]\n                parts = header.split(",", 3)\n                if len(parts) >= 3:\n                    chord_tags.append(int(parts[2].split("n", 1)[0].split("l", 1)[0]))\n            self.assertTrue(chord_tags, lines)\n            self.assertTrue(all(112 <= tag < 252 for tag in chord_tags), chord_tags)\n'''
text = text[:start] + new_hold + text[end:]
serial.write_text(text, encoding="utf-8")

# Native rhythm tests keep their state assertions; additionally forbid global
# transport/reset on a live timbre switch.
native = F / "tests" / "integration" / "test_native_rhythm.py"
text = native.read_text(encoding="utf-8")
needle = '''            switched_lines = app.bridge.lines_since(switch_start)\n            scheduled_chords = [\n'''
replacement = '''            switched_lines = app.bridge.lines_since(switch_start)\n            self.assertNotIn("zY0Z", switched_lines)\n            self.assertNotIn("S4096Z", switched_lines)\n            self.assertNotIn("zY1Z", switched_lines)\n            scheduled_chords = [\n'''
if needle not in text:
    raise RuntimeError("native switched-lines marker missing")
text = text.replace(needle, replacement, 1)
native.write_text(text, encoding="utf-8")

# Update regression contract with the tag semantics verified against current AMY.
use = F / "tests" / "USE_CASES.md"
text = use.read_text(encoding="utf-8")
marker = '''### RHYTHM — sequencer invariants\n\n'''
addition = '''### RHYTHM — sequencer invariants\n\n**RHYTHM-00 — drums, bass and automatic chords use independent AMY tag ranges**\n\n- Current AMY stores exactly one sequencer entry per user tag; reusing a tag replaces that entry, and `H0,0,<tag>` clears only that entry. Multiple simultaneous events therefore require distinct tags.\n- The application reserves non-overlapping ranges sized from the complete rhythm catalogue: drums 0..55, bass 56..111 and automatic chords 112..251. Tags 252..255 remain unused.\n- Every scheduled note-on/off owns one deterministic tag in its lane.\n- Holding/releasing a manual chord clears/reinstalls only the automatic-chord range; bass and drums keep running and transport remains started.\n- Bass on/off and bass retuning replace only the bass range. Tuning/chord pitch changes may replace both bass and automatic-chord ranges but must not touch percussion or stop transport.\n- A rhythm-style change may deliberately restart the bar; ordinary lane edits may not issue `RESET_SEQUENCER`.\n\n**Failure history:** whole-sequencer rebuilds were used for chord hold/release, pitch changes and other lane-local operations. On the ESP32-P4 this could make the rhythm audibly disappear while a manual chord was held and then return on release.\n\n'''
if marker not in text:
    raise RuntimeError("RHYTHM marker missing")
use.write_text(text.replace(marker, addition, 1), encoding="utf-8")

# Syntax smoke tests.
compile(amy.read_text(encoding="utf-8"), str(amy), "exec")
compile(main.read_text(encoding="utf-8"), str(main), "exec")
compile(serial.read_text(encoding="utf-8"), str(serial), "exec")
compile(native.read_text(encoding="utf-8"), str(native), "exec")
