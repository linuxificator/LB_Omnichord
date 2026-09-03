# AMY Omnichord regression catalogue

Status: authoritative executable regression-scenario contract
Owner: frontend integration/native/package tests
Applies to: active `amysynth_version/qt_frontend` implementation
Last verified: 2026-09-01

This file is the executable-test contract for the active `amysynth_version/qt_frontend` application. The Sonic Pi version is frozen and is intentionally outside this test plan.

The application has three observable layers:

1. **Frontend/backend state** — Qt `InstrumentBackend`, preset state and slider models.
2. **Transport** — logical events translated to AMY wire commands and, in the Raspberry Pi setup, framed as 1,000,000-baud 8N1 serial lines.
3. **AMY engine state/output** — the commands must actually configure the supported AMY runtime as intended. Native-Linux tests use the exact `linuxificator/amy` nested-sequencer release pinned by CI and inspect native synth state / `dump_state()` after the same wire stream has been delivered.

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
| `unit` | all top-level `test_*.py`: catalogue/state, MIDI engine, socket framing, migration and structural invariants | none |
| `frontend` | real headless `QCoreApplication` + real `InstrumentBackend`, driven through the localhost test API | pseudo serial |
| `serial` | real `AmySerialClient` / `pyserial` framing, ordering and generated wire commands | Linux PTY |
| `native-controls` | feed the real serial wire stream into native AMY with the production 11-bus/336-oscillator configuration and inspect actual synth state | Linux PTY + pinned Gamma9001 LB AMY fork |
| `native-rhythm` | rhythm/sequencer scenarios against native AMY, including startup and live chord-instrument switching | Linux PTY + pinned Gamma9001 LB AMY fork in deterministic offline-render mode |
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
- Quick intentional taps must start and stop manual synth 3 immediately without
  changing effective chord activity or temporarily closing the
  automatic-chord lane. They do select the active chord and replace the
  corresponding strum, bass and automatic-chord pitches while transport keeps
  running.
- When Qt's `TapHandler` reports a platform-defined long press, the contact must
  enter the existing manual-hold takeover: future automatic child triggers are
  removed, already-running children retain their own note-offs, and release
  stops manual synth 3 immediately before reinstating the automatic chord lane. The backend must
  not run a second gesture-classification timer.

**Failure history:** earlier builds showed erratic repeated chord starts while
a chord was held. A backend release filter then hid spurious pointer events by
delaying some real releases by 450 ms. The unified Qt pointer grab makes that
filter unnecessary; release now follows the actual pointer-up directly.

**CHORD-03 — packaged QML input is portable across desktop targets**

- The package smoke must locate a real chord-key delegate in production QML
  and send pointer-down/up events through its `QQuickWindow`; calling
  `backend.pressChord()` directly is not an input test.
- A quick tap must select the chord, expose its blue active-border state, emit
  manual synth-3 note-on/off commands and leave no pressed chord behind.
- A contact held until Qt reports a long press must remain visually pressed,
  promote to the temporary accompaniment takeover, stop manual synth 3
  immediately on physical release, and restore the stored chord activity.
- The macOS job runs this test from the mounted final DMG. The Windows job runs
  it from the extracted final zip through the user-facing double-click
  launcher. Hosted pointer injection is deterministic package validation, not
  a substitute for testing a physical Mac trackpad or Windows touchscreen.

**Failure history:** the former package smoke loaded QML but invoked the
backend chord methods directly. It therefore passed while a physical macOS
installation failed to show or release chord-key interaction correctly.

### STRUM — strum input

**STRUM-01 — press/touch makes sound immediately**

- `strumStart()` must emit a note on finger/mouse down; a stationary press may not require a move event before producing sound.
- A sweep must not exceed the configured live voice count and must eventually release the tail.

**Failure history:** the strum area visibly accepted mouse/touch input but emitted no AMY commands/sound in an earlier AMY build.

**STRUM-02 — the OMNI note guide names the available strum tones**

- With an active chord, the narrow gap immediately left of the strum pad shows
  one vertically distributed light-blue round marker per available pitch
  class; with no active chord it shows none.
- APG uses the active chord intervals and LDR uses the ladder intervals that
  actually feed the strum gesture.
