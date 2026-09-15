# SuperCollider migration status

Status: implementation status, not a completion claim
Owner: SuperCollider edition integration
Applies to: `sc_version`
Last verified: 2026-09-15

Locally exercised target: Linux x86_64

Packaged targets: Linux x86_64, Raspberry Pi aarch64, macOS arm64 and Windows
x86_64

## Working vertical slice

- Qt and SuperCollider are separate supervised processes connected by a
  typed, versioned loopback OSC protocol.
- The production Python import closure is checked structurally and cannot
  reach the AMY transports, local AMY service, AMY compatibility adapter or
  `c_amy`; those modules and their firmware/package trees are absent from the
  SC edition rather than merely excluded at packaging time.
- Python compiles immutable musical plans; one SC `TempoClock` owns execution,
  quantization, note releases, gates and snapshot lifetimes.
- Session reset, panic, exact voice handles and global pitch bend are wired
  through the SC runtime. Standard MIDI sustain (CC64) is owner-scoped per
  pitched MIDI row: key releases are held inside SC and pedal-up releases only
  that row's deferred handles. It remains visible to the existing controller-
  learn path without transferring note-lifetime timing into Qt.
- Prepared program parameters are keyed by musical owner as well as stable
  program identity and session-wide revision. Selecting the same instrument
  on independent MIDI, manual, bass or automatic-chord parts therefore cannot
  leak one part's controls into another. Manual strum and MIDI preview gesture
  messages carry that exact revision too; they no longer fall back to revision
  1 and lose the selected program's prepared controls.
- The four native acid voices support the current conservative TB-303
  articulation contract, implement the visible ADSR controls and advertise
  riff articulation support with the bass-row orange indicator. Three-register
  NRT calibration now places each voice at the same median-RMS reference as the
  measured SCLOrk catalogue; the formerly hot Acid Oto source no longer masks
  otherwise balanced percussion.
- All 109 pinned SCLOrkSynths definitions compile and remain in the auditable
  source inventory. The pitched browser admits 76 measured definitions; 31
  raw drum definitions remain available to the dedicated drum path, nineteen
  used drum programs have their own measured playback calibration, and two
  numerically unstable definitions are explicitly excluded from playback.
  The automated float NRT audit exercises the browser voices at MIDI A2, A4
  and A5 with bounded per-program output calibration.
- The generated VSCO manifest contains all 75 source mappings and 3,163 sample
  regions. The PCM browser groups them into 22 instrument families and 66
  canonical pitched variant/articulation choices. Equivalent standalone and
  key-switch views are merged without dropping recorded instruments. The
  dedicated percussion identity remains drum-only, so playable notes are
  never stolen for frontend key-switches. Startup requires that percussion
  program to load before the engine announces readiness.
- OMNI bass, strum and chord selection is partitioned into `SYN` and `PCM`
  views. Synth controls come from checked-in source defaults and a reviewed
  alias/range vocabulary; engine names and ineffective native parameters are
  not exposed as UI promises. See [`INSTRUMENT_BROWSER.md`](INSTRUMENT_BROWSER.md).
- The five pitched MIDI rows now use that same `SYN`/`PCM` catalogue and
  parameter surface. Both percussion locations expose fifteen explicit drum
  kits: the legacy PCM kit, five native SC kits and nine expanded PCM kits.
  The compact runtime data preserves per-kit calibration, and tests require a
  common reference-groove target plus bounded pad peaks for every PCM kit and
  explicit measured gains for every selected native drum program.
  Reverb controls name the native SC model (`WET`, `ROOM`, `DAMP`) and no
  longer promise AMY-only ranges or terminology.
- Manual strum has no frontend voice-stealing limit: every accepted attack has
  an exact independent handle and SC owns its release. The engine admits 64
  live handles per gesture owner and releases the oldest with a short fade only
  under saturation, preventing GUI event bursts from exhausting native voice
  buses. See [`STRUM_PRESSURE.md`](STRUM_PRESSURE.md). Root sequence changes
  are scheduled at the current transport phase, so riff, arpeggio, leader and
  activity changes do not restart the beat clock.
- The complete mix crosses one private master stage with a 0.95 safety limiter.
  Upper-register filter adapters keep four pinned source definitions finite at
  the full strum boundary. Sample voices map stable lifetime control buses, so
  later release or retune never targets a naturally ended region node. Native
  SCLOrk voices use owned node groups for both control and cleanup, so neither
  `/n_set` nor `/n_free` can race a naturally ended source child.
- Legacy AMY patch keys are accepted only as preset-migration aliases. They do
  not appear in the SC instrument browser and all outgoing program selections
  use canonical `sc.*` or `sample.*` identities.
- Supernova starts with 8,192 buffer identifiers. This is intentionally above
  the 3,163-region VSCO inventory, while decoded sample RAM remains governed by
  the separate bounded cache.
