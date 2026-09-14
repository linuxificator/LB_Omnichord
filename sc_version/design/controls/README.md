# External controls

Status: authoritative category contract
Owner: MIDI/OSC control integration
Applies to: `sc_version`
Last verified: 2026-09-15

MIDI and OSC normalize into one external-control state machine and QML
presentation while retaining separate protocol adapters. Learning, binding,
takeover and unlink behavior call the same semantic setters as direct UI
interaction. Note messages are never mistaken for controller buttons.

Integration stimulus comes from a separate process. Native platform discovery
is adapter-owned; unavailable CoreMIDI/WinMM capability is reported explicitly.
Optional hardware profiles live under
[`../../controller_profiles/`](../../controller_profiles/README.md).
