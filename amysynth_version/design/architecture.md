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
AMY engine
```

The Qt application must not call AMY synthesis APIs directly.

## Transport independence

Supported transports:

- local AMY execution for development and testing
- serial transport to ESP32-P4

The same user action must result in the same AMY wire command stream regardless of transport.

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

## ESP32-P4 direction

Future ESP32 firmware work expands AMY bus availability and keeps the wire protocol boundary intact.
