# T25 result: release provenance, SBOM, retention and signing decision

Status: complete
Recorded: 2026-09-01
Branch: `rework/code_quality`
Owner: release evidence and distribution trust boundary

## Outcome

- Publication generates signed GitHub/Sigstore build provenance for exactly
  the five package digests in `release-manifest.json`.
- A deterministic SPDX 2.3 document describes all five hashed release
  packages and relates each to its applicable PySide6 components, portable
  Python dependencies, immutable AMY commit and desktop build dependency.
  GitHub signs that SBOM predicate for the same five subjects.
- The workflow verifies normal provenance and the SPDX predicate for every
  package before creating the release. It attaches the human-inspectable SBOM
  and both exact Sigstore bundles, then checks the complete final asset set.
- `packaging/RELEASE_VERIFICATION.md` gives independent checksum, provenance,
  SBOM and predicate-inspection commands and states precisely what they do not
  prove.
- Screenshot retention is now executable policy: keep the newest three
  release-tagged OMNI/MIDI pairs, preserve the untagged capture baselines and
  README target, and remove only older exact-name matches after a new pair has
  passed the existing decode/dimension/visual-density sanity checks.
- `packaging/SIGNING_DECISION.md` explicitly defers Windows Authenticode,
  macOS Developer ID/notarization and Android production signing until the
  distribution channel, key owner and physical acceptance are decided. No
  signing keys, secrets or broader PR permissions were introduced.

## Compatibility and proof

- The SBOM tests generate an exact five-platform manifest, prove five hashed
  described artifacts, dependency/build relationships, deterministic output
  and rejection of an incomplete platform set.
- Screenshot tests prove exact retention of three releases per screen while
  preserving capture baselines and unrelated files. Existing semantic image
  checks still exercise the current README screenshots and reject a blank,
  error-like capture.
- Workflow guards require the attestation action's reviewed full SHA and the
  publish job alone receives the minimal `id-token: write` and
  `attestations: write` permissions.
- Product behavior and package construction are unchanged; the new work runs
  only after all five existing build/smoke gates and before publication.

## Security interpretation

An attestation binds a digest to repository/workflow identity and an asserted
predicate. The SBOM improves dependency visibility. Neither is vulnerability
scanning, proof of absence of malicious dependencies, byte reproducibility or
an operating-system publisher signature. Release documentation now keeps
those trust claims separate.

## Progressive insight and future work

- One release-level SBOM is preferable to five nearly duplicated documents
  while the product has one coordinated release and one exact subject set. If
  platform packaging diverges materially, split it into per-package SBOMs
  rather than adding conditional ambiguity to this graph.
- The current SBOM records reviewed application/native component evidence;
  OS runner packages and complete SDK file inventories remain build
  environment provenance. Expand that boundary only with an automated,
  verifiable source rather than hand-maintained pseudo-precision.
- Production signing is a future project, not T26 by default. Its first task
  is an explicit distribution/threat/key-ownership decision with user
  authorization.
