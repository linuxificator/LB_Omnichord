# AMY Omnichord regression catalogue

This file is the executable-test contract for the active `amysynth_version/qt_frontend` application. The Sonic Pi version is frozen and is intentionally outside this test plan.

The application has three observable layers:

1. **Frontend/backend state** — Qt `InstrumentBackend`, preset state and slider models.
2. **Transport** — logical events translated to AMY wire commands and, in the Raspberry Pi setup, framed as 1,000,000-baud 8N1 serial lines.
3. **AMY engine state/output** — the commands must actually configure current upstream AMY as intended. Native-Linux tests use the current `shorepine/amy` `main` branch and inspect native synth state / `dump_state()` after the same wire stream has been delivered.

Every defect below must have a permanent regression test before it is considered fixed.

## Architecture invariant

**ARCH-01 — one object owns synth state; one convergence path applies it**

For each frontend role (chord, strum, bass), `SynthState` is the sole owner of:

- selected instrument;
- per-instrument slider values;
- default construction;
- preset overlay;
- instrument switching;
- UI slider mutation/clamping;
- QML control-model values;
- complete transport payload;
- sparse preset serialization;
- copying state between roles.

Startup, preset loading, instrument switching and UI edits may not maintain independent dictionaries or independent transport logic. They mutate the same `SynthState` object through its methods and publish the same complete logical synth-state payload.

On the AMY receiver side, normal complete synth-state messages converge through one `_apply_synth_state()` method. That method decides whether the operation is a patch change, a same-instrument parameter diff, or an ADSR reset and applies the result to all physical synth instances owned by that logical role. Legacy name-only / parameter-only handlers are compatibility adapters into the same method, not separate implementations.

**Failure mode this prevents:** a preset could previously update the UI-side dictionary while a later UI edit followed a different send path. That made it possible for the UI to display the correct stored slider value while rhythm synth 4 retained another value until the slider was moved.

A static regression test rejects reintroduction of the former parallel `SynthRuntime`/`values_by_synth`, global serializer and separate `_send_synth_name()` / `_send_synth_params()` frontend paths.

## Test suites

| Suite | Purpose | Hardware/AMY |
| --- | --- | --- |
| `unit-controls` | catalogue defaults, `SynthState`, control mapping, sparse preset state, structural invariants | none |
| `frontend` | real headless `QCoreApplication` + real `InstrumentBackend`, driven through the localhost test API | pseudo serial |
| `serial` | real `AmySerialClient` / `pyserial` framing, ordering and generated wire commands | Linux PTY |
| `native-controls` | feed the real serial wire stream into native current AMY and inspect actual synth state | Linux PTY + native AMY |
| `native-rhythm` | rhythm/sequencer scenarios against native AMY, including startup and live chord-instrument switching | Linux PTY + native AMY |
| `presets` | per-instrument session state and sparse preset save/load semantics | none/headless backend |
| `all` | all suites sequentially; intended for local/manual use. CI runs the component suites in parallel for a PR to `main`. | mixed |

`python tests/run_tests.py --suite <name>` selects one suite. `--list` prints the available suites.

## Required behavior and regression history

### START — startup and basic transport

**START-01 — deterministic startup**

- Start the headless application with a pseudo serial device.
- AMY transport stops the sequencer, clears the previous oscillator/instrument allocation and creates drums, bass, strum, manual-chord and rhythm-chord synths.
- Startup must finish without a real display server.
- The command log must contain the expected reset and synth setup commands.

**Failure history:** the first CI attempt depended on XCB/Xvfb runtime libraries. The regression harness was changed to `QCoreApplication`; GUI rendering is not part of the functional test process.

**START-02 — real serial framing**

- Production serial mode is 1,000,000 baud, 8 data bits, no parity, 1 stop bit, no hardware flow control.
- Every AMY command is terminated with `Z` and one LF transport delimiter.
- A Linux PTY test must exercise the real `pyserial` writer rather than replacing it with a fake send method.

**START-03 — clean-home P7 rhythm start preserves Chorus Vibes parameters**

Exact hardware reproduction:

1. remove everything from `~/.omnichord`, start the application and select preset 7;
2. press a chord while rhythm is stopped — it must sound like the P7 default chord instrument, **Chorus Vibes** (`juno_066`);
3. press Start in the rhythm;
4. the first and all subsequent automatic rhythm chords must use exactly the same stored Chorus Vibes slider state as the manual chord;
5. moving Cutoff afterward must not be necessary to synchronize the two chord paths.

Preset 7 intentionally stores no chord parameter overrides. Its Chorus Vibes values therefore come entirely from the current instrument catalogue defaults, making this a direct test of startup/default-state propagation rather than user-preset persistence.