- Labels use uppercase note letters and musical enharmonic spelling. In
  particular, C minor is shown as `C`, `E♭`, `G`, not `C`, `D♯`, `G`;
  ordinary scales do not arbitrarily mix sharps and flats.
- Every chord suffix in `music/chords.csv` has an explicit audited LDR mapping,
  and every chord pitch class must occur in that mapping. Adding a chord without
  adding and testing its LDR mapping is an error rather than a silent fallback
  to a broad family rule.
- LDR may use a consonant subset of a conventional chord-scale because every
  available note is sounded mechanically. It omits avoid tones and opposite
  alterations unless the chord itself names them. G minor-major 7 therefore
  uses `G A B♭ D E F♯`, never F natural beside the defining F♯.

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

**MIDI-05 — screen masters are independent, bus-scoped and reversible**

- OMNI master writes final gain only to buses 0–3; MIDI master writes only to
  buses 4–10.
- `MUT` applies zero to the owned buses without changing the displayed master
  value; `UMT` restores that retained value.
- Changing a muted slider updates the value that will be restored on unmute.
- OMNI and MIDI master volume/mute state survive their own preset switches and
  cannot mutate one another.
- Reconfiguring a synth or rebuilding after panic reapplies the owning master
  gain so a patch cannot bypass it.

**MIDI-CC-01 — only genuine CC movement creates activity**

- Controller identity is `(channel, controller)`.
- The first value is a baseline and produces no indicator or mapped edit.
- Repeated identical values produce no activity.
- A later changed value creates/updates the indicator and its LRU timestamp.
- Raw running-status CC bytes must satisfy the same behavior.

**MIDI-CC-02 — visible capacity, LRU and outgoing animation**

- Indicators fill the calculated bar capacity from left to right.
- Refreshing an existing controller makes that controller newest.
- A new changed controller replaces the oldest eligible controller when full.
- The outgoing channel/controller remains visible in red for two flashes before
  the incoming identity is displayed.
- Red learn controls are never evicted. Blue controls are protected unless all
  slots are protected, in which case the oldest blue control leaves early.
- Green bindings may become invisible without losing their mapping; activity
  makes a hidden binding visible again when an eligible slot exists.

**MIDI-CC-03 — one-click indicator state transitions**

- Clicking an idle grey or manually unlinked blue indicator selects exactly one
  blinking red learn controller.
- Clicking another idle/blue indicator transfers red selection.
- Clicking a green indicator unlinks it and turns it blue; that click does not
  also start learn or replace another indicator's red learn selection.
- Clicking the red controller again cancels learn and turns it off.
- The OMNI screen mirrors red learn state without exposing controller details.
- Its red LED blinks to the right of the label inside the large `MIDI` button
  and is completely invisible when learn is inactive.
- The independent green binding-location LED remains left of the button label.

**MIDI-CC-04 — one-to-one binding and complete numeric target coverage**

- Touching a numeric target while red binds it and consumes that gesture.
- Instrument parameters, role/row and master volumes, both reverb sections,
  both tuning references, tempo, bass voicing and the riff selector are
  bindable; switches/selectors, including `MUT`/`UMT`, are not.
- One CC owns at most one target and one target owns at most one CC.
- Reassigning an occupied target turns the displaced controller blue.
- The target handle and bound controller LED are steady green.

**MIDI-CC-05 — range mapping and normal backend convergence**

- CC 0 and 127 reach the target minimum and maximum.
- Linear targets map linearly and logarithmic targets map across logarithmic
  visual slider travel, then round/clamp to catalogue range and step.
- Binding alone does not jump the value; the next genuine CC change applies it.
- Updates use existing setters and emit the same AMY wire state as manual edits.

**MIDI-CC-06 — deliberate manual unlink and blue expiry**

- The learning touch cannot unlink the new binding in the same gesture.
- Pressing and releasing a bound slider without changing its value does not
  unlink.
- The first value-changing mouse/touch drag event on a bound numeric target
  performs manual takeover: MIDI ownership is released before the UI value is
  applied and the previous controller becomes blue.
- The first increment/decrement on a bound click-only numeric control follows
  the same release-before-edit ordering.
