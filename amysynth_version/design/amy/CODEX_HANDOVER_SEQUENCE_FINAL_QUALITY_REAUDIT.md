# Codex handover: reusable-sequence final quality re-audit

Status: source and host validation complete; ready for the requested merge
decision
Re-audit date: 2026-09-04
AMY feature branch: `rework/sequencer_simplification`
Audited AMY head: `ab2a02ec351ca4328069955abf674bc459f7262e`
Comparison base: Shorepine `main` at
`0fb0a00b5a9f9443d7e1f85261cc7e70a0adb76b`
Repair-plan baseline: `596047be3d5a9013822660f996279356e2492abe`

This is a differential audit of the reusable-sequence work. It records Codex
analysis in LB Omnichord only; none of this handover material is present in the
Shorepine-facing AMY branch.

## Conclusion

All blocking and important source findings from
`CODEX_HANDOVER_SEQUENCE_FINAL_QUALITY_AUDIT.md` have been addressed. The
result is ready to merge into the AMY `rework/sequencer` branch when that merge
is explicitly requested. No merge is part of this handover commit.

The implementation remains a deliberately bounded extension of AMY's existing
sequencer: definitions and executions are separate, active executions retain
immutable snapshots, the render path performs neither definition destruction
nor live-edit allocation, and public behavior is expressed through ordinary
AMY event payloads plus explicit start, stop and gate controls. Musical policy
remains outside AMY.

Physical ESP32 timing and memory measurements remain target validation, not a
source blocker and not something desktop tests can prove.

## Resolved original findings

### Explicit dispatch origin and realtime reclamation boundary

The code no longer infers caller context from racy process-global flags.
External, render and stored-event origins are passed explicitly. External
controls take their next-tick snapshot under the queue lock; render-originated
controls receive their actual current tick. CV-triggered render dispatch uses
the render-safe entry point. The render path only links zero-reference
definitions to the intrusive retired list; external command boundaries detach
and destroy that list outside the shared lock.

ThreadSanitizer now passes while render ticks race with gate controls, future
definition reset/rebuild, reclamation and the two-writer publication retry.

### Slot-independent same-tick controls

Same-tick control processing uses bounded repeated passes and a per-execution
tick marker. A child created in a previously visited lower slot receives its
tick-zero controls. The number of successful visits remains bounded by the
configured execution capacity, so cyclic graphs cannot recurse or spin
without bound.

### Capacity and integer safety

All new allocation products are checked against both arithmetic overflow and
the `uint32_t` size accepted by `malloc_caps()`. Invalid zero or unrepresentable
capacities fail closed. Pool-initialization failure, first-definition failure,
every clone allocation stage and recovery are covered by deterministic tests.

Python and wire control/reset fields use strict unsigned parsing. Booleans,
fractions, negatives and uint32 overflow are rejected instead of truncated.
Gate duration and alignment are capped at `INT32_MAX`, matching the safe
half-range of AMY's wrapping time comparison.

### Clock lifetime and rollover

An execution latches once its start boundary is reached, so a long-running
periodic execution is not reclassified as pending after half the uint32 clock.
A finite event at `UINT32_MAX` fires exactly once and releases its execution.
Alignment across rollover treats wrapped tick zero as a boundary for every
period, including non-powers of two such as 48.

### Gate contract

Gate is explicitly event-agnostic. Phase advances while ordinary events in the
interval are dropped and never replayed; sequence-control events remain live.
This includes note-offs and parameter restoration, so complete stateful
gestures must be placed outside the gated interval or in a separately started
finite sequence. The behavior is documented and regression-tested without
assuming percussion or any other application-specific payload.

### Terminology and generated checks

Retired command and nesting terminology was removed from current code and
documentation. Generated-source freshness and executable JavaScript behavior
are separate checks; a C-only generated check no longer acquires an accidental
Node dependency. Current Godot source regenerates without a diff and parses
with `gdparse`.

## Additional findings discovered and fixed during re-audit

- Strict `ticks` parsing initially rejected AMY's established empty-zero list
  spelling, including the documented `ticks=",24,tag"`. Empty fields are again
  accepted and tested without weakening strict parsing of supplied numbers.
- The reusable tagged invariant `tick < period` had accidentally been applied
  to untagged legacy scheduling too. It is now scoped to tagged definitions;
  direct scheduling retains its historical acceptance behavior.
- Alignment near `UINT32_MAX` incorrectly carried a pre-wrap modulo phase into
  the wrapped clock for periods which do not divide `2^32`. Overflow-aware
  alignment now selects tick zero.
- Pool OOM output lacked a newline and ran into the next diagnostic. The
  sequence-specific message is now clear and allocation-failure paths have
  explicit tests.