The serial regression requires the factory patch to remain authoritative for native filter coefficients. Chorus Vibes' `F27.365,0.181,,5.11,0,0` is a complete AMY CtrlCoef model: 27.365 Hz is only the base term, while note and envelope coefficients also contribute to the instantaneous cutoff. Starting rhythm therefore must **not** emit a redundant `v0F27.365i4Z` override. A real user slider edit, by contrast, is an explicit override and must update both chord synths 3 and 4.

**Observed failure (2026-08-21):** the manual chord sounded correctly mellow after selecting P7, but automatic rhythm chords were effectively inaudible until the VCF base slider was moved. The visible native factory coefficient had been conflated with an application override.

**Automated verification after the fix:** the real-serial test proves that selecting P7 and starting rhythm do not resend the native VCF base coefficient, while a user cutoff edit is sent to both synth 3 and synth 4. Native-AMY tests require synth 3 and synth 4 to retain equivalent factory filter/resonance state across rhythm Start.

### CHORD — manual chord behavior

**CHORD-01 — chord press emits the correct tuned notes**

- Pressing representative chord buttons through the test-control API must produce the expected AMY note-on commands.
- The configured tuning table is part of the expected output; tests must not assume equal temperament when a preset selects HARM/JV tuning.

**CHORD-02 — release does not produce false re-triggers**

- A held chord must not repeatedly drop to activity 0 and re-trigger because of touch-release bounce.
- Quick intentional taps must remain responsive.

**Failure history:** earlier builds showed erratic repeated chord starts while a chord was held. Debugging introduced explicit chord-touch state and release filtering.

### STRUM — strum input

**STRUM-01 — press/touch makes sound immediately**

- `strumStart()` must emit a note on finger/mouse down; a stationary press may not require a move event before producing sound.
- A sweep must not exceed the configured live voice count and must eventually release the tail.

**Failure history:** the strum area visibly accepted mouse/touch input but emitted no AMY commands/sound in an earlier AMY build.

### MIDI — input, tuning, preview and effects

**MIDI-01 — Linux raw-MIDI input reaches matching rows**

- The Linux reader opens configured `/dev/snd/midiC*D*` devices non-blocking.
- It parses Note On/Off, velocity-zero Note Off and running status.
- A row receives notes for its selected channel; channel 0 receives all.
- SysEx, CC, Program Change and real-time clock are not musical inputs in the
  current implementation.

**MIDI-02 — incoming notes use active MIDI tuning**

- At A=440 and C root, C4/60 remains 60 under EQ, HARM and JV.
- E4/64 is 64 under EQ and fractional under HARM/JV.
- The exact tuned onset pitch is retained for its matching Note Off.
- Coupled tuning synchronizes from the section that changes; decoupled OMNI and
  MIDI tuning state cannot mutate one another.

**MIDI-03 — preview stays within allocated voices**

- Each pitched MIDI row has four voices.
- Before a fifth live preview onset, the oldest preview note is explicitly
  released.
- Tail callbacks release only notes still tracked as active; no preview sweep
  may overflow AMY's forgotten-note pool or emit unmatched delayed Note Offs.

**MIDI-04 — MIDI reverb is independent and bus-scoped**

- The MIDI header controls buses 4–9 and optionally drum bus 10.
- The OMNI header controls buses 0–3 and cannot mutate MIDI UI state.
- `midiPlayer` is exposed to QML as a `QObject`, so all four reverb slots are
  callable rather than opaque QVariant/Python attributes.

### INSTRUMENT — selected patch identity

**INST-01 — selecting an instrument changes the manual chord synth**

- Selecting a chord instrument must configure manual chord synth 3 with that instrument.
- A subsequent chord press must use the selected instrument.

**INST-02 — manual and rhythm chord synths are one logical instrument**

- Chord synth 3 (manual) and synth 4 (rhythm) are separate voice pools but must have equivalent patch/control state at all times after a chord-instrument change.
- Native AMY readback is the authority, not only the frontend's selected index.

**INST-03 — live rhythm follows chord-instrument changes**

Exact reproduction sequence:

1. select **Brass Ensemble** as the chord instrument;
2. enable/start a rhythm with chord activity;
3. press a chord and allow rhythm chords to sound;
4. select a different chord instrument while rhythm keeps running;
5. press another chord.

Expected:

- the manual chord uses the new instrument;
- every subsequent rhythm chord also uses the new instrument;
- synth 3 and synth 4 native AMY state are equivalent after the change;
- the rhythm need not restart from beat zero solely because the instrument changed.

**Observed failure:** manual chords changed instrument correctly, while rhythm chords continued sounding as Brass Ensemble or otherwise diverged from the selected chord instrument. Previous fixes that merely resent slider state or rebuilt the sequencer did not reliably fix the audible behavior.

**INST-04 — switching away and back restores edited controls to AMY**

Sequence:

1. select instrument A;
2. move a clearly audible slider (for example resonance);
3. select instrument B;
4. select instrument A again.