- There is no separate double-click/double-tap unlink gesture.
- The controller becomes blue and visible when capacity permits.
- The next genuine CC movement changes a blue controller immediately into an
  ordinary grey unbound indicator. Without movement, blue expires and removes
  the indicator after 30 seconds.

**MIDI-CC-07 — hidden instrument targets reactivate on MIDI and OMNI**

- A synth-parameter target retains its row/role, instrument key and control key.
- Switching that row/role to another instrument does not delete the binding.
- Later mapped CC movement switches the MIDI row or OMNI role back to the bound
  instrument before applying its parameter.
- Tests inspect frontend state and delivered AMY commands after the switch.

**MIDI-CC-08 — screen-owned preset persistence**

- MIDI targets serialize only into the MIDI preset; OMNI targets only into the
  OMNI preset.
- Loading replaces only the selected screen's bindings and admits their
  indicators as capacity permits.
- Old presets without `midi_control_bindings` load normally with no bindings.
- Red/blue/visible-LRU state and current CC values are not serialized.

**MIDI-CC-09 — bound values survive RST and runtime preset switches**

- A section RST restores its preset instrument, unbound parameters and unbound
  volume, but preserves every bound parameter and bound volume value.
- Hidden instrument-specific bound values remain protected without selecting
  their instrument.
- Runtime preset selection protects the union of targets bound before the
  switch and targets stored in the destination preset.
- Startup loading may initialize all stored values normally.
- After reset or switching, genuine CC movement remains authoritative through
  the normal setter and AMY convergence path.

**MIDI-CC-10 — green binding has exclusive numeric authority**

- Manual slider/tap gestures and direct frontend setter actions cannot change
  any bound instrument control, role/row volume, master volume, reverb
  parameter, tuning reference, rhythm tempo, bass voicing or riff-selector
  value.
- Copy actions, RST and runtime preset selection preserve bound values while
  still applying their normal changes to unbound state.
- Bound rhythm tempo disables and greys both rhythm UP/DWN buttons.
- Bound effective tuning disables and greys both tuning UP/DWN buttons on the
  affected screen, or both screens while coupled.
- Recoupling uses a bound side as source and refuses two divergent,
  independently bound references.

**MIDI-CC-11 — rhythm transport symbol matches bass**

- The stopped rhythm button draws the same centered triangle geometry as the
  stopped bass button rather than a font glyph.
- A rhythm state change repaints the Canvas so play/stop state cannot become
  visually stale.

**MIDI-CC-12 — preset binding conflict has an explicit handoff**

- Given a CC bound to target A, when the destination preset assigns that same
  channel/controller pair to a different target B, the destination preset wins
  the one-to-one mapping immediately.
- The destination preset's stored numeric value for B, and for A when A belongs
  to the same preset screen, is authoritative; live bound-value preservation
  does not override those values for this conflict. The other preset screen's
  numeric state is not changed.
- For approximately two seconds A's handle flashes red and B's handle flashes
  blue using 110 ms fade halves. Both reject manual edits during this handoff.
- After expiry A is free with its normal handle color, B is steady green and
  bound, and genuine movement of the CC changes only B.
- An unchanged preset binding does not trigger the handoff and retains normal
  live-value preservation.

**MIDI-CC-13 — hidden bindings advertise their screen and preset location**

- Only genuine changed CC input can start location feedback; the first value
  and repeated-identical packets remain silent.
- The visible `MIDI`/`OMNI` mode button flashes whenever the binding is located
  on the other screen, whether it belongs to that screen's selected preset or
  to a non-selected preset. The mode button deliberately ignores preset status
  and means only "look on the other screen". Its green LED is left of the label
  in the red button area.
- If no active binding owns the controller, every valid non-selected preset
  containing its channel/controller identity is located without loading it.
  Its round preset button flashes a small green LED between the label and top
  edge when that screen is visible. Once the destination screen is visible, its
  selected preset needs no preset LED; an inactive destination preset does.
- Selected preset files are excluded from inactive lookup so unsaved live
  binding changes remain authoritative. If multiple inactive presets contain
  the identity, all matching locations are indicated.
- Feedback lasts approximately two seconds and restarts on fresh movement. It
  never selects a preset, changes screen, applies the inactive preset's value,
  or changes musical state.

