# SCLOrk non-realtime audio audit handoff

Status: completed and superseded on 2026-09-14

The original single-pitch smoke audit was completed. Its current contract,
three-register calibration method, catalogue-admission result, runtime fixes
and remaining limits are consolidated in
[`PLAYBACK_QUALIFICATION.md`](PLAYBACK_QUALIFICATION.md). Use that document and
the executable `sc-audio` suite; do not resume from the older assumptions that
every compilable definition belongs in the pitched browser or that integer WAV
output is sufficient to detect unstable graphs.

The workstation still needs the distribution `pipewire-jack` package for an
ordinary source launch. During verification, an uninstalled package extraction
under `/tmp` provided the standard `pw-jack` shim without changing the host.
The launcher correctly refuses raw JACK while PipeWire owns the desktop audio
session.