Expected:

- the UI shows the edited value;
- both chord synth 3 and rhythm synth 4 receive and retain the edited value in actual AMY state;
- the sound matches the restored setting.

**Failure history:** the slider returned visually to its edited position, but AMY sounded as if the stored value had not been resent.

**INST-05 — Juno A82 / Resonance Funk remains audible**

- Selecting the curated Juno A82-compatible entry must produce a usable output on current AMY with the documented compatibility excitation.

**Failure history:** the patch was silent in an earlier version because its sound-source amplitudes provided no excitation for the resonant filter.

### CTRL — slider meaning, ranges and isolation

**CTRL-00 — native patch value is not automatically an engine override**

- A numeric UI default may represent an AMY factory-patch coefficient.
- If the application default equals that native value, selecting a preset or starting rhythm must not retransmit it as an override.
- Juno frequency controls are CtrlCoef models: for Chorus Vibes the factory `F27.365,0.181,,5.11,0,0` means a 27.365 Hz **base** plus note/envelope modulation, not MIDI note 27.
- Frequency sliders display values in Hz with the unit after the number and logarithmic travel. A future MIDI-note-valued control must display note names such as C4 rather than a raw MIDI integer.

**Failure history:** with factory P7/Chorus Vibes, automatic rhythm chords were effectively inaudible until Cutoff was moved. The UI/transport model was treating the visible native VCF base coefficient as an explicit override instead of leaving the complete AMY factory filter model authoritative.

**CTRL-01 — every instrument has explicit physical defaults**

- Every slider of every curated instrument has a numeric default within its physical UI range.
- No current UI slider uses `-1` as an exposed "native/default" sentinel.

**CTRL-02 — Sustain range is exactly physical 0..1**

- Sustain zero is the left edge, not the middle of the slider.
- The label always renders a numeric value such as `Sustain 0.00`.

**Failure history:** Sustain had a range of `-1..1`, placing 0 halfway along the control; negative values also caused the numeric text to disappear.

**CTRL-03 — one slider changes only its intended AMY parameters**

- Moving one slider publishes the same complete logical state used by every other state source.
- `AmySerialClient` must diff that complete state and emit only engine controls that actually changed.
- A special frontend slider transport path is not permitted.

**CTRL-04 — Repeater Sustain does not act like cutoff**

- On Juno A73 **Repeater**, changing Sustain must update the amplitude breakpoint only.
- It must not emit or modify filter cutoff (`F`) or resonance (`R`).
- Native AMY readback must show the filter state unchanged after the Sustain edit.

**Failure history:** moving Sustain audibly changed the Repeater as though cutoff had moved because unrelated controls were retransmitted.

**CTRL-05 — musically appropriate attack defaults**

- Harpsichord 1/2 use a short non-zero de-click attack (currently 20 ms).
- Orchestral Pad uses a slow pad-style attack/release rather than the previous effectively instantaneous attack.
- Regeneration from upstream AMY must retain explicit documented musical corrections.

**Failure history:** Harpsichord and Orchestral Pad sounded harsh/horrible with the former 0 ms default attack; increasing attack manually fixed the sound.

### STATE — per-instrument session memory

**STATE-01 — controls belong to the instrument, not the role globally**

Sequence:

1. select Piano and change several controls;
2. select Organ and change other controls;
3. return to Piano.

Expected: Piano returns with its edited Piano values, while Organ retains its own edited values independently.

**STATE-02 — defaults apply on first selection**

- First selection of an instrument uses catalogue defaults unless the loaded preset contains an override for that instrument/control.

### PRESET — persistence

**PRESET-01 — store every modified instrument**

- If four different instruments were edited during the session and Store is pressed, the user preset contains all four modified instruments, not only the currently selected one.

**PRESET-02 — sparse storage**

- Presets store only controls differing from that instrument's defaults.
- Unmodified instruments/controls are omitted.

**PRESET-03 — loading overlays defaults**

- Loading constructs current catalogue defaults first and overlays saved values through `SynthState.load_preset()`.
- Legacy negative `-1` values are treated only as "unspecified/default" and may not re-enter the current UI range.

### RHYTHM — sequencer invariants

**RHYTHM-00 — drums, bass and automatic chords use independent AMY tag ranges**

- Current AMY stores exactly one sequencer entry per user tag; reusing a tag replaces that entry, and `H0,0,<tag>` clears only that entry. Multiple simultaneous events therefore require distinct tags.
- The application reserves non-overlapping ranges sized from the complete rhythm catalogue: drums 0..55, bass 56..111 and automatic chords 112..251. Tags 252..255 remain unused.
- Every scheduled note-on/off owns one deterministic tag in its lane.
- Holding/releasing a manual chord clears/reinstalls only the automatic-chord range; bass and drums keep running and transport remains started.
- Bass on/off and bass retuning replace only the bass range. Tuning/chord pitch changes may replace both bass and automatic-chord ranges but must not touch percussion or stop transport.
- A live rhythm-style or preset change must preserve tempo and sequencer timebase; it may replace tagged pattern events but may not stop/restart transport or issue `RESET_SEQUENCER`.

