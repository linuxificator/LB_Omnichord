# Architecture

## Main flow

GUI controls do not talk directly to AMY.

```
Qt GUI
  |
application state
  |
AMY wire command generator
  |
transport
  |
AMY
```

Transports:
- local development AMY transport
- ESP32 serial transport

Both must receive identical wire commands.

## Audio ownership

OMNI:
- chord
- strum
- bass
- drums

MIDI:
- MIDI melodic instruments
- MIDI drums

MIDI must use separate AMY buses from OMNI.
