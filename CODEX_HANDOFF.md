# Codex session handoff — AMY/LB Omnichord state and code-quality audit

Updated: 2026-09-02.

This file is intentionally written for future Codex sessions. It records the
working state, decisions, lessons learned and branch/release discipline from
the AMY socket, Android, nested-sequencer, rhythm-fill, Gamma9001 and release
automation work. It supplements `AGENTS.md` and the authoritative design
contracts under `amysynth_version/design/`; it does not override either of
them or the current user's request.

The branch intended for analysis/continuation is `rework/code_quality` in
`linuxificator/LB_Omnichord`. T01-T25 and package slimming were merged to
`main`, released as `R20260901T212205`, and fast-forwarded back into the
retained rework branch with both release fixes and the validated screenshot
follow-up. Read
`amysynth_version/design/code_quality_tasks/POST_T25_MAIN_RELEASE_20260901.md`
for the exact release timeline and lessons. Analysis documents still do not
authorize new product refactoring without a current user request.

## Mandatory startup route

Before changing active AMY/LB code, read:

1. `AGENTS.md`;
2. `amysynth_version/README.md`;
3. `amysynth_version/design/README.md`;
4. the baseline contracts listed there: `principles.md`, `architecture.md`,
   `behavior.md`, `testing.md`;
5. the routed subsystem documents for the task.

For `rework/external_controls`, also read at minimum:

- `amysynth_version/design/midi.md`;
- `amysynth_version/design/midi_control.md`;
- `amysynth_version/design/presets.md`;
- `amysynth_version/design/sound_balance.md`;
- `amysynth_version/design/amy_interface.md`;
- `amysynth_version/qt_frontend/docs/CONTROL_SAFETY.md`;
- `amysynth_version/qt_frontend/tests/USE_CASES.md`.

Also read `amysynth_version/design/CODEX_HANDOVER_EXTERNAL_CONTROLS.md` before
changing slider or MIDI-learn interaction. It records why stable QML delegates
are required during a drag and why manual movement of a bound numeric control
is now an intentional release-before-edit operation rather than an incidental
side effect. Indicator clicks use the explicit grey/blue-to-learn,
green-to-unlinked-blue and red-to-grey state machine documented there.

For code-quality/refactoring work, start at
`amysynth_version/design/CODEX_HANDOVER_CODE_QUALITY_BASELINE.md`, read the
dedicated handover for the selected boundary and then
`CODEX_HANDOVER_CODE_QUALITY_ROADMAP.md`. Each future implementation must still
read the authoritative subsystem contracts and obtain normal user direction;
analysis findings are not a behavioral specification.

If the task touches rhythm, platform packages, Windows, Android, ESP32-P4 or
the AMY fork, follow the additional rows in `design/README.md` before editing.

## Current repository state

### LB Omnichord

- Own origin: `git@github.com:linuxificator/LB_Omnichord.git`.
- Current `main` before this documentation-only rework continuation:
  `6ccebe9a66bdd8d6fe72a095082d9162ee194836` (`Refresh README screenshots`).
- Latest successful full release: `R20260901T212205`, produced from commit
  `3740191e9ae44c17e83188c78cf67c0668f20d58` by GitHub Actions run
  `33560667071`. All seven regression groups, five platform packages, Android
  emulator, exact manifest, SPDX SBOM, signed attestations, publication and
  screenshot refresh passed. The release uses Gamma9001 AMY commit
  `7c34aa514f10c33f02692f735166d65f4e20374a` and contains exactly five
  packages, five SHA-256 companions and four release-evidence files.
- Branch `rework/external_controls` was merged into `main` by
  `50118fb18c952a27c64a77a6486527a64559ebb5`. It is retained as branch history;
  continuation analysis now belongs on `rework/code_quality`.
- Historical run `33372709995` built and published `R20260831T082359`, but
  its screenshot-refresh job failed because `refresh-readme-screenshots` did
  not include `release-metadata` in `needs`, so the release tag output was out
  of scope. Commit `026272d` fixed that by making the dependency explicit.
