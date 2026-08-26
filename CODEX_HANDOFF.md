# Codex Session Handoff

Updated 2026-08-27 on branch `main`. The implementation and four-platform
release baseline described below was built from commit `3345502`; this handoff
and its companion documentation were committed afterward. Inspect `git status`
and the current branch before continuing.

This file records operational state and completed work from the AMY/Qt bugfix,
MIDI-control and native-Windows sessions. It supplements, but does not override,
`AGENTS.md`, the current user request or the authoritative contracts under
`amysynth_version/design/`.

## Mandatory continuation route

Before changing active AMY code, follow the complete startup route in
`AGENTS.md` and `amysynth_version/design/README.md`. For Windows work, also read
all of:

- `amysynth_version/qt_frontend/docs/WINDOWS_NATIVE.md`;
- `amysynth_version/qt_frontend/README.md`;
- `amysynth_version/qt_frontend/INSTALL.md`;
- `.github/workflows/desktop-release.yml`.

Do not use this handoff as a replacement for those contracts.

## Current architectural state

- The active implementation is Qt/PySide6 plus AMY. Sonic Pi is frozen
  historical material.
- Qt generates AMY wire requests only. It does not import `amy`/`c_amy`, link
  AMY or control the synth service from application code.
- Desktop packages contain two separate runtime components. A packaging
  launcher may start and supervise both processes without changing their wire
  boundary.
- Linux uses `AF_UNIX/SOCK_SEQPACKET` between Qt and the Python AMY service.
- macOS uses LF-framed `AF_UNIX/SOCK_STREAM` because Darwin has no Unix-domain
  `SOCK_SEQPACKET`.
- Native Windows uses Qt `QLocalSocket` to a private Windows named pipe owned by
  the native C `amy_service.exe`. It does not use TCP and does not use WSL.
- ESP32-P4 uses LF-delimited AMY wire requests over UART. Android's proven
  design likewise keeps the app and AMY service in separate processes.

## Completed musical/UI work

### Live preset changes

Commit `e52dbb2` (`Preserve live chords across preset changes`) fixed the
original bug where selecting an OMNI preset stopped a held chord.

- Physical chord-button ownership, active row/root and chord-gate state survive
  the change.
- Sound converges to the destination preset's chord type, inversion, octave,
  tuning and chord instrument without requiring the player to release and press
  the chord again.
- A held chord may therefore change voicing/timbre during a preset switch, but
  it must not become silent merely because the preset changed.

### MIDI control feedback and preset ownership

Commits `f0ed4fd`, `8e66bbe` and `9e4ef0f` completed the MIDI-control regression
work described during this session.

- Real incoming CC movement updates the bound backend value and the visible QML
  slider, including OMNI/MIDI reverb and rhythm tempo.
- After explicit unlink, the temporary blue controller notice ends on the next
  genuine CC movement; without movement it expires normally.
- APG/LDR is backend-owned OMNI preset state. Presets store `strum_mode`; old
  presets default to APG.
- A green MIDI binding has exclusive numeric authority. Manual clicks, drags,
  tap controls, setters, nudge/UP/DOWN actions, copies and resets cannot change
  its value. Double-tap is the explicit unlink gesture; the unlinking gesture
  itself does not edit the number.
- Section RST restores selection and unbound values while preserving bound
  values and section volume. Hidden instrument targets are restored without
  temporarily selecting/sending their patch.
- Runtime preset selection preserves live values for source/destination
  bindings, except for an explicit same-controller/different-target conflict.
- In that conflict, the destination preset wins the global one-to-one mapping
  and its stored target value is authoritative. The outgoing handle flashes red
  and incoming handle flashes blue for about two seconds (110 ms fade halves),
  then they settle free/green respectively.
- MIDI-owned tempo disables/greys both rhythm UP/DWN buttons. MIDI-owned tuning
  disables/greys the affected tuning controls; coupled tuning takes authority
  from a bound side and refuses divergent independently bound references.
- Rhythm and bass play symbols now share centered Canvas triangle geometry and
  repaint from backend transport state.
- Reverb level is consistently 0.00–3.00 through QML, backend clamps, CC mapping
  and owned AMY bus commands.

The authoritative details are in `amysynth_version/design/midi_control.md`,
`amysynth_version/design/presets.md`, `amysynth_version/design/gui.md`,
`amysynth_version/design/tuning.md`,
`amysynth_version/design/rhythm_bahavior.md`,
`amysynth_version/qt_frontend/docs/CONTROL_SAFETY.md` and
`amysynth_version/qt_frontend/tests/USE_CASES.md`.

### Manual takeover of rhythm chords

