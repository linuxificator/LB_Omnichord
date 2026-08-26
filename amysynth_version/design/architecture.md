# Architecture

## Main data flow

The frontend architecture is:

```
Qt GUI
  |
application state and controllers
  |
AMY wire command generation
  |
transport
  |
separate AMY service / ESP32-P4
```

The Qt application must not import AMY, call AMY synthesis APIs, or manage the
AMY service lifetime. It only produces AMY wire messages. On Linux those
messages cross an `AF_UNIX` `SOCK_SEQPACKET` socket; on macOS, which does not
provide Unix-domain `SOCK_SEQPACKET`, they use a Unix `SOCK_STREAM` with one
newline-framed AMY request per record. Native Windows uses the same LF-framed
`AF_UNIX` `SOCK_STREAM` contract with a native C AMY service; Windows does not
support `SOCK_SEQPACKET`. Android uses the app-private `amy.sock`; ESP32-P4
uses serial. Framing is a transport concern and does not expose the AMY Python
or C API to Qt.

The Linux convenience launcher owns both child processes only as a development
shell wrapper. Released Linux and Raspberry Pi AppImages and the macOS app
bundle use an equivalent packaging wrapper: it starts the bundled AMY
executable as a separate child, waits for its private socket and then starts
Qt. The Qt process itself neither imports AMY nor starts or stops its service.
Each socket packet contains one complete logical AMY wire request, matching the
`upstream/android-oboe` service and decoupled hello-world reference.

The native Windows service/package is now built by the Windows packaging
script as an experimental zip: `amy_service.exe` is compiled against the
checked-out AMY fork and the PySide6 frontend is a separate executable. Native
audio/MIDI validation and a final low-latency profile remain outstanding.
WSL2/WSLg is an optional way to experiment with the Linux artifact and is not
the Windows architecture. See `../qt_frontend/docs/WINDOWS_NATIVE.md` for the
verified status and acceptance criteria.

## Transport independence

Supported transports:

- external local AMY service over a Unix-domain socket
- serial transport to ESP32-P4

The same user action must result in the same AMY wire command stream regardless of transport.

That guarantee also requires identical built-in PCM preset numbering. Local
Linux AMY is built with `AMY_PCM_BANK=tiny`, matching ESP32-P4. Gamma9001 uses a
different meaning for PCM presets 0–18 and must not be selected for this
application unless the wire-level sample map changes for every target.

## Audio ownership

OMNI owns:

- chords
- strum
- bass
- rhythm/drums

MIDI owns:

- MIDI instrument rows
- MIDI routing
- MIDI preview
- MIDI drums

The current AMY instrument IDs are 0–4 for OMNI, 5–10 for the six MIDI rows,
and 11 for MIDI drums. A MIDI row showing Drum Kit 0 routes hits through synth
11 and does not allocate its otherwise corresponding pitched synth.

OMNI and MIDI must not accidentally share mutable synth state or AMY buses.

## Bus ownership

There are eleven isolated buses:

- 0: OMNI drums
- 1: OMNI bass
- 2: OMNI strum
- 3: OMNI manual/rhythm chords
- 4–9: MIDI rows 1–6, one bus per synth
- 10: MIDI drums

Patch-local EQ, chorus, echo and reverb state therefore cannot leak from one
MIDI instrument into another. The OMNI header reverb controls buses 0–3. The
independent MIDI header reverb controls buses 4–10; its DRM switch determines
whether bus 10 joins the MIDI room.

## ESP32-P4 direction

ESP32 firmware must provide at least eleven buses before this complete MIDI bus
layout is deployed there. This does not change the wire-protocol boundary.

The older four-bus ESP32-P4 documentation describes the proven OMNI-only audio
baseline, not the resource contract of the complete OMNI+MIDI application. The
complete target also has to preserve independent OMNI and MIDI reverb state;
a build exposing only one shared room's liveness/damping cannot satisfy that
contract without extending the target-side mixer/effect implementation.
