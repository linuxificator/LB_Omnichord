# Codex implementation handover — LB Omnichord to SuperCollider

Prepared 2026-09-13. Implementation specification, not an implemented or audio-tested migration.

The requested outcome is one Omnichord whose sequencing, synthesized instruments, multisample playback, musical note ownership and audio mixing run in SuperCollider. Preserve the existing Qt instrument, rhythm library, MIDI integration and performance gestures. Include all 109 SCLOrkSynths definitions, the complete VSCO 2 Community Edition bank, the additional banks below, and several acid-bass voices with proper accent, slide and tie semantics.

This document is deliberately in English for direct use as a Codex task. `MUST` is a release requirement. `Proposed` filenames, classes and OSC addresses describe code to create; they are not existing SuperCollider APIs. Source findings and design decisions are distinguished throughout. The catalogs appended below are part of the specification.

## 1. Starting point and non-negotiable decisions

### 1.1 Exact source baseline

| Component | Verified revision | Entry point |
| --- | --- | --- |
| LB Omnichord | `955cbbfa3b8fd805e84ecca1be7d5cb46aaf84b4` | [Repository](https://github.com/linuxificator/LB_Omnichord/tree/955cbbfa3b8fd805e84ecca1be7d5cb46aaf84b4) |
| Modified AMY actually pinned by Omnichord | `5e3cd575fc744b9a0cd3e9014030acc7bf4dc5c2` | [Fork](https://github.com/linuxificator/amy/tree/5e3cd575fc744b9a0cd3e9014030acc7bf4dc5c2), [sequencer.c](https://github.com/linuxificator/amy/blob/5e3cd575fc744b9a0cd3e9014030acc7bf4dc5c2/src/sequencer.c) |
| SuperCollider | release `Version-3.14.1`, commit `426edf6d8742e1cc3bd85b51ca0c4e595d37a903` | [Release](https://github.com/supercollider/supercollider/releases/tag/Version-3.14.1) |
| SCLOrkSynths | `6730c745971aa45c95d9b4cddfb4d5ca342774b3` | [109 definition files](https://github.com/SCLOrkHub/SCLOrkSynths/tree/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs) |

Use the specified commits for characterization fixtures. Before implementing against a newer LB branch, compare its executable code and tests with this baseline and record the differences. Do not silently replace the pinned AMY fork with upstream AMY or the current tip of the fork.

The root `CODEX_HANDOFF.md` is older than several source files: its statement that the TB-303 voice is not yet implemented is stale. At this baseline, `qt_frontend/code/tb303.py`, `design/music/tb303.md` and the bass gesture compiler contain an implementation. The current bass library has 1,664 riffs. Current implementation/tests/configuration outrank older handoff prose.

### 1.2 Chosen architecture

1. Keep Python/Qt responsible for UI, MIDI/OSC input, musical selection policy, validated catalogs, preset storage and compiling immutable musical plans.
2. Run a headless `sclang` process for one `TempoClock`, immutable definition storage, pattern execution, musical gates, voice handles, sample selection and resource management.
3. Run `scsynth` as the audio process for SynthDefs, sample buffers, buses and effects. The supervisor owns both processes; the UI does not boot servers or import audio-engine implementation modules.
4. Use stock SuperCollider synthesis and a native SuperCollider multisampler with an offline, source-specific bank compiler. Do not require Kontakt, Sforzando, Muse Sounds, a DAW, Surge or a separate sampler process. SFZ is an import format, not something stock `scsynth` plays automatically.
5. Keep the existing public control addresses at the UI-facing adapter boundary. Introduce a versioned, typed internal OSC protocol to `sclang`; do not translate AMY wire strings at runtime.
6. Keep 48-PPQ-equivalent timing for the migration acceptance baseline. Original 96-PPQ catalog data remains untouched. SuperCollider represents times in beats; preserve the existing per-source floor/round rules when compiling. Increased resolution is a subsequent musical change, not an accidental migration side effect.
7. Preserve the current conservative bass drain handover first. Node-specific ownership removes its old all-notes-off hazard, but does not authorize changing musical phrase-switch timing without an explicit later change.
8. Improve acid articulation deliberately: support accent on a slide destination without retriggering the amplitude envelope. This is a documented improvement over the current AMY limitation.

### 1.3 Platform and completeness boundary

Target Linux x86_64 and Raspberry Pi aarch64 first, then macOS arm64 and Windows x86_64. Use the same SC engine sources and musical tests on all four. A full-bank workstation profile starts with a **proposed 16 GB RAM target**, subject to measured working-set admission; this is a sizing choice, not a measured minimum. Pi profiles must be measured separately, including the existing Pi 4 / 2 GB device. Full banks stay on disk even where fewer heavyweight programs can be simultaneously resident.

The present ESP32-P4 AMY firmware cannot be replaced by this desktop `sclang`/`scsynth` design. Android also needs its own SC embedding/packaging work; its existing AMY/Oboe packaging does not prove SC support. Keep those existing artifacts available as legacy releases and state their status explicitly. Do not claim all-platform migration completion while they still use AMY. An ESP32 may remain an input controller sending commands to a Linux/Pi SC host; that is a deployment option, not SC running on the ESP32.

The requested broad sound library must not be reduced to a tiny GM soundfont or one velocity per instrument. “Complete” means all source recordings, velocity layers, round robins, sampled articulations, releases and microphone choices in the selected banks are accounted for. It does not mean every upstream GUI preset, effect-only variation, duplicate keyswitch wrapper or duplicate audio file must become a separate browser item.

## 2. Repository reading and change map

Paths in this section are relative to the LB repository. Work in `amysynth_version`; the Sonic Pi tree is frozen history. Read root `AGENTS.md` first. Do not rename the active tree during the engine migration: it would obscure the behavioral diff.

| Existing path | Required use / migration action |
| --- | --- |
| `amysynth_version/design/README.md` | Documentation precedence and required architecture reading |
| `amysynth_version/design/arch/{principles,architecture,behavior,testing}.md` | Preserve ownership, composition, packaging, screen behavior and testing contracts; update for SC |
| `amysynth_version/design/music/{sequences,rhythm,bass_handover,bass_riffs,tb303,tuning}.md` | Musical requirements, including running/stopped precedence and immutable gestures |
| `amysynth_version/design/amy/sequencer.md` | Old engine semantics to characterize |
| `amysynth_version/qt_frontend/docs/SEQUENCER_TAGS.md` | Exact old lane namespaces and transport lifecycle |
| `amysynth_version/qt_frontend/code/main.py` | Sole production composition root; inject SC client and engine services here |
| `amysynth_version/qt_frontend/code/app_core.py` | Startup/UI assembly; retain dependency injection |
| `amysynth_version/qt_frontend/code/amy_transport.py` | Extract musical configuration policy; replace wire construction and timed note-off ownership |
| `amysynth_version/qt_frontend/code/rhythm_command_plan.py` | Refactor pure compiler to typed events; keep old compiler as test oracle during migration |
| `amysynth_version/qt_frontend/code/bass_riffs.py` | Keep selection, harmony matching, transposition and stable riff IDs |
| `amysynth_version/qt_frontend/code/tb303.py` | Preserve parameter semantics; replace engine-specific voice commands |
| `amysynth_version/qt_frontend/code/performance_backend.py` | Preserve tap/hold, chord, strum and transport policy |
| `amysynth_version/qt_frontend/code/midi_player.py` | Replace `MidiAmyEngine` and its direct `_wire` calls; retain MIDI UI/routing/binding semantics |
| `amysynth_version/qt_frontend/code/musical_state.py` | Keep tuning calculation and immutable tuning snapshots |
| `amysynth_version/qt_frontend/code/{synth_programs,synth_state}.py` | Add stable SC/sample program identities and versioned parameter metadata |
| `amysynth_version/qt_frontend/code/{transport_scheduler,transport_sinks}.py` | Reuse delivery ownership concepts; no musical clock here |
| `amysynth_version/qt_frontend/code/{gm_percussion,midi_levels,shared_reverb}.py` | Preserve roles/GM semantics; replace AMY-specific gain/effect mapping |
| `amysynth_version/qt_frontend/config/amy_config.json` | Existing physical capacities and IDs; migrate into engine-neutral configuration plus SC settings |
| `amysynth_version/qt_frontend/music/` | Preserve all rhythms, fills, riffs, schemas and provenance; do not regenerate music to hide bugs |
| `amysynth_version/qt_frontend/packaging/release_inputs.json` | Single release-input authority; add exact SC and bank manifest revisions |
| `amysynth_version/qt_frontend/tests/USE_CASES.md` | Preserve all relevant executable use cases |
| `amysynth_version/qt_frontend/tests/run_tests.py` | Keep single local/CI runner; add SC suites here |

New code layout (proposed):

| New path | Responsibility |
| --- | --- |
| `amysynth_version/qt_frontend/code/engine_protocol.py` | Frozen DTOs, schema validation and transport interface; no Qt/audio imports |
| `.../code/musical_sequence_plan.py` | Pure musical compiler using typed actions and legacy timing normalization |
| `.../code/supercollider_client.py` | Delivery, ACK/retry, coalescing, health and session handling |
| `.../code/midi_engine.py` | Engine-neutral MIDI note/program/bus commands |
| `.../code/instrument_catalog.py` | Immutable catalog with source/provenance/controls/articulations |
| `amysynth_version/supercollider/bootstrap.scd` | Deterministic headless startup and handshake |
| `amysynth_version/supercollider/Classes/Omni{Protocol,Registry,Coordinator,Voices,Sampler,Buses}.sc` | Application-specific SC classes; use a dedicated class-library configuration |
| `amysynth_version/supercollider/SynthDefs/` | Reviewed 109 adapters, native sampler definitions, acid voices and mixer |
| `amysynth_version/supercollider/vendor/SCLOrkSynths/` | Unmodified pinned upstream source plus license; never auto-run demo material |
| `amysynth_version/tools/banks/` | Download, verify, inspect, normalize, deduplicate and render catalog tools |
| `amysynth_version/assets/manifests/` | Small committed bank locks, mapping manifests, selection decisions and checksums |
| `amysynth_version/tests/supercollider/` | SC unit/trace/NRT fixtures driven by the existing frontend runner |

Expand `.../code/` as `amysynth_version/qt_frontend/code/`. These paths do not yet exist. Do not leave two competing production rhythm-policy implementations after cutover.

## 3. What must remain musically identical

### 3.1 Independent musical parts and routing

| Old synth identity | Musical part | Logical stereo bus |
| --- | --- | --- |
| 0 | OMNI percussion | 0 |
| 1 | OMNI bass | 1 |
| 2 | OMNI strum | 2 |
| 3 | Manual held chord | 3 |
| 4 | Automatic chord/arpeggio | 3 |
| 5–10 | Six independent MIDI instrument rows | 4–9 |
| 11 | MIDI drum part | 10 |

Keep these as logical IDs for compatibility, **not scsynth node IDs or raw audio-bus indices**. Allocate 11 stereo `Bus.audio` objects and maintain an explicit mapping. Each musical note receives its own server node/voice handle. Manual and automatic chords share a mix bus but have distinct ownership groups. Stopping automatic chords must not cut the manual chord.

There are separate OMNI and MIDI reverbs. OMNI buses 0–3 feed one room; MIDI buses 4–10 feed another, with the current MIDI drum-send toggle. Place source groups before channel-strip/send groups, then reverbs, then master mix/limiter. Preserve per-role, per-instrument, row and master volume factors. Recalibrate engine-specific factors instead of copying AMY's acoustic calibration numbers blindly.

### 3.2 State precedence

- Stopped: selecting a preset/rhythm applies its stored defaults according to existing policy. It does not implicitly start playback.
- Running: preserve live transport continuity, tempo and the current live performance settings that existing tests preserve. A rhythm/preset change must not reset the clock, insert silence or revert to stored tempo. Retain compatible riff selection by stable ID; selecting an incompatible suffix/riff is a phrase change.
- Tempo changes alter `TempoClock.tempo` in beats/second (`BPM / 60`) without resetting phase. Preserve existing CC ownership/locks.
- Screen changes are display-only. OMNI and MIDI preset banks remain independent.
- Hold/tap behavior remains in Qt gesture handling. Held manual chord attacks immediately; automatic chord parent suppression does not destroy already-started arpeggios. On release, restore automatic behavior according to current CHORD state.
- CHORD ON/OFF controls future automatic child launches. Ordinary release of a held manual chord addresses only that manual chord's handles.
- Fill selection order, density and allowed start-beat rotation follow `fill_occurrences` exactly. The density options remain 32, 16, 8, 6, 4, 3, 2 and 1 bars. Do not replace them with powers of two.
- Percussion activities are selected complete alternatives, not cumulatively enabled runtime layers. Preserve the actual catalogs/UI mapping rather than normalizing them to a new four-layer scheme.
- Bass activity gain `1.4` before clipping, and TB-303 activity velocity quantization to 127 steps, are part of the baseline compiler behavior.

### 3.3 Tuning and note identity

Continue calling the existing `tune_note` logic with the current OMNI or MIDI `TuningSnapshot`; preserve EQ/HARM/JV, reference pitch and coupling behavior. Do not round fractional pitches to MIDI integers. For a sampled or synthesized pitch use its tuned frequency. Global 14-bit pitch bend remains a separate continuous multiplier; it must not rebuild definitions or mutate reference tuning.

New `noteOn` returns/records an application handle such as `(session, owner, gesture, ordinal)` mapped to server node IDs. A later release uses that handle, never a fresh pitch lookup. Repeated notes of equal pitch in independent gestures and old/new harmony can coexist without one release killing the other. Preserve the current MIDI input retrigger policy: `MidiAmyEngine.note_on` first releases the previous active note for the same `(row, channel, source_note)`, then stores the new one. Its SC equivalent stores the new handle, not only a frequency; note-off releases that handle. Do not accidentally switch this input policy to an unlimited same-key stack just because SC supports polyphony.

### 3.4 Manual, strum and MIDI timing details

Preserve one active manual chord voice ID: a new manual start releases the old manual chord's handles and installs the new ID/notes. An update or stop for a stale ID is ignored. Map the active ID to its group of owned note handles, so its release cannot affect automatic chords or a later manual touch. Preserve the current manual-chord restoration on relevant program changes instead of leaving held UI state silent.

`_strum_note_on` currently releases an existing note at the same rounded MIDI key before retrigger, releases the oldest note when the configured strum voice limit is reached, and restarts one **idle-tail deadline** after every new strum note. That deadline releases all remaining strum notes after `performance.strum_tail_ms` since the last strum input. It is not a separate fixed-duration timer per note. Preserve this behavior using an SC-owned owner token and seconds-based deadline; stale deadline callbacks must be no-ops. Use exact handles for release while retaining the old rounded-key duplicate-selection policy.

MIDI preview has its own per-row active-note/idle-tail ownership and preview capacity. It must not consume OMNI strum handles or accidentally share its deadline. Keep current MIDI channel assignments, sustain/binding behavior and six row identities. Move musical release scheduling out of `application_scheduler` only after these concrete semantics have been ported; UI activity indicators and tap/hold recognition may still use their normal UI timers.

## 4. AMY-to-SuperCollider sequencer contract

### 4.1 Translate semantics, not wire syntax

| Existing operation | Observed AMY behavior | SC implementation contract |
| --- | --- | --- |
| `HR<tag>Z` | Clear the definition used by future starts; active executions retain their old definition | Publish a new immutable registry revision; old executions hold references |
| Repeated `H<tick>,<period>,<tag><payload>Z` | Cumulative append; period 0 is finite, nonzero event periods may differ | Construct a complete validated `Definition` off-line, then publish once |
| `HC<tag>,1,<alignment>Z` | Start another independent execution, capturing the definition when the start control executes | Allocate a unique execution ID and hold that snapshot, including during alignment-pending time |
| `HC<tag>,0,<alignment>Z` | Stop executions of that tag at boundary; stopping a parent does not recursively stop independent children | Stop root production; leave already-started finite gestures/release ownership alive |
| `HC<tag>,2,<duration>,<alignment>Z` | Suppress regular events in currently affected executions; controls still run; consumed events are not replayed | Use event-kind-aware musical gates, as specified below |
| aligned stop/publish/start replacement | Latest matching pending replacement can replace a not-yet-started slot; ordinary repeated starts still overlap | Replacement tickets coalesce; explicit launches never coalesce |
| timebase reset | Clear execution timing, retain preloaded definitions | New transport epoch, fresh clock origin, retained registry/buffers |
| full sequence reset | Clear definitions and executions | Engine/session reinitialize, only during explicit full reset/reconnect |

AMY's present capacities are 1,280 tags, 64 events/definition and 40 simultaneous or pending executions. These are compatibility fixture bounds, not desirable SC storage limits. The new runtime must handle at least the current maximum workloads; start with a configurable 256 active finite-execution budget and bounded event storage, then measure. Capacity exhaustion is a visible error with a trace, never a silently missing release.

An important precision point: AMY gating is not inherently a universal “note-on only” operation; it suppresses its regular payloads, which could include note-offs. The current fill design applies it to drum-role sequences containing hits. The SC implementation intentionally generalizes the **musical intent** safely by classifying actions.

### 4.2 Canonical immutable data

Proposed Python/SC schema:

```text
Definition {
  id: stable string, revision: positive integer, kind: root|finite,
  lane: string, periodTicks: integer or 0, ppq: 48,
  events: ordered immutable Event[], maxEndTick: integer,
  sourceIdentity: immutable musical identity
}
Event {
  tick: nonnegative integer, ordinal: nonnegative integer,
  kind: launch|gateBegin|rootStop|rootStart|noteOn|noteOff|voiceSet,
  payload: kind-specific validated fields
}
Execution {
  id, definitionSnapshot, startBeat, transportEpoch,
  nextEventIndex, ownedVoiceHandles, rootTicket,
  status: pending|running|complete|cancelled
}
```

All cyclic root events are expanded over their exact finite common period during pure compilation. Preserve event multiplicity and stable equal-tick ordering; only deduplicate where the old `compact_repeating_events` does so. For mixed periodic events use the LCM, with a validated storage ceiling and explicit error for unreasonable expansion. Current catalogs fit; do not invent an unbounded LCM operation for user input.

Use string IDs such as `root/bass`, `bass/gesture/00`, `root/chords`, `chord/velocity/03`, `drum/role/snare`, `fill/<rhythmId>/<fillId>`. Keep old tags only in trace/provenance to compare behavior:

The initial authored nesting limit is root → finite child (two execution levels); reject authored child-to-child recursion and cycles. The internal bass handover controller is a lifecycle control mechanism, not an authored third nested phrase level. Keep its scheduled root stop/start actions outside the ordinary phrase nesting validator, with their own bounded ticket lifecycle. Do not silently enable unbounded recursive scheduling.

| Old tag range | New identity family |
| --- | --- |
| 0, reserved 0–55 | fill-launch root |
| 56 | bass root |
| 57–110 | bass finite gestures |
| 111 | bass handover controller |
| 112, reserved 112–251 | automatic chord root |
| 252–255 | unused/reserved |
| 256–1191 | persistent fill definitions; current use 256–525 = 270 fills |
| 1192–1255 | chord children grouped by velocity |
| 1256–1279 | drum-role roots |

### 4.3 One native clock, explicit same-beat ordering

Use **one `TempoClock`**. `Pseq`/`Prout` can produce each definition's events and delta times. A small application coordinator merges these streams and applies the musical action semantics. It is not a second wall-clock, Python scheduler or 48-times-per-beat polling loop. Schedule only the next due beat using `TempoClock.schedAbs`; record execution state exclusively inside `sclang`.

Do not rely on unspecified equal-time ordering among independent `Ppar` players. At each due logical beat:

1. Apply scheduled replacement/stop tickets and gate controls.
2. Expand due root/child-launch control events, resolving child snapshots; process any newly exposed same-beat controls to a bounded fixed point.
3. Process explicit note-offs for existing handles.
4. Apply existing-voice continuation controls, then new note-ons that survive gates.
5. Emit one ordered OSC bundle for audio actions at that logical beat plus server latency.
6. Advance all consumed streams, including suppressed events, and schedule the next due head. Remove completed finite executions only after their last control/release event has been processed.

Use a stable sort key `(beat, phase, creationOrdinal, eventOrdinal)`; same-kind source order is preserved. Stops/gates precede sound because the AMY fork explicitly has a control pass before a regular-event pass. A child launched at this beat may sound at this beat; never insert one extra beat/tick by using a generic asynchronous `play` call.

Implementation sketch (algorithm, **not executable SC code**):

```text
onWake(ticket, dueBeat):
    if ticket != currentWakeTicket or epoch != currentEpoch: return
    due = consumeAllStreamHeadsAt(dueBeat)
    while due contains controls:
        apply controls in stable order
        add tick-zero heads of newly launched children to due
        enforce finite same-beat control-expansion budget
    audio = releaseExistingHandles(due.noteOff)
    audio += continueExistingHandles(due.voiceSet)
    audio += attackAdmittedNotes(due.noteOn, effectiveGates(dueBeat))
    emitAudioBundle(dueBeat, audio)
    advance consumed streams, retaining immutable snapshots
    armNextDueBeat()
```

The coordinator can keep stream heads in a priority queue, but `TempoClock` remains the time authority. An incoming transaction that adds an earlier deadline increments the wake ticket and arms a new `schedAbs`; an already-scheduled old callback becomes a no-op. There is no API assumption that arbitrary clock callbacks can be individually removed. Transport epochs and wake tickets must not invalidate legitimate releases belonging to still-active manual/MIDI notes.

Quantization: externally arriving controls take effect no earlier than the next 48th-of-a-beat tick. For alignment `a > 0`, round that tick up to a multiple of `a`. Nested controls use the current logical tick. If current clock beat is `b`, compute the next external tick as `floor(b * 48) + 1`, then `ceil(tick/a)*a`; at an exact boundary an external control still starts on the next tick before alignment. Use integer ticks within the transport epoch for these calculations; convert to beats only at the clock boundary.

SC `Pdef` is a replaceable reference, not a sufficient immutable-snapshot implementation. Do not let a running child read a mutable registry entry repeatedly. Resolve and deep-freeze events, harmony, articulation and future-note program settings when its start control executes. An external start awaiting alignment already owns its snapshot: a later definition-only publication must not alter that pending start. A matching explicit replacement transaction can replace it. Already-running voice nodes retain the sample buffers/program revision from their own note-on. Root definitions intentionally resolve the latest child revision at **each future nested launch**, because that is when the nested start control executes.

References for the native mechanisms: [TempoClock](https://doc.sccode.org/Classes/TempoClock.html), [Pseq](https://doc.sccode.org/Classes/Pseq.html), [Pspawner](https://doc.sccode.org/Classes/Pspawner.html), [EventStreamPlayer](https://doc.sccode.org/Classes/EventStreamPlayer.html). The coordinator above is an Omnichord design; these classes do not provide that entire contract automatically.

### 4.4 Musical mute, phase and tails

Maintain separate gate causes, keyed by owner/token. Effective gate is the union of active half-open intervals `[beginBeat, endBeat)` and any indefinite role suppression. Removing one cause must not remove another overlapping fill/hold cause.

| Action during gate | Required behavior |
| --- | --- |
| New ordinary note-on / drum hit | Consume and suppress; do not allocate a voice or RR selection |
| New child launch in a muted automatic lane | Suppress launch, retain parent phase |
| Release of a voice started before gate | Always execute |
| Pitch slide/control of a voice started before gate | Continue its captured gesture |
| Later notes of an already-launched finite arpeggio | Continue: parent gating prevents new phrases, not the rest of the old phrase |
| Existing audio/reverb tail | Leave untouched |
| Gate end | Resume at current phase, with no replay or restart |

Distinguish **root-launch gate** from **note-on gate**. Auto-chord OFF/hold uses root-launch gating. Fill role gating suppresses base drum hits. A future user-facing lane mute must name its intended scope; do not introduce a universal bus-amplitude mute for this behavior.

Do not use `EventStreamPlayer.mute` around a stream containing explicit note-off or maintenance events. Native muting can turn its emitted events into rests, not just note-ons. Do not use `Pspawner.suspendAll` when the desired behavior is to leave finite children and their releases alive.

SC cannot retract audio bundles already submitted to `scsynth`. Define the boundary honestly: a live gate affects events not yet committed to the server; its audible effective time includes the fixed server lookahead. Start with a proposed 20 ms server latency and tune by platform measurement. Do not queue many future bars to the server. The future musical plan remains in `sclang`; only due-beat actions plus short fixed latency are sent. Report effective boundary in the ACK so tests distinguish delivery time, logical beat and audible time. See [server timing](https://doc.sccode.org/Guides/ServerTiming.html).

### 4.5 Beat-based releases and tempo changes

For sequenced notes, use explicit note-off events at absolute musical beats. Do not assume the default SC Event `sustain` path preserves AMY semantics when tempo changes after note-on: a release precomputed in seconds may no longer land on the required beat. The finite execution or dedicated release owner holds the release event in the same TempoClock domain.

Envelope release duration and acid slide time are timbral seconds/milliseconds, distinct from the beat at which release begins. A tempo change moves future note-off beats but does not rescale an already-running 60 ms glide or a reverb decay. Manual strum/preview durations that are specified in seconds remain seconds, with their timers owned by the SC service rather than Qt.

### 4.6 Detailed bass migration

Port these pure functions structurally before changing behavior: `_scaled_bass_source`, `_bass_gesture_sources`, `_ordinary_bass_gesture`, `_tb303_bass_gesture`, `compile_bass_sequence_plan`. Replace embedded AMY strings with typed events; do not re-infer notes from strings in production.

1. Normalize riff ticks/durations using the source PPQ and existing `round(sourceTick * 48 / sourcePPQ)`; duration minimum one tick. Retain source accent/slide flags and velocity /127. Activity events use current beat positions, gain and stable equal-tick ordering.
2. Define a safe gap after event i only when it has no outgoing slide and `endTick < nextTick`, including the circular edge.
3. If the phrase crosses its nominal wrap, rotate at an internal safe gap and unwrap the crossing events to increasing ticks. Reduce only root-launch ticks modulo phrase period. Never split an attack from its final release at the wrap.
4. A dense multi-note non-slide phrase with no safe gap uses the existing one-tick release margin if every interval is at least two ticks. Do not apply that shortening to a single sustained note or a slide chain. Preserve the existing validation error for a phrase with no valid handover boundary.
5. Each connected gesture becomes one finite execution, capturing all pitches, releases and slide continuations. Root 56 only launches gesture IDs. It never directly emits an unowned bass note.
6. Harmony-only change with equal `BassSequencePlan.identity`: publish future child definitions; retain root phase and all active old children. Identity includes source type/ID, engine articulation class, period and launch timing; it does not include pitch, velocity or live timbre values.
7. Phrase change: cancel/replace pending handover ticket; publish new root and children atomically. At the next external tick stop old root launches. Wait `D + 1` legacy ticks, where `D` is the maximum of the remembered published drain bound, old-plan drain and new-plan drain. Start the latest root at local tick zero. Preserve the current monotonic drain bound until reset/clear. Do not wait for the old entire phrase period.
8. During repeated edits while draining, newest pending phrase wins; the controller's generation check prevents an older scheduled callback starting it later. Old finite gestures are still independent.
9. Note-off is addressed to the gesture's voice handle. Never retain AMY's global `l0i<bass>` as the release mechanism for ordinary overlapping SC gestures.

Current catalog facts from existing docs/tests: maximum 20 bass gestures in a riff, reserved capacity 54; current TB-303 finite definition maximum 45 events. Validate all 1,664 riffs after refactoring, including their transpositions and compatibility selection. These are expected baseline facts, not new hard caps.

### 4.7 Chords and nested arpeggios

`compile_chord_sequence_plan` currently creates a finite child per distinct velocity, using stable sorted velocity slots. For block chords it emits all selected notes at child tick zero and a release at `round(chord_gate_beats * 48)`, minimum one tick. Replace that one old synth-wide release with the child's list of owned voice handles.

For arpeggios: selected chord length is 2–7 notes; rate is clamped to 1–4 notes/beat; `stepTicks = max(1, round(48/rate))`; `gateTicks = max(1, round(chord_gate_beats * stepTicks))`. Sort using the existing chord-note ordering and reverse for downward motion. Emit each note-on at `index * stepTicks` and its own release at `start + gateTicks`. At every selected activity onset the root launches a fresh finite child. Do not truncate a child at a bar boundary or stop the preceding child when the next onset arrives.

Nested here means a repeating launcher starts an independent finite phrase. `Pseq([childA, childB], inf)` alone would serialize complete phrases and would not reproduce overlapping launches. Likewise one `Pbind` that replaces its note array halfway through a child would break snapshot semantics.

Test seven-note upward/downward children at every rate, overlapping onsets, harmony changes in their middle, automatic-chord OFF, manual hold and transport Stop. The current architecture can approach 34 overlapping arp executions; use this as a minimum stress fixture, alongside the former 40-execution ceiling.

### 4.8 Drums and fills

Port `compile_drum_activity_sequences`, `compile_fill_sequence`, `fill_occurrences`, `compile_fill_schedule`, `_drum_quantum`, `_drum_commands` and their existing alignment decisions. The source drums/fills are 96 PPQ; existing conversion uses integer `tick // 2` for relevant fill positions/durations. Do not substitute rounding there just because bass normalization uses rounding.

Precompile all 270 persistent fill definitions once per catalog load. Each fill starts role gates for base roles absent from `continue_roles`, followed by its own hit events. Gates last `fill.duration_ticks // 2` legacy ticks. Base roles included in `continue_roles` keep running; roles absent from the selected base activity are not enabled by the fill. Fill hits use a separate execution/source identity so the fill does not mute itself.

`fill_occurrences` cycles both selected F1–F5 order and each selected fill's `allowed_start_beats` index until the state repeats. Keep that exact deterministic sequence. Launch-root period is `len(occurrences) * densityBars * barTicks`; occurrence offset is `occurrenceIndex*densityBars*barTicks + (startBeat-1)*(fill.beat_unit_ticks//2)`. Replace this root on a bar boundary, preserving the clock. First enabling fills while running starts at the next eligible whole bar under existing policy.

Disabling a selected fill prevents new launches; it does not remove an active fill or its gates before their expiry. Overlapping gate tokens merge by union. At a gate end beat a base hit is allowed. Tests must cover gates and a base hit at the exact same tick, multiple simultaneous fills and disabling during a fill.

Keep source velocities and musical accents. Re-render and regenerate the per-fill loudness calibration for the selected SC drum kits; `drum_fill_levels.json` was calibrated for the old samples. Do not flatten dynamics by normalizing each sample or fill independently to full scale.

### 4.9 Start, Stop, Panic, program change and disconnect

| Operation | New contract |
| --- | --- |
| Start from stopped | New transport epoch/origin; definitions and buffers remain resident; install current roots before enabling execution; first musical phase zero |
| Duplicate Start while running | Preserve current idempotence; no duplicate roots |
| Stop | Disable/cancel accompaniment roots and future accompaniment children; explicitly release accompaniment-owned voices (drums/bass/auto chord), preserve manual chord/strum/MIDI according to existing Stop behavior |
| Automatic chord OFF | Stop future launches only; active finite children finish |
| Bass-running OFF | Preserve existing immediate bass release/clear behavior, distinct from a generic musical mute |
| Program change | Prepare new program first; publish for future attacks; old voices/buffers remain until their release; preserve any explicit manual-chord re-articulation required by existing tests |
| Panic | Invalidate all execution generations, clear deferred releases/held state, release or immediately free every musical voice and effect tail as the explicit emergency action; reset MIDI sustain state |
| Audio-process failure | Mark engine unavailable; no replay of old note-ons after reconnect; restart stopped, rehydrate latest configuration/definitions/resources, require a fresh explicit Start |

A transport Stop intentionally differs from a musical mute. Do not change all stops into “tails forever” or all mutes into all-notes-off.

## 5. Internal OSC protocol and atomic delivery

### 5.1 Boundary and message families

Keep external hardware-control OSC in the existing input subsystem. The new internal port is loopback-only and separately configured. `thisProcess.openUDPPort`/`OSCdef` receive typed messages; the supervisor allocates ports/session IDs and passes them through arguments/config. No arbitrary code evaluation over OSC, no paths supplied by musical note messages, and no dependency on a nonexistent stock JSON parser.

The following addresses are **proposed application protocol**, not SC server commands:

| Address | Fixed arguments after OSC address |
| --- | --- |
| `/omni/v1/hello` | clientSession:string, protocolVersion:int, replyPort:int |
| `/omni/v1/ready` | engineSession:string, protocolVersion:int, catalogDigest:string, status:string |
| `/omni/v1/tx/begin` | session:string, txId:int, lane:string, generation:int, packetCount:int, applyMode:string, alignmentTicks:int |
| `/omni/v1/tx/def` | session, txId, packetIndex:int, definitionId:string, revision:int, kind:string, periodTicks:int, eventCount:int |
| `/omni/v1/tx/event` | session, txId, packetIndex, definitionId, tick:int, ordinal:int, action:string, then action-specific atoms |
| `/omni/v1/tx/value` | session, txId, packetIndex, objectId:string, parameter:string, typed value |
| `/omni/v1/tx/commit` | session, txId |
| `/omni/v1/ack` | session, txId, stage:string, generation:int, effectiveBeat:double, code:string |
| `/omni/v1/note/on` | session, messageId:int, owner:string, noteHandle:string, programId:string, revision:int, logicalKey:int, freq:double, velocity:float |
| `/omni/v1/note/off` | session, messageId, owner, noteHandle, releaseVelocity:float |
| `/omni/v1/voice/set` | session, messageId, noteHandle, parameter, typed value |
| `/omni/v1/transport` | session, messageId, action:start\|stop\|panic, tempo:double |
| `/omni/v1/program/prepare` | session, messageId, owner, programId, revision |
| `/omni/v1/program/status` | session, messageId, owner, programId, status:loading\|ready\|failed, detail:string |
| `/omni/v1/health` | session, counters/status fields defined in a versioned schema |

Action payloads are fixed by kind: `launch(targetDefinitionId)`; `gateBegin(targetRole, token, durationTicks, scope)`; `rootStop(targetRootId)`; `rootStart(targetRootId)`; `noteOn(localHandle, owner, programId, programRevision, logicalKey, freq, velocity, articulation, accent)`; `noteOff(localHandle, releaseVelocity)`; `voiceSet(localHandle, parameter, value)`. Preserve the pre-tuning logical key for sample-region selection and the separately tuned frequency for playback. Resolve local handles against the execution ID, ensuring two starts of the same definition never share a voice handle. More than one parameter update uses multiple value/event records within the same transaction.

Each packet must fit a configured 1,000-byte OSC payload ceiling, including encoding overhead; split records, never truncate names/values. Do not send a multi-megabyte JSON catalog over UDP. Catalogs and buffers load from verified local files at startup; OSC uses IDs.

### 5.2 Delivery state machine

UDP requires application-level reliability here. Implement:

1. Sender stages a complete plan, gives it a lane generation and transaction ID, sends `begin`, indexed records and `commit`.
2. Receiver stores indexed records without changing live state. Duplicate identical indices are harmless; differing payload under an existing index rejects the transaction. Enforce count/size/time bounds.
3. A commit arriving before all records yields `incomplete`, identifying missing indices through bounded reply records; it never partially publishes a definition.
4. Validate types, finite numeric values, references, resources, graph depth/cycles and musical invariants. Resolve required ready program revisions. Publish all records atomically or none.
5. ACK stages are `received`, `scheduled`, `applied`, `rejected`. Apply only once. A retry of an already-applied transaction returns its stored result.
6. Initial retry interval 100 ms, maximum three retransmission rounds; transaction staging expires after 5 seconds. These are delivery timers outside the musical clock. On failure report unhealthy transport and stop automatic resubmission of notes; the UI must not pretend the update was applied.
7. Keep a bounded replay window of monotonic message IDs per session. Never reapply a duplicate note-on. Release is idempotent. After disconnect/new session discard old transaction/message IDs and all old wake tickets.

Coalesce **unsent** low-priority transactions only within the same lane, preserving the current writer principle. Once a multi-record plan begins delivery, finish or explicitly reject it before dependent deltas. A bass update cannot cancel an unrelated drum/fill update. An operation changing harmony for bass and chords must stage both definitions in one shared transaction when the existing policy requires one atomic musical change. High-priority note-off, Stop and Panic must not sit behind sample downloads or long definition uploads.

The existing `send_message(address, value)` adapter handles volume, reverb, synth selection/state, parameters, manual chord, chord state, strum note, bass-running, rhythm config, rhythm-chord-enabled, pitch bend, transport and panic. Preserve that public behavior while refactoring. **Also migrate `MidiAmyEngine`**, which currently bypasses this facade via `_wire`; swapping just the facade leaves MIDI on AMY.

## 6. Synth catalog: all 109 definitions

Appendix A lists the exact 109 source files; do not substitute 109 arbitrary presets or count files under `in-process/` and demos. Each source gets a stable program ID `sc.sclork.<originalName>`. Maintain source name/category/commit/path/hash/credits, adapter revision, supported roles, control schema, release mode and measured resource cost.

The upstream repository declares GPL-3.0 and retains credits from several sources; its README notes some original authors are unidentified. Preserve the actual license and per-file notices, and generate a provenance report. Do not describe the collection as CC0 or unconditionally free of all attribution/source obligations. [License and credits](https://github.com/SCLOrkHub/SCLOrkSynths/tree/6730c745971aa45c95d9b4cddfb4d5ca342774b3).

### 6.1 Adapter rules

- Vendor source separately from adapted production SynthDefs. Do not run demonstration `Pbind`s or interactive code during bootstrap.
- Common normalized controls: `out`, `freq`, `velocity`, `gain`, `pan`, `gate`; optional `attack`, `decay`, `sustain`, `release` only where the underlying design supports them. Map old `att/dec/sus/rel` explicitly.
- Distinguish gated, naturally decaying, continuously running and special-trigger definitions. Add an outer lifetime/release envelope where needed without deleting the original tonal envelope. A one-shot does not need to become a sustained organ, but it must support Panic and safe voice stealing.
- Every definition must output finite stereo audio on the supplied bus and eventually free its node after release/end. Remove hard-coded hardware output buses and mouse controls. Avoid asynchronous buffer loading from inside a SynthDef.
- `freq` might not mean the same thing in noise/drum/FX definitions. Declare pitch support accurately; do not expose fake keyboard tuning for an unpitched noise patch. All 109 remain represented in the catalog, with suitable role/category metadata.
- Keep intentional sonic differences. Do not replace all complex patches with a generic saw to satisfy compile tests. For expensive definitions, retain the full version and add a separately named economical variant if needed; do not silently change its source identity.
- Compile all adapters with pinned SC; build a UGen dependency report from compiled definitions, not only regex. If any extension is needed, pin and package it explicitly. Missing plugins are a build failure, not a runtime silent fallback.
- Establish per-program gain from standardized render material, leaving headroom. Test low/high notes and sustained/released notes; metadata is not proof of stability.

Known source pitfalls: `acidOto3092` has a `lagTime` argument but its inspected graph does not apply it; its percussive envelopes self-free. `bassWarsaw` smooths pitch but does not implement independent acid accent/filter triggers. `moogBass` exposes envelope argument names while parts of its envelope graph use hard-coded values. Do not equate a control's presence with functioning behavior. Review `superSaw` voice/oscillator expansion and feedback patches for worst-case cost.

### 6.2 Presets and compatibility

Use a new versioned `ProgramSelection` storing engine kind, stable program ID, adapter revision and normalized parameter values. Keep legacy AMY selection data in a migration sidecar when importing an old preset; never overwrite the user's only copy.

Provide a checked-in legacy-to-new mapping table for every old `synth_programs` entry. Suggested semantic mappings are electric piano → FMRhodes family, organ → tonewheel/organ family, strings → sampled strings or `prophet5pwmStrings`, brass → VSCO, acid → `sc.omni.acid303`. They are **musical replacements, not waveform-equivalent ports**. Mark unsupported AMY-specific Juno/DX7 parameters as preserved legacy metadata and map only documented equivalent controls. Never display an ineffective DX7 operator control as if the new program implements it. Load old presets into a new schema version and retain an explicit migration report.

Factory choices should cover bass, pads, leads, keys, organ, plucks, strings, winds, bells, percussion and FX. The raw 109-source count is fixed; the number of useful curated presets can exceed 109 through intentional parameter variations. Do not inflate the count with aliases.

Each control schema must specify `applyScope=liveVoice|nextAttack|futureGesture|mixer`. Mixer volume/reverb and global bend affect current audio. Controls that the existing UI applies to sounding voices, such as a live filter sweep, update those owned nodes through `voiceSet`; do not freeze them accidentally inside a pattern snapshot. Riff-authored accent/slide edges and their captured note/release sequence stay immutable. Changing future-gesture settings republishes child definitions without rewriting active children. A program change itself remains prepare/commit and does not replace the graph or buffers underneath an old node.

## 7. Acid / TB-303 alternatives

Implement a shared acid-gesture control protocol and **three primary voices**. Retain the original SCLOrk sources as their own programs; new adapted voices have new IDs and credits.

| New program ID | Tonal basis | Required work |
| --- | --- | --- |
| `sc.omni.acid303` | Saw/pulse oscillator, resonant low-pass, saturation | New core SC voice designed for the exact accent/slide contract; no claim of circuit-perfect 303 emulation |
| `sc.omni.acidOto` | `acidOto3091` / `acidOto3092` pulse-acid family | Replace one-shot lifetime/always-on lag with explicit held gate, triggered filter/accent envelopes and destination-aware slide |
| `sc.omni.acidMoog` | `moogBass`, stock `MoogFF` | Shared gesture protocol, independent acid envelopes, retain thicker multi-oscillator character |
| `sc.omni.acidWarsaw` (additional) | `bassWarsaw` distorted detuned VarSaw | Add envelope-modulated filter and independent accent; distinguish from 303 rather than claiming identical tone |

### 7.1 Voice controls and envelope ownership

One synth node per connected acid gesture. Required inputs:

```text
freqTargetHz, gate, velocity, gain, waveform,
cutoffHz, resonanceNormalized, envOctaves, filterDecaySeconds,
slideSeconds, slideEnabled,
t_attack, t_filter, t_accent, accentAmount,
pitchBendBus, out
```

Use SC trigger controls (`t_...` / `\tr` control rate) for retriggerable envelopes; do not simulate a new accent by momentarily dropping the main gate. Main amplitude sustain/release owns node lifetime. `t_filter` starts the normal acid filter-decay component, `t_accent` starts an independent accent component. Set destination parameters and trigger values in one bundle and one consistent action order.

Pitch interpolation is in semitones/log-frequency: compute MIDI-equivalent pitch from target Hz, glide there, convert back to Hz and apply global bend. A detached attack sets initial pitch directly and never glides from an unrelated preceding gesture. An outgoing `slide_to_next` flag on step i controls the edge **into i+1**. No flag means no automatic portamento just because two notes are close together.

Suggested full-voice starting values, subject to audible calibration: cutoff 400 Hz; filter envelope 2 octaves; filter decay 0.25 s; slide 0.060 s; accent amount 0.35; pulse width 0.5. These match the old UI's intended scale where applicable. Existing AMY resonance 1.2 is not a `MoogFF`/`RLPF` resonance value: map the normalized UI range through per-model curves. Clamp cutoff below Nyquist and resonance to a tested stable range.

### 7.2 Articulation truth table

| Destination action | New node? | Amp attack | Filter attack | Accent | Pitch |
| --- | --- | --- | --- | --- | --- |
| Detached normal note | Yes | Yes | Yes | No | Immediate |
| Detached accented note | Yes | Yes | Yes | Yes | Immediate |
| Slide to different pitch | No | No | No ordinary retrigger | Destination accent may trigger | Glide |
| Tie to same pitch | No | No | No ordinary retrigger | Destination accent may trigger | Hold |
| Rest/end of connected chain | No | Begin release | Let/filter-release per model | Let decay | Hold final pitch |

Accent must affect brightness/envelope depth as well as loudness; it is not simply velocity ×2. Start from the old amplitude factor `1 + 0.5*accentAmount` and envelope-depth increment `2*accentAmount` octaves as calibration references, but place the accent transient in a separate envelope so it works on a slide destination. Do not retrigger the oscillator or amplitude attack on a slide/tie.

Preserve base velocity captured at the chain's attack; destination velocity does not accidentally restart amplitude. Accent is a separate gesture event. Normal note durations can end before the next detached note; a slide chain remains held through all connected edges until its final explicit release. No pitch-wide or part-wide note-off may terminate a newer gesture.

A tie can be represented internally as an outgoing slide edge with equal destination pitch, or as an explicit normalized `tie` action for future authoring. Do not rewrite the current riff JSON to add unsupported fields; derive the internal representation.

For held chords, strum and external MIDI, the same acid instruments remain playable polyphonically through independent gesture nodes. The bass riff annotations alone drive Accent/Slide automation; ordinary chord notes do not fabricate TB-303 sequence flags.

### 7.3 Acid acceptance material

Render a 16-step pattern at 90, 120 and 180 BPM with detached notes, rests, two- and four-note slides, same-pitch ties, accent at chain start, accent on slide destination, and accent on a same-pitch tie. Verify node counts and trigger traces as well as sound. Sweep cutoff/resonance while held; change harmony midway through a chain; change phrase rapidly during draining. Compare the three models for useful tonal differences. Label listening results honestly; no audio audition was performed while writing this handover.


## 8. Sample-bank selection and exact acquisition

### 8.1 Required bank set

Use the full source banks below as the bounded initial scope. This is a broad researched set, not a claim to have found every free sample on the internet. The release catalog contains all distinct useful instrument families across these banks after the deduplication procedure. Downloaded banks are assets, not Python packages and not protected product containers.

| Bank | Pin | Source / included directories | License position |
| --- | --- | --- | --- |
| VSCO 2 CE, SFZ branch | `6dd651d55dde97fd4028699be9d4481f26917891` | [Exact tree](https://github.com/sgossner/VSCO-2-CE/tree/6dd651d55dde97fd4028699be9d4481f26917891); root SFZ files and `Brass/`, `Keys/`, `Percussion/`, `Strings/`, `Woodwinds/` | CC0; retain source notices |
| VCSL, full SFZ release | tag `v1.2.2-RC`, commit `b6e6ac82d22248edee98a0bde185eb9ef6d439ad` | [Exact tree](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad); all instrument folders and `Scripts/` | CC0 |
| Salamander Grand Piano v3 | `3382bf9496bba2486f5ab0de55a264d1dfc38404` | [Exact tree](https://github.com/sfzinstruments/SalamanderGrandPiano/tree/3382bf9496bba2486f5ab0de55a264d1dfc38404); `Samples/`, `Data/`, `Salamander Grand Piano V3.sfz` | Preserve this distribution's CC BY 3.0 attribution and mapping credits |
| University of Iowa MIS | No repository pin; freeze fetched URL list and file SHA-256s | [Instrument index and permission](https://theremin.music.uiowa.edu/MIS.html); instrument pages and direct audio/archive links | Author's unrestricted-use statement; do not relabel as CC0 without an actual CC0 dedication |
| Black And Green Guitars | `b3b3249d37dc977a1a297bd2dc053e6d9b6b805c` | [Exact tree](https://github.com/sfzinstruments/karoryfer.black-and-green-guitars/tree/b3b3249d37dc977a1a297bd2dc053e6d9b6b805c) | Karoryfer free-library CC0 statement and included license |
| Black And Blue Basses | `6e7d674cdb41be7a54dbccb15472401ad01099b9` | [Exact tree](https://github.com/sfzinstruments/karoryfer.black-and-blue-basses/tree/6e7d674cdb41be7a54dbccb15472401ad01099b9) | CC0 |
| Meatbass | `ac9e859564bda286ab5ec672d00ff1aa2fef2895` | [Exact tree](https://github.com/sfzinstruments/karoryfer.meatbass/tree/ac9e859564bda286ab5ec672d00ff1aa2fef2895); `Programs/`, `Samples/` | CC0 |
| Emilyguitar | `b4920dc662fd9cad6dcaccdeecffdd91c8725d8c` | [Exact tree](https://github.com/sfzinstruments/karoryfer.emilyguitar/tree/b4920dc662fd9cad6dcaccdeecffdd91c8725d8c); root SFZ files and samples | CC0 |
| Bear Sax | `7abb3c652525a15dfac80e1b5dfbba9964ee568f` | [Exact tree](https://github.com/sfzinstruments/karoryfer.bear-sax/tree/7abb3c652525a15dfac80e1b5dfbba9964ee568f); `Programs/`, samples | CC0 |
| Weresax | `a4d756b21d2a573aca0d840cce7e71ba5effd4c6` | [Exact tree](https://github.com/sfzinstruments/karoryfer.weresax/tree/a4d756b21d2a573aca0d840cce7e71ba5effd4c6); `Programs/`, samples | CC0 |
| Virtuosity Drums | `9f04cf9a734527edfbb0a4eee1f674e45bbf71bc` | [Exact tree](https://github.com/sfzinstruments/virtuosity_drums/tree/9f04cf9a734527edfbb0a4eee1f674e45bbf71bc); full kit/percussion and all microphone recordings | CC0; preserve credits |
| Swirly Drums | `c40dafe0011cb2e54c0c220ff0fa308a11fc60f5` | [Exact tree](https://github.com/sfzinstruments/karoryfer.swirly-drums/tree/c40dafe0011cb2e54c0c220ff0fa308a11fc60f5); all brushed-kit/percussion recordings and articulations | Karoryfer free-library CC0 statement and included license |

Karoryfer's current [free-library page](https://shop.karoryfer.com/pages/free-samples) explicitly says its free libraries are CC0 even where older downloads carried less permissive licenses, with Marie Ork as an exception. Keep a dated copy of that statement with the downloaded licenses. Do not include Marie Ork's product-specific voice bank. For Salamander, retain the stated CC BY license of this particular remapping even if a different source recording distribution has later permissions.

The pinned VSCO `SFZ` branch is capitalized. Its separate `master` pin is `440300901dfe9275fd84e0b7763af1f8443ae62e`; do not download master and assume it contains the same mappings. VCSL master is `c1ea7bcc3c7309650ab0da9d15c9cd1fbc4a4c7e` and contains no `.sfz` files in the inspected tree. Use the pinned release above, with **183 `.sfz` files** and generator scripts `Scripts/createInstruments.py`, `Scripts/createKeyswitches.py`, `Scripts/wavio.py`.

VCSL master and that release contain the same 4,231 audio-file contents in the inspected trees, with one case-only path difference: release `Chordophones/Zithers/Dan Tranh/Normal/B2_mf_1.wav`, master `.../b2_mf_1.wav`; both have Git blob `09f91f6c04c3e72246d53306a63e9b058459cc39`. Keep mappings and sample tree from the same pin. A case-insensitive development machine can hide this Linux playback failure.

### 8.2 Verified file inventory, not instrument counts

These counts are from pinned recursive Git trees, matching `.wav/.aif/.aiff/.flac`, before content deduplication. Sizes are sums of repository file sizes, not compressed download size or decoded RAM requirement. Every sample's decoded header still needs verification at implementation time.

| Bank | Audio files | Source bytes, approximately |
| --- | ---: | ---: |
| VSCO SFZ | 3,168 | 3.18 GB |
| VCSL | 4,231 | 6.15 GB |
| Salamander | 641 | 0.75 GB, compressed FLAC |
| Black And Green Guitars | 1,776 | 0.58 GB |
| Black And Blue Basses | 2,208 | 1.12 GB |
| Meatbass | 536 | 0.29 GB |
| Emilyguitar | 323 | 0.12 GB |
| Bear Sax | 755 | 0.14 GB |
| Weresax | 256 | 0.20 GB |
| Virtuosity Drums | 4,858 | 1.47 GB |
| Swirly Drums | 4,796 | 1.82 GB |

Total for these Git banks: **23,548 audio-file entries**, **15,829,773,925 source-file bytes (15.83 GB)** before deduplication, plus Iowa. Recompute totals in the implementation lock; Git files can include duplicates, processed copies and multiple microphone recordings. Neither this total nor the 75 VSCO SFZ files is a count of distinct musical instruments.

Do not use a repository's reported GitHub `size` field as installed sample size. Do not multiply “program count” by “number of samples” to estimate RAM. Check for Git LFS pointer text and retrieve actual LFS assets where applicable; never count a pointer as valid audio.

### 8.3 Exact download recipes

For every pinned Git bank, a deterministic source archive is available through this pattern:

```text
https://github.com/<owner>/<repo>/archive/<40-character-commit>.zip
```

For example [VSCO pinned archive](https://github.com/sgossner/VSCO-2-CE/archive/6dd651d55dde97fd4028699be9d4481f26917891.zip) and [VCSL pinned SFZ archive](https://github.com/sgossner/VCSL/archive/b6e6ac82d22248edee98a0bde185eb9ef6d439ad.zip). Store the resolved download URL, content length, archive SHA-256 and per-file SHA-256 in `banks.lock.json` after downloading. A commit pin identifies source content; an archive checksum additionally verifies the fetched artifact. Do not invent checksum values in advance.

For a source checkout, fetch only the pinned commit into a fresh destination, check out detached, verify `git rev-parse HEAD`, then inventory. Source archives and checkouts are acquisition alternatives, not two installations of the same bank. Keep large sample binaries outside the LB Git repository; commit manifests and source-conversion scripts.

The author-linked prebuilt archives for several extensions are also available, but the Git pin above is the reproducible source authority:

- [Black And Green Guitars v1.000](https://github.com/sfzinstruments/karoryfer.black-and-green-guitars/releases/download/v1.000/Karoryfer_Black_And_Green_Guitars_1000.zip)
- [Black And Blue Basses v1.002](https://github.com/sfzinstruments/karoryfer.black-and-blue-basses/releases/download/v1.002/Black_And_Blue_Basses_1002.zip)
- [Swirly Drums v1.104](https://github.com/sfzinstruments/karoryfer.swirly-drums/releases/download/v1.104/Swirly.Drums_1104.zip)
- [Virtuosity Drums v0.925](https://github.com/sfzinstruments/virtuosity_drums/releases/download/v0.925/Virtuosity_Drums_v0.925.zip)
- [Emilyguitar v1.001](https://github.com/sfzinstruments/karoryfer.emilyguitar/releases/download/v1.001/Karoryfer.Emilyguitar.v1.001.zip)
- [Bear Sax v1.004](https://github.com/sfzinstruments/karoryfer.bear-sax/releases/download/v1.004/Karoryfer.Bear_Sax.v1.004.zip)
- [Weresax v1.003](https://github.com/sfzinstruments/karoryfer.weresax/releases/download/v1.003/Karoryfer.Weresax.v.1.003.zip)

These asset URLs were observed in the authors' download links; their binary payloads were not downloaded for this handover. Verify bytes and archive contents before using them. Do not assume a release ZIP and the repository pin are byte-identical.

### 8.4 Iowa: where the files actually are

The sample links are in the instrument page HTML, even when a text-only page extraction shows just navigation and introductory text. Fetch HTML and enumerate `href` values ending in `.aif`, `.aiff`, `.wav` or `.zip`; resolve against that page URL and percent-encode spaces. Do not guess a separate FTP/file server.

- [Piano page with individual AIFF links](https://theremin.music.uiowa.edu/MISpiano.html)
- [Direct piano example, pp Bb0](https://theremin.music.uiowa.edu/sound%20files/MIS/Piano_Other/piano/Piano.pp.Bb0.aiff)
- [Post-2012 tuba page](https://theremin.music.uiowa.edu/MIS-Pitches-2012/MISTuba2012.html)
- [Direct tuba ff stereo ZIP](https://theremin.music.uiowa.edu/sound%20files/MIS%20Pitches%20-%202014/Brass/Tuba/Tuba.ff.stereo.zip)
- [Post-2012 flute page](https://theremin.music.uiowa.edu/MIS-Pitches-2012/MISFlute2012.html)
- [Post-2012 violin page](https://theremin.music.uiowa.edu/MIS-Pitches-2012/MISViolin2012.html)

Use the [MIS index](https://theremin.music.uiowa.edu/MIS.html) as the complete discovery root for winds, brass, strings, percussion, piano and guitar. Restrict discovery to instrument pages/audio links, not the entire university site. Store fetched HTML/permission text, timestamp and a manifest of final URLs/checksums. Reject an HTML error page saved with an audio extension.

Prefer the highest-quality complete original recording set available for an instrument, usually the individual-note stereo archives where actually provided. Do not assume a “post-2012” page guarantees every listed file is new stereo 24/96: verify channel count, sample rate, dynamics, pitch and recording identity. The piano is a separate older collection. Preserve all available pp/mf/ff layers and articulations. If only concatenated chromatic scales are available, split with a reproducible boundary manifest, verify every pitch/onset/release and retain original files; never map an entire scale recording as one note.

### 8.5 Instrument families and initial curation

| Family | Primary bank/programs | Distinct complements to retain |
| --- | --- | --- |
| Grand/upright piano | Salamander Yamaha C5; VSCO/VCSL upright family | A clearly different upright and a dry grand; see three-piano decision below |
| Electric/digital piano and clav | SCLOrk FMRhodes family; VCSL TX81Z FM Piano/Piano 1/Clavisynth | Retain sampled FM timbre vs synthesized electric-piano controls; no acoustic-piano duplication |
| Harpsichord | VCSL English, Flemish, French, Italian, unknown source | Group stop/articulation differences; retain distinct builds after listening |
| Organ | VSCO organ; VCSL Pipe Organ/Renaissance Organ; seven SCLOrk organ definitions | Pipe, historical reed/organ and tonewheel synthesis are distinct families |
| Orchestral strings | VSCO solo violin/contrabass and violin/viola/cello sections | Iowa dry solo violin/viola/cello/bass; preserve solo vs section and arco/pizz/spic/trem |
| Harp and plucked strings | VSCO harp; VCSL concert/folk harp | Dan Tranh, psaltery, strumstick, guitar; collapse identical harp recordings |
| Plucked guitars | Iowa guitar where complete; Emilyguitar direct-recorded electric guitar | Verify Iowa's recorded instrument metadata; Emily's clean DI character is a candidate complement to the hollowbodies |
| Electric guitar | Black And Green Guitars | Both recorded guitars and their real articulations; do not make mono/wide FX aliases separate instruments |
| Electric bass | Black And Blue Basses | Fingered hollowbody and picked solidbody are meaningfully different |
| Acoustic bass | VSCO/Iowa orchestral bass; Meatbass | Keep Meatbass's different folk/pop attack/articulations; sampled vs synth bass remain distinct |
| Flutes/recorders | VSCO flute/piccolo; VCSL soprano/alto/tenor/bass recorders | Iowa alto/bass flute; ocarinas, whistles; match octave and articulation metadata |
| Reeds | VSCO oboe/clarinet/bassoon | Iowa Eb/bass clarinet; VCSL saxello and tenor sax; Bear baritone sax and Weresax alto |
| Brass | VSCO trumpet/horn/trombone/tuba | Iowa bass trombone and dry solo alternatives; retain straight/Harmon mutes as articulations |
| Harmonicas and unusual winds | VCSL Hohner C/F/Super64, didgeridoo | Keep chromatic vs diatonic as distinct; transposed duplicate sets are not automatically new timbres |
| Mallets and bells | VSCO/VCSL glockenspiel, marimba, xylophone, tubular bells | VCSL vibraphone, balafon, handbells/chimes; Iowa crotales; SCLOrk synthetic bells |
| Tuned hand-plucked percussion | VCSL kalimbas/mbiras/nyunga nyunga | Keep distinct instruments/tunings, not renamed generic kalimba presets |
| Orchestral/hand percussion | Full VSCO/VCSL percussion; Iowa complements | Timpani hits/rolls, cymbals, gong, triangles, snare/bass drum, conga, bongos, darbuka, shakers, tambourine, guiro, claves, woodblocks |
| Acoustic drum kit | Virtuosity full kit with microphone choices | Swirly brushed kit and brush articulations; not a second copy of the same stick kit |
| Electronic drums/FX | SCLOrk's 31 drum definitions and misc/FX | Retain synthetic kits separately from acoustic recordings |

Weresax's detailed author page and mappings identify an **alto sax**, despite the free-library index calling it tenor. Use the actual mapping/recording identity in the catalog. Bear Sax is baritone. VCSL provides the tenor family. Verify these metadata conflicts during import rather than copying marketing list labels blindly. [Weresax detail](https://shop.karoryfer.com/pages/free-weresax), [Bear Sax detail](https://shop.karoryfer.com/pages/free-bear-sax).

Three-piano initial default shortlist: `sample.salamander.yamaha-c5`, one VSCO/VCSL upright (prefer the richer distinct Yamaha/Knight recording after checking shared content), and `sample.iowa.steinway`. These are candidate contrasting recordings, not a completed listening verdict. VCSL Kawai and Steinway B remain fully imported candidates. If a VCSL grand proves more useful/distinct than Iowa, select it as the third default and retain the decision record. The user said three different pianos as an example, not a mandatory ceiling on genuinely different instruments. A fourth clearly distinct piano is acceptable; four mappings of the same recording are not.

### 8.6 Deduplication with accountable decisions

Perform two separate operations:

1. **Storage deduplication:** hash original bytes and canonical decoded PCM with sample rate/channel count/frame count. Different file containers can contain the same audio. Store identical content once with all source aliases/licenses/provenance preserved. Do not merge a left-only mic, stereo mix and room recording just because they share a filename/pitch.
2. **Instrument curation:** group by recorded instrument, session, performer, articulation, velocity/RR/microphone coverage and actual sound. A keyswitch wrapper and separate articulation maps become one instrument with articulations. Mono/poly, volume, tuning or reverb-only variants are controls/presets, not new recorded instruments.

Create `selection-decisions.json` with `candidateId`, `keepAsInstrument|mergeAsArticulation|aliasIdenticalAudio|hideNearDuplicate`, canonical ID, source references, measured coverage, listening-example paths and a concrete reason. No silent deletions. Full source banks remain recoverable on disk; the default browser displays the curated result.

For possible near duplicates, render a common audition sequence dry at matched perceived loudness, across low/middle/high range and soft/medium/hard velocity. Compare attack, sustain spectrum, release, room/stereo character and playing technique. Spectral features or sample-hash similarity can flag candidates but must not automatically decide that two musical instruments sound the same. Keep a pair when distinct articulation/recording behavior is useful even if their long-note spectra resemble each other.

No honest final distinct-instrument count can be supplied before downloading, mapping and auditioning all candidates. Do not manufacture that count to match an arbitrary target. The fixed verifiable count here is 109 synth sources; sample-family counts are an output of the importer/curation report.

## 9. Native SuperCollider multisampler

### 9.1 Why an explicit importer is required

Stock `PlayBuf` plays a buffer, not a complete SFZ instrument. It does not automatically implement key ranges, velocity layers, RR, sustain pedal, release samples, keyswitches or SFZ extensions. `BufRd` and `Phasor` can implement controlled sample reading, but they are building blocks. The implementation must build the mapping/voice layer described here. [PlayBuf](https://doc.sccode.org/Classes/PlayBuf.html), [BufRd](https://doc.sccode.org/Classes/BufRd.html), [Phasor](https://doc.sccode.org/Classes/Phasor.html).

Keep the runtime independent of SFZ parsing: a Python build/install tool resolves source formats into a versioned normalized manifest. `sclang` loads a generated, data-only representation (for example an SC literal generated by a strict trusted serializer, loaded only from installed assets) or typed binary records. Do not call `.interpret` on downloaded SFZ or untrusted user text. If using generated SC literals, quote strings with a tested encoder and accept only schema-validated local compiler output; a binary reader is preferable for future untrusted bank imports.

Salamander's inspected remap uses SFZ2/ARIA extensions and explicitly warns about non-ARIA players. Several Karoryfer banks have modular includes and GUI/control logic. Thus **“read each `<region>` and ignore the rest” is not an acceptable converter**. [Salamander compatibility notes](https://github.com/sfzinstruments/SalamanderGrandPiano/blob/3382bf9496bba2486f5ab0de55a264d1dfc38404/README.md).

### 9.2 Normalized bank manifest

Proposed data model, all numeric units explicit:

```text
Bank { id, sourcePin, licenseRecords[], files[], programs[], compilerVersion }
SampleFile {
  id, relativePath, sha256, pcmSha256, frames, sampleRate, channels,
  originalBitDepth, embeddedRootKey?, embeddedLoops[], decodedBytes
}
Program {
  id, family, displayName, recordingIdentity, articulations[],
  playableKeyRange, controls[], regionIds[], mixerDefaults,
  sourceMappings[], coverageReport, dependencyIds[]
}
Region {
  id, programId, articulationId, sampleId,
  keyLo, keyHi, keyCenter, tuneCents, pitchKeytrack,
  velocityLo, velocityHi, gainDb, velocityGainCurve,
  trigger: attack|release|releaseKey|pedalDown|pedalUp,
  rrGroup?, rrPosition?, rrLength?, randomLo?, randomHi?,
  micGroup?, micPosition?, pan, offsetFrames, endFrameExclusive,
  loop: { mode:none|continuous|sustain, startFrame, endFrameExclusive,
          crossfadeFrames },
  envelope: { delaySec, attackSec, holdSec, decaySec, sustainLevel, releaseSec },
  keyConditions[], ccConditions[], ccCrossfades[], modulations[],
  exclusiveGroup?, offByGroup?, offMode?, releaseGainPolicy,
  provenance: { sourceFile, line, inheritedScopes, overrides }
}
```

Separate condition selection from modulation. A CC can select an articulation, crossfade velocity-like dynamics or control a filter; those are not interchangeable. Keep all source region gains and recorded relative dynamics. Convert dB with `10 ** (gainDb/20)`; do not treat SFZ `volume` as a linear amplitude.

### 9.3 SFZ normalization rules

Implement real lexical parsing: comments, quoted/unquoted paths containing spaces, Windows backslashes, `#include`, `#define`, note names, `<control>/<global>/<master>/<group>/<region>/<curve>` and source locations. Expand includes using the including file's directory and SFZ `default_path` semantics; reject include cycles and paths escaping the bank. Macros may appear in opcode names, values and filenames. A regex-only “split on spaces” parser will lose valid sample paths.

Resolve scope inheritance according to the SFZ reference. More-specific values override inherited values; do not add the same `volume` at global, group and region scope unless the relevant opcode explicitly defines additive behavior. Keep a region's effective map plus provenance. Treat missing files, ambiguous case matches and impossible ranges as errors. [SFZ syntax/reference](https://sfzformat.com/).

Classify every encountered opcode into exactly one bucket: implemented runtime behavior; compile-time metadata/control UI; explicitly translated source-specific behavior; or unsupported-error. There is no default “ignore unknown opcode.” Write `opcode-coverage.json` and make complete program import fail on unaccounted audible behavior.

| Opcode/feature family | Required normalized behavior |
| --- | --- |
| `sample`, `default_path`, includes/macros | Resolve actual file; retain verified relative path/hash |
| `lokey/hikey/key/pitch_keycenter`, note names | Selection key range and sample root pitch, with source octave convention verified |
| `lovel/hivel`, key/velocity crossfade | Layer selection/crossfade with explicit edge inclusivity and curve |
| `volume`, `amplitude`, `amp_veltrack`, pan | Separate source gain, velocity response and pan; no double velocity scaling |
| `tune`, transpose, pitch tracking | Root correction vs target pitch; preserve tuning version choices |
| `seq_length/seq_position`, `lorand/hirand` | RR group/counter or one shared random draw per musical trigger |
| `sw_*`, CC conditions | Explicit named articulation selection; retain keyswitch compatibility for MIDI if enabled |
| amplitude envelope and dynamic envelope controls | Native envelope parameters and live-modulation policy |
| `loop_mode/start/end`, sample header loops | Forward loop with correct frame units; SFZ inclusive end converted to exclusive end |
| `trigger=release/release_key`, `rt_decay` | Release-sample matching, sustain interaction, hold-time/velocity response |
| `group/off_by/off_mode/off_time`, polyphony | Scoped choke/retrigger behavior; never all-parts note-off |
| CC curves/modulations, filters and LFOs | Translate into named SC program controls and explicit graphs |
| GUI labels/bank XML/digital signatures | Preserve documentation/credits; omit proprietary GUI execution, not the underlying recorded sound |

At the inspected VSCO root mappings, the opcode set includes `ampeg_attack`, `ampeg_dynamic`, `ampeg_release`, `default_path`, `group_label`, key/velocity bounds, random bounds, `pitch_keycenter`, `sample`, sequence RR, keyswitch fields, `tune`, `volume`. Account for sample-header sustain/loop metadata too; absence of an SFZ `loop_start` string is not proof that a recording has no loop metadata.

### 9.4 Bank-specific conversion work

**VSCO:** import all 75 root SFZ mappings. Fold `*-KS` wrappers into articulation selectors of the corresponding instrument. Keep quiet/vibrato variants as articulations/controls when they use the same recordings. Preserve random sample groups and all velocity regions. Infer no pitch from filename when an explicit mapping exists. Map `GM-StylePerc.sfz` by its actual keys; do not assume every note follows the current Omnichord GM abstraction unchanged. All source audio, including currently unmapped recordings, needs a coverage entry and an explicit mapping/duplicate/noninstrument decision.

**VCSL:** use the 183 mapping files in the pinned release and its generator scripts as a reference, not a new unpinned derivative bank. The raw master tree is not a ready mapping catalog. Validate every include/file path on Linux. Preserve recorder articulations, organ stops, historical keyboard variants, harp types, percussion RR and tuned mbira ranges. Collapse legacy/current mappings only after checking actual PCM/recording coverage. Appendix C enumerates the raw instrument folders for coverage.

**Salamander:** process `Salamander Grand Piano V3.sfz` and every `Data/*.txt` include, including `notes.txt`, `region.txt`, `vel_01.txt` through `vel_16.txt`, `tune_nat.txt`, `tune_ret.txt`, `str_res.txt`, `hammer.txt`, `pedal.txt`. Import all 16 attack velocity layers and all release/pedal/string-resonance recordings. Natural/retuned are modes of one recording, not two pianos. Reconstruct the control curves for string resonance, hammer noise, pedal noise, release, offset and velocity response. Preserve high-register undamped behavior where the mapping specifies it. Do not claim physical sympathetic-resonance modeling merely because release resonance samples are present.

**Guitars/basses/saxes:** follow each bank's top-level program include graph. Keep real articulations and microphone/dynamic variants. Fold effect-only mono/unison/wide/synth transformations into named optional presets or native SC effects. They must not replace the clean base recording. Particular requirements: both Black And Green guitars; both Black And Blue basses; Meatbass arco velocity/modwheel mappings and pizzicato RR; Bear Sax sustain/staccato/subtone/growl; Weresax actual alto mappings. If a source-only articulation is missing from the top program, add a named articulation using its explicit source map rather than dropping samples.

**Drum kits:** Virtuosity's `Programs/02-full-kit.sfz` is the completeness reference, alongside its microphone programs; do not choose only `01-basic-kit.sfz`. Swirly requires brushed articulations, swirls/stirs/flutters where sampled, six hi-hat openness states, foot/pedal noises and its hand percussion. Imported microphone choices remain available; one default microphone mix is not permission to discard alternate recordings. Convert their modular includes/CC/keymap logic into a role→articulation→region map. Reproduce deliberate hi-hat/cymbal choke groups separately from musical fill mute.

**Iowa:** prefer supplied individual-note files; create explicit note/root/dynamic/articulation mapping. Verify octave naming with pitch estimation and a known note reference (MIDI 69 = 440 Hz at standard tuning); do not assume each source's C4 convention agrees. A nonlooped wind sample ends when its recording ends; do not invent a seamless sustain loop automatically. If adding reviewed loops, retain the source audio and store loop positions/crossfades as derived metadata with audibly verified acceptance.

The compiler must generate a coverage table for **every audio-file entry**, not just mapped regions. Acceptable dispositions are reachable recorded articulation, identical-content alias, alternate microphone/tuning mode, documented source duplicate, or explicitly noninstrument material. “Unrecognized filename” is not a successful import. A missing useful articulation blocks that bank's complete status.

### 9.5 Runtime region selection

On admitted note-on:

1. Capture program revision, articulation state and tuning snapshot; select regions using the original logical key and velocity. Tuning changes playback rate, not which unrelated key region is selected.
2. Evaluate source key/velocity/CC conditions and crossfade weights. Advance a deterministic RR counter once per audible musical trigger in its group. All simultaneous microphone layers share the same RR/random choice.
3. Select all required microphone/dynamic layers. Preserve recorded velocity layering; apply the source's velocity-to-gain curve once, followed by Omnichord's separate role/program/user gain.
4. Allocate one voice handle owning all selected sample-layer nodes. Record source key, attack/release velocity, press time, sustain state and selected RR set for matching release samples.
5. Emit all layer nodes together at the scheduled timetag. On release, address this exact handle and trigger its matching release layers under the pedal policy.

Do not advance RR for a suppressed note. For reproducible tests seed randomness per test/session and group; production random selection may vary but must remain coherent between microphones. Keep counters per logical part/program so another MIDI row does not disturb a drum pattern's RR sequence.

### 9.6 Playback, rate, stereo and loops

For ordinary root-key samples with 100% pitch tracking:

```text
playbackRate = (sourceSampleRate / serverSampleRate)
             * (targetTunedHz / nominalRootHz)
             * 2 ** (regionTuneCents / 1200)
             * globalPitchBendRatio
```

`nominalRootHz` is the frequency implied by the declared sample root under the source reference; do not both bake a tuning correction into it and also apply the same `tuneCents`. Handle non-100% tracking explicitly in semitone space. Unpitched drums normally use unity transposition unless their program defines tuning.

Use separate mono/stereo SynthDefs because `PlayBuf`/`BufRd` channel count is fixed when the SynthDef is built. Mono may be panned to stereo; stereo samples keep stereo width and use a balance/width stage rather than summing to mono. For more microphone channels use coordinated mono/stereo layer nodes. `BufRateScale` handles source/server sample-rate differences; no destructive resampling of source banks is required.

Nonlooped samples can use `PlayBuf` with cubic interpolation and a separate controllable envelope. Natural sample end and envelope release must both lead to cleanup exactly once. Percussion one-shots may ignore ordinary note-off if the instrument's articulation specifies it, but must respond to Panic/choke and bounded voice stealing.

For sustain/continuous loops use a native phase-driven reader. Required algorithm:

- Start at `offsetFrames`, play the attack before the loop. Wrap only between validated loop start and exclusive loop end; never loop the entire file merely because it has a sustain articulation.
- For no-crossfade loops, preserve exact source phase/frame interval. For an enabled crossfade of X frames, blend end-window and start-window reads with a defined linear or equal-power curve and advance to `loopStart+X` after the wrap, avoiding replay of the overlap. Store the curve and shortened effective loop interval in metadata.
- Use separate read heads where needed for the overlap. Test constant signals, impulses and sine-wave loops at fractional rates to verify boundaries and gain; a single `PlayBuf(loop:1)` cannot implement arbitrary loop windows.
- `loop_sustain`: once sustain ends, stop wrapping at the next loop boundary and continue into the recording's release/tail, while applying the specified release envelope. Capture this exit state so a pedal change does not repeatedly jump back into an old loop.
- `loop_continuous`: keep loop phase during the release envelope, then free. `no_loop`: never wrap. A source lacking a loop does not automatically become infinite sustain.
- Never read beyond the last frame. On very long files, account for the finite precision of audio-rate phase indices; reject unsupported lengths or use segmented buffers with a tested transition, not imprecise indexing. The selected instrument samples are expected to be short, but measure this.

This loop reader is custom SynthDef work using SC primitives; it is not an already-tested component supplied with this document. The explicit loop tests are a required implementation gate.

### 9.7 Sustain pedal, releases and voice stealing

Each pitched part has independent sustain state. Physical note release while pedal is down records key-up but retains appropriate sounding layers. For SFZ `release_key`, trigger at physical key-up; for `release`, follow the mapped sustain-aware release behavior. Pedal-up releases deferred voices and triggers pedal-up noise once per actual transition. Same-pitch repetitions remain separate handles until the program's deliberate self-masking rule/choke policy acts.

Implementation note (2026-09-14): the generic owner-scoped CC64 lifetime path
is now implemented for pitched MIDI rows and tested in both Python routing and
the production SC state machine. Bank-specific `release`, `release_key` and
pedal-noise layer selection still belongs to the incomplete additional-bank
normalization work and must not be inferred from this generic sustain support.

Store note age and velocity for release-layer scaling; do not play a full loud hammer/release sample after an inaudible gated note. Choke groups are scoped to part/program/exclusive group. A closed hi-hat may choke that part's open hat; it must not choke another MIDI row or undo unrelated fill gates.

Voice stealing is a documented overload policy: first completed/released quiet voices, then oldest release tail, then oldest sustained voice only when the part's hard limit is reached. Apply a short fade to stolen layers, cancel only their handle-specific later releases, and increment a diagnostic counter. Never use the oldest server node across all parts indiscriminately. Reserve capacity for note-off/control processing; memory/CPU exhaustion must not create stuck notes.

### 9.8 Full-bank storage and bounded RAM

Store the complete selected banks outside the app binary in a versioned asset directory. Keep the pristine originals or a verified lossless deduplicated content store. FLAC/WAV/AIFF conversion may change container but must not remove layers, truncate tails, downmix or reduce bit depth/sample rate by default.

`PlayBuf`/`BufRd` require resident decoded buffers. RAM is approximately `frames * channels * 4` bytes per float buffer plus engine overhead, not the compressed FLAC size. `ServerOptions.memSize` is not the total budget for all sound buffers; measure actual process RSS as well as server allocation failures.

Implement a shared buffer cache keyed by sample-content ID, independent of part/program. Program prepare calculates the full playable program's working set, including release samples and default active mic layers, and loads asynchronously using `Buffer.read` with completion/sync. The program is `ready` only after every region reachable under its selected articulation/microphone configuration has valid buffers. Full-bank availability on disk and ready-in-RAM are separate catalog states.

Program switch is a two-phase action: prepare → commit. During prepare the old program continues sounding and accepts input. On success, new attacks select the new revision; old voices retain references to old buffers. Evict only unpinned buffers with no active voices/pending release layers. Release-source buffers for a currently-held note count as pinned even before its release sample starts. Canceling an obsolete prepare frees only its unreferenced assets.

Use a configurable explicit sample RAM budget. Compute admission before allocating: active references + new prepared set + safety margin must fit. If it does not, report “program combination exceeds this device's memory profile,” keep the old program and offer a user-visible alternative profile; do not silently strip velocity layers. The full workstation profile and limited Pi profile have separate acceptance results. A 2 GB Pi must not be advertised as supporting every full multi-mic kit plus multiple large pianos simultaneously without evidence.

No disk-streaming subsystem is assumed in the initial native sampler. `DiskIn`/`VDiskIn` alone are not a ready SFZ streaming engine with arbitrary loops and many regions. If full concurrent banks are required on 2 GB hardware, treat a streaming implementation as a separate necessary engineering milestone with measured deadlines, not a one-line substitution. An optional alternative is a separately evaluated sfizz integration, but it changes this pure-native-sampler design and SFZ compatibility still needs verification. [sfizz capabilities and partial SFZ2 support](https://sfz.tools/sfizz/). Do not add it silently or claim a stock SC sfizz UGen exists.

## 10. UI and preset behavior for the new catalog

Keep current control gestures and layouts unless additional metadata requires a selector. The instrument browser distinguishes Synth, Sampled and Drum Kit, then instrument family. Display meaningful names and articulations; hide source paths, opcode names and engine node IDs from musical use.

Controls come from a program-specific capability schema. Typical sampled controls are articulation, brightness where implemented, envelope/release, stereo width, mic mix and dynamics. Do not expose a generic synthesis knob which has no effect on a sample program. Do not force an articulation keyswitch onto the Omnichord's playable strum range; the UI sends explicit articulation IDs. MIDI keyswitch behavior, if offered, is a separate explicit mode.

Program selection displays loading/ready/error without blocking Qt. A loading label does not mean the audible old program has already changed. Persist stable program IDs and parameter schema versions, not list indices. User preset import must survive catalog reorder and retain original source IDs even when aliases merge.

The default percussion mapping must cover every drum role referenced by the existing 270 fills/rhythms and every supported GM note. Create explicit mappings and intentional substitutions for missing kit pieces with a report; do not treat every unknown percussion role as snare. Preserve independent OMNI and MIDI kit selections. Calibrate kits as a whole while retaining within-kit velocity relationships.

## 11. Startup, build and release plan

### 11.1 Process lifecycle

1. Supervisor reads validated configuration and asset lock; locates pinned SC runtime and dedicated class-library configuration.
2. Start headless `sclang` with the packaged bootstrap, private session and ports. Bootstrap configures and boots `scsynth` with the platform's audio backend. Keep launch flags in one platform adapter, verified against the packaged runtime's help; do not copy unverified flags between executables.
3. Create control/audio buses and ordered groups; load and verify SynthDefs; load catalog metadata and the initial selected sample programs asynchronously.
4. Build immutable sequence registry and preload fills. No transport starts during bootstrap.
5. Exchange protocol/catalog/version handshake. UI enters ready only after audio server sync and required programs are ready; errors include missing assets, unsupported program, incompatible protocol and audio device failure.
6. On shutdown, send Panic, wait a bounded grace interval, close engine and supervisor-owned child processes, release device resources. Do not kill another user's unrelated SC process by name.

Use one dedicated SC class-library search path so installed personal Quarks do not alter reproducibility. Do not depend on IDE startup files or user-global startup.scd. Keep audio device, rate, block size, sample budget and latency in versioned runtime profiles.

### 11.2 Packaging and legal/provenance outputs

Bundle pinned SC binaries and reviewed application code on supported platforms, with licenses and corresponding source pointers. Keep sample banks as a separate versioned downloadable/installable asset pack, with an offline installation option; do not fetch gigabytes on every app launch. Verify assets before activation, stage updates alongside existing versions, and atomically replace the catalog pointer after validation.

Extend `release_inputs.json`, `release-manifest.json` and SBOM generation with SC version, SCLOrk commit, adapter hash, bank-manifest hash, converter version and per-bank license records. Preserve attribution for Alexander Holm, retuning/remapping contributors and every bank's included notices. An account of a file's availability is not a substitute for its license record.

Use Linux/Pi native package CI, macOS native CI and Windows native CI. Test actual packaged input paths and process separation, not only Python import success. Leave Android/P4 legacy release status explicit; never swap their release metadata to SC without a working packaged backend and device-specific tests.

The current LB `music/catalogue_provenance.json` also records that no repository-level license file is present. Public visibility is not a license grant. Before distributing the combined migration, resolve and document the LB application's own licensing consistently with the included GPL components and preserved catalog provenance; the sample banks' CC0/BY terms do not license the application automatically. This does not block local implementation or this handover, but it belongs in release preparation.

### 11.3 Sequential implementation milestones

| Milestone | Deliverable | Exit evidence |
| --- | --- | --- |
| M0 — baseline capture | Clean worktree; pinned old source; semantic trace exporter; bank/synth lock skeleton | Current tests characterized, no musical edits; all old program IDs and public control messages inventoried |
| M1 — SC skeleton | Supervisor, handshake, one safe synth, buses, manual/MIDI handles, Panic | Packaged Linux/Pi proof of process ownership and note-off safety |
| M2 — pure compiler | Typed definitions/events retaining 48-PPQ-equivalent behavior | All rhythm/fill/riff plans match legacy semantic fixtures, including rounding and ordering |
| M3 — coordinator | Native TempoClock execution, immutable nested children, gates, replacement tickets | Deterministic trace tests for every sequencer contract; no UI musical timer |
| M4 — synthesis | All 109 adapters and three acid models; program schema | 109 compile/render/lifetime reports; acid articulation truth table passes |
| M5 — multisampler | Offline parser/normalizer, native player, sustain/releases/RR/mic mapping/cache | Synthetic mapping fixtures pass; complete VSCO import and full 16-layer Salamander playback |
| M6 — full banks | VCSL/Iowa/selected Karoryfer/kit imports; curation and source coverage | Zero unaccounted useful audio; sample/program manifest; repeatable audition/selection report |
| M7 — application cutover | Qt/MIDI uses SC exclusively on supported targets; migrated presets | Existing use cases pass; no production `_wire`/AMY engine calls on SC route |
| M8 — release | Native platform packages, asset pack, documentation, SBOM | Real-device timing/CPU/RAM acceptance; explicit platform/capacity matrix; no unsupported completeness claims |

Complete one vertical slice early (manual note + bass root + one fill + one VSCO instrument) to expose timing/routing mistakes, then finish the complete scope. Do not stop after the slice and call the handover implemented. Keep commits reviewable by milestone, with tests and documentation updated together. Do not publish/merge/release merely because this handover requests implementation guidance.

## 12. Acceptance tests: exact scenarios and expected results

### 12.1 Existing test entry points

Run from `amysynth_version/qt_frontend` in the project's declared environment:

```bash
python tests/run_tests.py --list
python tests/run_tests.py --suite unit
python tests/run_tests.py --suite quality
```

Use the existing runner for additional applicable frontend/presets/input/native suites. The full current `all` suite requires pinned AMY and platform dependencies; do not report it passed unless actually run. Add new suite names `sc-compiler`, `sc-sequencer`, `sc-audio`, `sc-banks`, `sc-packaged` to that same runner, with artifact/report conventions preserved.

Existing characterization targets include `tests/test_sequencer_tags.py`, `tests/test_bass_riffs.py`, `tests/test_bass_riff_musical_contracts.py`, `tests/test_transport_characterization.py`, `tests/integration/test_native_rhythm.py`, plus preset/tuning/MIDI/provenance tests. Do not replace a failing invariant with a new expected value until the difference is explicitly classified as intentional.

### 12.2 Semantic trace format

Instrument test builds with a structured trace:

```text
transportEpoch, logicalTick48, logicalBeat, executionId,
definitionId, revision, eventOrdinal, action,
owner, voiceHandle, programRevision, pitchHz,
gateReasons, suppressed, audioTimetag, transactionId
```

Capture comparable AMY semantics from the pinned compiler/native tests. Compare note/launch/gate timing, phase and release ownership rather than raw OSC strings or waveform equality. Use a test-only in-memory trace sink; do not add debug playback/timing drivers to production classes. Record exceptions for intentional SC behavior changes: node-specific release safety, acid destination accents, new sound programs and recalibrated gains.

### 12.3 Required deterministic sequencer cases

| ID | Scenario | Expected result |
| --- | --- | --- |
| S01 | Publish finite A; start; republish A midway | Current execution keeps old notes/releases; next start uses new revision |
| S02 | Launch A twice at same or overlapping beats | Two execution IDs; no accidental replacement; releases remain separate |
| S03 | Root launches finite arp; stop root | Arp continues all scheduled notes/releases; no further child launches |
| S04 | Gate drum role for `[1,2)` beats | Hit at 1 suppressed; hit at 2 allowed; prior tail unchanged; phase unchanged |
| S05 | Two overlapping fill gates; first expires | Role remains gated until last applicable interval ends |
| S06 | Fill control and base hit same tick | Control applies first; base hit suppressed; fill's own hit sounds |
| S07 | Gate while an existing note awaits release | Release still executes exactly once; no stuck voice |
| S08 | Rapid same-lane aligned replacements before boundary | Only newest pending replacement starts, without consuming unbounded slots |
| S09 | Concurrent bass and drum updates | Neither lane's coalescing cancels the other |
| S10 | 7-note arp, rate 1/2/3/4, repeated onsets | Correct step/gate math; overlaps and cross-bar tails preserved |
| S11 | Harmony update during arp/bass slide | Old child retains old pitch chain; future child gets new harmony |
| S12 | Tempo changes between attack and release | Release stays at prescribed beat; timbral decay/slide seconds stay seconds |
| S13 | Phrase change at arbitrary old local phase | Old root stops next eligible tick; newest phrase starts at D+1 drain deadline with local phase zero |
| S14 | Three phrase changes before drain completion | No obsolete phrase starts; old captured releases are safe |
| S15 | Bass circular slide/overlap across phrase end | One finite unwrapped gesture, exactly one final release |
| S16 | No-gap dense non-slide phrase | Existing one-tick-margin rule only where allowed; sustained/slide invalid cases rejected |
| S17 | Fill-order and allowed-beat rotations | Exact `fill_occurrences` cycle for each selected subset/order and density |
| S18 | Running preset/rhythm switch | No clock reset or transport gap; existing live precedence preserved |
| S19 | Stop while manual chord/strum/MIDI sounds | Only specified accompaniment ownership stopped; manual parts retain expected state |
| S20 | Panic then delayed stale callback/packet | No new note; no stale release affects a newly allocated handle |
| S21 | Out-of-order/lost/duplicate transaction packets | All-or-none publication; bounded retries; no duplicate note-on |
| S22 | Program prepare fails or is superseded | Old program continues; no freed buffer used; no partial new program |
| S23 | External vs nested control at exact boundary | External next-tick rule; nested same-tick rule |
| S24 | Long finite child at final event delta zero | Last release executes before completion; no busy zero-delta loop |
| S25 | Pitch-bend/tuning/coupling across OMNI and MIDI | No pitch rounding or wrong note-off lookup; no pattern recompilation for bend |
| S26 | External aligned start pending; publish a different definition without another start | Pending execution retains its captured revision; only a later explicit replacement changes it |

For S04 use a diagnostic synth whose release tail can be measured independently of new attacks. Assert both event trace suppression and unchanged tail energy; merely checking bus volume is insufficient. For S12 test tempo up/down, including a change immediately before a release boundary and a bar-aligned replacement.

### 12.4 Multisample tests

Build tiny original synthetic audio fixtures (distinct frequencies/amplitudes per layer/RR/mic) for deterministic region-selection tests; these are test assets, not substitute shipping instruments. Required checks:

- Every boundary key and velocity including 1/127, all 16 Salamander layers, inclusive range edges and note-on velocity zero → note-off at MIDI input.
- Correct dB/velocity scaling, no independent per-file normalization, no double pitch/tune correction.
- Mono/stereo and source-rate differences, fractional tuning and global bend.
- RR progresses once per audible trigger; muted hits do not consume it; mic layers stay synchronized.
- Sustain pedal, repeated same-key strikes, release-key versus sustain-aware release, pedal transition noise once, correct release samples at long/short note ages.
- Loop attack, wrap, crossfade and gate exit at fractional rates, with no clicks/OOB reads/NaN.
- Choke one open hat without truncating unrelated cymbal/other part; fill gate does not invoke choke.
- Switch program while notes and release layers remain active; no use-after-free or missing tail.
- Bank integrity, missing file/case mismatch, include cycle, unsupported audible opcode and invalid root pitch all produce explicit import failures.
- Every required bank has complete source coverage and all installed programs can prepare, attack and release offline; no “ready” state with a missing buffer.

### 12.5 Audio and performance evidence

Use SC non-realtime rendering for repeatable audio checks and trace comparison, and live packaged tests for latency/dropouts. These prove different things: an offline render cannot prove real-time Pi safety. See [Score](https://doc.sccode.org/Classes/Score.html) for SC NRT tooling.

For each of 109 synths and each curated sample instrument, render a short low/mid/high phrase, soft/hard dynamics, held note where appropriate, release and panic. Check finite samples, clipping, silent unexpected output and node cleanup. Keep measured peak/RMS, render hashes, source/adaptation revision and listening disposition. Do not force bit-identical random-noise audio across architectures; compare bounded properties and deterministic seeded traces.

Measure a representative full performance: drums + active fill + bass slide + overlapping 7-note arp + manual chord + strum burst + six MIDI rows + MIDI drums + both reverbs. Start with source-platform audio settings, then tune buffer size/latency. Record hardware/OS/device/backend/sample rate/block size, scsynth average/peak CPU, RSS, buffer cache bytes, node/execution counts, underruns, and latency distribution. Proposed release targets: zero underruns in a 30-minute representative run, no stuck notes after a 10,000-event mixed trace, and an interactive input-to-audio p95 target under 35 ms where the chosen audio hardware permits. If a platform misses a target, publish its measured profile rather than claiming success.

Exercise sustained 120 Hz strum input on the real Pi with the existing QML visual workload. Preserve the preview voice limit/oldest-release semantics where the UI contract specifies four voices, independently of the larger engine's physical capacity. The full-bank memory benchmark must include simultaneous preparation of a replacement program while old voices still hold buffers.

## 13. Definition of done and implementation reporting

The migration is complete for a declared platform only when:

1. Qt manual performance, accompaniment and all MIDI paths use SC; no hidden AMY fallback is needed for an advertised feature.
2. All 109 synth source entries have working, credited, tested adapters or an explicitly blocking failure; no silent omissions from the requested baseline.
3. The mandatory VSCO bank and the other selected banks have verified downloads, normalized mappings, complete recording coverage, instrument curation and playable presets. All selected articulations/layers are available, with honest device-memory constraints.
4. Three primary acid models pass detached/slide/tie/destination-accent tests.
5. Sequencer trace tests prove phase, nested snapshot, mute, fill rotation and bass handover contracts, and existing application use cases pass.
6. Asset installation, reconnect, program loading, Stop/Panic, errors and preset migration work in the actual packaged application.
7. Platform package, asset lock, license/attribution records, SBOM and reproducible reports are delivered. Unsupported P4/Android migration work is identified, not hidden.

Implementation status reports must say what changed, exact commits, which suites ran, failures, measured hardware results, source bank coverage and any intentional musical differences. “SuperCollider can do this” is not evidence that this implementation does it. This handover supplies design and source evidence; it does not claim compiled SC, full sample downloads, auditions or device benchmarks have already been performed.

## 14. Important resolved choices and remaining empirical work

Resolved: one SC clock; typed plans rather than AMY-wire emulation; immutable finite children; event-kind-aware gating; node-specific releases; legacy timing normalization; conservative bass handover; three acid models; native SC multisampling; complete source banks on disk; bounded RAM cache; source-specific SFZ normalization; independent OMNI/MIDI buses and effects; stable program IDs; reproducible asset pins.

Still empirical, with implementation procedures specified above: audible near-duplicate decisions, final curated instrument count, per-program loudness, safe maximum polyphony, exact sample working sets, acid tonal calibration, native loop-reader audio quality and physical platform performance. Do not disguise these as verified facts, and do not stop implementation to ask the user to guess them: produce the renders/measurements and make the documented selection within the agreed criteria.

Optional banks not included by default: Muse Sounds (product-specific ecosystem), arbitrary internet SoundFonts with unclear redistribution terms, product-locked Kontakt/Alter-Ego banks, and repackaged orchestral compilations with mixed licenses/duplicated VSCO material. Broader Karoryfer instruments remain discoverable from the linked free-library page, but do not expand scope indefinitely before delivering the full selected set.


## Appendix A — exact 109 synth definitions

The table is a source inventory, not a compile/lifetime test result. “Gate” means an explicit `gate` argument is present in the inspected source; no gate means the adapter must determine one-shot/trigger/lifetime behavior. Original source names are retained as stable ID suffixes. All source files were fetched as text for this inventory; no SynthDefs were executed.

Category counts: bass 13, bells 6, drums 31, guitar 3, keyboards 8, misc 19, organ 7, pads 9, percussion 9, strings 3, winds 1. Total: **109**.

| # | Source / stable ID suffix | Category | Gate |
| --- | --- | --- | --- |
| 1 | [acidOto3091](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/bass/acidOto3091.scd) | bass | Yes |
| 2 | [acidOto3092](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/bass/acidOto3092.scd) | bass | No |
| 3 | [bassWarsaw](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/bass/bassWarsaw.scd) | bass | Yes |
| 4 | [combs](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/bass/combs.scd) | bass | Yes |
| 5 | [doubleBass](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/bass/doubleBass.scd) | bass | No |
| 6 | [fmBass](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/bass/fmBass.scd) | bass | No |
| 7 | [ikedaBass](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/bass/ikedaBass.scd) | bass | Yes |
| 8 | [ksBass](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/bass/ksBass.scd) | bass | No |
| 9 | [moogBass](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/bass/moogBass.scd) | bass | Yes |
| 10 | [noQuarter](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/bass/noQuarter.scd) | bass | No |
| 11 | [rubberBand](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/bass/rubberBand.scd) | bass | No |
| 12 | [subBass1](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/bass/subBass1.scd) | bass | No |
| 13 | [subBass2](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/bass/subBass2.scd) | bass | No |
| 14 | [glockenspiel](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/bells/glockenspiel.scd) | bells | No |
| 15 | [prayerBell](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/bells/prayerBell.scd) | bells | No |
| 16 | [pulseRisset](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/bells/pulseRisset.scd) | bells | No |
| 17 | [rissetBell](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/bells/rissetBell.scd) | bells | Yes |
| 18 | [sosBell](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/bells/sosBell.scd) | bells | No |
| 19 | [tubularBell](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/bells/tubularBell.scd) | bells | No |
| 20 | [blueNoise](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/drums/blueNoise.scd) | drums | Yes |
| 21 | [clapElectro](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/drums/clapElectro.scd) | drums | No |
| 22 | [clapGray](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/drums/clapGray.scd) | drums | No |
| 23 | [clapOto309](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/drums/clapOto309.scd) | drums | No |
| 24 | [cymbal808](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/drums/cymbal808.scd) | drums | No |
| 25 | [cymbalicMCLD](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/drums/cymbalicMCLD.scd) | drums | No |
| 26 | [hashercymbal](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/drums/hashercymbal.scd) | drums | No |
| 27 | [hihat1](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/drums/hihat1.scd) | drums | No |
| 28 | [hihatElectro](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/drums/hihatElectro.scd) | drums | No |
| 29 | [kick1](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/drums/kick1.scd) | drums | No |
| 30 | [kick808](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/drums/kick808.scd) | drums | No |
| 31 | [kickBlocks](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/drums/kickBlocks.scd) | drums | No |
| 32 | [kickRingz](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/drums/kickRingz.scd) | drums | No |
| 33 | [kick_chirp](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/drums/kick_chirp.scd) | drums | No |
| 34 | [kick_electro](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/drums/kick_electro.scd) | drums | No |
| 35 | [kick_oto309](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/drums/kick_oto309.scd) | drums | No |
| 36 | [kik3](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/drums/kik3.scd) | drums | No |
| 37 | [kraftySnare](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/drums/kraftySnare.scd) | drums | No |
| 38 | [neuroSnare](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/drums/neuroSnare.scd) | drums | No |
| 39 | [oneclapThor](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/drums/oneclapThor.scd) | drums | No |
| 40 | [purpleNoise](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/drums/purpleNoise.scd) | drums | Yes |
| 41 | [snare1](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/drums/snare1.scd) | drums | No |
| 42 | [snare909](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/drums/snare909.scd) | drums | No |
| 43 | [snareElectro](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/drums/snareElectro.scd) | drums | No |
| 44 | [snareOto309](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/drums/snareOto309.scd) | drums | No |
| 45 | [snareStein](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/drums/snareStein.scd) | drums | No |
| 46 | [sosHats](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/drums/sosHats.scd) | drums | No |
| 47 | [sosKick](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/drums/sosKick.scd) | drums | No |
| 48 | [sosSnare](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/drums/sosSnare.scd) | drums | No |
| 49 | [sosTom](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/drums/sosTom.scd) | drums | No |
| 50 | [squareDrum](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/drums/squareDrum.scd) | drums | No |
| 51 | [distortedGuitar](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/guitar/distortedGuitar.scd) | guitar | No |
| 52 | [modalElectricGuitar](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/guitar/modalElectricGuitar.scd) | guitar | No |
| 53 | [pluck](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/guitar/pluck.scd) | guitar | No |
| 54 | [FMRhodes1](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/keyboards/FMRhodes1.scd) | keyboards | Yes |
| 55 | [FMRhodes2](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/keyboards/FMRhodes2.scd) | keyboards | Yes |
| 56 | [cheapPiano1](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/keyboards/cheapPiano1.scd) | keyboards | No |
| 57 | [cs80leadMH](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/keyboards/cs80leadMH.scd) | keyboards | Yes |
| 58 | [defaultB](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/keyboards/defaultB.scd) | keyboards | Yes |
| 59 | [everythingRhodes](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/keyboards/everythingRhodes.scd) | keyboards | No |
| 60 | [harpsichord1](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/keyboards/harpsichord1.scd) | keyboards | No |
| 61 | [harpsichord2](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/keyboards/harpsichord2.scd) | keyboards | No |
| 62 | [beating](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/misc/beating.scd) | misc | No |
| 63 | [blip1](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/misc/blip1.scd) | misc | No |
| 64 | [chaoscillator](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/misc/chaoscillator.scd) | misc | Yes |
| 65 | [crossoverDistortion](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/misc/crossoverDistortion.scd) | misc | No |
| 66 | [decimator](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/misc/decimator.scd) | misc | Yes |
| 67 | [laserbeam](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/misc/laserbeam.scd) | misc | No |
| 68 | [moreHarmonics](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/misc/moreHarmonics.scd) | misc | Yes |
| 69 | [musicBox](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/misc/musicBox.scd) | misc | No |
| 70 | [noisy](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/misc/noisy.scd) | misc | No |
| 71 | [phazer](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/misc/phazer.scd) | misc | Yes |
| 72 | [ping_mh](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/misc/ping_mh.scd) | misc | No |
| 73 | [saturatingWavefolder](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/misc/saturatingWavefolder.scd) | misc | No |
| 74 | [sillyVoice](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/misc/sillyVoice.scd) | misc | Yes |
| 75 | [sputter](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/misc/sputter.scd) | misc | No |
| 76 | [triangleWaveBells](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/misc/triangleWaveBells.scd) | misc | Yes |
| 77 | [trig_demo](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/misc/trig_demo.scd) | misc | Yes |
| 78 | [vintageSine](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/misc/vintageSine.scd) | misc | Yes |
| 79 | [werkit](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/misc/werkit.scd) | misc | Yes |
| 80 | [werkit2](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/misc/werkit2.scd) | misc | Yes |
| 81 | [organDonor](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/organ/organDonor.scd) | organ | Yes |
| 82 | [organReed](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/organ/organReed.scd) | organ | Yes |
| 83 | [organTonewheel0](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/organ/organTonewheel0.scd) | organ | Yes |
| 84 | [organTonewheel1](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/organ/organTonewheel1.scd) | organ | Yes |
| 85 | [organTonewheel2](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/organ/organTonewheel2.scd) | organ | Yes |
| 86 | [organTonewheel3](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/organ/organTonewheel3.scd) | organ | Yes |
| 87 | [organTonewheel4](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/organ/organTonewheel4.scd) | organ | Yes |
| 88 | [apadMH](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/pads/apadMH.scd) | pads | Yes |
| 89 | [arpoctave](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/pads/arpoctave.scd) | pads | Yes |
| 90 | [feedbackPad1](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/pads/feedbackPad1.scd) | pads | Yes |
| 91 | [feedbackPad2](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/pads/feedbackPad2.scd) | pads | Yes |
| 92 | [feedbackPad3](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/pads/feedbackPad3.scd) | pads | Yes |
| 93 | [line](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/pads/line.scd) | pads | No |
| 94 | [midSideSaw](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/pads/midSideSaw.scd) | pads | Yes |
| 95 | [sawSynth](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/pads/sawSynth.scd) | pads | No |
| 96 | [superSaw](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/pads/superSaw.scd) | pads | Yes |
| 97 | [abstractDrum](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/percussion/abstractDrum.scd) | percussion | No |
| 98 | [frameDrum](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/percussion/frameDrum.scd) | percussion | No |
| 99 | [kalimba](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/percussion/kalimba.scd) | percussion | No |
| 100 | [marimba1](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/percussion/marimba1.scd) | percussion | No |
| 101 | [metalPlate](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/percussion/metalPlate.scd) | percussion | No |
| 102 | [modalMarimba](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/percussion/modalMarimba.scd) | percussion | No |
| 103 | [pmCrotales](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/percussion/pmCrotales.scd) | percussion | No |
| 104 | [steelDrum](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/percussion/steelDrum.scd) | percussion | No |
| 105 | [xylophone](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/percussion/xylophone.scd) | percussion | No |
| 106 | [prophet5pwmStrings](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/strings/prophet5pwmStrings.scd) | strings | Yes |
| 107 | [strings](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/strings/strings.scd) | strings | Yes |
| 108 | [violin](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/strings/violin.scd) | strings | Yes |
| 109 | [waveguideFlute](https://github.com/SCLOrkHub/SCLOrkSynths/blob/6730c745971aa45c95d9b4cddfb4d5ca342774b3/SynthDefs/winds/waveguideFlute.scd) | winds | Yes |

Static inspection of active UGen calls did not identify a mandatory third-party plugin in this set; the apparent `Disintegrator` reference in `organReed` is commented out. This is not a substitute for compiling all 109 definitions. `superSaw` builds 100 oscillator branches in its source; turning down a runtime count does not necessarily remove those branches from the graph. Its divisions also require safe handling of count=1 and zero detune. Preserve the full sound and use separately named optimized graphs if measured hardware needs them.

## Appendix B — all 75 VSCO SFZ mappings

These are the exact root mappings of the pinned SFZ branch. Import them all, then group articulation and keyswitch wrappers as specified in section 9. A mapping is not automatically a separate instrument. The bank also contains 3,168 audio files; every one needs a coverage disposition.

| # | Mapping |
| --- | --- |
| 1 | [BassoonStac.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/BassoonStac.sfz) |
| 2 | [BassoonSus.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/BassoonSus.sfz) |
| 3 | [BassoonVib.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/BassoonVib.sfz) |
| 4 | [CelloEns-KS.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/CelloEns-KS.sfz) |
| 5 | [CelloEnsPizz.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/CelloEnsPizz.sfz) |
| 6 | [CelloEnsSpic.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/CelloEnsSpic.sfz) |
| 7 | [CelloEnsSusVib-Quiet.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/CelloEnsSusVib-Quiet.sfz) |
| 8 | [CelloEnsSusVib.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/CelloEnsSusVib.sfz) |
| 9 | [CelloEnsTrem.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/CelloEnsTrem.sfz) |
| 10 | [Clarinet-KS.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/Clarinet-KS.sfz) |
| 11 | [ClarinetStac.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/ClarinetStac.sfz) |
| 12 | [ClarinetSus.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/ClarinetSus.sfz) |
| 13 | [Contrabass-KS.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/Contrabass-KS.sfz) |
| 14 | [ContrabassPizz.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/ContrabassPizz.sfz) |
| 15 | [ContrabassSpic.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/ContrabassSpic.sfz) |
| 16 | [ContrabassSusNV.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/ContrabassSusNV.sfz) |
| 17 | [ContrabassSusVB-Quiet.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/ContrabassSusVB-Quiet.sfz) |
| 18 | [ContrabassSusVB.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/ContrabassSusVB.sfz) |
| 19 | [ContrabassTrem.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/ContrabassTrem.sfz) |
| 20 | [FHornMute.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/FHornMute.sfz) |
| 21 | [FHornStac.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/FHornStac.sfz) |
| 22 | [FHornSus.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/FHornSus.sfz) |
| 23 | [Flute-KS.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/Flute-KS.sfz) |
| 24 | [FluteExpVib.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/FluteExpVib.sfz) |
| 25 | [FluteStac.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/FluteStac.sfz) |
| 26 | [FluteSusNV.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/FluteSusNV.sfz) |
| 27 | [FluteSusVib.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/FluteSusVib.sfz) |
| 28 | [GM-StylePerc.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/GM-StylePerc.sfz) |
| 29 | [Glockenspiel.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/Glockenspiel.sfz) |
| 30 | [Harp.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/Harp.sfz) |
| 31 | [Marimba.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/Marimba.sfz) |
| 32 | [OboeStac.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/OboeStac.sfz) |
| 33 | [OboeSusNV.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/OboeSusNV.sfz) |
| 34 | [OboeSusVib.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/OboeSusVib.sfz) |
| 35 | [OrganLoud.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/OrganLoud.sfz) |
| 36 | [OrganLoudPedal.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/OrganLoudPedal.sfz) |
| 37 | [OrganQuiet.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/OrganQuiet.sfz) |
| 38 | [OrganQuietPedal.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/OrganQuietPedal.sfz) |
| 39 | [PiccoloStac.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/PiccoloStac.sfz) |
| 40 | [PiccoloSus.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/PiccoloSus.sfz) |
| 41 | [SViolin-KS.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/SViolin-KS.sfz) |
| 42 | [SViolinPizz.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/SViolinPizz.sfz) |
| 43 | [SViolinSpic.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/SViolinSpic.sfz) |
| 44 | [SViolinTrem.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/SViolinTrem.sfz) |
| 45 | [SViolinVib-Quiet.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/SViolinVib-Quiet.sfz) |
| 46 | [SViolinVib.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/SViolinVib.sfz) |
| 47 | [Timpani.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/Timpani.sfz) |
| 48 | [TimpaniRolls.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/TimpaniRolls.sfz) |
| 49 | [TromboneStac.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/TromboneStac.sfz) |
| 50 | [TromboneSus.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/TromboneSus.sfz) |
| 51 | [TromboneVib.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/TromboneVib.sfz) |
| 52 | [TrumpetHarmonMuteSus.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/TrumpetHarmonMuteSus.sfz) |
| 53 | [TrumpetStac.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/TrumpetStac.sfz) |
| 54 | [TrumpetStraightMuteSus.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/TrumpetStraightMuteSus.sfz) |
| 55 | [TrumpetSus.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/TrumpetSus.sfz) |
| 56 | [TrumpetSusVib.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/TrumpetSusVib.sfz) |
| 57 | [Tuba-KS.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/Tuba-KS.sfz) |
| 58 | [TubaStac.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/TubaStac.sfz) |
| 59 | [TubaSus.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/TubaSus.sfz) |
| 60 | [TubularBells.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/TubularBells.sfz) |
| 61 | [UprightPiano.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/UprightPiano.sfz) |
| 62 | [VSUpright1.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/VSUpright1.sfz) |
| 63 | [ViolaEns-KS.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/ViolaEns-KS.sfz) |
| 64 | [ViolaEnsPizz.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/ViolaEnsPizz.sfz) |
| 65 | [ViolaEnsSpic.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/ViolaEnsSpic.sfz) |
| 66 | [ViolaEnsSusVib-Quiet.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/ViolaEnsSusVib-Quiet.sfz) |
| 67 | [ViolaEnsSusVib.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/ViolaEnsSusVib.sfz) |
| 68 | [ViolaEnsTrem.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/ViolaEnsTrem.sfz) |
| 69 | [ViolinEns-KS.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/ViolinEns-KS.sfz) |
| 70 | [ViolinEnsPizz.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/ViolinEnsPizz.sfz) |
| 71 | [ViolinEnsSpic.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/ViolinEnsSpic.sfz) |
| 72 | [ViolinEnsSusVib-Quiet.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/ViolinEnsSusVib-Quiet.sfz) |
| 73 | [ViolinEnsSusVib.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/ViolinEnsSusVib.sfz) |
| 74 | [ViolinEnsTrem.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/ViolinEnsTrem.sfz) |
| 75 | [Xylophone.sfz](https://github.com/sgossner/VSCO-2-CE/blob/6dd651d55dde97fd4028699be9d4481f26917891/Xylophone.sfz) |

## Appendix C — VCSL complete source-folder inventory

The instrument folders below are from the full release sample tree. They include legacy/alternate recordings; curation determines which become separate browser instruments. All 183 SFZ mappings and all audio-file paths are additionally listed in the machine-readable source inventory in the companion bundle.

| Source family | Exact instrument folder |
| --- | --- |
| Aerophones / Edge-blown Aerophones | [Ball Whistle](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Aerophones/Edge-blown%20Aerophones/Ball%20Whistle) |
| Aerophones / Edge-blown Aerophones | [Baroque Alto Recorder](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Aerophones/Edge-blown%20Aerophones/Baroque%20Alto%20Recorder) |
| Aerophones / Edge-blown Aerophones | [Baroque Bass Recorder](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Aerophones/Edge-blown%20Aerophones/Baroque%20Bass%20Recorder) |
| Aerophones / Edge-blown Aerophones | [Baroque Soprano Recorder](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Aerophones/Edge-blown%20Aerophones/Baroque%20Soprano%20Recorder) |
| Aerophones / Edge-blown Aerophones | [Baroque Tenor Recorder](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Aerophones/Edge-blown%20Aerophones/Baroque%20Tenor%20Recorder) |
| Aerophones / Edge-blown Aerophones | [Ocarina, Small](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Aerophones/Edge-blown%20Aerophones/Ocarina%2C%20Small) |
| Aerophones / Edge-blown Aerophones | [Ocarina, Typical](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Aerophones/Edge-blown%20Aerophones/Ocarina%2C%20Typical) |
| Aerophones / Edge-blown Aerophones | [Pipe Organ](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Aerophones/Edge-blown%20Aerophones/Pipe%20Organ) |
| Aerophones / Edge-blown Aerophones | [Renaissance Organ](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Aerophones/Edge-blown%20Aerophones/Renaissance%20Organ) |
| Aerophones / Edge-blown Aerophones | [Train Whistle, Toy](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Aerophones/Edge-blown%20Aerophones/Train%20Whistle%2C%20Toy) |
| Aerophones / Free Aerophones | [Harmonica-Hohner-Special20-C](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Aerophones/Free%20Aerophones/Harmonica-Hohner-Special20-C) |
| Aerophones / Free Aerophones | [Harmonica-Hohner-Special20-F](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Aerophones/Free%20Aerophones/Harmonica-Hohner-Special20-F) |
| Aerophones / Free Aerophones | [Harmonica-Hohner-Super64](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Aerophones/Free%20Aerophones/Harmonica-Hohner-Super64) |
| Aerophones / Free Aerophones | [Siren](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Aerophones/Free%20Aerophones/Siren) |
| Aerophones / Lip Aerophones | [Didgeridoo](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Aerophones/Lip%20Aerophones/Didgeridoo) |
| Aerophones / Reed Aerophones | [Saxello](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Aerophones/Reed%20Aerophones/Saxello) |
| Aerophones / Reed Aerophones | [Tenor Saxophone](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Aerophones/Reed%20Aerophones/Tenor%20Saxophone) |
| Chordophones / Composite Chordophones | [Concert Harp](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Chordophones/Composite%20Chordophones/Concert%20Harp) |
| Chordophones / Composite Chordophones | [Folk Harp](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Chordophones/Composite%20Chordophones/Folk%20Harp) |
| Chordophones / Composite Chordophones | [Strumstick](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Chordophones/Composite%20Chordophones/Strumstick) |
| Chordophones / Zithers | [Dan Tranh](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Chordophones/Zithers/Dan%20Tranh) |
| Chordophones / Zithers | [Grand Piano, Kawai - Legacy](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Chordophones/Zithers/Grand%20Piano%2C%20Kawai%20-%20Legacy) |
| Chordophones / Zithers | [Grand Piano, Kawai](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Chordophones/Zithers/Grand%20Piano%2C%20Kawai) |
| Chordophones / Zithers | [Grand Piano, Steinway B](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Chordophones/Zithers/Grand%20Piano%2C%20Steinway%20B) |
| Chordophones / Zithers | [Harpsichord, English](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Chordophones/Zithers/Harpsichord%2C%20English) |
| Chordophones / Zithers | [Harpsichord, Flemish](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Chordophones/Zithers/Harpsichord%2C%20Flemish) |
| Chordophones / Zithers | [Harpsichord, French](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Chordophones/Zithers/Harpsichord%2C%20French) |
| Chordophones / Zithers | [Harpsichord, Italian](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Chordophones/Zithers/Harpsichord%2C%20Italian) |
| Chordophones / Zithers | [Harpsichord, Unk](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Chordophones/Zithers/Harpsichord%2C%20Unk) |
| Chordophones / Zithers | [Psaltery, Bowed and Plucked](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Chordophones/Zithers/Psaltery%2C%20Bowed%20and%20Plucked) |
| Chordophones / Zithers | [Upright Piano, Knight](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Chordophones/Zithers/Upright%20Piano%2C%20Knight) |
| Chordophones / Zithers | [Upright Piano, Yamaha](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Chordophones/Zithers/Upright%20Piano%2C%20Yamaha) |
| Electrophones / TX81Z | [Clavisynth](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Electrophones/TX81Z/Clavisynth) |
| Electrophones / TX81Z | [FM Piano](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Electrophones/TX81Z/FM%20Piano) |
| Electrophones / TX81Z | [Piano 1](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Electrophones/TX81Z/Piano%201) |
| Idiophones / Friction Idiophones | [Wine Glasses](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Friction%20Idiophones/Wine%20Glasses) |
| Idiophones / Plucked Idiophones | [Kalimba, Kenya](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Plucked%20Idiophones/Kalimba%2C%20Kenya) |
| Idiophones / Plucked Idiophones | [Kalimba, Tanzania](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Plucked%20Idiophones/Kalimba%2C%20Tanzania) |
| Idiophones / Plucked Idiophones | [Mbira Mavembe (Gandanga), Zimbabwe, Low G](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Plucked%20Idiophones/Mbira%20Mavembe%20%28Gandanga%29%2C%20Zimbabwe%2C%20Low%20G) |
| Idiophones / Plucked Idiophones | [Mbira dzaVadzimu Nyamaropa, Zimbabwe, Low B](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Plucked%20Idiophones/Mbira%20dzaVadzimu%20Nyamaropa%2C%20Zimbabwe%2C%20Low%20B) |
| Idiophones / Plucked Idiophones | [Nyunga Nyunga, Mozambique, Low F](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Plucked%20Idiophones/Nyunga%20Nyunga%2C%20Mozambique%2C%20Low%20F) |
| Idiophones / Struck Idiophones | [Agogo Bells](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Agogo%20Bells) |
| Idiophones / Struck Idiophones | [Anvil](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Anvil) |
| Idiophones / Struck Idiophones | [Balafon](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Balafon) |
| Idiophones / Struck Idiophones | [Bell Tree - Legacy](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Bell%20Tree%20-%20Legacy) |
| Idiophones / Struck Idiophones | [Bell Tree](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Bell%20Tree) |
| Idiophones / Struck Idiophones | [Brake Drum](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Brake%20Drum) |
| Idiophones / Struck Idiophones | [Cabasa](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Cabasa) |
| Idiophones / Struck Idiophones | [Cajon](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Cajon) |
| Idiophones / Struck Idiophones | [Claps](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Claps) |
| Idiophones / Struck Idiophones | [Clash Cymbals 1](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Clash%20Cymbals%201) |
| Idiophones / Struck Idiophones | [Clash Cymbals 2](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Clash%20Cymbals%202) |
| Idiophones / Struck Idiophones | [Claves](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Claves) |
| Idiophones / Struck Idiophones | [Cowbells](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Cowbells) |
| Idiophones / Struck Idiophones | [Finger Cymbals](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Finger%20Cymbals) |
| Idiophones / Struck Idiophones | [Flexatone](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Flexatone) |
| Idiophones / Struck Idiophones | [Glockenspiel](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Glockenspiel) |
| Idiophones / Struck Idiophones | [Gong 1](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Gong%201) |
| Idiophones / Struck Idiophones | [Gong 2](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Gong%202) |
| Idiophones / Struck Idiophones | [Guiro](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Guiro) |
| Idiophones / Struck Idiophones | [Hand Bells, Nepalese](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Hand%20Bells%2C%20Nepalese) |
| Idiophones / Struck Idiophones | [Hand Chimes](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Hand%20Chimes) |
| Idiophones / Struck Idiophones | [Hi-Hat Cymbal](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Hi-Hat%20Cymbal) |
| Idiophones / Struck Idiophones | [Marimba](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Marimba) |
| Idiophones / Struck Idiophones | [Mark Trees](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Mark%20Trees) |
| Idiophones / Struck Idiophones | [Ratchet](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Ratchet) |
| Idiophones / Struck Idiophones | [Shaker - Legacy](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Shaker%20-%20Legacy) |
| Idiophones / Struck Idiophones | [Shaker, Large](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Shaker%2C%20Large) |
| Idiophones / Struck Idiophones | [Shaker, Small](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Shaker%2C%20Small) |
| Idiophones / Struck Idiophones | [Slapstick](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Slapstick) |
| Idiophones / Struck Idiophones | [Sleigh Bells](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Sleigh%20Bells) |
| Idiophones / Struck Idiophones | [Slit Drum](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Slit%20Drum) |
| Idiophones / Struck Idiophones | [Suspended Cymbal 1](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Suspended%20Cymbal%201) |
| Idiophones / Struck Idiophones | [Suspended Cymbal 2](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Suspended%20Cymbal%202) |
| Idiophones / Struck Idiophones | [Tambourine 1](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Tambourine%201) |
| Idiophones / Struck Idiophones | [Tambourine 2](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Tambourine%202) |
| Idiophones / Struck Idiophones | [Tambourine 3 - Legacy](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Tambourine%203%20-%20Legacy) |
| Idiophones / Struck Idiophones | [Tambourine 4 - Legacy](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Tambourine%204%20-%20Legacy) |
| Idiophones / Struck Idiophones | [Tambourine 5 - Legacy](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Tambourine%205%20-%20Legacy) |
| Idiophones / Struck Idiophones | [Triangles](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Triangles) |
| Idiophones / Struck Idiophones | [Tubular Bells 1](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Tubular%20Bells%201) |
| Idiophones / Struck Idiophones | [Tubular Bells 2](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Tubular%20Bells%202) |
| Idiophones / Struck Idiophones | [Tubular Bells 3 - Legacy](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Tubular%20Bells%203%20-%20Legacy) |
| Idiophones / Struck Idiophones | [Tubular Glockenspiel](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Tubular%20Glockenspiel) |
| Idiophones / Struck Idiophones | [Vibraphone](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Vibraphone) |
| Idiophones / Struck Idiophones | [Vibraslap](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Vibraslap) |
| Idiophones / Struck Idiophones | [Woodblock](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Woodblock) |
| Idiophones / Struck Idiophones | [Xylophone](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Idiophones/Struck%20Idiophones/Xylophone) |
| Membranophones / Other Membranophones | [Ocean Drum](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Membranophones/Other%20Membranophones/Ocean%20Drum) |
| Membranophones / Struck Membranophones | [Bass Drum 1](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Membranophones/Struck%20Membranophones/Bass%20Drum%201) |
| Membranophones / Struck Membranophones | [Bass Drum 2](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Membranophones/Struck%20Membranophones/Bass%20Drum%202) |
| Membranophones / Struck Membranophones | [Bass Drum 3 - Legacy](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Membranophones/Struck%20Membranophones/Bass%20Drum%203%20-%20Legacy) |
| Membranophones / Struck Membranophones | [Bongos](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Membranophones/Struck%20Membranophones/Bongos) |
| Membranophones / Struck Membranophones | [Conga](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Membranophones/Struck%20Membranophones/Conga) |
| Membranophones / Struck Membranophones | [Darbuka](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Membranophones/Struck%20Membranophones/Darbuka) |
| Membranophones / Struck Membranophones | [Frame Drum](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Membranophones/Struck%20Membranophones/Frame%20Drum) |
| Membranophones / Struck Membranophones | [Legacy Snares](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Membranophones/Struck%20Membranophones/Legacy%20Snares) |
| Membranophones / Struck Membranophones | [Legacy Toms](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Membranophones/Struck%20Membranophones/Legacy%20Toms) |
| Membranophones / Struck Membranophones | [Snare Drum, Modern 1](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Membranophones/Struck%20Membranophones/Snare%20Drum%2C%20Modern%201) |
| Membranophones / Struck Membranophones | [Snare Drum, Modern 2](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Membranophones/Struck%20Membranophones/Snare%20Drum%2C%20Modern%202) |
| Membranophones / Struck Membranophones | [Snare Drum, Modern 3](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Membranophones/Struck%20Membranophones/Snare%20Drum%2C%20Modern%203) |
| Membranophones / Struck Membranophones | [Snare Drum, Rope Tension](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Membranophones/Struck%20Membranophones/Snare%20Drum%2C%20Rope%20Tension) |
| Membranophones / Struck Membranophones | [Timpani 1](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Membranophones/Struck%20Membranophones/Timpani%201) |
| Membranophones / Struck Membranophones | [Timpani 2](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Membranophones/Struck%20Membranophones/Timpani%202) |
| Membranophones / Struck Membranophones | [Tom 1](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Membranophones/Struck%20Membranophones/Tom%201) |
| Membranophones / Struck Membranophones | [Tom 2](https://github.com/sgossner/VCSL/tree/b6e6ac82d22248edee98a0bde185eb9ef6d439ad/Membranophones/Struck%20Membranophones/Tom%202) |

## Appendix D — machine-readable companion bundle

The accompanying ZIP contains this handover plus:

- `source-lock.json`: exact repositories/commits, license classifications, audio-entry counts and source byte totals. Archive/audio SHA-256 fields are explicitly unverified until the implementation downloads them.
- `synth-catalog-source.json`: the 109 source entries, original argument names, source URLs, Git blob IDs and SHA-256 of fetched source text. These are not finished adapter presets.
- `vsco-sfz-inventory.json`: all 75 mapping paths/URLs and Git blob IDs.
- `source-file-inventory.json`: complete pinned Git file inventories for the 11 sample banks and the synth collection; distinguishes Git blob IDs from download SHA-256.
- `opcode-inventory-static.json`: a lexical inventory from fetched SFZ/include text for research; comments are stripped, but it is not a resolved parser/support report and includes macros. Generate authoritative semantic coverage in the actual compiler.

Use the JSON files as acquisition/checklist inputs. `adapter_status=to_implement`, `compile_test_status=not_run` and `audio_test_status=not_run` are intentional. The bundle contains no audio banks, SC binaries, completed migration code or claimed listening results.
