# Codex handover: dependency selection and reuse policy

Status: clarified engineering guideline; no dependency or code changed
Recorded: 2026-09-01
Branch: `rework/code_quality`
Builds on: `CODEX_HANDOVER_PORTABILITY_RELEASE_AND_SECURITY.md`

## Guideline

Do not reimplement mature general-purpose Python functionality merely to avoid
an external dependency. Use the Python standard library, the already selected
Qt/PySide6 stack or a suitable external Python package when one already solves
the requirement well.

An external package is suitable only when it is demonstrably well maintained,
widely used, appropriately licensed, secure enough for the role, compatible
with the project's supported Python versions and supported on every release
platform where the importing code runs.

The normal rule for portable application code is strict: do not add an obscure,
single-purpose or effectively abandoned package to save a small amount of
local code. A dependency transfers implementation work to another project; it
does not transfer responsibility for correctness, availability, packaging,
updates or security.

This handover defines what a future dependency change must do. It does not
approve a new package and makes no change to `requirements.txt` now.

## Source-of-truth rule

Every directly imported third-party runtime dependency of the portable Python
frontend must be declared in
`amysynth_version/qt_frontend/requirements.txt`.

Do not:

- rely on a transitive dependency without declaring it when project code
  imports it directly;
- hide a runtime dependency in a launcher, workflow-only `pip install`, local
  developer instructions or an already-populated virtual environment;
- import a package opportunistically and silently change behavior depending on
  whether it happens to be installed;
- vendor copied package source into the repository to avoid declaring the
  dependency;
- install Python packages at application startup.

Specialized dependency groups may be separate when their lifecycle is truly
different:

- runtime dependencies: `requirements.txt`;
- build/packaging tools: a reviewed build requirements or constraints file;
- test/quality tools: a reviewed development/test requirements file;
- platform build toolchains: the platform packaging manifest/workflow plus
  resolved version evidence;
- the custom AMY fork: the existing exact branch and SHA build input, because
  PCM bank/build options make it more than an ordinary unqualified PyPI
  dependency.

Those files must be explicit, version controlled and installed by named build
steps. Separate files are not permission to duplicate or contradict versions.
One generated/resolved constraints or release manifest should make the complete
environment inspectable.

## Current baseline

At the time of this handover, frontend `requirements.txt` declares:

- `PySide6>=6.6`;
- `pyserial>=3.5`.

Release workflows also install tools such as a pinned PyInstaller directly,
and install the exact LB AMY fork separately. Android overrides/resolves parts
of the PySide6 build stack and has additional native toolchain pins.

This is not an instruction to move every tool into the runtime requirements.
It is a finding that dependency intent and fully resolved build inputs are
currently spread across requirements and workflow code. Future dependency
quality work should make each group explicit and eliminate hidden installation
knowledge while preserving the custom AMY build contract.

Do not assume the two currently declared libraries automatically satisfy every
future version/platform criterion. Audit them through the same process when
changing their range or release pin.

## Selection order

For every proposed implementation, evaluate options in this order:

1. **Existing project capability.** Reuse an already adopted and appropriate
   PySide6/Qt or project abstraction if it meets the requirement without
   violating boundaries.
2. **Python standard library.** Use it when it provides the complete behavior
   clearly and portably.
3. **Established external package.** Prefer a mature package when the local
   alternative would recreate substantial parsing, protocol, validation,
   compatibility, security or algorithmic work.
4. **Small local implementation.** Use only when the requirement is genuinely
   small/project-specific or no qualifying portable package exists.

“Use a library” and “keep architecture simple” are not contradictory. A
well-chosen library may remove complexity. A library plus several wrappers,
workarounds and platform exceptions may add more complexity than a small local
function.

Do not add a generic abstraction in anticipation of several libraries. Select
the concrete requirement first and keep the integration boundary narrow.

## Required package assessment

Before adding an external package, create a short dependency decision record
in the relevant branch/PR documentation. Record evidence and the date of the
assessment for every item below.

### 1. Functional fit

- Which exact requirement does it satisfy?
- Which local code and tests will it replace or prevent?
- Does its public API express the required behavior without relying on private
  internals?
- Does it handle the error, validation and edge cases that justify reuse?
- Is a smaller already-installed capability sufficient?

Reject a package if only a small fraction is used while it brings a large
runtime or transitive surface.

### 2. Maintenance health

Review the actual upstream project, not only its PyPI description:

- recent releases or meaningful maintenance activity;
- response to important bugs and security reports;
- support for current Python and dependency versions;
- a documented release/deprecation policy where appropriate;
- more than one person or a credible organization able to maintain releases;
- healthy issue/PR handling proportional to the project's size;
- no unresolved signs that the project is archived or seeking an unresponsive
  new maintainer.

Do not use a rigid “released within N months” rule by itself. A small stable
library may correctly need few releases. There must nevertheless be evidence
that supported platforms/Python versions still work and that security or
compatibility fixes can be published.

