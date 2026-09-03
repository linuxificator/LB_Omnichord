# Codex handover: portability, release integrity and security

Status: analysis; no workflow, package or security behavior changed
Audit base: `c46b93b607722dd429ac54cab163deb61801632a`

## Current release strengths

- One workflow gates publication on six regression groups and five platform
  builds.
- Every platform consumes the declared AMY fork branch and exact commit.
- Android pins Python, PySide wheels with hashes, Cython, NDK, SDK, Gradle and a
  python-for-android commit more tightly than the desktop builds.
- Native/package smokes verify entry points and actual AMY behavior.
- Android emulator checks guest AMY/Oboe audio rather than treating host
  PulseAudio output as proof.
- Windows uses a private named pipe and native AMY/miniaudio service.
- Release assets have SHA-256 companions.
- Release concurrency is serialized and the screenshot-only follow-up uses the
  explicit `skip-rebuild`/`skip-checks:true` contract.
- The successful audited release published five packages and five hashes from
  exact commit `50118fb18c952a27c64a77a6486527a64559ebb5`.

These are significant supply-chain and portability controls to preserve.

## Finding P1 — desktop dependencies are ranges, not reproducible inputs

Desktop requirements specify minimum ranges such as `PySide6>=6.6` and
`pyserial>=3.5`. PyInstaller may be pinned in workflow steps, but transitive
Python dependencies and apt/Homebrew packages can move between builds. A green
build proves the environment that day, not which dependency graph must be
recreated later.

Recommendation:

- maintain platform-specific constraints/lock inputs with hashes where tooling
  supports them;
- separate direct intent (`requirements.in`) from resolved release constraints;
- update dependencies deliberately through reviewed automation;
- record the resolved dependency manifest with every release;
- keep Android's existing explicit pins and verify them from one manifest;
- test oldest supported/runtime policy separately if minimum-version support is
  intentional.

Do not claim reproducible builds until the same declared source, environment
and instructions produce bit-identical artifacts. The Reproducible Builds
project defines that term precisely.

Primary reference: [Reproducible Builds definition](https://reproducible-builds.org/docs/definition/).

## Finding P2 — GitHub Actions use mutable major tags

The workflow uses actions such as `actions/checkout@v4`. GitHub states that a
full-length commit SHA is the only immutable way to reference an action.

Recommendation:

- pin every third-party action to a verified full commit SHA;
- retain the release/tag name in a comment for readability;
- use Dependabot or another reviewed mechanism to propose updates;
- keep workflow permissions minimal per job;
- add a static gate that rejects unpinned `uses:` entries except explicitly
  documented local/reusable workflows.

Primary reference: [GitHub Actions secure-use reference](https://docs.github.com/en/actions/reference/security/secure-use).

## Finding P3 — no build provenance or SBOM attestation

Hashes detect changed downloads only if the expected hash is obtained through a
trusted channel; they do not prove which workflow/source produced the file.
GitHub artifact attestations can bind artifact digest to repository, workflow,
commit and event, and can also carry an SBOM.

Recommendation:

- generate build provenance for the five release packages after validation;
- generate SPDX or CycloneDX SBOMs for packaged dependencies;
- document `gh attestation verify` alongside SHA verification;
- verify the attestation in a post-publication or independent smoke job;
- treat an attestation as provenance, not evidence that the artifact is
  vulnerability-free.

Primary reference: [GitHub artifact attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations).

NIST SP 800-218 provides the broader secure-development framework: prepare the
organization, protect software, produce well-secured software and respond to
vulnerabilities. Apply it proportionally; this project does not need compliance
ceremony, but it benefits from documented dependencies, protected build inputs
and a vulnerability response path.

Primary reference: [NIST SP 800-218 SSDF](https://csrc.nist.gov/pubs/sp/800/218/final).

## Finding P4 — publication uses a broad asset glob

Publication takes `dist/*`. The current release happened to contain exactly the
desired ten assets. A stale or unexpected file in `dist` could be published.

Recommendation:

- construct a release manifest with exactly five expected packages, canonical
  names, platform, size, SHA-256, AMY SHA and source commit;
- fail on missing, duplicate or extra files before release creation;
- publish only manifest entries;
- attach the manifest and verify GitHub's final asset list against it;
- make screenshot artifacts explicitly non-release-package outputs.

## Finding P5 — workflow repetition can drift

At roughly 659 lines, the workflow repeats AMY checkout/identity verification
and some package preparation across jobs. Platform-specific acceptance is
necessarily different; shared dependency identity is not.

Extract a small versioned script or local composite action for:

- checking out the declared AMY branch/SHA;
- verifying remote/commit identity;
- emitting build metadata;
- validating the common release manifest fragment.

Keep platform build/smoke steps readable and separate. A dense matrix should
not conceal Windows/macOS/Android-specific correctness.

## Finding P6 — signing and distribution trust are explicit limitations

Current Windows artifacts are unsigned, macOS uses ad-hoc signing and Android
is a test/debug-style package path. This is documented experimental release
behavior, not an accidental regression.

If distribution expands beyond controlled testing:

- use Windows Authenticode;
- Developer ID signing and notarization on macOS;
- a protected release keystore and release signing for Android;
- documented key rotation/revocation;
- protected environments/manual approval for signing secrets;
- never expose signing credentials to pull-request code.

Signing should follow a threat/distribution decision, not be bolted on as a
cosmetic green check.

## Finding P7 — platform selection must be capability-safe

The shipped MIDI `tech_profile: linux` defect demonstrates that a single
cross-platform config can override actual platform capabilities. Platform
package tests should always load the real shipped config and assert:

- correct MIDI technology names/availability;
- correct AMY transport type and private endpoint;
- correct audio owner/backend;
- no accidental Linux device probes on Windows/macOS/Android;
- graceful absence of optional hardware;
- package-smoke/test endpoints disabled during normal launch.

Prefer capability detection over operating-system string branches when APIs
permit it, while keeping explicit platform profiles for deterministic tests.

## Finding P8 — local input and config trust should be bounded

Security positives include Unix socket mode 0600, app-private Android sockets,
Windows named pipes and no remote TCP control. Remaining defensive needs:

- bounded local wire frame and queue sizes;
- strict ASCII/protocol validation before AMY ingestion;
- full config/preset schema validation;
- atomic user data writes;
- no production packaging of the localhost test-control server;
- log rotation and clear retention;
- surfacing background I/O failure;
- dependency vulnerability/update policy.

The test-control HTTP server binds localhost and is used by integration
headless mode. Keep it test-only and cap body size. Localhost is a narrower
trust boundary, not input validation.

## Release quality scenarios

- Given a release tag, a user can identify source SHA, workflow, AMY SHA,
  dependency manifest, asset hash and provenance.
- An unexpected file in `dist` stops publication.
- A mutable action tag is rejected by CI.
- The unmodified package chooses the correct transport/MIDI profile on each
  platform.
- A dependency update is a visible review with full regression results.
- Compromising one test job cannot publish/sign a release through excess token
  permissions.
- A rebuilt artifact is not called reproducible unless bit-identical evidence
  exists.

## Recommended order

1. Exact asset manifest and real shipped-config package tests.
2. Pin action SHAs and add dependency-update automation.
3. Resolve/record desktop dependencies with hashes.
4. Add provenance and SBOM attestations plus verification docs.
5. Add signing only when the intended distribution model and protected secret
   process are approved.