Commit `53a67e4` (`Release rhythm chords on manual takeover`) fixed the former
regression-list point 13.

- Pressing a manual chord first closes the automatic-chord gate.
- It sends `l0i4`, an ordinary velocity-zero note-off for all active voices of
  automatic chord synth 4, before manual synth-3 note-ons.
- The selected patch's normal release envelope and effect tail remain audible;
  this is not an oscillator reset or hard kill.
- Only future automatic-chord tags are cleared. Drums, bass, transport and the
  sequencer timebase continue.
- This prevents a currently sounding rhythm chord from hanging after its
  scheduled future note-off was removed.

## Native Windows implementation

### Stable transport decision

The supported Windows path is:

```text
LB_Omnichord.exe (frozen PySide6 frontend)
    -> QLocalSocket
    -> private \\.\pipe\LB_Omnichord_AMY_<unique-guid>
    -> amy_service.exe
    -> AMY C engine/miniaudio
```

Important implementation details:

- `code/amy_transport.py` owns `_QtLocalSocketWriter`. The `QLocalSocket`
  object is created, connected, written and closed entirely on the existing
  command-writer thread to preserve QObject thread affinity and keep blocking
  writes away from the UI thread.
- `app_core.py --amy-local-name NAME` selects this transport. It is mutually
  exclusive with Unix `--amy-socket`.
- `packaging/windows/amy_service.c` uses `CreateNamedPipeA` with
  `PIPE_REJECT_REMOTE_CLIENTS`, one client, byte mode and blocking reads.
- Every logical AMY request ends in `Z` and is followed by LF. The service
  buffers partial/multiple `ReadFile()` results and splits only on LF.
- `packaging/windows/run_windows.ps1` creates a unique pipe name. It starts the
  service, waits for a short-lived `%LOCALAPPDATA%/LB_Omnichord/amy.pipe` ready
  file, verifies that its content is the expected name, deletes it, then starts
  the frontend. The ready file is discovery only, never command transport.
- The launcher owns child-process cleanup. The Qt application still does not
  own or import AMY.
- `packaging/build_windows.ps1` builds native `amy_service.exe`, freezes the Qt
  frontend independently with PyInstaller `--onedir`, and packages both plus
  the launcher in a self-contained zip.
- Frozen assets resolve from `sys._MEIPASS`; source-tree-relative lookup is
  wrong for the final PyInstaller layout.

### Why this is not AF_UNIX or TCP

Windows has native `AF_UNIX/SOCK_STREAM` since Windows 10 build 17063, and the
CI runner is Windows Server 2025 build 26100. Old Windows compatibility was not
the problem. Official CPython for Windows still does not expose
`socket.AF_UNIX`. Adding a ctypes Winsock implementation or custom Python
extension would duplicate Qt's already-supported local IPC layer.

Several commits are deliberate failed/diagnostic history and must not be read
as the current architecture:

- `6eace68` through `78376ce` diagnosed the Windows AF_UNIX startup failure;
- `df0899d` temporarily used loopback TCP to prove the rest of the package;
- `fbaa1ce` hardened that temporary service behavior;
- `906b4c5` replaced both experiments with the final native named-pipe design.

Do not restore TCP or the earlier Python AF_UNIX writer unless a new explicit
requirement changes the architectural decision.

### AMY and drum-bank compatibility

The release workflow pins the AMY fork at
`25213785696dd40e6cce59ab428e560a410d240f`.

- Linux and macOS apply `packaging/amy-tiny-bank.patch`, install with
  `AMY_PCM_BANK=tiny`, and Linux CI rejects Gamma9001 symbols.
- The Windows build does not go through AMY `setup.py`. Its CMake target
  compiles `amy.c`/`pcm.c` without defining `GAMMA9001` and does not link the
  optional generated `drums_bin.c`.
- At the pinned AMY revision, that selects `pcm_tiny.h` and the tiny version of
  MIDI drum patch 258 by construction.
- OMNI rhythm commands use direct preset/native-note pairs 0–10 from
  `config/amy_config.json`; these meanings match Linux, macOS and ESP32-P4.
- Defining `GAMMA9001` on Windows would make identical wire requests select
  different drums and is therefore a compatibility regression.

The current Windows smoke proves non-silent PCM rendering, but it does not yet
identify each tiny-bank drum acoustically. If the AMY pin/build inputs change,
add or run an explicit bank-identity regression rather than relying only on a
nonzero-sample check.

### Windows build and release status

The native package work began at `7a7ed04`. MSVC/CMake/path/launcher corrections
continued through `a711123`. Package smoke work began at `0223166`; diagnostics
and asset-resolution fixes continued through `ddc64e7`; named pipes landed in
`906b4c5`; `7962956` selects Visual Studio 2026 when available and falls back to
Visual Studio 2022.

