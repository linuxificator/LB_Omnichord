# Codex handover: real-time-safe reusable-sequence publication

Status: implemented and host-tested; physical ESP32-P4 timing still required
Date: 2026-09-04
Affected AMY branch: `rework/sequencer_simplification`
Primary target of concern: ESP32-P4 at 48 kHz, 128-sample AMY blocks

Release note: the integration release recorded below is historical. The
current immutable release, built from the final merged PR head, is recorded in
`CODEX_HANDOVER_AMY_RELEASE_20260905.md`.

Implementation commits on the clean AMY branch:

- `2669c3ae` — exercise append-while-active COW and three overlapping
  definition generations;
- `b2a88659` — construct versions outside the render-blocking lock and defer
  zero-reference destruction;
- `7c98ad2b` — make the public control/wire boundary the guaranteed reclaimer
  and structurally bypass it for render-fired wires.
- `b6f559a5` — route a root-scheduled definition reset through the same deferred
  destruction path and cover it explicitly.

LB consumes the same commits through immutable integration branch
`releases/amy_omnichord_R20260904T215233` at
`8a896e9319957ed8eea49f26fe16378fcc2a27c5`.

## Decision summary

Do not solve sequence replacement with exactly two reusable buffers and do not
add a tracing garbage collector. The most practical design for this code is:

1. keep definitions immutable while executions refer to them;
2. build a new definition version outside the AMY/audio queue lock;
3. publish it with one short, synchronized pointer swap;
4. let each execution hold a reference for its complete lifetime;
5. link zero-reference old versions onto an allocation-free intrusive list;
6. reclaim their heap memory only from a non-rendering command/control context.

This is a small read-copy-update-like design with explicit reference counting
and deferred reclamation. It evolves the current ownership model rather than
introducing a general garbage collector. It is now implemented. “Real-time
safe” remains a measured hardware claim, not a conclusion from source review.

## Path from the original COW to the implemented design

The original copy-on-write semantics were worth keeping: an execution retained
the exact definition it started with, and an edit made a new definition for
future starts. The problem was where the work happened, not the snapshot rule.
The implementation was changed incrementally:

1. Add tests which force the old COW branch by appending while an execution is
   active. Add a second test with A, B and C alive together, proving that two
   physical buffers cannot represent the valid state space.
2. Split “drop a reference” from “destroy the object”. Reference changes stay
   inside the existing short AMY queue-lock boundary.
3. Give a writer a temporary reference to the observed source. This makes the
   source immutable and alive after the writer releases the lock.
4. Allocate the candidate definition, its event array and all copied strings
   outside the lock.
5. Re-enter the lock, compare the slot pointer with the captured source and
   publish with a pointer swap only if it still matches. A losing writer drops
   its private candidate and retries against the newer cumulative definition.
6. Preserve the `refs == 1` in-place append fast path. Bulk preload therefore
   stays O(n); it does not clone the growing definition for every event.
7. When render drops the last reference, link the object through a pointer in
   the definition itself. No queue node is allocated and no heap object is
   freed there.
8. Stop routing render-fired wires through public `amy_add_message()`. Internal
   playback dispatches directly, while the public wire boundary drains and
   destroys the detached retire list after parsing. This is a structural
   control/render separation and does not depend on observing a global firing
   flag which another thread could change concurrently.

This route keeps the already-tested COW behavior and changes only publication
and destruction ownership. It does not add a public revision, buffer, garbage
collector or execution-lifetime concept.

## Why the current path is a real-time risk

`sequencer_sequence_add_wire()` currently takes `amy_queue_lock`. If the active
definition has more than one reference, it calls
`stored_sequence_definition_clone()` before releasing that lock. The clone:

- allocates a new definition;
- allocates the full configured event array;
- allocates and copies every existing wire string;
- may unwind and free those allocations after a partial failure.