- A sample request outside an articulation's recorded key range selects the
  nearest valid source region and then tunes it to the requested note. Strum
  therefore remains complete without inventing missing recordings.
- Live startup plus attacks/releases across all 76 admitted SCLOrk voices,
  percussion roles and out-of-range VSCO notes completed without server
  failures, duplicate `/n_free` requests or buffer-number exhaustion.
- MIDI and OSC integration tests keep the sender, frontend and engine receiver
  in separate processes.
- The independent SC workflow runs the active dependency-free frontend unit
  and portable MIDI/OSC process contracts in addition to the SC compiler,
  coordinator, NRT audio, bank and package suites. Old engine, Android and
  ESP32 contracts are not copied into this test tree or presented as evidence
  for the SC product.
- Sequencer tests cover immutable running snapshots, overlapping finite
  executions, root/child lifetime separation, exact release ownership,
  overlapping half-open gates, same-boundary replacement coalescing,
  external-versus-nested timing boundaries, tempo-domain releases, stale
  callbacks and every 1--4 note/beat direction of a seven-note arpeggio.
- A single GitHub workflow tests all four packaged platforms. Publication and
  package construction require an explicit `release=true` manual dispatch and
  use an independent `-SC` release tag. Linux and Raspberry Pi receive
  AppImages, macOS a DMG and Windows a ZIP. Each contains the same
  checksum-pinned, source-built headless SuperCollider 3.14.1 runtime and no
  AMY runtime. The IDE, SC Qt bindings, help browser and QtWebEngine are not
  part of any package; diagnostic package builds enforce the whole-package
  size budget without an engine-runtime exemption.
- First launch streams the commit-pinned GitHub tree snapshot of the
  `linuxificator/VSCO-2-CE` runtime branch at the first-run location chosen
  through Qt (or the exact `--sample-root` path).
  Its 2,166 WAVs are the union of
  playable SFZ and direct PCM-drum references; 1,002 unreachable source files
  and Git history are not downloaded. No archive or `.git` object store remains,
  preventing the WAV payload from being stored twice. Startup admits a checkout or ordinary
  copy by semantically comparing the required-path JSON with an atomic receipt
  and checking that every listed path exists. JSON ordering is irrelevant and
  no file hashes are calculated at startup; Git metadata is not a runtime
  dependency for an ordinary copy.
- SuperCollider configuration revision 7 and protocol revision 2 include the
  explicit sample branch and commit, per-event drum duration cap and per-owner gesture
  voice boundary. Every frozen package
  self-check exercises additive migration from all earlier revisions before an
  audio process is opened.
- Frozen package verification resolves both source and PyInstaller asset
  layouts through the production catalogue loader; a package cannot pass by
  checking directory names while its instrument metadata is unreachable.
- Frozen package verification executes the packaged bootstrap with the pinned
  SC class library before publication. The Supernova executable is configured
  on `Server.program`, the API owned by SC 3.14, and host `systemctl` probes
  are isolated from the package's private dynamic-library search path.
  Bundled `sclang` uses SC's standalone mode and one explicit class tree, so
  neither its former build prefix nor host extensions enter the engine.
- The production server is Supernova. Independent sources, bus strips and room
  effects use ordered `ParGroup` stages; each dependent voice chain and the
  final master stage remains serial. Source builds enable Supernova, every
  package requires it, and source launch refuses to fall back to `scsynth`.
- Linux launch completes Supernova's parallel DSP pool with the standard
  RealtimeKit service when the JACK callback is realtime but helpers are not.
  Discovery is restricted to the exact executable in the launcher's private
  process session and ends after startup verification; it never watches or
  modifies unrelated processes. See [`SUPERNOVA.md`](SUPERNOVA.md).
- The bounded sample-source catalogue records all eleven pinned Git banks and
  the separate Iowa discovery authority. The local inventory tool rejects LFS
  placeholders and produces per-file asset locks; see
  [`SAMPLE_BANKS.md`](SAMPLE_BANKS.md).
- Production-QML endurance is distinct from the controller graph: the real
  `Main.qml` is rendered and captured in a separate process, QML binding loops
  are fatal, and browser-model regression tests exercise rapid program changes.
  A repeatable idle phase also distinguishes startup/test-driver cost from
  steady-state `sclang` CPU usage.
- The source compiler now safely expands the macro/include structure used by
  the next banks while preserving region provenance. Their audible opcode
  normalization and playback semantics remain explicitly incomplete. Its
  audio inventory reads WAV, AIFF and FLAC and hashes decoded PCM in one
  architecture-independent representation for cross-container deduplication.

## Expanded music data

- Fifteen kits each have 54 exact rhythm arrangements and five activity
  levels: 810 arrangements in total. Their 4,050 finite fills preserve exact
  role-and-slot continuation under selective gates.
