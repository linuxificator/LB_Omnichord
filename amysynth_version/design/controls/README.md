# External controls

Status: authoritative category index
Owner: MIDI/OSC control integration
Last verified: 2026-09-08

- `midi.md`: MIDI input technologies, channel and note behavior.
- `midi_control.md`: CC/button learn, binding, takeover and persistence.
- `osc.md`: OSC UDP input, discovery and shared binding semantics.

MIDI and OSC share one external-control state machine and QML presentation but
retain independent protocol adapters. Integration senders run outside the
production application process.

Optional device-side profiles that make third-party hardware emit these
standard protocol messages live under [`../../controller_profiles/`](../../controller_profiles/README.md).
