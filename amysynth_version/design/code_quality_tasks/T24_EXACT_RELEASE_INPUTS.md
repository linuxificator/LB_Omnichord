# T24 result: exact release inputs and output set

Status: complete
Recorded: 2026-09-01
Branch: `rework/code_quality`
Owner: five-platform build and release supply-chain boundary

## Outcome

- `qt_frontend/packaging/release_inputs.json` is the machine authority for the
  AMY repository/branch/full commit/PCM bank, exact desktop constraint inputs,
  reviewed component license/source evidence and the five release package
  shapes. Its loader rejects malformed values and content-hash drift in every
  declared requirements/constraints file.
- Desktop release resolution is constrained to exact versions. Linux x86_64,
  macOS arm64 and Windows x86_64 use PySide6 6.10.3. Raspberry Pi aarch64 uses
  6.7.3 because later aarch64 wheels require a newer glibc than the Ubuntu
  22.04 Pi release runner supplies. Android retains its separate exact 6.11.2
  host deployer while sharing only portable target requirements.
- One cross-platform checkout helper fetches the requested AMY full SHA and
  declared release branch, proves ancestry, checks out detached and verifies
  exact `HEAD`. Native tests, desktop packages, Android AAR/analyzer and local
  release preparation now consume the central values; platform-specific AMY
  acceptance remains in each owning build.
- Every external GitHub Action is pinned to a reviewed full commit SHA. A
  repository guard rejects moving tags, while weekly Dependabot pull requests
  make updates explicit and reviewable.
- Publication first rejects any package directory other than the exact five
  packages and five canonical checksum files. It writes
  `release-manifest.json` with package sizes/hashes, source SHA, AMY identity,
  declared-input hashes and component evidence. Only manifest-listed files
  are uploaded, and the final GitHub asset-name set is compared exactly.

## Compatibility and proof

- The release-input tests cover a valid five-platform manifest, missing and
  extra files, invalid checksums, GitHub environment export, branch ancestry,
  detached checkout and exact-HEAD verification.
- Packaging, dependency-declaration, Android-packaging, static-contract and
  quality-guardrail tests cover all consumers and reject duplicated active
  workflow pins or mutable action references.
- All workflow and Dependabot YAML parses successfully. Both new packaging
  tools pass strict mypy; the complete quality gate remains green at 37/42
  ratcheted legacy diagnostics and 24 strict new modules.
- Existing product/runtime behavior is unchanged. These changes constrain and
  describe build inputs and publication outputs; all native and packaged
  acceptance gates remain in place.

## Limits and honest reproducibility statement

The hashes in the input authority cover the reviewed requirements and
constraint declarations. They are not hashes of every downloaded wheel, SDK,
runner image or operating-system package. Component versions, licenses and
source locations are recorded, but byte-identical builds are not claimed.
T25 adds signed GitHub provenance and an SBOM so an independent consumer can
verify the relationship between a published artifact and this workflow; that
still must not be described as proof that the artifact has no vulnerabilities.

## Findings and progressive insight

- One PySide6 version cannot be forced on all desktop runners: the current
  aarch64 wheels moved beyond the Pi runner's glibc baseline. Separate exact
  constraints preserve a shared application dependency contract without
  pretending native binary compatibility is platform-independent.
- Repeating the AMY SHA in workflow environment blocks made drift easy. The
  common helper is safe because it centralizes identity verification only;
  it does not centralize Windows, Android, ESP32 or PCM-bank acceptance.
- A wildcard upload can publish stale files even if each build job succeeded.
  Exact pre-publication enumeration and post-publication comparison are both
  needed because they protect different boundaries.

## Follow-up task effects

T25 should use `release-manifest.json` as the subject inventory for provenance
and SBOM generation, add independently documented verification commands and
define deliberate screenshot retention. Signing desktop/mobile applications
remains a separate threat/distribution decision requiring protected keys and
explicit authorization.
