# Runtime behavior

Status: authoritative runtime behavior contract
Owner: shared application behavior
Applies to: `sc_version`
Last verified: 2026-09-15

Screen changes are visual only: sounding notes, rhythms and executions continue.
OMNI and MIDI presets remain independent; tuning coupling is runtime state.

The MIDI strum preview uses the selected MIDI row program and routing. An
external control bound to OMNI strum drives the same OMNI semantic action as
mouse/touch and does not disable direct strumming. Preview voices use bounded
oldest-first ownership and engine-timed releases.

All musical actions cross the typed SC protocol. Python may animate UI and
classify gestures but never schedules a note, gate or beat. Failed engine
validation and unavailable capabilities are explicit; they do not silently
select a different backend.