- Branch `feature/drum_fills` ended at
  `57f627ac060bc4cb3d84298ea313211ec1232226`
  (`Remove obsolete rhythm rework task`) and has been merged into `main`.
- Historical branch `features/gamma9001` ended at
  `067e7437b85b1613783160f764b1042de14bce07`
  (`Make native wire waits ingestion-aware`) and remains a separate
  Gamma9001 implementation. It was not merged into `main`; configuration
  revision 5 and AMY release `R20260901T201533` restore it as the hosted
  published-package default on `rework/code_quality`.

### AMY fork

Local convention: `/home/jeroen/omnichord/amyfork/amy`.

Relevant fork branches and exact commits:

- `origin/upstream/amy_socket_api_xtra`:
  `e501d497316d6bea1666c7c8e7bcd118d13b9a05`
  (`Document Android integration lessons`).
- `origin/upstream/nested_sequencer`:
  `4de6d4ffd58964edd519eb14b2dc0046663ed1d1`
  (`Document arpeggio one-shot use case`).
- Historical Tiny-bank LB release branch:
  `origin/releases/amy_omnichord_R20260831T042456` at
  `14240031c135fdcd76a7a3a8ec81da8ef405c4b0`
  (`Support deterministic offline live configuration`).
- Historical Gamma9001 LB release branch:
  `origin/releases/amy_omnichord_R20260831T001253` at
  `00157856312de89f6dc293f90efb1889f0ceff23`
  (`Register Gamma9001 PCM in Android service`).
- Current hosted Gamma9001 LB release branch:
  `origin/releases/amy_omnichord_R20260901T201533` at
  `7c34aa514f10c33f02692f735166d65f4e20374a`
  (`Record unified Gamma9001 Omnichord release`).

On 2026-08-31, `gh pr list --repo shorepine/amy --state all --head
linuxificator:upstream/amy_socket_api_xtra` and the same command for
`upstream/nested_sequencer` returned no matching PRs. Before changing or
commenting on Shorepine PRs, re-check the actual GitHub state rather than
relying on this note.

## Branch and release discipline

- Do not implement directly on `main`. Use an explicit feature/fix/rework
  branch and push it to the LB fork origin.
- "Own origin" means `linuxificator/LB_Omnichord` for LB and
  `linuxificator/amy` for AMY. Do not push work branches to Shorepine remotes.
- Pushing ordinary commits to LB `main` intentionally runs the complete release
  workflow. Use that only after explicit merge/release approval.
- A screenshot-only post-release commit is different: it contains only
  `README.md` plus the two release-tagged PNGs and includes both trailers:
  `skip-rebuild: README screenshots only` and `skip-checks:true`.
  `skip-rebuild` is the human-readable project marker; `skip-checks:true` is
  the GitHub-recognized trailer that prevents another workflow loop.
- AMY release branches consumed by LB are immutable integration branches.
  Create a new release branch when the pinned AMY dependency changes. LB CI
  must pin both branch and exact SHA.
- Clean AMY upstream-offer branches must not contain Codex handoff text,
  LB-specific implementation policy or abandoned experiments.

## Primary engineering rules established in this work

- Keep generic AMY functionality in AMY; keep LB/Omnichord musical policy in
  LB. AMY may know about pattern instances and tags; it must not know that a
  tag means "kick", "hi-hat", "fill", "bass riff" or "Omnichord chord lane".
- Minimize AMY changes. If LB behavior can be expressed through generic AMY
  primitives and wire messages, do not extend AMY for LB-specific convenience.
- Existing AMY sequencer behavior, both C/Python API and wire `H` commands,
  must remain compatible. New nested-pattern behavior lives under the existing
  `zQ` extended-control family.
- Do not resurrect the bus-mixer experiment. It was abandoned for upstream and
  is not required by the current LB rhythm/fill design.
- Qt remains a wire-only client. It must not import `amy` or `c_amy`, link AMY
  directly, or manage AMY internals. Platform wrappers may supervise processes.
- Use existing working platform references before inventing new architecture.
  Android is an AMY/Oboe service over a private Unix socket, not Kivy and not
  a PulseAudio design. Windows is a native service over a private named pipe,
  not TCP and not WSL.
