# Dependency assessment: fastjsonschema

Date: 2026-09-01
Decision: adopt
Owner: portable runtime requirements
Requirement and code replaced/prevented: standards-based structural validation
of versioned AMY configuration without implementing JSON Schema locally
Owning dependency group: `requirements.txt`

## Functional fit and public API

LB needs Draft 7 structural validation before creating Qt, serial, MIDI, socket
or AMY resources. `fastjsonschema.compile` turns a checked-in schema into a
normal callable and its exception exposes an exact data path. Domain invariants
that JSON Schema cannot express clearly remain small typed Python checks. This
avoids writing a partial schema language or mixing all structural rules into
the configuration converter.

The alternative `jsonschema` project is broader and organization-maintained,
but its current runtime dependencies include `rpds-py`. That Rust/native
dependency has no proven path through this project's Python-for-Android build.
Adding a native target dependency solely for startup validation violates the
five-platform and smallest-dependency rules.

## Maintenance health and release activity

The project has existed since 2016, is marked Production/Stable, keeps the
official JSON-Schema-Test-Suite as a conformance input and had 402 commits when
checked. Version 2.22.2 was published on 2026-08-15 after 2.22.0 was promptly
yanked and corrected. The latest repository push was 2026-08-24 and only two
issues were open when checked. The project has a public security policy.

## Adoption and ecosystem standing

The package is a long-standing JSON Schema implementation used in the Python
notebook/Jupyter ecosystem (including nbformat), with a 2016-present release
history. GitHub reported 496 stars and 79 forks on the review date. Its use here
is limited to a stable standards boundary rather than project-specific helper
APIs.

## Five-platform and packaging evidence

PyPI publishes `fastjsonschema-2.22.2-py3-none-any.whl`; the package is
OS-independent, pure Python and declares no runtime native library. It supports
CPython 3.10-3.14, covering the Android Python 3.11 target, CI/desktop Python
3.12 and the current development Python 3.14. The same exact pin is included in
desktop requirements and the generated Android Buildozer target requirements.

The full Android build/emulator gate is still required before this branch is a
release input; a universal wheel is packaging evidence, not a substitute for
that product gate.

## License and redistribution obligations

BSD-3-Clause. T24 must include its license and resolved wheel/hash in release
metadata and the later SBOM.

## Security and supply-chain evidence

The accepted wheel is published on PyPI and the repository documents security
reporting. Version 2.22.0 is not accepted because PyPI yanked it for missing
minimum-Python metadata. T24 must hash/lock 2.22.2 and must not silently float
to a later release.

Schemas are application-controlled static files. No untrusted remote schema is
compiled. User configuration is data only and receives domain validation after
structural validation.

## Runtime/thread/real-time impact

Compilation and validation occur once during startup before I/O construction.
The validator is not imported by QML, audio callbacks, MIDI reader threads or
AMY command scheduling. The compiled callable is cached by schema path.

## Test boundary, migration and exit cost

Adversarial config fixtures cover structure, paths and domain invariants. The
schema is Draft 7 JSON and is not generated from Python, so another conforming
validator can replace this dependency. Typed config and compatibility-view APIs
do not expose `fastjsonschema` types.

## Exact accepted version/range and sources

Accepted: exactly `fastjsonschema==2.22.2`.

- [official PyPI project and universal wheel](https://pypi.org/project/fastjsonschema/)
- [official source repository](https://github.com/horejsek/python-fastjsonschema)
- [python-jsonschema dependency declaration used in the alternative assessment](https://github.com/python-jsonschema/jsonschema/blob/main/pyproject.toml)

## Required follow-up and review date

Run the five-platform release, including Android packaging/emulator validation,
before merge to `main`. Review the pin with T24 or by 2027-03-01, whichever
comes first.
