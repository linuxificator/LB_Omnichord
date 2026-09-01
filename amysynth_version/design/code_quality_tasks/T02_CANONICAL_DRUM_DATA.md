# T02 result: canonical drum data

Status: complete
Completed: 2026-09-01
Task source: `../CODEX_HANDOVER_ORDERED_CODE_QUALITY_TASKS.md` T02

## Changes

- Verified that all nine JSON files in the historical design data directory
  were byte-for-byte copies of the runtime `music/drums` files.
- Removed those duplicate JSON files from the design tree.
- Added `canonical_drum_data_manifest.json` with canonical relative paths and
  reviewed SHA-256 values.
- Updated the active rhythm documentation and historical handovers to point to
  the runtime tree as the single authority.
- Added a structured unit test that verifies all manifest hashes/paths and
  rejects a reintroduced duplicate runtime-data file in the design directory.

## Findings and decisions

- The runtime tree was already the only path used by loaders and packagers; no
  executable path depended on the design copies.
- Historical handovers remain useful for rationale. They now explicitly label
  their original information-only state and link to current canonical data.
- Hashes are useful historical review evidence, but T22 may legitimately update
  the manifest when a reviewed schema/data change modifies canonical files.

## New or refined follow-up

- T22 should add schema revision, source/license and generator/manual-process
  provenance without creating another dataset copy.
- T23 should keep the structured manifest test and avoid literal prose tests.

## Verification

- SHA-256 and byte comparison before deletion.
- `test_repository_data_hygiene.py`.
- Drum catalogue and complete unit suites.
- Markdown local-link check and `git diff --check`.
