# Codex Session Handoff

Updated 2026-08-26 on branch `feature/midi_control`.

This file records the completed work and exact repository state from the
current AMY/Qt session. It supplements, but does not override, `AGENTS.md` or
the authoritative documents under `amysynth_version/design/`.

## Completed and pushed earlier in this session

- `e52dbb2 Preserve live chords across preset changes`
  - OMNI preset selection no longer silences an active chord.
  - The active row/root, chord gate and physical button ownership survive.
  - The sounding notes converge to the destination preset's chord type,
    inversion, octave, tuning and instrument.
- `f0ed4fd Fix MIDI control feedback and document WSL testing`
  - Real CC movement clears the temporary blue/unbound state immediately and
    notifies both MIDI and OMNI indicators.
  - Raw MIDI, backend reverb mapping and QML slider synchronization gained
    permanent regressions.
  - The WSL2/WSLg AppImage testing guide and release links were completed.

Both commits were pushed to `origin/feature/midi_control`. The last fetched
`origin/main` during this session was `24488cd`, the merge of the original MIDI
control feature.

## Completed implementation in this handoff

Points 2, 3 and 9 from
`amysynth_version/qt_frontend/docs/regressions.txt` are implemented:

1. APG/LDR is backend-owned OMNI preset state.
   - Presets store `strum_mode` as `APG` or `LDR`.
   - Older/factory presets without the field load as APG.
   - `Main.qml` observes `backend.strumLadderMode`; the button calls the
     backend toggle instead of owning an independent QML boolean.
2. MIDI-bound numeric values are live controller state.
   - Section RST restores selection and all unbound values, but preserves
     bound parameters and section volume.
   - Hidden instrument target values are restored directly in `SynthState`
     without briefly selecting or sending that hidden patch.
   - Runtime preset selection preserves the union of source bindings and
     bindings declared by the destination preset. Startup loading remains a
     normal full initialization.
   - The rule is implemented for both OMNI and MIDI presets/RST paths.
3. Reverb level spans 0.00 through 3.00 consistently.
   - QML, OMNI and MIDI backend clamps, CC mapping and the program-aware AMY
     receiver all accept 3.0.
   - OMNI buses 1-3 and MIDI melodic buses 4-9 are covered by exact wire tests.

Authoritative contracts were updated in `amysynth_version/design/presets.md`,
`amysynth_version/design/midi_control.md`,
`amysynth_version/design/sound_balance.md`, `amysynth_version/design/gui.md`,
`amysynth_version/design/testing.md`,
`amysynth_version/qt_frontend/docs/CONTROL_SAFETY.md` and
`amysynth_version/qt_frontend/tests/USE_CASES.md`.

## Verification

The complete regression matrix passed after these changes: 119 tests across
unit, frontend, serial, presets, native-controls and native-rhythm suites.

Command used from `amysynth_version/qt_frontend`:

```bash
ALSA_CONFIG_PATH="$PWD/tests/alsa-null.conf" \
  /home/jeroen/omnichord/omnichord-env/bin/python \
  tests/run_tests.py --suite all
```

`git diff --check` and Python compilation of the changed backend modules also
passed. No physical MIDI controller, Raspberry Pi, ESP32-P4 or packaged release
was exercised for these changes.

## Deliberately untouched local notes

`amysynth_version/qt_frontend/docs/regressions.txt` is a user-owned task list
and `.regressions.txt.swp` is an active Vim swap file. Do not delete, rewrite
or commit either file without explicit user direction. Points 4, 5, 6, 7, 8
and 10 in that list remain outside the work completed here.

## Native Windows audit (2026-08-26)

The user requested point 4 to be reassessed against the Android service
architecture. The audit found:

- The Qt production code is wire-only. Only `local_amy_service.py` and the
  packaging/service entry path import AMY; the frontend does not load `amy`,
  `c_amy`, AMY headers or AMY APIs.
- Linux and macOS already run AMY separately from Qt. Linux uses
  `AF_UNIX/SOCK_SEQPACKET`; macOS uses LF-framed `AF_UNIX/SOCK_STREAM`.
- The AMY fork's `origin/upstream/android-oboe` branch contains the intended
  separate Android `:amy` process, private `amy.sock`, service-only JNI and
  transport-only Java client. That branch is not an ancestor of the active
  `feature/bus-mixer` branch, so the Android service work is not yet unified
  with the desktop fork used by LB Omnichord.
- The active AMY fork's Windows tree contains only the native C/miniaudio
  `amy_sine.exe` example. It has no AMY wire-socket service or Windows package.
- Native Windows AF_UNIX is stream-only, so the Qt writer now selects LF-framed
  stream mode on `win32`, matching macOS. The transport regression covers both
  platforms through a patched platform test.
- The existing Windows AMY audio settings are not yet a realtime release
  profile: host AMY defaults are 44.1 kHz/256 samples, DirectSound is tried
  before WASAPI, and the current request is 20 ms × 4 periods. This needs
  measured native tuning; the ESP32 48 kHz/64-sample baseline must not be
  copied blindly.
- The current MIDI reader is ALSA raw-MIDI only, so native Windows MIDI remains
  an explicit future adapter task.

New/updated documentation and contracts:

- `amysynth_version/qt_frontend/docs/WINDOWS_NATIVE.md` is the native-Windows
  architecture, status and acceptance handout.
- `design/architecture.md`, `design/principles.md` and `design/README.md` now
  state the Windows stream contract and route the native-Windows document.
- `INSTALL.md`, frontend README, root README, release notes and testing docs no
  longer present WSL as the Windows route. The WSL guide remains an optional
  Linux-artifact experiment.
- A static contract test rejects direct `amy`/`c_amy` imports in frontend code
  (apart from the separate local service) and packaging tests require the
  native-Windows contract to remain explicitly not-ready until implemented.

No native Windows service, package or physical Windows audio/MIDI test was
claimed or performed. Before claiming Windows support, implement the service
in the AMY fork, merge the needed Android queue principles with the active
bus-mixer branch, establish a measured WASAPI profile, add a separate package
launcher and Windows MIDI adapter, then add native CI and hardware validation.

## Windows package continuation (2026-08-26)

The requested build work has since added an experimental native Windows
package path in this repository:

- `packaging/windows/amy_service.c` is a separate native C wire service using
  Windows `AF_UNIX/SOCK_STREAM`, AMY's C API and miniaudio; it configures 11
  buses, 336 oscillators and no default synths.
- `packaging/windows/CMakeLists.txt` builds that service against the pinned AMY
  fork. `packaging/build_windows.ps1` builds the service, freezes the Qt
  frontend independently with PyInstaller and emits a self-contained zip.
- `packaging/windows/run_windows.ps1` starts the service, waits for its socket,
  starts the frontend with `--amy-socket`, and cleans up the service.
- `.github/workflows/desktop-release.yml` now has a Windows 2022 job that
  builds/self-tests the zip and publishes it as an experimental release asset.

This is a buildable design on the native Windows runner, but it has not been
executed in this Linux session. The Windows job must be the source of truth for
first compile validation. Physical Windows audio/MIDI validation is still
required; the current AMY Windows audio profile is not yet a low-latency
release baseline, and Windows MIDI input still needs a native adapter.