The dedicated `testing/windows_smoke` branch builds only the Windows package
and does not publish a release. On `main`, all six frontend suites gate Linux,
Raspberry Pi, macOS and Windows jobs, and one release is published only after
all four packages pass.

GitHub Actions run `33021825480`, from main commit
`33455020101744ffa9c360b1a3cbf04dabd3009d`, completed successfully on
2026-08-26:

- all six frontend suite jobs passed;
- Linux x86_64 AppImage passed;
- Raspberry Pi aarch64 AppImage passed;
- macOS arm64 DMG passed;
- native Windows x86_64 zip passed;
- release publication passed.

The Windows Server 2025 job extracted only the final zip and then observed:

- `amy_service.exe --self-test`: 6,140 nonzero rendered samples;
- packaged launcher smoke: 209 real wire commands and 13,138 nonzero rendered
  samples;
- offscreen/software Qt/QML startup, packaged asset loading, initial-state
  publication, test-chord note-on/release, named-pipe delivery and clean Qt
  event-loop exit;
- no leaked `amy_service.exe` and no leftover ready file.

The resulting four-platform release is `R20260826T230234`. It contains:

- `LB_Omnichord.R20260826230234.Linux-x86_64.AppImage`;
- `LB_Omnichord.R20260826230234.RaspberryPi-aarch64.AppImage`;
- `LB_Omnichord.R20260826230234.macOS-arm64.dmg`;
- `LB_Omnichord.R20260826230234.Windows-x86_64.zip`;
- one matching SHA-256 file per package.

### What Windows CI does not prove

- No physical Windows speaker/interface output was heard or measured.
- No physical Windows MIDI controller was tested. Native Windows MIDI input is
  not implemented; the current reader is ALSA raw-MIDI only.
- Command-to-audio latency, jitter, drop-outs and behavior under heavy
  patches/reverb were not measured.
- The current host profile still defaults to 44.1 kHz/256 samples, tries
  DirectSound before WASAPI and requests roughly 20 ms x 4 periods. It is not a
  proven realtime/low-latency profile.
- Do not copy the ESP32-P4 48 kHz/64-sample/2x32-DMA baseline blindly to
  Windows. Establish a measured native WASAPI profile.
- Raspberry Pi and macOS release packages also still need their first physical
  device/audio validation. The Linux x64 package has prior physical UI/audio
  validation.

## Android/fork audit context

The local AMY fork convention is `/home/jeroen/omnichord/amyfork/amy`.
`origin/upstream/android-oboe` contains the separate Android `:amy` process,
private `amy.sock`, service-only JNI and transport-only Java client used as the
process-separation reference. That branch was not an ancestor of the active
`feature/bus-mixer` line during the audit, so Android service work and the
desktop bus-mixer fork are not assumed to be unified. Preserve the proven
service/wire boundary when those lines are eventually reconciled.

## Verification already completed

- The complete local regression matrix reached 127 passing tests after the
  MIDI, rhythm and Windows-related fixes.
- `3345502` made the preset integration test wait deterministically for live
  preset continuation instead of racing the frontend.
- GitHub Actions run `33021825480` independently passed each of the six suites
  and all release jobs as described above.
- `git diff --check` and Python compilation were run during the implementation
  work before its commits.

The standard complete local command, from
`amysynth_version/qt_frontend`, is:

```bash
ALSA_CONFIG_PATH="$PWD/tests/alsa-null.conf" \
  /home/jeroen/omnichord/omnichord-env/bin/python \
  tests/run_tests.py --suite all
```

Use `testing/windows_smoke` only for isolated Windows package iteration. Merge
or apply the final Windows changes to `main` to exercise the full gated
four-platform release.

## Remaining work / safe next steps

1. Physically test the released Windows zip on a recent Windows 10/11 x64 host:
   UI, native audio, shutdown and representative heavy patches/rhythms.
2. Implement a native Windows MIDI input adapter behind the existing MIDI
   callback boundary, without changing CC-learning/application semantics.
3. Measure and tune a WASAPI-first realtime audio profile on physical hardware.
4. Add an explicit Windows tiny-bank identity regression if AMY build inputs or
   the pinned revision change; the current smoke checks non-silence only.
5. Reconcile relevant Android service work with the active AMY bus-mixer line
   only when that fork task is explicitly in scope.

WSL2/WSLg documentation remains an optional way to experiment with the Linux
artifact. It is not the Windows implementation, release gate or realtime-audio
baseline.