The same lock is a FreeRTOS mutex taken with `portMAX_DELAY` on ESP. The render
path also takes it while processing active sequence executions. When an
execution finishes, the render path can decrement the last reference and free
every wire allocation while still holding the lock.

At 48 kHz and 128 samples, one AMY render block has about 2.67 ms. Allocator
latency, fragmentation, many string copies and cache misses are not a useful
use of that budget. The risk is intermittent rather than continuous: normal
preloading and editing of an unreferenced definition mutates it in place, and
copy-on-write is needed only when an active execution owns the old version.
That makes a dropout less frequent, not impossible.

The current P4 project has PSRAM disabled, so this exact build uses default
internal-capability memory for these definitions. The design must still avoid
heap work under the audio lock. If later releases place definition/event data
in PSRAM, cache variability and the shared flash/PSRAM cache make the bound
less predictable. Espressif also recommends preallocation rather than heap
operations in latency-sensitive interrupt work; an audio task is not an ISR,
but the same bounded-latency principle applies.

Conclusion: the concern is valid. It must be measured on hardware, but the
current code cannot prove that a live edit will never block a render deadline.

## Why ping-pong alone is insufficient

With two buffers, the writer can build B while readers use A and then swap the
published pointer to B. That works only if A becomes free before the next
publication.

Reusable sequences allow:

- several overlapping executions of one tag;
- long finite executions;
- indefinitely repeating executions;
- a new definition version while older executions continue.

Successive edits can therefore produce active executions holding versions A,
B and C at the same time. No fixed two-buffer rule can safely overwrite A or B
merely because it is no longer the published version. Waiting for one to
become free defeats the non-blocking goal. More fixed buffers postpone the same
problem and require an explicit exhaustion policy.

The theoretical maximum number of old versions retained across all tags is
bounded by the configured execution pool, because an old version survives only
while at least one execution refers to it. The current published versions add
up to one per defined tag. That is a useful bound, but it is much larger than
two and allocating a full event array for every possible buffer would waste
memory.

## Why a conventional garbage collector is a poor fit

A tracing collector would add more code, metadata and unpredictable scanning
or pause behavior while solving a lifetime problem that is already explicit.
AMY knows exactly which owners exist:

- one public tag slot owns the current definition;
- zero or more active executions own the version they started with;
- a writer temporarily owns a version being constructed.

Reference counting is therefore sufficient. The required “GC-like” part is
only deferred destruction: the audio task announces that an object is no
longer needed, while another task performs the variable-time frees.

An epoch-only RCU grace period of one or two audio blocks is also insufficient.
An execution retains its definition across many blocks and may repeat forever.
Lifetime references, or an equivalent hazard/lease mechanism, are necessary.

## Recommended ownership model

### Objects

- A definition is immutable after publication to an execution.
- A tag slot holds one reference to its current definition.
- Starting an execution adds one reference; completing it drops that reference.
- A writer pins the observed source version while cloning and drops that pin
  after publication or retry.
- Reaching zero references retires the object; it does not free it on the
  render task.

Use atomic reference operations or perform the individual ownership changes
inside the same very short synchronization boundary. Do not rely on `volatile`
for publication or memory ordering.

### Writer algorithm

For an edit of an actively referenced definition:

1. briefly lock, read the slot pointer and add a writer reference;
2. unlock;
3. allocate and clone the old contents plus the new event entirely on the
   command/control task;
4. lock briefly and compare the slot pointer with the captured source;
5. if it is unchanged, swap the slot to the new immutable version and transfer
   slot ownership;
6. if another writer won, unlock, discard/retire the unused candidate and
   retry from the new source;
7. release the writer reference outside the render path.

AMY currently serializes normal message ingestion, so retries should be rare.
The compare step nevertheless makes the ownership rule correct rather than
depending on that incidental serialization.

For a definition which is not shared with an execution, the existing in-place
append is efficient and avoids an O(n-squared) clone while preloading a phrase
event by event. Keep that fast path, but make its exclusivity test safe.

### Render algorithm