- For input bugs, first identify the failing boundary: QML event, backend
  state, wire generation, transport, AMY parsing, sequencer execution, or audio
  output. Fix the failing layer without redesigning unrelated layers.

## AMY changes and rationale

### Minimal socket API / Android portability offer

The reduced Shorepine-facing socket offer is `upstream/amy_socket_api_xtra`.
It was created after the earlier full Android/Godot branches proved too large
for upstream maintenance.

What belongs in that minimal offer:

- `src/amy_unix_socket.[ch]`: a small Linux/Android pathname `AF_UNIX`
  `SOCK_SEQPACKET` transport helper.
- A plain Linux regression for the socket helper.
- Documentation for Android/porting facts, including references to the larger
  retained fork branches.

What intentionally does not belong there:

- the full Android AAR/service implementation;
- Godot Android project code;
- LB Omnichord release wrappers;
- bus mixer code;
- Codex handoff files.

The generic socket rule is: the socket thread receives packets and queues them;
AMY processing happens at a safe owner boundary such as immediately before an
Oboe render block. The transport is packet/wire framing only, not an audio
backend and not a language-specific AMY API.

Android lessons:

- The client and AMY service remain separate processes in the same Android
  package/UID.
- The AMY process owns Oboe/AAudio.
- The service publishes `amy.sock` only after Oboe has started and the audio
  callback has run at least once.
- The Qt/Godot/client side opens the app-private socket and sends normal AMY
  wire messages. It does not start/stop `AmyService` directly.
- Emulator host logs may mention PulseAudio because the emulator host uses it;
  the app-level proof is the guest service reporting Oboe/AAudio and the test
  comparing AMY render samples with the exact Oboe callback buffer.

Windows lesson:

- LB's Windows release did not require AMY core changes. The adaptation is a
  wrapper/service design: PySide6 connects via Qt `QLocalSocket` to a private
  Windows named pipe; a separate native `amy_service.exe` owns AMY/miniaudio.
  The pipe is LF-framed because Windows named pipes are byte streams.

### Nested sequencer / finite pattern primitives

The nested-sequencer upstream branch is `upstream/nested_sequencer`. The
motivation came from LB Omnichord rhythm fills and chord arpeggios: sending
large root-sequencer blocks for every fill or arpeggio state change is
unnecessarily heavy, fragile over serial, and makes note-off ownership hard to
reason about.

The chosen AMY abstraction is stored finite patterns with an explicit
one-shot/loop lifetime:

- `LOOP` expresses a repeating base role.
- `ONE_SHOT` expresses a finite phrase such as a drum fill, whole automatic
  chord or one arpeggio note.
- A triggered instance adds only lifetime, phase and optional public tag; the
  committed pattern definition stays immutable for already-running instances.

This deliberately reuses sequencer concepts instead of adding an Omnichord
special case. One musical nesting level is enough in practice and prevents
recursive nesting. Pattern payloads reject root sequencer commands and
pattern-creating `zQ` controls; finite `zQM` is the only allowed leaf-control
exception.

Wire/API shape:

- `zQB`: begin or replace a staging pattern;
- `zQE`: add a pattern event using the familiar tick/period/tag semantics;
- `zQC`: atomically commit a staged pattern;
- `zQT`: trigger a pattern as one-shot or loop;
- `zQA`: schedule root events that trigger patterns;
- `zQS`: stop tagged instances;
- `zQM`: finite muting of tagged instances, currently used by fills;
- `zQR`: clear a pattern definition.

The earlier temporary top-level pattern command was removed. Keeping authoring
under `zQ` avoids introducing a new top-level wire syntax family and keeps the
new behavior grouped with sequencer control.

The portable AMY default remains small (`max_patterns` defaults to 32). LB's
release profiles configure 1024 stored patterns, 64 events per pattern and 32
active/pending instances because the Omnichord fill/arpeggio catalogue is large
but only a few instances run at once.

Behavioral proof required and maintained:

