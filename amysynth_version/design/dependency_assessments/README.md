# Dependency assessment records

Status: active decision-record template
Owner: LB Omnichord maintainers
Applies to: every proposed new or replacement external package
Last verified: 2026-09-01

Create one Markdown file per proposed package before adding its import or
requirement. Use `YYYY-MM-DD_<normalized-package-name>.md`. A package is not
approved merely because a record exists.

## Required record

```text
# Dependency assessment: <package>

Date:
Decision: adopt | use existing/standard capability | implement locally | defer
Owner:
Requirement and code replaced/prevented:
Owning dependency group:

## Functional fit and public API
## Maintenance health and release activity
## Adoption and ecosystem standing
## Five-platform and packaging evidence
## License and redistribution obligations
## Security and supply-chain evidence
## Runtime/thread/real-time impact
## Test boundary, migration and exit cost
## Exact accepted version/range and sources
## Required follow-up and review date
```

Link primary evidence and record the date it was checked. If portable code
imports the package, evidence must cover Linux x86_64, Raspberry Pi aarch64,
macOS arm64, Windows x86_64 and this project's Android arm64 path. See
`../CODEX_HANDOVER_DEPENDENCY_SELECTION_AND_REUSE.md` for rejection and stop
conditions.