**MIDI-CC-14 — hardware button takeover is scoped**

- MIDI CC-style button controls and pitch/note-style hardware controls that
  are explicitly treated as controller buttons may bind to supported app
  buttons. Ordinary musical Note On/Off input must never create controller
  button indicators or bindings.
- A held on/off hardware button owns only its target's logical button group.
  Preset choices block other preset choices, activity choices block only their
  own activity row and arpeggio-rate choices block only other arpeggio-rate
  choices. Independent toggles block only their exact screen button.
- Tap-only actions, including panic, store-preset and cycle-channel, trigger on
  press but do not create held takeover state. Unrelated screen buttons remain
  usable while any hardware button is held.

Unit tests cover the state machine and mapping math. Headless frontend tests use
simulated user actions plus simulated MIDI CC input and inspect state, preset
JSON and AMY output. The offscreen Qt test feeds real raw-MIDI bytes, records
JSONL indicator/layout state and verifies the replacement transition fits the
actual bar.

### OSC-CTRL — portable OSC controller input

**OSC-CTRL-01 — configured UDP input and source identity**

- The shipped configuration enables OSC on `0.0.0.0:8000`; both address and
  port are editable and no consumer fallback duplicates them.
- Removing the complete endpoint (or disabling OSC) opens no socket and omits
  OSC from the input-technology row.
- A valid OSC 1.0 UDP message or bundle is decoded off the Qt thread. Each
  numeric argument is identified by exact address and zero-based argument
  index, reaches the Qt thread once and preserves packet order.
- Malformed packets and unsupported argument types create no indicators and do
  not stop the listener. Bind failure is reported as failed rather than ready.

**OSC-CTRL-02 — common learn and ownership state**

- A changing normalized OSC value appears in the same grey capacity/LRU bar as
  MIDI, labelled with its address and argument index.
- OSC uses flat F01 rotary/pushbutton visuals; MIDI remains F06. F01 contains no
  virtual light, highlight or shadow effect.
- Grey/blue/red/green click behavior, target learning, manual takeover, blue
  expiry, hidden binding behavior and button takeover exactly match MIDI.
- MIDI and OSC share global one-to-one ownership. Binding an OSC source to a
  MIDI-owned target displaces the MIDI source to blue, and vice versa.
- The MIDI input-technology row contains one `OSC` item for a configured
  endpoint. Its LED is green while listening, flashes green on accepted data
  and turns red on bind failure or loss of the configured network.
- The OMNI rainbow button says `OSC` above `MIDI`; its existing red learn and
  green binding-location LEDs represent both protocols without duplication.

**OSC-CTRL-03 — mapping and preset compatibility**

- Numeric `0.0..1.0` maps over the target's complete declared range and calls
  the existing target setter/AMY convergence path. OSC never calls AMY itself.
- Boolean or endpoint-only control messages can drive application buttons;
  zero is released and any positive normalized value is pressed.
- OSC bindings persist by address/index/type inside the existing screen-owned
  binding list. Existing MIDI binding JSON round-trips byte-for-shape without
  acquiring OSC fields.
- All five release packages install and exercise `python-osc`; startup and
  package tests retain the separate wire-only frontend/AMY process boundary.

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
- Dragging a synth-parameter slider must not republish/reset the QML
  `Repeater` control-list model on every movement. The live edit still updates
  backend state and AMY immediately, but the active delegate must keep Qt's
  pointer grab until release.
- Mouse and touchscreen drags use the same native Qt Slider path. During every
  move and after release, `Slider.value`, the custom handle and the filled track
  must remain aligned with the value accepted from that gesture, even when the
  live backend intentionally leaves the QML model at its previous value.
- A later external backend update remains authoritative and synchronizes all
  three visual/value representations.

**Failure history:** Sustain had a range of `-1..1`, placing 0 halfway along the
control; negative values also caused the numeric text to disappear. After the
shared slider primitive was consolidated, release always restored its backend
binding. Synth-control live edits intentionally suppress model publication to
preserve the pointer grab, so a macOS mouse edit could reach the backend while
the visible handle/fill returned to an old value. Tests that asserted only the
emitted/backend value did not detect that visual regression.

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

**PRESET-04 — a sounding chord survives an OMNI preset switch**