- legacy sequencer API and wire behavior remains compatible;
- existing `H` semantics are tested;
- new `zQ` operations have API/wire equivalence tests;
- one-shot/loop timing, quantization, immutable commits, reset and stop
  behavior are tested in AMY;
- LB native tests then prove the real deployed AMY release accepts the complete
  Omnichord wire stream.

### Optional future onset gate

Do not implement this unless explicitly requested. It remains documented as an
optional route in
`amysynth_version/design/rhythm_rework/new_patterns/CODEX_HANDOVER_OPTIONAL_SEQUENCER_ONSET_GATE.md`.

The desired future primitive would behave like explicit gate-on/gate-off for
future note-ons of a tagged instance while allowing already-sounding notes to
receive their normal note-offs. It should be generic AMY sequencer functionality,
not an Omnichord role command. It is not required for the current fill or
arpeggio implementation.

## LB rhythm/fill/arpeggio implementation decisions

- Five percussion activity levels are complete alternatives, not cumulative
  layers.
- Current data has 54 rhythms, five levels and 270 fills. The design reserves
  enough pattern IDs for more than 700 fills.
- At startup LB validates and authors every fill into AMY once. A fill is a
  compact `ONE_SHOT`; runtime scheduling sends root trigger events rather than
  streaming the fill content repeatedly.
- Base percussion roles are independent tagged `LOOP` pattern instances.
- Fill continuation is LB policy. LB uses
  `music/drums/drum_fill_continuation_roles.json` to decide which roles
  continue. For roles not continuing, LB stores generic finite
  `zQM<tag,duration>` controls in the fill. AMY only sees tagged-instance
  muting.
- It is not necessary to synthetically add every continuing base instrument
  into each fill. The per-role `zQM` approach suppresses only the roles that
  should pause.
- No bus mixer is used or required for this behavior.
- Pressing rhythm Start must sound the already-visible selected percussion
  level immediately; the user must not need to reselect one of the five levels.
- Live rhythm/preset/control changes must not stop `zY`, reset the AMY
  timebase or create an artificial gap.

The chord/arpeggio regression path produced two important conclusions:

- Stopping/replacing future arpeggio root triggers must not delete or defer the
  note-off of an already-started arpeggio note.
- The robust solution is immutable `ONE_SHOT` children. Each whole chord or
  arpeggio note owns its own note-on and matching note-off. `/1`, `/2`, `/3`
  and `/4` use disjoint child-pattern families, so switching rate replaces only
  future triggers; a sounding `/2` note still releases at its original `/2`
  gate and is not shortened.

Manual chord ownership remains separate:

- synth 3 is manually held chord input and stops on real pointer-up;
- synth 4 is automatic rhythm chord/arpeggio output;
- manual long-press takeover clears future synth-4 triggers but does not issue
  immediate synth-4 all-off and does not alter percussion, bass, transport or
  timebase.

## Drum banks and Gamma9001

The hosted published default is Gamma9001. ESP32-P4 remains a separately
declared Tiny-bank firmware target because its current flash/storage profile
does not contain the Gamma9001 blob.

Supported concepts:

- `tiny`: compact built-in PCM bank; used by the current ESP32-P4 target.
- `gamma9001`: AMY built with Gamma9001 sample data and GM-mapped kit patches.
- `general_midi`: AMY's patch-258 drum-note map; it is still AMY audio, not
  external MIDI output.

Do not assume the same wire preset/note means the same sound across tiny and
Gamma9001 builds. A Gamma9001 release must use an AMY release branch built
for Gamma9001 on all locally hosted targets being tested. On Android that means
defining `GAMMA9001`, generating/linking the Gamma9001 blob with AMY's
`gamma9001-blob-c` generator, and verifying that presets 0..18 select the full
Gamma808 ROM while presets 256..391 use the larger blob.

The native drum-kit audio smoke tests render every distinct realization and
reject silence:

```bash
python tests/drum_kit_audio_smoke.py tiny
python tests/drum_kit_audio_smoke.py gamma9001
python tests/drum_kit_audio_smoke.py general_midi
```

Run each one with an AMY extension built for the selected bank.

Observed warning in manual Gamma9001 testing:

