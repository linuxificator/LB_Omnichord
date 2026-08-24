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
