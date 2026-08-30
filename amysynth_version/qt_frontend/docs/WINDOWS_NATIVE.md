# Native Windows architecture and status

## Decision

Windows is a native target. Running the Linux AppImage through WSL2/WSLg is
not the intended Windows architecture: it adds Linux display/audio forwarding
and complicates low-latency audio and physical MIDI access.

The intended runtime is:

```text
native Python/PySide6 frontend
        |
        | ordinary AMY wire requests
        v
private Windows named pipe (`QLocalSocket`)
        |
        v
native amy_service.exe -> AMY C engine -> native Windows audio
```

The frontend must not import `amy`, load `c_amy`, link AMY, call AMY C APIs or
own the synth service lifecycle. A package launcher may start and supervise the
two executables. AMY remains independently replaceable as long as its service
implements the same wire and transport contract.

Qt for Python supports native Windows deployment. The inability of AMY's
Python `setup.py` to build on Windows is a service limitation, not a frontend
limitation and not a reason to run the frontend under WSL.

## Windows local IPC contract

Windows itself supports native Winsock `AF_UNIX/SOCK_STREAM` on sufficiently
recent releases (initially build 17063). The GitHub package job runs on Windows
Server 2025 build 26100, so the OS is not the limitation. The official CPython
Windows build still does not expose `socket.AF_UNIX`; its upstream enablement
issue remains open. Reimplementing Winsock through `ctypes` or adding a custom
Python extension would add an unnecessary second socket layer.

The packaged frontend therefore uses Qt's supported local IPC API:
`QLocalSocket` maps a server name to a Windows named pipe. The native C service
owns the other end with `CreateNamedPipeA` and explicitly sets
`PIPE_REJECT_REMOTE_CLIENTS`. This is local IPC, not a network listener. It
uses the same stream framing as macOS:

- one complete AMY wire request per record;
- every wire request ends in `Z`;
- one LF byte terminates each stream record;
- partial or multiple `ReadFile()` results are buffered and split on LF;
- no AMY-specific Python or C API crosses the process boundary.

The launcher creates a unique pipe name for each run. The service creates the
pipe and publishes that name through a short-lived ready file below the
per-user application directory only after AMY is ready. The launcher verifies
and removes the file, then passes the name to the frontend. The `QLocalSocket`
object lives entirely on the existing dedicated command-writer thread, keeping
blocking pipe writes away from the Qt UI thread.

The implementation is intentionally small and direct:

- `code/amy_transport.py` contains the `QLocalSocket` writer selected by
  `--amy-local-name`;
- `packaging/windows/amy_service.c` owns AMY, miniaudio, the named-pipe server
  and LF record assembly;
- `packaging/windows/run_windows.ps1` creates a unique name, starts the service,
  validates its ready file, launches Qt and cleans up both processes;
- `packaging/windows/LB_Omnichord.cmd` is the user-facing double-click entry
  point. It applies `-ExecutionPolicy Bypass` only to the bundled launcher
  process and leaves an interactive error visible;
- `packaging/build_windows.ps1` independently builds `amy_service.exe`, freezes
  `LB_Omnichord.exe`, and places both beside the launcher in the final zip.

The resulting zip is a portable, dependency-complete directory after
extraction, not a single-file executable. That layout is intentional: the Qt
frontend and AMY service remain separately replaceable processes. Users should
extract the complete zip and double-click `LB_Omnichord.cmd`; invoking an
unsigned `.ps1` through Explorer's **Run with PowerShell** can be rejected by
the machine execution policy before the script can report its own error.

The ready file contains only the generated pipe name. It is written below the
per-user application directory after both AMY and the pipe exist, consumed and
deleted by the launcher, and is not the command transport.

