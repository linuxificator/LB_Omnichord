# Application signing decision

Status: authoritative deferred decision
Owner: release/distribution security
Applies to: Windows, macOS and Android packages
Decision date: 2026-09-01

## Current decision

Do not add production application signing yet. Current releases are
experimental/test distributions from a public GitHub repository: Windows is
unsigned, macOS is ad-hoc signed but not Developer-ID-signed or notarized, and
Android uses CI debug signing. Release notes must continue to state those
limitations plainly.

SHA-256 files and GitHub/Sigstore provenance protect integrity and establish
which repository workflow produced a package. They do not give Windows,
macOS or Android a stable publisher identity and must never be presented as a
substitute for platform signing.

## Decision required before signing

Production signing becomes appropriate only after the intended distribution
and update channel are selected, a human owner accepts the key-management
responsibility, and physical platform acceptance is complete. The decision
must separately cover:

- Windows Authenticode certificate ownership, timestamping, renewal and
  revocation;
- Apple Developer ID ownership, hardened-runtime/notarization policy and
  entitlement review;
- Android package identity, protected release keystore, key rotation/recovery
  and whether the product is distributed as an APK, AAB or store build.

Signing credentials must live in protected environments or platform key
services, never in repository files, build artifacts, pull-request workflows
or general-purpose logs. Untrusted pull-request code must have no path to a
signing identity. Adding secrets or enabling signing requires explicit user
approval and a dedicated threat/distribution review; it is not an automatic
follow-up to provenance.