```text
**_instrument_push_forgotten_note: forgotten pool overflow synth 0 note 292/60
```

No audible malfunction was reported at that time, but future Gamma work should
treat this as a real diagnostic to investigate rather than ignoring it.

## Platform/release lessons learned

- Android packaging uses the PySide6 Android deployment path, not Kivy.
- The Android release gate builds x86_64 and arm64 APKs, installs the x86_64
  APK in an emulator, drives packaged QML tap/hold behavior and verifies AMY
  render samples match Oboe callback samples.
- Qt Android library ordering matters. `Quick` must load before
  `QuickControls2`; tests guard against accidental ordering from Python set
  iteration.
- Windows package validation must run the packaged entry point, not just source
  scripts. It verifies native AMY compilation, non-silent offline rendering and
  the named-pipe boundary, but does not prove physical audio, MIDI, latency or
  drop-out behavior.
- macOS/Windows packaged QML chord tests must wait for the real packaged
  `TapHandler` hold promotion and then observe immediate release on pointer-up.
- Release screenshots are captured from the real production Qt scene after a
  successful `main` release. They are stored as
  `screenshots/omni-RYYYYMMDDTHHMMSS.png` and
  `screenshots/midi-RYYYYMMDDTHHMMSS.png`, and README links are updated to
  those exact files.
- Screenshot sanity validation checks that files are readable PNGs, are
  1920x850 and have enough sampled color variation to reject a blank or obvious
  error screen. Pixel-perfect screenshot comparison was removed because sparse
  renderer jitter of a few pixels caused false churn.

## Local verification commands

From `amysynth_version/qt_frontend` in the frontend environment:

```bash
/home/jeroen/omnichord/omnichord-env/bin/python tests/run_tests.py --list
/home/jeroen/omnichord/omnichord-env/bin/python tests/run_tests.py --suite unit
/home/jeroen/omnichord/omnichord-env/bin/python tests/run_tests.py --suite all
```

In the managed Codex sandbox, Unix-socket tests can fail with:

```text
PermissionError: [Errno 1] Operation not permitted
```

That is a sandbox restriction around local socket `bind()`. Re-run the suite
outside the sandbox before treating it as a product failure.

Targeted screenshot/release-contract checks:

```bash
/home/jeroen/omnichord/omnichord-env/bin/python tests/test_release_screenshots.py
/home/jeroen/omnichord/omnichord-env/bin/python tests/test_packaging.py
/home/jeroen/omnichord/omnichord-env/bin/python tests/test_static_contracts.py
git diff --check
```

For AMY itself, use the branch-specific tests documented in that repository,
including `make test`, `tests/run_amy_unix_socket_test.sh`, and the nested
sequencer C/Python tests when changing the relevant subsystem.

## Safe next work on `rework/external_controls`

The likely next feature area is external control/MIDI behavior. Keep the work
inside LB unless a generic AMY primitive is demonstrably required.

Recommended first steps:

1. Read the mandatory startup route and the MIDI/control documents listed
   above.
2. Inspect existing tests before changing behavior:
   `test_midi_control_bindings.py`, `test_midi_cc_qt.py`,
   `test_midi_engine.py`, `test_sound_balance_features.py`,
   `test_static_contracts.py` and the MIDI/control sections of
   `tests/USE_CASES.md`.
3. Preserve the wire-only frontend boundary and the current AMY pin unless the
   user explicitly asks for an AMY release update.
4. Add or update executable tests before relying on manual testing.
5. Do not change release packaging or `main` workflow behavior as a side effect
   of external-control work.

## Known unresolved or deliberately deferred items

- Physical validation is still separate from hosted CI for Windows audio/MIDI,
  Android touch/audio-route/latency, Raspberry Pi audio and macOS physical
  devices.
- Native Windows MIDI input remains future work behind the existing MIDI
  callback boundary.
- The optional AMY onset gate is not implemented and must not be added to the
  already-offered nested-sequencer work without a separate explicit request.
- Gamma9001 is the hosted LB release contract. Do not change it independently
  on only one package target; the exact AMY pin, compiled symbols and revision-5
  drum map must move together.
