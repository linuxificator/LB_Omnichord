# Codex handover: reusable-sequence final quality audit

Status: implementation changes required before merging into `rework/sequencer`
Audit date: 2026-09-04
AMY feature branch: `rework/sequencer_simplification`
Audited AMY head: `596047be3d5a9013822660f996279356e2492abe`
Comparison base: Shorepine `main` at
`0fb0a00b5a9f9443d7e1f85261cc7e70a0adb76b`

This audit is differential: findings apply to code added or behavior changed by
the reusable-sequence work. It does not treat unrelated existing AMY defects as
part of this task. No Codex-only material may be copied into an AMY branch.

## Merge decision

Do not fast-forward this head into `rework/sequencer` yet. The public model,
immutable snapshots and copy-on-write publication are sound, but two functional
defects and one realtime-boundary defect must be repaired first.

## Blocking findings

### Execution origin is inferred from racy process-global flags

`wire_firing` and `stored_sequence_wire_firing` are `volatile bool` globals.
New control-side code reads them to choose the activation tick, permit reset and
decide whether reclamation is safe while the render thread writes them.
`volatile` is not synchronization. ThreadSanitizer confirmed races involving
`stored_sequence_reclaim_retired()`, `sequencer_sequence_reset()` and
`sequence_control_tick()`. An external start can consequently be mistaken for
an internally fired command, and an external reset can be rejected
spuriously. The current tick is also read without synchronization.

Required direction: pass an explicit internal-versus-external execution origin
through the sequence-control boundary and take the tick snapshot under the
same synchronization contract as its writer. Do not infer caller identity from
render-thread globals.

### Same-tick controls depend on execution-slot order

The control pass scans execution slots once in ascending order. If a parent
starts a child into a lower slot freed earlier in that pass, the child's local
tick-zero control is never visited. A deterministic audit test constructed
that slot arrangement and reported `leaf_hits=0`.

Required direction: use bounded same-tick control work processing (or an
equivalent generation scheme) so every newly started execution receives its
tick-zero control pass independently of its slot number. Preserve controls
before ordinary events and retain a fixed bound for cycles.

### Deferred reclamation is reachable from the render path

`amy_add_message_with_sysex_flag()` unconditionally reclaims retired sequence
definitions on the assumption that every public wire call is control-side.
CV trigger processing calls `amy_add_message()` from `amy_execute_deltas()`, so
that assumption is false. Variable-time destruction of arrays and strings can
therefore occur on the audio/render thread.

Required direction: distinguish render-safe internal dispatch from external
wire ingress explicitly. Render-originated dispatch may retire definitions but
must not destroy them; a known non-rendering boundary performs destruction.

## Important validation and contract findings

- Allocation arithmetic checks `SIZE_MAX`, but `malloc_caps()` takes a
  `uint32_t`. Products above `UINT32_MAX` can truncate before an untruncated
  `memset`. Reject unrepresentable configurations before allocating, and make
  the `max_sequencer_tags` type consistent with its public `uint32_t` field.
- Python sequence helpers silently truncate fractional tags, ticks, durations
  and alignments and accept booleans as integers. Use one strict uint32 helper.
- The new `HR` reset parser uses the legacy `atoi` list parser and has no
  overflow detection. Parse it with the strict unsigned parser used by `HC`.
- A templated low-level gate control with duration and alignment is rejected by
  the Python shape check. Validate all supported action shapes consistently.
- `AMY_TIME_GEQ` is only unambiguous within half the uint32 clock range. Gate
  duration/alignment and finite completion need explicit supported bounds or a
  completion rule that does not rely on an impossible `elapsed > UINT32_MAX`.
- Gate suppresses every ordinary event, including note-offs and parameter
  restoration. This can intentionally preserve phase, but it can also leave
  state active indefinitely. Choose and document the generic contract and add
  a note-on/note-off regression test; do not assume percussion-only use.
- Remove retired implementation vocabulary (`HA`, sequence payloads described
  as "nested") while retaining uses of “nested call” that accurately describe
  parser re-entry.
- `check-c-api` now runs Node unconditionally while `js-api-test` duplicates
  that command. Keep the generated-file check and runtime test responsibilities
  explicit and avoid an accidental toolchain dependency if practical.

## Evidence

- Existing C, Python and JavaScript sequence/API tests passed.
- ASan found no sequence-specific memory errors in the exercised paths.
- UBSan stopped on pre-existing unrelated undefined behavior in
  `src/log2_exp2.c`; this is not attributed to this feature.
- GCC `-fanalyzer` found no ownership defect, but strict conversions identified
  the `size_t` to `uint32_t` allocation boundary.
- Main sequence-suite coverage of `src/sequencer.c`: 81.75% of 526 lines;
  88.46% of branches executed and 73.72% taken at least once.
- ThreadSanitizer reproduced the cross-thread race.
- A deterministic temporary test reproduced the missed lower-slot tick-zero
  control without concurrency.

## Positive conclusions to preserve

- definitions and executions have separate internal lifetimes without exposing
  execution identity to callers;
- active executions retain immutable definition snapshots;
- losing concurrent editors retry against the newly published cumulative
  definition;
- release on the render path uses an allocation-free intrusive retired list;
- capacity and execution pools are configured and bounded;
- composition and musical policy remain generic rather than Omnichord-specific;
- public compatibility changes and migration are documented.

## Recommended implementation order

1. Replace execution-origin inference and close the render reclamation path;
   add a permanent render/control TSan stress test where supported.
2. Make same-tick control processing slot-order-independent and add the exact
   deterministic regression.
3. Fix allocation-size/type boundaries and add non-allocating oversize tests.
4. Centralize strict Python and wire integer parsing and extend malformed-input
   tests.
5. Resolve and document gate and uint32 rollover contracts with boundary tests.
6. Remove stale vocabulary and small build/test duplication.
7. Rerun normal tests, generated API checks, static analysis, ASan, TSan and
   coverage, then record a new differential audit before merging.
