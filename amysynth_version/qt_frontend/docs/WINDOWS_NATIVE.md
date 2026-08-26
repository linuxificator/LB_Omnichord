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
private AF_UNIX / SOCK_STREAM socket
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

## Windows socket contract

Windows pathname `AF_UNIX` supports `SOCK_STREAM`, but not the Linux
`SOCK_SEQPACKET` mode used by the Linux service. Windows therefore uses the
same framing as macOS:

- one complete AMY wire request per record;
- every wire request ends in `Z`;
- one LF byte terminates each stream record;
- partial or multiple `recv()` results are buffered and split on LF;
- no AMY-specific Python or C API crosses the process boundary.

The native service passes the complete `sockaddr_un` size to Winsock `bind`,
matching the address representation used by Python's Windows `AF_UNIX`
client. A shortened POSIX-style address length is not used on Windows.

The socket belongs below a per-user private application directory. The service
publishes it only after native audio is ready; the client retries the
connection instead of relying on a fixed startup delay.

References: [Microsoft AF_UNIX](https://devblogs.microsoft.com/commandline/af_unix-comes-to-windows/)
and [Qt for Python deployment](https://doc.qt.io/qtforpython-6/deployment/index.html).

## Verified repository state (2026-08-26)

| Area | Current state |
| --- | --- |
| Qt/application logic | Wire-only; production frontend modules do not import `amy` or `c_amy`. |
| Linux desktop | Separate Python AMY service and Qt process over `AF_UNIX/SOCK_SEQPACKET`. |
| macOS desktop | Separate Python AMY service and Qt process over LF-framed `AF_UNIX/SOCK_STREAM`. |
| Raspberry Pi + ESP32-P4 | Qt sends LF-delimited wire requests over UART to an independent AMY target. |
| Android | `origin/upstream/android-oboe` contains the separate `:amy` service, private socket and transport-only Java client, but it is not merged with active `feature/bus-mixer`. |
| Native AMY on Windows | The fork builds the AMY C/miniaudio core; this repository now builds a separate `amy_service.exe` wrapper against that fork. |
| Native Windows frontend transport | The client now selects LF-framed `AF_UNIX/SOCK_STREAM` on `win32`. |
| Windows package/release | CI builds an experimental self-contained zip with separate service/frontend executables. It performs an offline native AMY render test and starts the unpacked launcher, offscreen Qt/QML frontend and socket service end to end; no physical validation yet for audio/MIDI. |
| Windows MIDI input | Not implemented; the current reader is Linux ALSA raw MIDI only. |

The current Windows AMY example is not yet a low-latency baseline: the fork's
host defaults are 44.1 kHz and 256 samples, its Windows backend tries
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
2. `run_windows.ps1 -SmokeTest` starts the separate service with offline
   rendering and one-client lifetime, then starts the frozen Qt executable with
   its offscreen/software renderer.
3. The frontend must load the packaged QML/assets, connect through Windows
   `AF_UNIX/SOCK_STREAM`, publish initial state, play/release a test chord and
   exit successfully.
4. The service must report both received wire commands and nonzero rendered PCM,
   exit after disconnect, and leave no process or socket behind.

Frozen frontend assets are resolved from PyInstaller's bundle root
(`sys._MEIPASS`). Deriving their location from the source-tree parent of
`app_core.py` is incorrect for the Windows `--onedir` layout, where that would
skip the packaged `config`, `gui`, `instruments` and `music` directories.

This smoke path deliberately does not substitute a mock transport or import AMY
into the frontend. It verifies the packaged two-process boundary while avoiding
an unreliable dependency on audio hardware in a hosted CI runner.

`WSL_APPIMAGE_TESTING.md` remains only an optional experiment for the Linux
artifact, not the Windows implementation plan or release gate.