### 3. Adoption and ecosystem standing

Use several signals rather than one popularity number:

- broad, sustained use or recognized ecosystem role;
- downstream projects/distributions relying on it;
- useful documentation and examples;
- independent users reporting/testing multiple platforms;
- package identity, maintainers and release history consistent across the
  source repository and package index.

Download counts and stars can be manipulated or reflect transient CI traffic.
They support a decision but do not prove quality.

The default is to reject code maintained by only a few individuals with little
adoption, stale releases and no recent compatibility evidence. An exception
requires explicit user approval and a documented ownership/exit plan.

### 4. Platform and packaging support

A dependency imported by the portable core must be supported and tested on all
five frontend release targets:

- Linux x86_64;
- Raspberry Pi/Linux aarch64;
- macOS arm64;
- Windows x86_64;
- Android arm64 in the project's PySide6/python-for-Android packaging path.

“Pure Python” helps but is not sufficient: filesystem, process, event-loop and
network assumptions may still be platform-specific. Native-extension packages
must supply compatible wheels/build recipes or be proven buildable in every
release job.

A platform-specific adapter may sometimes require a native package that cannot
run elsewhere. That is an exception to the portable-core rule, not a way to
introduce a platform dependency into shared code. It requires explicit user
approval, stays inside that adapter's dependency group and must have an
equivalent common port/capability behavior on other platforms.

If Android support is absent, the package is not suitable for portable core
code even when desktop support is excellent.

### 5. License and redistribution

- Confirm the declared license from the source distribution/repository.
- Verify compatibility with LB Omnichord and binary redistribution.
- Include required notices/source offers in every relevant package.
- Check licenses of material transitive/native dependencies, not only the top
  package.
- Reject unclear, custom or conflicting licensing.

### 6. Security and supply-chain risk

- Review known vulnerabilities and the project's response history.
- Prefer releases with hashes/signatures/provenance where available.
- Check package ownership history for suspicious transfer or name confusion.
- Minimize install-time execution, native code and large transitive trees.
- Pin/resolution-lock release inputs and verify hashes where supported.
- Ensure the package does not download or execute additional code/data at
  application startup.
- Define how security updates will be detected and released.

No popularity threshold makes a package safe. Broad use can improve review but
also increases attacker interest.

### 7. Runtime and real-time suitability

For code on MIDI, UI or AMY command paths, measure rather than assume:

- startup cost;
- steady-state latency and allocation behavior;
- thread/event-loop model;
- blocking I/O;
- memory use;
- shutdown/resource ownership;
- error reporting.

Never put an unmeasured convenience package in an audio callback or other hard
real-time path. The existing AMY native service remains the audio owner.

### 8. Testability and exit cost

- Can project code depend on a small stable public interface?
- Can tests use a fake at the project boundary without mocking the library's
  internals?
- Is data stored in a standard/documented format?
- What code/config migration is needed if upstream becomes unavailable?
- Can the package be upgraded independently from musical behavior?

Avoid letting external object types leak throughout application/domain state.
A narrow adapter is appropriate to isolate a library API; a wrapper that merely
renames every method without reducing coupling is not.

## Decision outcomes

Every assessment ends in one of four explicit outcomes:

1. **Adopt.** The package qualifies; add it to the correct requirements group,
   integrate narrowly and delete the superseded local implementation.
2. **Use existing/standard capability.** No new dependency is justified.
3. **Implement locally.** No qualifying package exists or the requirement is
   small/project-specific; document scope and tests.
4. **Defer.** A package would help but does not meet maintenance/platform/
   licensing/security requirements, and a safe local implementation is not
   justified yet.

Do not choose a package first and write the assessment to justify it afterward.

## Rules when adopting a package

- Add the dependency and code use in the same reviewable branch.
- Declare it in the correct requirements/constraints source before importing
  it.
- Pin or constrain it according to the release reproducibility policy; do not
  leave an unconstrained install hidden in CI.
- Record why the selected range is compatible with all supported Python/Qt
  versions.
- Remove local code that the library actually replaces; do not maintain two
  implementations indefinitely “just in case”.
- Preserve a thin boundary where it protects domain/platform separation.
- Add behavior, failure and platform packaging tests.
- Update dependency/license notices and release manifests/SBOM.
- Run the full five-platform release gate before merging to `main`.
- Document upgrade and vulnerability-monitoring ownership.

Optional imports are allowed only for genuinely optional adapter/capability
modules. Core behavior must not silently degrade because a declared runtime
dependency is missing; startup must report a clear packaging/configuration
error.

## Rules when implementing locally

Local code is acceptable when it is the lower-risk choice, but the decision
must be intentional:

- state why no qualifying library was selected;
- keep the implementation limited to the project's actual requirement;
- do not copy unlicensed snippets or partially vendor another package;
- test error and edge cases, not only the happy path;
- use standard formats/protocols where possible;
- add a comment/design reference if the code could otherwise look like an
  accidental reinvention;
