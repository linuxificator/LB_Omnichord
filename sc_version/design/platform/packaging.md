# Cross-platform packaging

Status: authoritative packaging summary
Owner: release architecture
Applies to: `sc_version`
Last verified: 2026-09-15

The four packages bundle Qt/Python and SuperCollider 3.14.1 but not VSCO audio
recordings. Runtime/config/source archives are checksum-verified, package
contents are audited and third-party licences are included. Linux uses the
host JACK/PipeWire session and does not install machine scheduling policy.

Ordinary pushes run tests only. A manual workflow dispatch with `release=true`
builds all targets and publishes them together under an `R<UTC timestamp>-SC`
tag. Partial platform success never publishes a release.
