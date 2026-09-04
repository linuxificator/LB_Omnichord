# Codex handover: real-time-safe reusable-sequence publication

Status: design analysis; not implemented
Date: 2026-09-04
Affected AMY branch: `rework/sequencer_simplification`
Primary target of concern: ESP32-P4 at 48 kHz, 128-sample AMY blocks

## Decision summary

Do not solve sequence replacement with exactly two reusable buffers and do not
add a tracing garbage collector. The most practical design for this code is:

1. keep definitions immutable while executions refer to them;
2. build a new definition version outside the AMY/audio queue lock;
3. publish it with one short, synchronized pointer swap;
4. let each execution hold a reference for its complete lifetime;
5. retire zero-reference old versions to a bounded queue;
6. reclaim their heap memory only from a non-rendering command/control context.

This is a small read-copy-update-like design with explicit reference counting
and deferred reclamation. It evolves the current ownership model rather than
introducing a general garbage collector.

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
atomic reference decrement. If that was the final reference, it pushes the
definition pointer into a preallocated retire ring and returns immediately.

The render path must never wait for space in the retire ring. Practical
policies are:

- size the ring for at least the maximum number of distinct obsolete versions
  which active executions can retain, bounded by the configured execution
  count, plus one publication/candidate allowance;
- drain it from the UART/parser/control task before or after message work;
- if a non-rendering writer observes a full ring, it may reclaim there;
- treat render-side ring exhaustion as a counted diagnostic/configuration
  defect, not as permission to call `free()` or block.

Because many executions can share one version, the actual queue demand is
normally well below the execution count. A control-side edit must drain the
ring before it can create another obsolete version; nested render-side starts
can create executions but cannot create definition versions. Those rules make
the bound defensible rather than an estimate based only on expected traffic.

### Reclaimer

No dedicated task is required solely for this feature. On ESP32-P4 the
existing HP UART command task is a natural reclamation owner. On desktop, the
message-ingestion/control context can drain the same portable retire API. A
small dedicated low-priority task is acceptable only if another platform
already needs one; it should not be mandatory architecture for AMY.

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
- A full retirement queue is observable; it must not silently leak forever.
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
- retirement-queue saturation follows its documented non-blocking policy.

### ESP32-P4

- measure worst and high-percentile duration of the publication critical
  section, clone construction and reclaim work separately;
- record maximum render duration and missed/late DMA blocks while repeatedly
  editing active 64-event definitions;
- test with the project baseline: 48 kHz, 128-sample AMY blocks and 2x64-frame
  DMA descriptors;
- repeat with effects and the maximum expected active execution load;
- record internal heap low-water mark, largest free block and retire-ring high
  water;
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

## Next action

Before editing AMY, agree the stop semantics and publication ownership model,
then add the failing COW correctness and allocation-failure tests. Implement
the minimal external-clone plus deferred-reclaim change first. Validate it on
host, then on the physical ESP32-P4 before describing it as real-time safe.
