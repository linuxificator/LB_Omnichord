# Codex handover: AMY upstream-baseline findings

Status: confirmed findings outside the reusable-sequence patch
Recorded: 2026-09-05
Baseline: Shorepine `main` at
`0fb0a00b5a9f9443d7e1f85261cc7e70a0adb76b`
Feature head used during discovery:
`ab2a02ec351ca4328069955abf674bc459f7262e`

This document deliberately separates defects and infrastructure limitations in
the existing AMY baseline from the reusable-sequence changes. These findings
must not be presented as regressions caused by the sequence patch. They were
discovered while extending pre-merge validation beyond AMY's normal test
matrix.

No corresponding changes have been added to the Shorepine-facing sequence
branch. Each source defect should be handled as a focused upstream issue or
patch with its own baseline regression test.

## Confirmed source findings

### MIDI-mapping parser reads beyond a completed patch string

Severity: memory-safety defect.

Running the complete native suite with AddressSanitizer reaches a global
buffer overread in `midi_mapping_from_message()` through
`tests/test_voice_osc_range`. After the parser has advanced `pos` to `mlen`,
the current condition does not leave the loop:

```c
if (pos < mlen && message[pos] != 'i') break;
cmd = message[pos + 1];
```

When `pos == mlen`, the first expression is false and `message[pos + 1]` reads
beyond the terminating byte. ASan reports the access from `src/parse.c` while
loading a built-in percussion patch string.

The same test, sanitizer flags and stack reproduce at Shorepine baseline
`0fb0a00b`; the reusable-sequence diff does not modify this function. A focused
fix should check the end position before looking for another `i<command>`
fragment and add parser tests for a fragment ending exactly at the string
boundary.

### Resetting oscillators leaks the previous bus-filter arrays

Severity: cumulative heap leak on repeated oscillator resets.

LeakSanitizer attributes allocations retained across process shutdown to
`filters_init()`, reached through:

```text
amy_reset_oscs -> buses_reset -> bus_reset -> filters_init
```

`bus_reset()` allocates new `eq_coeffs` and `eq_delay` trees. During
`amy_reset_oscs()`, `buses_reset()` replaces the existing pointers without
first releasing their allocations. Only the most recently installed arrays
remain reachable for `global_deinit()`.

This path and ownership behavior are unchanged from Shorepine main. A focused
fix should separate allocation from state reset, or safely deinitialize an
already initialized filter tree before replacing it. Tests should cover many
`RESET_ALL_OSCS` cycles and verify stable outstanding allocation counts.

### Patch-table backing allocations are never freed

Severity: heap leak across repeated `amy_start()`/`amy_stop()` lifecycles.

`patches_init()` makes one contiguous allocation and derives
`memory_patch_deltas`, `memory_patch_oscs`, `osc_to_voice`,
`voice_to_base_osc`, and `memory_patch_auto` from it. `patches_deinit()` only
sets those pointers to `NULL`; it does not free the allocation base.

LeakSanitizer reported 980-byte direct allocations from `patches_init()` on the
tested default configuration, accumulating once per lifecycle. The same code
is present in Shorepine main. A fix must preserve the correct ordering for
releasing stored delta lists versus `deltas_pool_free()`, then free the single
allocation base exactly once and make repeated stop calls safe.

### Fixed-point log lookup contains signed-shift undefined behavior

Severity: undefined behavior already present in the numeric core.

UndefinedBehaviorSanitizer stops in `src/log2_exp2.c` when a negative lookup
table value is converted through a macro which left-shifts a signed negative
value. This occurs before the reusable-sequence tests can complete under the
combined sanitizer build. The code predates the sequence patch.

The conversion should be expressed through a defined unsigned operation or a
safe multiplication/conversion which preserves the intended fixed-point bit
pattern. It needs numerical equivalence tests across the full table range,
particularly negative values and the extrema.

### Optional ALSA shutdown state has a ThreadSanitizer race

Severity: host MIDI shutdown race; previously observed, not re-measured in the
2026-09-05 pre-merge run.

An earlier full ThreadSanitizer run with the optional ALSA implementation
enabled reported unsynchronized shutdown-state access in the ALSA MIDI path.
The reusable-sequence concurrency test is therefore run in AMY's supported
no-ALSA host configuration, where it is clean. The ALSA source is not changed
by the sequence patch.

This should be reproduced and repaired separately with a clearly owned atomic
or lock-protected stop flag and a test which starts and stops the MIDI worker
repeatedly. Until revalidated, do not cite the no-ALSA TSan result as proof for
the ALSA lifecycle.

## Test and infrastructure observations

### Leak detection needs baseline-specific isolation

The local sandbox prevents LeakSanitizer from attaching through its required
ptrace path. A temporary GitHub Actions branch was therefore used. Plain leak
detection first reported the filter and patch-pool leaks above. The final
sequence-specific run suppressed only allocations whose stack starts in
`filters_init()` or `patches_init()`; all allocations from the new sequence
implementation remained visible. With that limited isolation, the sequence
lifecycle and RCU-like retirement tests passed LeakSanitizer.

The temporary sanitizer workflow and suppressions are validation fixtures and
must not be merged into the Shorepine-facing branch without an explicit
decision to maintain sanitizer CI.

### Full ASan and sequence-specific ASan answer different questions

The complete ASan suite currently stops on the baseline MIDI-parser overread.
All reusable-sequence C tests pass ASan independently. Record both facts:

- the feature's tested memory paths are clean;
- the repository as a whole is not ASan-clean at the comparison baseline.

Do not turn off ASan globally to obtain a green result; fix the independent
parser problem in its own change.

### Physical AMYboard validation is runner-dependent

The cloud half of AMY HW CI successfully builds the ESP32 firmware. The
follow-on physical benchmark requires the self-hosted `amyboard-hwci` runner.
Runs in the fork may remain queued when that runner is unavailable, so a green
cloud build is not evidence of measured realtime performance on hardware.

This is consistent with the reusable-sequence documentation: physical ESP32
render time, DMA deadlines, heap watermarks and retirement depth remain
target-dependent measurements.

### GitHub Actions reports Node runtime deprecation warnings

GitHub currently warns that the Node.js 20 runtime declared by
`actions/checkout@v4` and `actions/setup-python@v5` is deprecated and is being
forced to Node.js 24. The jobs still pass. This is workflow maintenance rather
than an AMY source or sequence-patch defect; update the actions when supported
releases with the desired runtime are available.

## Recommended separation of future work

Handle these as independent changes in this order:

1. fix and regression-test the parser out-of-bounds read;
2. fix patch-table lifecycle ownership and repeated start/stop tests;
3. fix filter allocation ownership and repeated oscillator-reset tests;
4. remove the fixed-point signed-shift undefined behavior with numerical
   equivalence coverage;
5. reproduce and fix the optional ALSA lifecycle race;
6. update CI action versions independently of source changes.

Keeping these outside the reusable-sequence PR makes review causality clear
and prevents unrelated baseline cleanup from expanding that patch.
