# Configuration contract

Status: authoritative startup configuration contract
Owner: configuration loading, migration and composition
Applies to: `sc_version/qt_frontend/config`
Last verified: 2026-09-15

`frontend.json` revision 1 owns MIDI/OSC input, default SC program IDs, MIDI
voice count, musical gate constants, strum tail and unique logical role IDs.
`frontend_v1.schema.json` is strict: unknown/missing fields and wrong types are
startup errors. Python adds cross-field checks for numeric IPv4 addresses,
service-name hygiene and unique role ownership. Consumers receive frozen typed
records; they contain no serial endpoint, AMY capacity or firmware setting.
The OSC listen address and port form one optional pair. Omitting both is the
explicit unconfigured state and removes OSC from the technology row; supplying
only one is invalid.

On first SC launch, a user `frontend.json` is seeded atomically. If the prior
edition's user config exists, only engine-neutral MIDI, OSC, voice-count,
rhythm, strum-tail and logical-layout settings are imported. Program IDs and
engine capacity never cross that boundary. Existing frontend config is never
silently replaced.

The immutable frontend schema remains a packaged asset; it is not copied into
the editable user directory. The composition root binds that exact schema to
the config loader, so validation of `~/.omnichord/config/frontend.json` never
depends on the frozen Python module's `__file__` layout. Package acceptance
must exercise this copied-user-config path from an empty directory.

`supercollider.json` revision 7 separately owns OSC protocol endpoints, server
options, buffer limits, the per-owner gesture voice boundary and the sample
repository identity, runtime branch, immutable commit and selected location. Its explicit
migrations are verified from an empty user directory and every supported old
revision inside the frozen package. Validation completes before Qt input or
engine processes are created.

Defaults occur once in checked-in JSON or an explicit migration. Runtime
consumers may not repeat fallback ports, capacities or paths in source code.
