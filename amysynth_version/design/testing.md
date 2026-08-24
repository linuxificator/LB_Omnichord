# Testing Design

Tests are based on use cases.

Each test should verify:

- initial state
- user action
- visible UI result
- AMY wire commands
- persistence behavior

Important regression tests:

- OMNI/MIDI switching does not affect sound
- tuning coupling works from both screens
- coupled tuning updates both views
- decoupled tuning stays independent
- local and serial AMY transports generate identical commands
- raw-MIDI running status, Note On/Off and velocity-zero Note Off parsing
- incoming EQ/HARM/JV MIDI conversion to exact/fractional AMY notes
- MIDI preview stays within its live voice allocation and emits no stale offs
- OMNI and MIDI reverb controls generate commands for only their owned buses
- live preset/rhythm changes preserve tempo without transport/timebase reset
