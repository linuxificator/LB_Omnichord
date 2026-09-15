# Cross-platform packaging

Status: authoritative packaging summary
Owner: release architecture
Applies to: `sc_version`
Last verified: 2026-09-16

The four packages bundle Qt/Python and a purpose-built headless SuperCollider
3.14.1 runtime, but not VSCO audio recordings. All targets build that runtime
from the same commit- and checksum-pinned source archive with the IDE, SC Qt
bindings, help and unused integrations disabled. macOS and Windows do not copy
the much larger official IDE distributions: doing so duplicated Qt and pulled
QtWebEngine into a product which already owns its Qt frontend. Windows keeps
the ASIO backend through a separately checksum-pinned, GPL-compatible SDK
input. No private SuperCollider source fork is needed while the build remains
an unmodified configuration of the pinned upstream source.

Runtime/config/source archives are checksum-verified, package contents are
audited and third-party licences are included. The audit applies the platform
size budget and forbidden-runtime rules to the complete package; an embedded
engine cannot be exempted from either check. Linux uses the host JACK/PipeWire
session and does not install machine scheduling policy.

Ordinary pushes run tests only. A manual workflow dispatch with `release=true`
builds all targets and publishes them together under an `R<UTC timestamp>-SC`
tag. Partial platform success never publishes a release.

For diagnostic packaging, dispatch with `build_packages=true` and
`release=false`. It follows the same four-platform test, package self-check,
content-audit and size-gate path, retains the artifacts for inspection and
cannot publish a release.

## Headless desktop runtime evidence

Diagnostic run `35035347234` built and tested all four targets from commit
`230bf5a`. Its complete-package audits reported no forbidden runtime content:

| Package | Full IDE runtime release | Headless runtime candidate | Reduction |
| --- | ---: | ---: | ---: |
| macOS arm64 DMG | 296,968,460 bytes | 51,786,964 bytes | 82.6% |
| Windows x86_64 ZIP | 203,302,533 bytes | 61,772,572 bytes | 69.6% |

The comparison baseline is published release `R20260915T180639-SC`. The
candidate figures are the package files themselves, not GitHub's outer
artifact archives. Both are well below the enforced 145,000,000-byte budgets.