References: [Microsoft's Windows AF_UNIX announcement](https://devblogs.microsoft.com/commandline/af_unix-comes-to-windows/),
[CPython Windows AF_UNIX issue](https://github.com/python/cpython/issues/77589),
[Qt for Python QLocalSocket](https://doc.qt.io/qtforpython-6/PySide6/QtNetwork/QLocalSocket.html)
and [Qt for Python deployment](https://doc.qt.io/qtforpython-6/deployment/index.html).

## Verified repository state (2026-08-30)

| Area | Current state |
| --- | --- |
| Qt/application logic | Wire-only; production frontend modules do not import `amy` or `c_amy`. |
| Linux desktop | Separate Python AMY service and Qt process over `AF_UNIX/SOCK_SEQPACKET`. |
| macOS desktop | Separate Python AMY service and Qt process over LF-framed `AF_UNIX/SOCK_STREAM`. |
| Raspberry Pi + ESP32-P4 | Qt sends LF-delimited wire requests over UART to an independent AMY target. |
| Android | `integration/android_build` packages PySide6 with the AAR from the pinned `releases/amy_omnichord_R20260830T220021` AMY fork commit. The frontend uses the private socket only; the AAR owns the separate `:amy`/Oboe process. Emulator package/QML/audio validation is a release gate, while physical validation remains outstanding. |
| Native AMY on Windows | The fork builds the AMY C/miniaudio core; this repository now builds a separate `amy_service.exe` wrapper against that fork. |
| Native Windows frontend transport | The launcher supplies a unique Windows named-pipe name; `QLocalSocket` sends LF-framed requests without opening a network port. |
| Windows package/release | CI builds an experimental portable zip with separate service/frontend executables and bundled dependencies. It performs an offline native AMY render test and starts the unpacked double-click launcher, offscreen Qt/QML frontend and named-pipe service end to end; no physical validation yet for pointer hardware, audio or MIDI. |
| Windows MIDI input | Not implemented; the current reader is Linux ALSA raw MIDI only. |

The Windows build script selects the newest supported Visual Studio CMake
generator installed on the host (currently Visual Studio 2026 in the Windows
Server 2025 CI image, with Visual Studio 2022 retained for local builds). It
does not pin the current runner to an absent older toolchain.

The first complete four-platform release containing this implementation is
`R20260826T230234`, built from main commit `3345502`. GitHub Actions run
`33021825480` passed all frontend suites and the Linux x64, Raspberry Pi
aarch64, macOS arm64 and Windows x64 package jobs before publishing. That is
native-runner package validation, not a physical Windows audio/MIDI test.

## PCM/drum compatibility

All supported targets must give PCM preset numbers 0–18 the same meaning. The
Windows service is built from pinned AMY release branch
`releases/amy_omnichord_R20260830T220021` at commit
`32f3a68861a68979ceb715cf32e0322e8614365b`. Its CMake target compiles `amy.c`
and `pcm.c` without defining `GAMMA9001` and without linking the optional
Gamma9001 `drums_bin.c`. The pinned source consequently includes `pcm_tiny.h`,
including the tiny-bank mapping for MIDI drum patch 258.

This is equivalent to the explicit `AMY_PCM_BANK=tiny` used by the Linux and
macOS Python-extension builds. That environment variable belongs to AMY's
`setup.py` path and is not required by the native Windows CMake path. Defining
`GAMMA9001` or adding `drums_bin.c` on Windows would change the meaning of the
direct rhythm presets in `config/amy_config.json` and produce different drum
sounds for the same wire commands.

The current Windows AMY service profile is not yet a low-latency baseline: the
fork's host defaults are 44.1 kHz and 256 samples, its Windows backend tries
DirectSound before WASAPI, and requests 20 ms periods with four periods.
Native Windows removes WSL's forwarding layer, but this audio profile still
needs measurement and tuning before release. The ESP32-P4 48 kHz/64-sample
settings must not be copied without measuring Windows device behavior.

## Remaining implementation work

1. Keep the native service wrapper aligned with the AMY fork's generic
   bus/runtime work and the service/queue principles proven by Android.
2. Measure a native WASAPI low-latency profile, including drop-outs and
   command-to-audio latency under heavy patches and reverb.
3. Add a native Windows MIDI adapter behind the existing MIDI callbacks.
4. Validate physical audio/MIDI and measure latency on real Windows hardware;
   GitHub's hosted runner covers offline PCM rendering and packaged process/
   socket/QML startup, but is not evidence of audible device output.

## Windows package smoke test

The desktop release workflow has a dedicated `testing/windows_smoke` push path.
On that branch it runs the Windows package job independently; the shared Linux
regression matrix, Linux, Raspberry Pi, macOS and release publication remain
disabled. The complete regression suite must still pass locally before pushing
that branch. On `main`, the shared regression matrix is again mandatory and the
exact same Windows validation participates in the complete gated release as
before.

Validation uses only files extracted from the final zip:

1. `amy_service.exe --self-test` initializes native AMY without an audio device,
   sends real wire note-on/off commands, renders PCM blocks and requires
   non-silent output.
2. `LB_Omnichord.cmd -SmokeTest` exercises the same user-facing wrapper that is
   double-clicked after extraction. It starts `run_windows.ps1` with a
   process-only execution-policy bypass; the supervisor starts the separate
   service with offline rendering and one-client lifetime, then the frozen Qt
   executable with its offscreen/software renderer.
3. The frontend must load the packaged QML/assets, connect through the native
   Windows named pipe, publish initial state, send quick-tap and framework-long-
   press pointer events through a real QML chord key, observe its active border
   and release both manual chords successfully.
4. The service must report both received wire commands and nonzero rendered PCM,
   exit after disconnect, and leave no process or ready file behind.

Frozen frontend assets are resolved from PyInstaller's bundle root
(`sys._MEIPASS`). Deriving their location from the source-tree parent of
`app_core.py` is incorrect for the Windows `--onedir` layout, where that would
skip the packaged `config`, `gui`, `instruments` and `music` directories.

This smoke path deliberately does not substitute a mock transport or import AMY
into the frontend. It verifies the packaged two-process boundary and the QML
pointer path while avoiding an unreliable dependency on audio hardware in a
hosted CI runner. Synthesized Qt pointer events still do not prove a physical
mouse, trackpad or touchscreen.

The successful four-platform run above observed 6,140 nonzero samples in the
service's standalone offline self-test. Its packaged end-to-end smoke delivered
209 real wire commands through the named pipe and observed 13,138 nonzero
rendered samples. These counts are evidence for that run, not fixed golden
values. The current smoke proves that PCM rendering is non-silent; it does not
yet identify every tiny-bank drum sample acoustically.

`WSL_APPIMAGE_TESTING.md` remains only an optional experiment for the Linux
artifact, not the Windows implementation plan or release gate.
