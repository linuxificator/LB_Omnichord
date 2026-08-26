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
| Windows package/release | CI now builds an experimental self-contained zip with separate service/frontend executables; no physical validation yet. |
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
3. Validate the Windows package launcher supervising the native service and frozen
   PySide6 frontend as separate processes.
4. Add a native Windows MIDI adapter behind the existing MIDI callbacks.
5. Extend native Windows CI beyond file/self-tests to audio startup and package
   smoke tests, followed by physical audio/MIDI validation.

`WSL_APPIMAGE_TESTING.md` remains only an optional experiment for the Linux
artifact, not the Windows implementation plan or release gate.
