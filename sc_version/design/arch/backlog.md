# Current backlog

Status: active backlog; not implementation authorization
Owner: application architecture
Applies to: `sc_version`
Last verified: 2026-09-15

## Technical

1. Add maintained native CoreMIDI and WinMM input adapters; packages currently
   expose those capabilities as unavailable rather than pretending support.
2. Continue cohesive extraction from `InstrumentBackend` only where ownership
   and regression tests justify it.
3. Separate MIDI performance ownership from its Qt view model.
4. Replace remaining implementation-location assertions with semantic tests.
5. Decide and test live-parameter behavior for already sounding sample voices.

## Product/evidence

- Continue subjective playback review across physical platform audio stacks.
- Decide voice priority when preview and external input fill one MIDI row.
- Complete distribution signing/trust decisions before claiming signed builds.
- Audit new catalogue assets and licences before adding them.
