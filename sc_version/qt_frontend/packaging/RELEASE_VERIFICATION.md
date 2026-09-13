# Verifying an LB Omnichord release

Status: authoritative consumer verification procedure
Owner: five-platform release publication
Applies to: packages published from `main`
Last verified: 2026-09-01

Each release contains five platform packages, five matching `.sha256` files,
`release-manifest.json`, one release-level SPDX 2.3 SBOM and the retained
Sigstore bundles for the build-provenance and SBOM attestations. The signed
attestations are also stored by GitHub against the repository.

## Verify a downloaded package

Download one package and its adjacent checksum file from the same release,
then run the platform's SHA-256 verifier. On Linux, macOS with GNU coreutils,
or WSL:

```bash
sha256sum --check LB_Omnichord.R<timestamp>.<platform>.<extension>.sha256
```

The output must name the package and end in `OK`. The checksum only detects
byte changes relative to the downloaded checksum; use the signed attestation
to establish repository/workflow provenance:

On stock macOS, use `shasum -a 256 PACKAGE` and compare its digest with the
first field in `PACKAGE.sha256`. In Windows PowerShell, use
`(Get-FileHash PACKAGE -Algorithm SHA256).Hash.ToLower()` and compare it with
that same field.

```bash
gh attestation verify LB_Omnichord.R<timestamp>.<platform>.<extension> \
  --repo linuxificator/LB_Omnichord
```

Verify the signed SPDX predicate separately:

```bash
gh attestation verify LB_Omnichord.R<timestamp>.<platform>.<extension> \
  --repo linuxificator/LB_Omnichord \
  --predicate-type https://spdx.dev/Document/v2.3
```

To inspect the verified SBOM rather than only its signature and subject:

```bash
gh attestation verify LB_Omnichord.R<timestamp>.<platform>.<extension> \
  --repo linuxificator/LB_Omnichord \
  --predicate-type https://spdx.dev/Document/v2.3 \
  --format json \
  --jq '.[].verificationResult.statement.predicate'
```

The `documentDescribes` set must contain all five release platforms, and the
selected package's SHA-256 must equal its entry in both the SBOM and
`release-manifest.json`. The manifest also records the LB source commit, AMY
commit/branch/PCM bank and reviewed Python input evidence.

The attached `*.sigstore.json` files preserve the exact signed bundles for
archival or GitHub's documented offline-verification procedure. Online
verification is the normal project procedure because it obtains GitHub's
current trusted root and repository identity directly.

## What this proves—and what it does not

A passing attestation establishes that GitHub Actions in this repository
asserted the package digest, source/workflow context and SBOM predicate. It
does not prove that the package is vulnerability-free, that every native SDK
or runner byte is reproducible, or that the application carries a platform
publisher signature. Those are separate security properties.
