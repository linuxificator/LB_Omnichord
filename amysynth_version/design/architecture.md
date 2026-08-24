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
messages cross an `AF_UNIX` `SOCK_SEQPACKET` socket; on Android the same packet
contract crosses the app-private `amy.sock`; on ESP32-P4 they cross serial.

The Linux convenience launcher owns both child processes only as a development
shell wrapper. The Qt process itself neither starts nor stops AMY. Each socket
packet contains one complete logical AMY wire request, matching the
`upstream/android-oboe` service and decoupled hello-world reference.

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