- Active row/root identity, chord-gate state and physical button-hold tracking
  are live performance state rather than preset state.
- Selecting another OMNI preset preserves that state and republishes the
  sounding chord using the destination preset's chord type, octave, inversion,
  tuning and chord instrument.
- A chord held across the switch remains releasable by the original button-up;
  the preset load may not turn that release into an ignored/stale event.
- Runtime preset selection uses the live convergence path even while rhythm is
  stopped; the startup/recovery reset path is not a preset-switch operation.

**PRESET-05 — APG/LDR is OMNI preset state**

- Store writes the backend-owned strum traversal mode as `strum_mode`.
- Selecting another preset updates both strum behavior and the APG/LDR button.
- A legacy preset without the field loads as APG.

**PRESET-06 — reverb level range is 0–3**

- Both OMNI and MIDI sliders, backend clamps and MIDI CC mapping expose the
  complete `0.00..3.00` range.
- Setting or mapping the maximum sends reverb level 3 to each owned melodic
  bus; drum inclusion keeps its existing independent behavior.

### RHYTHM — sequencer invariants

**RHYTHM-00 — drums, bass and automatic chords use independent AMY tag ranges**

- Current AMY stores exactly one sequencer entry per user tag; reusing a tag replaces that entry, and `H0,0,<tag>` clears only that entry. Multiple simultaneous events therefore require distinct tags.
- The application reserves non-overlapping ranges sized from the complete rhythm catalogue: drums 0..55, bass 56..111 and automatic chords 112..251. Tags 252..255 remain unused.
- Stored patterns reserve 0..935 for fills, 936..999 for automatic-chord
  one-shots and 1000 upward for base drum roles. The current chord bank needs
  at most 58 definitions and the complete overlap audit reaches 30 of 32
  active instances.
- Every scheduled wire body owns deterministic lane tags. Exact circular
  repetitions may share one shorter-period tag only when expanding that tag
  reproduces the complete original tick/body set.
- Holding/releasing a manual chord clears/reinstalls only the automatic-chord range; bass and drums keep running and transport remains started.
- Bass on/off, bass retuning and riff selection replace only the bass range.
  The largest current riff uses 34 of its 56 tags. Tuning/chord pitch changes
  may replace both bass and automatic-chord ranges but must not touch
  percussion or stop transport.
- A live rhythm-style or preset change must preserve tempo, all three activity
  values, chord-arpeggio mode/rate/direction, bass voicing, the active-row
  octave and sequencer timebase. It may replace tagged pattern events but may
  not stop/restart transport or issue `RESET_SEQUENCER`.

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

**RHYTHM-06 — manual chord input lets the current automatic chord finish**

- Finger-down immediately starts manual synth 3 and selects the new active
  chord for strum, bass and future automatic-child definitions. An already
  running child keeps its immutable old definition and release.
- Every real finger-up immediately stops the manual synth-3 voice, including a
  release shortly after hold promotion. Its release is neither delayed by a
  dropout-grace timer nor quantized to rhythm. A tap must not change effective
  chord activity or close the automatic-chord lane.
- If Qt reports a long press using its platform style hint, hold promotion
  suppresses the effective automatic-chord lane without changing the `CHORD
  ON/OFF` state or sending an immediate `l0i4`.
- Future synth-4 `zQT` root triggers are cleared. Root tags own no release;
  every currently sounding whole-chord or single-note child executes its own
  original `l0` event and completes the configured gate.
- No later automatic-chord note-on may occur while the manual chord is held.
  The lane is reinstalled on release.
- Drums, bass, transport and sequencer timebase continue without a stop,
  restart or reset. The manual synth-3 chord may overlap the remaining gate and
  normal release of synth 4.

**Failure history:** manual chord input set chord activity to zero and cleared
the tagged chord lane, including the scheduled note-off for a chord which was
already sounding. The old synth-4 chord could then remain audible indefinitely
under the new manual chord. The first correction added an immediate `l0i4`;
that prevented hanging but audibly shortened the accompaniment gate. A later
arpeggio implementation exposed a second form: finger-down rewrote the lane to
new pitches before hold promotion, so one old pitch-specific release could be
replaced and one arpeggio note remained indefinitely. The final design moved
release ownership into immutable `ONE_SHOT` children. The serial regression
proves that hold promotion clears only root triggers and emits no immediate
`l0i4`.