- Documentation overstated whole-upload atomicity. One candidate publication
  is atomic, but a multi-message wire upload is not a transaction. Python
  validates all events before sending its reset; a target capacity or
  transport failure may still leave the accepted prefix. The status guide now
  states the correct acknowledgement boundary and reset/retry response.
- A remaining `size_t` to `malloc_caps(uint32_t)` conversion in the legacy
  direct-event firing path was made explicit and guarded.
- The compatibility matrix now names C `amy_event.ticks` with `TICKS_TAG` and
  preserved empty-zero fields, not only Python spellings.

## Architecture and maintainability assessment

The repair work added tests and explicit state but reduced hidden coupling:

- execution origin is data passed through the call graph, not global ambient
  state;
- definition ownership has one reference-count and retirement contract;
- control ordering is independent of storage-slot accidents;
- one strict integer parser is shared by new wire operations;
- wrap-safe interval limits are enforced at both Python and C boundaries;
- allocation, publication and reclamation responsibilities are separated;
- ordinary AMY payloads remain opaque to the sequence engine.

The entire feature branch versus Shorepine main contains 3,288 insertions and
190 deletions across code, generated bindings, tests and documentation. The
production C/Python surface accounts for roughly 1,265 insertions and 54
deletions; `src/sequencer.c` accounts for 784 insertions and 34 deletions. Much
of the branch size is contract explanation and regression coverage rather than
additional runtime policy. The final audit-repair series itself changed 19
files with 768 insertions and 211 deletions, including its tests and docs.

Splitting the new sequencer internals into another C module would move lines
but would not reduce the ownership or synchronization model. Keeping the
definition/execution machinery beside the existing tick engine currently gives
the shortest dependency path. No further source reduction was identified that
would preserve the now-tested concurrency, failure and compatibility
contracts.

## Validation evidence

The following completed successfully on the audited head or the immediately
preceding code-identical head (later changes were documentation only):

- complete `make ctest`, including reusable sequence behavior, OOM and
  concurrency binaries;
- `tests/test_sequence_api.py`;
- generated C, Python, JavaScript and Godot freshness checks;
- executable JavaScript serialization tests;
- `gdparse godot/amy.gd`;
- Python bytecode compilation of `amy`, `tests` and `scripts`;
- the full Python audio suite with CI's `AMY_TEST_THRESHOLD_DB=-70.0`: 133
  tests passed;
- AddressSanitizer with leak detection disabled: no sequence memory error;
- ThreadSanitizer without the optional ALSA backend: no race in the exercised
  sequence publication/render/control paths;
- GCC `-fanalyzer` plus strict conversion, sign, shadow and format warnings:
  no warning in the changed sequencer implementation (only pre-existing
  warnings from `amy_fixedpoint.h`);
- main reusable-sequence suite coverage for `src/sequencer.c`: 83.19% of 583
  executable lines, 90.22% of 368 branches executed, 75.82% taken at least
  once, and 77.16% of calls. OOM and concurrency tests use a separate
  test-instrumented sequencer object and add failure/race coverage beyond that
  main-object figure.

LeakSanitizer cannot attach under this sandbox's ptrace restrictions. UBSan
still stops in the pre-existing `src/log2_exp2.c` signed-left-shift path before
the sequence tests begin; neither condition was attributed to this feature.
The optional ALSA implementation also has a previously observed unrelated
shutdown-flag race when included in a TSan binary, so the sequence TSan run
uses AMY's supported no-ALSA host build.

## Compatibility boundary after re-audit

One- and two-field untagged scheduling—including empty-zero list spellings—
retains its existing behavior. The intentional break remains confined to
tagged scheduling: repeated tagged writes accumulate a stopped reusable
definition and require explicit start rather than replacing and immediately
running one event. Empty `H0,0,tagZ`/`H,,tagZ` remains an explicit definition
reset spelling. Existing C callers must rebuild because `amy_config_t` grew;
they should continue to initialize it with `amy_default_config()`.

The AMY public status document contains the complete migration table. No
Omnichord-specific behavior or reference appears in the AMY branch.

## Remaining target-dependent checks

These are validation work, not unfinished host implementation:

- measure worst render time, DMA misses, publication lock duration, heap low
  water, largest free block and retired-list depth on the intended ESP32-P4
  build at 48 kHz/128 samples with realistic effects and authoring load;
- execute the Godot binding in a real Godot runtime in addition to its parser
  and Linux CI build;
- let the normal Shorepine-facing CI run the web and Godot toolchains, which
  were not downloaded locally while unattended.

Do not merge Codex handovers into AMY. When propagation is requested, merge or
cherry-pick only the AMY commits on `rework/sequencer_simplification`.