- reconsider the decision when requirements grow materially.

A 30-line project-specific transform is not automatically “reinventing the
wheel”. Reimplementing a robust schema validator, MIDI backend, cryptography,
archive parser or cross-platform process supervisor likely is.

Never implement security-sensitive primitives such as cryptography or signature
verification locally when a maintained, established platform/library solution
exists.

## Dependency-file design

Future dependency-quality work should establish an explicit structure such as:

```text
requirements.txt                 direct portable runtime dependencies
requirements-build.txt           package construction tools
requirements-test.txt            test/quality-only tools
constraints/<release>.txt        fully resolved versions and hashes
platform/<name>/...              approved native adapter/toolchain inputs
release dependency manifest      actual resolved inputs per built artifact
```

The exact filenames may differ. Preserve these semantics:

- direct intent is human reviewed;
- resolution is reproducible/inspectable;
- runtime, test and build environments are not accidentally conflated;
- platform exceptions do not leak into portable requirements;
- all jobs consume the same declared source rather than repeating versions in
  workflow YAML;
- update automation proposes changes, but review and the full matrix decide.

Avoid five independent complete requirements files. Common dependencies should
have one authority, with platform/build groups extending that authority.

## Testing and enforcement

### Dependency declaration test

Use Python AST/import metadata plus a small standard-library/first-party map to
verify every direct third-party import is declared in the appropriate
requirements group. Avoid literal source-string assertions.

Account explicitly for:

- PySide6 submodules belonging to one distribution;
- the separately pinned AMY service dependency;
- imports used only inside platform adapters;
- imports used only by tests, diagnostics or build scripts;
- lazy imports that are still required for an enabled runtime feature.

### Platform matrix

Every adopted portable runtime dependency must install, import and exercise its
used API in all five release jobs. An import-only smoke is insufficient for
native/event-loop/I/O libraries.

### Lock and drift checks

- fail when workflow YAML installs an undeclared Python package/version;
- fail when the same direct package has conflicting pins;
- record resolved package name/version/hash/license per artifact;
- update caches from the complete dependency-source hash;
- scan known vulnerabilities and preserve results as release evidence;
- verify dependency/license/SBOM generation before publication.

### Behavioral proof

When replacing local code with a package, run the old characterization fixtures
against the new boundary. Preserve public QML, preset, MIDI and AMY wire
behavior unless a separate approved requirement changes it.

## Concrete future work for this repository

1. Inventory every third-party import in production, tests, tools and packaging
   and map it to its distribution and owning dependency group.
2. Move directly installed build/test tools out of workflow literals into
   explicit reviewed dependency sources without adding them to runtime.
3. Add resolved cross-platform constraints/hashes consistent with the release
   provenance roadmap.
4. Document the exact AMY fork branch/SHA/build options as the intentional
   first-party external component exception.
5. Add AST-based declared-import and workflow-install drift tests.
6. Add license/dependency manifest and later SBOM/provenance to each release.
7. Apply the assessment template to every future proposed external package;
   do not retrospectively add a new library merely because this handover prefers
   reuse.

## Acceptance scenarios

- A developer imports a new portable package: CI fails until it is declared,
  assessed and install-tested on all five platforms.
- A workflow adds `pip install some-tool`: CI fails unless that tool comes from
  the declared build/test dependency source.
- A useful package lacks Android support: it is rejected for portable core code
  or, with explicit approval, isolated to a native adapter with common
  capability behavior elsewhere.
- A mature package replaces substantial local parsing/validation code: existing
  characterization tests pass and the superseded code is removed.
- An obscure inactive package would save little code: the decision records
  reject it and retain a small tested local implementation.
- A dependency publishes a security fix: update automation/review can identify
  every affected artifact and rebuild the full five-platform release.

## Stop conditions

Pause and request direction if a proposed dependency:

- lacks verified support for any platform used by the importing portable code;
- has unclear maintenance ownership, license or package provenance;
- is maintained by very few people, lightly used and not recently verified;
- requires disabling security/verification or downloading runtime code;
- introduces a large transitive/native surface for a small convenience;
- leaks platform/library types through musical or UI domain state;
- conflicts with the Qt event loop, worker ownership or real-time constraints;
- cannot be built into the Android or frozen desktop package paths;
- would make AMY fork/build identity implicit;
- duplicates rather than replaces the existing implementation.

## Definition of done

- every direct third-party runtime import is represented in
  `requirements.txt` or an explicitly documented component exception;
- build/test/platform dependency groups are explicit and contain no hidden
  workflow-only versions;
- every new package has a dated fit/maintenance/adoption/platform/license/
  security decision record;
- portable dependencies are exercised on all five release platforms;
- adopted libraries replace real local complexity instead of adding a second
  path;
- local implementations state why a qualifying external solution was not used;
- release artifacts record resolved dependencies, hashes and licenses;
- full behavior and package gates remain green.