**Failure history:** whole-sequencer rebuilds were used for chord hold/release, pitch changes and other lane-local operations. On the ESP32-P4 this could make the rhythm audibly disappear while a manual chord was held and then return on release.

**RHYTHM-01 — chord pitch follows the active chord**

- With rhythm chord activity enabled, changing/pressing a chord rebuilds accompaniment pitch without changing the selected chord instrument.

**RHYTHM-02 — instrument change does not silently leave stale rhythm state**

- Chord patch changes update synths 3/4 directly; existing tagged synth-4 events remain installed and use the new patch on their next firing.
- A timbre-only switch must not stop transport or reset/rebuild unrelated sequencer lanes. Tests inspect both serial commands and native AMY synth state.

**RHYTHM-03 — no unnecessary phase reset on a timbre-only change**

- Changing only the chord timbre should preserve the running rhythmic phase where the AMY sequencer permits it.
- If correctness ever requires a phase reset, that behavior must be explicit and tested rather than accidental.

**RHYTHM-04 — starting automatic chords converges synth 4 first**

- Starting rhythm from stopped state installs the authoritative tagged drum/bass/chord ranges and resumes transport only after those definitions are queued ahead of `zY1`.
- Starting rhythm must not require `RESET_SEQUENCER`; tagged replacement itself removes stale lane entries.

**RHYTHM-05 — stopping transport releases sounding accompaniment**

- `zY0` stops future sequencer execution, so a note-off scheduled later in the pattern cannot be relied upon after Stop.
- Every rhythm Stop must therefore immediately send all-off to percussion synth 0, bass synth 1 and automatic-chord synth 4.
- Manual chord synth 3 and strum synth 2 are not rhythm-owned and must remain untouched.
- The frontend Stop action must complete normally and emit the changed `rhythmRunning` state so the Play/Stop control follows the backend.

**Failure history:** stopping while an automatic chord was sounding froze transport before its tagged note-off fired, leaving a hanging chord. The same stop path called a missing `_silence_accompaniment()` method after sending `zY0`, raising `AttributeError`; as a result the actual transport stopped but `rhythmStateChanged` was never emitted and the button remained visually stuck on STOP.

### TUNING — all note-producing paths follow the selected tuning

**TUNING-01 — live EQ/HARM/JV changes propagate everywhere**

When an active chord exists, changing tuning mode or the A-reference tuning must use the same tuned-note functions for every musical note path:

- manually held chord notes on synth 3 are retuned in place;
- future automatic rhythm-chord events on synth 4 are rebuilt with the new tuned pitches;
- future rhythm bass events on synth 1 are rebuilt from the retuned `bass_notes` state;
- strum notes on synth 2 use the new tuning on the next gesture;
- one-shot/manual chord selection uses the selected tuning as well.

The real-serial regression fixes A=440 Hz, selects C major, compares EQ with HARM, and requires non-root chord/bass/strum pitches to change. For example, an equal-tempered bass E at MIDI 40 becomes approximately `39.8631371` under the HARM table, while the C root remains unchanged. The test also verifies that a physically held chord is resent on synth 3 when tuning changes.

**Debug-log interpretation:** rhythm bass is sequenced by AMY. A tuning change therefore appears primarily as a sequencer rebuild with new `H...,n<note>...i1Z` events, not necessarily as an immediate standalone `n...i1Z` command.

### UI/REPOSITORY — structural regressions

**UI-01 — tuba watermark asset resolves from the canonical GUI directory**

- `gui/InstrumentWatermarks.qml` and `gui/tuba_watermark.png` remain colocated and no compatibility symlink is required.

**Failure history:** after directory reorganization the PNG existed but the watermark disappeared because relative resolution occurred through a `code/` symlink. The repository now has no compatibility symlinks.

**UI-02 — instrument names contain useful names only**

- Curated names must not acquire redundant `PATCH` suffixes or unwanted generic engine prefixes in the visible label.

**Failure history:** labels previously appeared with unwanted Juno/DX7 prefixes and later a `PATCH` suffix.

## Proof produced by CI

For serial/native suites, failures must preserve artifacts containing:

- frontend logical/AMY command log;
- exact serial lines received from the PTY;
- current upstream AMY commit SHA/version;
- native AMY `dump_state()` output;
- native synth-state readback for synths 3 and 4 at relevant checkpoints;
- application stdout/stderr and native bridge diagnostics.

Passing a native test therefore means not merely "the expected command was written" but "current AMY accepted the real serial wire stream and its readback state satisfies the invariant".