An execution owns its immutable definition for its lifetime. The render loop
can read through that stable pointer without allocating, cloning or freeing.
When the execution ends, it clears the execution slot and performs one bounded
reference decrement while already inside the AMY lock. If that was the final
reference, it prepends the definition to an intrusive retire list and returns.
The list link lives in the definition, so this operation needs no allocation,
fixed-capacity queue or queue-full policy.

This was chosen over the initially considered preallocated retire ring. A ring
would need a defensible capacity and an overflow policy, while the retired
definition itself already provides the only node required. Memory use remains
bounded by the definitions actually created and not yet reclaimed. Every
ordinary public wire-ingest completion drains the list, and direct non-render
sequence operations also drain opportunistically. Deinitialization performs a
final synchronous drain.

### Reclaimer

No dedicated task is required solely for this feature. The portable public
wire-ingest boundary is the reclamation owner. On ESP32-P4 that boundary is
normally entered by the HP UART command task; on desktop it is entered by the
socket, pipe or local command/control context. Render-fired wires use a direct
internal dispatch path and therefore cannot accidentally run reclamation.

The reclaimer frees all wire strings, the event array and the definition. It
also owns cleanup of unpublished candidates after a failed compare or OOM.
Shutdown/reset may synchronously drain after audio execution has stopped.

## Allocation layout

The smallest safe change is to move the existing clone allocations outside the
lock and defer destruction. A later optimization can pack a definition's event
descriptors and wire bytes into one allocation. That changes an active clone
from one event-array allocation plus up to N string allocations into one
allocation and mostly contiguous copying, reducing fragmentation and cache
traffic.

Do not make packing a prerequisite for fixing the lock. It is a measurable
optimization and complicates incremental append. The likely practical order
is:

1. externalize clone work and add compare-and-swap publication;
2. defer all render-side frees;
3. instrument timing, queue depth and allocation failures on P4;
4. pack snapshots only if measurements justify it.

## Failure and overload behavior

- Failure to allocate a candidate leaves the old slot definition unchanged.
- An edit reports a clear error; it never publishes a partial definition.
- A compare failure retries on the command task with a finite diagnostic
  counter.
- Publication takes only the bounded pointer/ownership critical section.
- The audio task never blocks for a writer and never performs heap work.
- A full execution pool remains an explicit start failure.
- Reset and deinit have a defined quiescent phase before final reclamation.

The slot pointer exchange itself can be an aligned pointer store under AMY's
existing mutex. A lock-free C11 atomic exchange is optional, not the first
goal: the critical property is that allocation, copying and freeing are
outside the render-blocking section and publication has correct memory
ordering. A short mutex publication may still delay the render task by a few
instructions; hardware measurements should decide whether eliminating that
last critical section is worth the more complex atomic ownership protocol.

## Required tests and measurements

### Host correctness

- append to a definition while an execution uses it, proving the old execution
  sees the old tail and a later execution sees the cumulative new tail;
- repeated publications while three or more versions remain active;
- allocation failure at every candidate-construction step leaves the old
  definition usable and leak-free;
- a losing compare/retry path cannot lose or duplicate an event;
- reset, stop, global reset and shutdown reclaim every version exactly once;
- ThreadSanitizer stress with simultaneous ingestion and tick processing where
  supported;
- public dispatch retains root controls and same-tick child launch behavior
  after render dispatch is separated from the public reclamation boundary.

### ESP32-P4

- measure worst and high-percentile duration of the publication critical
  section, clone construction and reclaim work separately;
- record maximum render duration and missed/late DMA blocks while repeatedly
  editing active 64-event definitions;
- test with the project baseline: 48 kHz, 128-sample AMY blocks and 2x64-frame
  DMA descriptors;
- repeat with effects and the maximum expected active execution load;
- record internal heap low-water mark, largest free block and maximum retired
  list depth;
- if PSRAM is enabled later, repeat the same test with explicit memory-capability
  placement and cache-stressing background work.