**RHYTHM-07 — live preset changes preserve beat-shaping controls**

- With rhythm stopped, preset selection loads stored tempo, percussion
  activity, chord activity, chord-arpeggio mode/rate/direction, bass activity,
  bass voicing, riff selector and all chord-row octaves.
- With rhythm running, preset selection preserves the effective values of the
  tempo, all three activities, chord-arpeggio controls and bass voicing. A
  compatible playing riff is preserved by stable ID and the selector follows
  its new position; otherwise the destination preset/default selector is used.
- The octave of the active chord row is also preserved. Every non-active row
  loads its octave from the destination preset.
- The destination rhythm pattern may change, but transport and sequencer
  timebase remain continuous.

**RHYTHM-08 — CHORD ON/OFF controls only sequencer chords**

- The control starts OFF, is usable before a chord is selected and retains its
  own state when any chord button is pressed or released.
- Its label reports the current state rather than the next action: `CHORD ON`
  means sequencer chords are enabled and `CHORD OFF` means they are disabled.
  ON uses the selected chord-activity colors; OFF uses its unselected colors.
- `CHORD OFF` removes future automatic synth-4 onsets while preserving the
  sequenced release of a currently sounding automatic chord.
- `CHORD ON` reinstalls automatic synth-4 events without playing the remembered
  chord once on manual synth 3.
- Neither action releases a chord which is physically held on a chord-button
  row. That manual synth-3 voice ends only through its normal button release.

**RHYTHM-09 — chord and bass activity add equal-width fifth columns**

- Chord activity fills the yellow bar height with two five-button rows. Upper
  `1..4` retain the old exclusive onset selection and upper-right `A` toggles
  arpeggio mode independently. Lower `/1..4` are exclusive and lower-right
  toggles `U` (idle/up) and `D` (selected/down).
- Bass activity retains that button size and adds a fifth `R` button. The bass
  and chord groups become wider and the tempo slider narrower.
- Chord activity has no zero button. `CHORD OFF` is the only user-facing way
  to disable automatic sequencer chords.
- While a manual chord suppresses the automatic lane, no chord-activity button
  is selected. Releasing it restores the unchanged 1–4 selection.
- A legacy preset containing chord activity 0 loads as level 1.

**RHYTHM-10 — R selects independent, live-transposed bass riffs**

- Selecting `R` changes `bass voicing` into a discrete `riff selector` whose
  `1..N` range is the stable catalogue order for the current rhythm ID and exact
  chord suffix. Levels 1–4 restore the voicing slider and simple bass patterns.
- A riff uses only its own 96-PPQ ticks, durations, pitches and velocities; it
  is never generated from or quantized to `rhythms.json` `bass_levels`.
- C2-normalized pitches transpose by the active chord root and use normal OMNI
  tuning. A root change alters pitch but not timing, duration or velocity.
- If a playing riff remains compatible after an available-set change, its ID is
  retained and the selector follows its position in the new set. Otherwise the
  preset selector, or the application default for legacy presets, is used.
- Riff selector changes replace only bass tags and never stop/reset transport
  or edit the percussion/automatic-chord ranges.

**RHYTHM-11 — A selects complete circular chord arpeggios**

- With `A` off, automatic whole chords and upper activity `1..4` behave exactly
  as before; the lower row remains editable but has no musical effect.
- With `A` on, each existing chord onset launches every note in the active
  chord voicing at `/1`, `/2`, `/3` or `/4` notes per beat. `U` plays low to
  high and `D` high to low. A new onset may overlap an unfinished arpeggio.
- Note and release ticks wrap across the repeating period. A four-note maj7 at
  `/1`, starting only at beat 1 of a four-beat measure, therefore starts notes
  at beats 1, 2, 3 and 4 and repeats from beat 1.
- The tag audit expands every compacted period and proves exact timing for all
  catalogue rhythms, activity levels, rates and 2–7-note chords. Root tags
  launch short one-shot children; the worst arpeggio uses 42 of the existing
  140 chord tags.