- The neutral 1,664-riff bass catalogue resolves against all 810 kit/rhythm
  contexts. Explicit voice capabilities choose gated tie/glide/accent behavior
  or a conservative detached fallback without moving timing into Qt.
- Eighteen complete factory preset snapshots select the expanded data while
  preserving user-owned preset files. The detailed contract and evidence are
  in [`MUSIC_EXPANSION.md`](MUSIC_EXPANSION.md).

## Not yet complete

- The migration handover's additional large instrument banks are not imported.
- VSCO import preserves its declared key/velocity/random/round-robin regions,
  gain, tuning, attack/release and named keyswitch articulations. It does not
  silently turn the six whole-file RIFF sampler loops into sustain loops: they
  are inventoried with an explicit ignored disposition. No reviewed partial
  loop exists in this bank. The importer does not yet claim the advanced
  release, sustain and microphone behavior needed by the additional planned
  banks.
- Sequential round-robin state advances only for admitted notes and is scoped
  by musical owner, program, key, articulation and velocity layer. OMNI drums
  and a MIDI row therefore cannot disturb each other's sample sequence.
- Sample-program admission publishes and accounts asynchronous buffer reads in
  one language-interpreter turn. Concurrent program changes share pending
  buffers, cannot admit the same decoded bytes twice and cannot evict a buffer
  protected by the program currently being prepared.
- Direct MIDI sample attacks arriving during asynchronous preparation are held
  at the typed client boundary and emitted only after the engine reports the
  exact program revision ready. A matching early note-off cancels the deferred
  attack, preventing both dropped first notes and late ghost notes.
- Reconfiguring a MIDI row releases its voices first and then releases its
  superseded program revision, so the sample cache can reclaim recordings
  without affecting another row's owner-scoped program state.
- Immutable root and finite sequencer executions retain every exact PCM
  `program@revision` carried by their events. A frontend selection may be
  released immediately after lane replacement, but its decoded buffers remain
  admitted until the final SC-owned execution ends. Roots inherit the sample
  revisions of finite children they can launch, so a boundary replacement
  cannot create a use-after-release window.
- Natural source/sample completion and later release or drum-choke requests no
  longer race on node identifiers. Stable control buses own those gates and
  are freed only from the corresponding node completion callback.
- Sample-drum lane publication requires an explicit ready status for that
  kit's program; the generic engine-ready handshake no longer guesses that the
  legacy VSCO percussion bank is loaded. Namespaced legacy catalogue slots are
  resolved to semantic roles before SC maps them to distinct VSCO keys at
  original playback speed.
- SFZ `trigger=release_key` and `trigger=release` regions are normalized as
  release layers rather than attacks. Physical key-up and final sustain-aware
  release are separate SC-owned hooks, preserve release velocity, and spawn
  only the matching release-layer kind. Every possible release recording for
  a held key/articulation remains pinned even after a program change; its
  release velocity and round-robin choice need not be guessed at note-on.
  Naturally-ended pitched attacks retain their lightweight handle metadata
  until key-up, while percussion one-shots clean up immediately. The
  additional banks' duration curves, pedal noises and source-specific
  release-gain opcodes remain incomplete.
- Deterministic non-realtime tests render the production mono and stereo
  sample SynthDefs from synthetic fixtures, including gated release, without
  taking over the workstation's live audio session.
- Fixed-register qualification proves bounded signal production, browser
  admission and technical gain staging. It does not prove subjective musical
  usefulness across every dynamic, polyphonic texture and long performance.
  The exact method and remaining listening work are in
  [`PLAYBACK_QUALIFICATION.md`](PLAYBACK_QUALIFICATION.md).
- Full soft/mid/hard and low/mid/high sample audits and measured resident-set
  admission remain open. A separate-process live endurance qualification now
  covers interaction, engine logs and physical PipeWire output continuously.
  Its four-cycle release baseline exercised 3,254 public actions across the
  complete current SYN/PCM catalogue without server, clipping or dropout
  failure; extended human listening remains appropriate.
- Linux source behavior was exercised locally with SuperCollider 3.13.0. The
  pinned 3.14.1 compiler, engine, frontend and package workflow passed on
  commit `fc3b26e` in GitHub run `34790456369`.
- Physical acceptance on Raspberry Pi, macOS and Windows remains outstanding;
  their CI jobs exercise the same engine/protocol contracts and verify their
  packaged runtime layouts. Android and ESP32-P4 are not SuperCollider-edition
  targets.

## Distribution boundary

Each application package bundles the Qt frontend and SuperCollider runtime. It
does not bundle the VSCO recordings. Linux retains the operating system's
normal JACK/PipeWire integration, and Raspberry Pi receives no realtime or CPU
isolation policy. Sample licensing, audio-session ownership and machine policy
therefore remain explicit.

Current code and executable tests take precedence over the original migration
handover where implementation details have evolved. The handover remains the
acceptance backlog for items explicitly listed above.