Acceptance is not “no audible dropout in one run.” The render path should have
no allocator/free calls from this subsystem, publication lock time should be a
small bounded fraction of 2.67 ms, and a long stress run should report zero
missed audio deadlines.

## Relationship to other risks

The current stored-sequence tick path scans the bounded execution pool twice
per tick and briefly takes the AMY lock per occupied/empty slot. With the AMY
default of 32 executions and LB's current 40, that may be acceptable, but it
also needs an ESP32 load measurement. Fixing copy-on-write clone latency does
not prove the rest of the sequencer real-time safe.

Similarly, the anonymous legacy sequencer copies a repeating wire string while
holding the lock when the event fires. That behavior predates this feature but
is another allocator-under-lock path worth measuring or addressing separately;
do not silently widen the current PR to fix it without scope agreement.

## External technical references

- ESP-IDF 6.0.2 heap allocation and thread-safety guidance:
  <https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/system/mem_alloc.html>
- ESP32-P4 external-RAM cache and access restrictions:
  <https://docs.espressif.com/projects/esp-idf/en/stable/esp32p4/api-guides/external-ram.html>
- ESP32-P4 RAM measurement and queued-worker guidance:
  <https://docs.espressif.com/projects/esp-idf/en/stable/esp32p4/api-guides/performance/ram-usage.html>
- ESP32-P4 performance/task-priority guidance:
  <https://docs.espressif.com/projects/esp-idf/en/stable/esp32p4/api-guides/performance/speed.html>

## Verification completed and next action

The clean feature branch and the LB integration release both pass
`make ctest -j2`, `python3 tests/test_sequence_api.py` and `make check-c-api`. GCC
`-fanalyzer` reports no finding for `src/sequencer.c`. The new tests prove
append-while-active snapshot isolation and three simultaneously retained
generations. The complete C suite also proves that separating render dispatch
from public reclamation preserves root controls and same-tick child starts.

Allocation-failure injection and a deterministic simultaneous-writer
compare/retry test now pass. A ThreadSanitizer build of that targeted test also
passes when the unrelated Linux MIDI backend is excluded. Physical P4 timing
remains open. The next action is a hardware stress run at the
48 kHz / 128-sample / 2x64 DMA baseline before describing the implementation as
hard real-time safe. In particular, measure publication-lock time, render
deadline misses, heap low-water mark and worst retained-list depth while active
64-event definitions are repeatedly edited under maximum expected FX load.

### ESP-IDF compile proof

The implementation was also compiled and linked with ESP-IDF 6.0.2 using the
physically established `rework/esp32p4` v1 profile at LB commit `65d95d1` and
the earlier AMY integration release at `a26fa6ca`. The first compile exposed the
expected API migration in the P4 application: its three assignments still used
the retired group field names. In the temporary validation worktree they were
mapped one-for-one as follows:

| Retired field | Cumulative-sequence field |
| --- | --- |
| `max_sequence_groups` | `max_sequencer_tags` |
| `max_sequence_group_tags` | `max_sequence_events` |
| `max_sequence_group_executions` | `max_sequence_executions` |

With only that integration rename, the v1 build completed, linked Gamma9001,
and produced a merged flash image. The application binary was `0x4ad720` bytes
in the 8 MiB app partition, leaving `0x3528e0` bytes (42%). This proves source,
ABI-at-build-time and linker compatibility for the new reclamation code on the
ESP32-P4 toolchain. It does not prove runtime timing, sound, heap high-water or
physical board behavior.

The field mapping was deliberately tested in a disposable worktree and was
not committed onto the older sequencer-group P4 product branch. When that P4
branch is rebased or merged into cumulative-sequence work, migrate its Kconfig,
firmware contract tests and package metadata together instead of leaving old
“group” terminology around the new fields.

The finalized host integration release is now `8a896e93`; a physical P4 build
and timing run against that exact head has deliberately not yet been claimed.