- The real serial test proves a seven-note dominant-13 chord is sent in both
  directions using only tags 112..251. Disabling `A` restores the old four-note
  whole-chord limit. Arpeggio changes never touch drums, bass, transport or
  sequencer timebase.
- Both manual and automatic chord synths require seven voices. Config revision
  1 migrates only the former shipped `rhythm_chord: 4` default to 7 while
  retaining other user overrides; startup validation rejects smaller custom
  pools instead of silently allowing voice stealing to truncate an arpeggio.
- `/1..4` use disjoint child-pattern families. The `/2 -> /4` serial regression
  proves that `/2` children own a 17-tick release, `/4` children own a 9-tick
  release and the switch does not rewrite any `/2` definition. The exhaustive
  instance audit includes every overlap, all current drum roles and one fill;
  its worst case is 30 of the configured 32 instances.

**RHYTHM-12 — cold Start plays the visible percussion level immediately**

- With a fresh application and rhythm stopped, press Start without touching a
  percussion activity button first.
- The backend sends the reset, waits until it has crossed an AMY audio-block
  boundary, creates the visible level's loop at tick zero and starts transport.
- The native PTY bridge applies the queued sequencer reset and, for a timebase
  reset, its deferred second block boundary before accepting later serial
  commands. This models the independently running production audio callback
  without making the regression depend on CI thread scheduling.
- Native CI compiles the same Gamma9001 PCM bank as the hosted packages and
  proves its registration and linked-data symbols. ESP32-P4 is a separately
  declared Tiny-bank target.
  AMY runs with `audio=False`, so only the bridge's explicit renderer advances
  engine time or consumes samples; no ALSA/miniaudio callback races the test.
- The native regression requires non-silent rendered drum audio within one
  second. A one-bar delay or a required activity reselection is a failure.

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

**UI-02 — public screenshots render the current real interface**

- `capture_screenshots.py` runs the production QML scene offscreen with an
  isolated temporary home and writes `screenshots/omni.png` and
  `screenshots/midi.png`.
- The OMNI frame shows an active C-minor strum-note guide; the MIDI frame shows
  three representative CC knobs in the grey lower bar.
- Release refreshes store timestamped screenshot files such as
  `screenshots/omni-RYYYYMMDDTHHMMSS.png` and update the repository README to
  embed those files. Screenshot refreshes may not use a hand-drawn or generated
  substitute for the actual Qt interface.
- Before README assets are committed, the generated PNGs must load at the
  expected 1920x850 size and must have enough sampled color variation to reject
  a blank or obvious error screen.
- The capture helper continuously drains the pseudo-serial endpoint, so the
  complete startup wire stream cannot block its writer while large rhythm and
  fill libraries are installed.
- A successful `main` release captures the exact released commit. CI commits
  only `README.md` and the new release-tagged screenshot PNGs. That
  screenshot-only commit uses a human-readable `skip-rebuild` note plus
  GitHub's required `skip-checks:true` trailer, so ordinary merges and pushes to
  `main` still rebuild while screenshot refreshes do not create a release loop.

**UI-03 — instrument names contain useful names only**

- Curated names must not acquire redundant `PATCH` suffixes or unwanted generic engine prefixes in the visible label.

**Failure history:** labels previously appeared with unwanted Juno/DX7 prefixes and later a `PATCH` suffix.

**UI-04 — bass function slider aligns with bass activity**

- The `bass voicing` / `riff selector` slider and the five bass-activity
  buttons use the same horizontal column origin and width.
- The layout contract references the shared `bassColumnX`; it may not reuse
  the obsolete four-button activity width.

## Proof produced by CI

For serial/native suites, failures must preserve artifacts containing:

- frontend logical/AMY command log;
- exact serial lines received from the PTY;
- pinned LB Omnichord AMY fork commit SHA/version;
- native AMY `dump_state()` output;
- native synth-state readback for synths 3 and 4 at relevant checkpoints;
- application stdout/stderr and native bridge diagnostics.

Passing a native test therefore means not merely "the expected command was written" but "the supported 11-bus AMY runtime accepted the real serial wire stream and its readback state satisfies the invariant". CI pins the fork by commit and stores that commit in the test artifact; dependency updates are deliberate rather than silently following an upstream branch.
