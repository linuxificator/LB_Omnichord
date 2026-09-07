# ESP32-P4 render jitter, DMA buffering and overload pacing

Status: physically validated and released on the AMY fork
Date: 2026-09-08
AMY development branch: `rework/shared-reverb`
AMY release branch: `releases/amy_omnichord_R20260908T005616`
AMY commit: `e9a96c20da31b4130a243bf75b984408c1dff5e0`
LB integration branch: `rework/shared-reverb`
Physical target: Waveshare ESP32-P4 Pico M, chip revision 1.3, 360 MHz,
32 MiB PSRAM at 200 MHz

## Outcome

The complete LB workload runs with two shared reverbs in dedicated SRAM and a
128-sample AMY block behind a 2 x 128-frame I2S DMA ring. Individual blocks may
take more than their 2.667 ms real-time budget, but the measured backlog is
repaid by the following cheaper blocks and remains within the one additional
2.667 ms DMA block.

The audible dropout was not caused by one isolated block being slightly late.
It was caused by the recovery code converting every such block into a 10 ms
FreeRTOS sleep. AMY now measures cumulative *unpaced render-time debt*: a DMA
write which blocks proves the producer has caught up and clears the debt;
unpaced over-budget blocks add only their excess; cheaper unpaced blocks repay
it. The max-priority audio task yields for one scheduler tick only after the
unrepaid debt reaches the duration of that actual tick.

This retains starvation protection during sustained overload without turning
normal event/onset jitter into a much larger dropout.

## How the investigation reached this result

### 1. Establish the old, known-good baseline

The original local P4 project in `/home/jeroen/projects/amy-p4-test` could
render a simple chord correctly. That established the board, PCM5102A wiring,
I2S format, 128-sample block size and dual-core AMY arrangement as viable.

Increasing configured synths, buses or reusable sequence capacity does not by
itself cost render time. The live number and kind of oscillators and effects do.
Gamma9001 also was not the direct cause: simple Gamma9001 tones rendered
normally in isolated tests.

### 2. Isolate reverb cost and memory placement

Four synths without reverb, the same four synths with two shared reverbs, and
four historical per-bus reverbs were measured with the same serial workload.
Moving two 111,888-byte reverb arenas from PSRAM into two exclusive 128 KiB
internal-SRAM banks roughly halved each room's DSP time from about 216 us to
109 us. Running room 0 on core 0 and room 1 on core 1 made their shared stage
follow the slower room instead of their sum.

This removed PSRAM from the hot reverb-delay path, but the full application
could still crackle. It therefore was a necessary performance improvement, not
the complete explanation.

### 3. Attribute time by render stage

Deferred target diagnostics were added for execute, render and fill stages,
core split, audible oscillator count, executed deltas and reusable-sequence
sub-stages. Measurements are accumulated in the realtime tasks and printed
later in response to `?loadZ`, `?reverbZ` or `D1Z`; no printing occurs in the
audio path.

The synthetic source matrix showed:

| Source/workload | Typical execute time | Observation |
| --- | ---: | --- |
| Shorepine main, root scheduler | 14-16 us | Baseline |
| Initial stored-sequence implementation | about 179 us | Repeated bounded scans dominated |
| Optimized stored sequences | 51-52 us | No misses without effects |

The sequence changes that produced the latter result were deliberately
generic:

- finite executions no longer rescan events that can never fire again;
- irrelevant event classes are skipped;
- uniform periodic definitions advance from their previous due position;
- active executions have a bounded active index rather than requiring every
  free slot to be visited on every tick;
- render-owned runtime state is kept in internal render memory on ESP32, while
  immutable definitions can remain in larger memory.

Existing ordering, exact tick timing, start/stop/gate semantics, stored
definition ownership and wire/API behavior remain unchanged. AMY's complete
host test suite passed after these changes.

### 4. Test the actual application, not only a synthetic load

The physical integration test used the real LB headless application on a
Raspberry Pi, its production 1 Mbaud serial transport, all preloaded rhythm and
fill definitions, maximum rhythm/bass/chord activity, fills, arpeggios, manual
chord changes, shared Omnichord reverb, shared MIDI reverb and one held external
MIDI patch. Multiple rhythm changes intentionally exercised dense event
boundaries.

This revealed isolated 3-4 ms blocks. A raw `total_deadline_misses` count alone
made these look fatal even though the average remained safely below 2.667 ms.
With a 2 x 128 ring, one additional audio block is already buffered and can
absorb such a spike if subsequent blocks repay it.

### 5. Find the artificial 10 ms gap

The ESP fill task still contained this recovery condition in substance:

```c
if (busy_us >= AMY_BLOCK_US && blocked_us < 150) vTaskDelay(1);
```

The ESP-IDF configuration uses a 100 Hz scheduler tick, so `vTaskDelay(1)` is a
10 ms pause, not a one-millisecond backoff. A single naturally expensive onset
therefore drained far more than the available ring. The empty ring then made
the next write unpaced too, which could re-arm the behavior.

This is the same mechanism reported in upstream AMY issue 1118. Upstream PR
1119 had already improved the older rule by requiring one full over-budget
block as well as an unblocked write. The full stored-sequence workload showed
that this condition was still too eager when DMA buffering is intentionally
used to absorb isolated jitter.

References:

- <https://github.com/shorepine/amy/issues/1118>
- <https://github.com/shorepine/amy/pull/1119>

### 6. Replace the threshold with measured debt

For each unpaced block:

```text
busy > block budget: debt += busy - block budget
busy < block budget: debt -= min(debt, block budget - busy)
DMA write blocked:   debt = 0
```

The escape yield occurs only at:

```text
debt >= ceil(1,000,000 / configTICK_RATE_HZ) microseconds
```

The threshold therefore follows the actual FreeRTOS configuration and does not
hard-code 10 ms. Arithmetic saturates rather than wrapping. The existing
long-window `amy_overload_check()` remains active as the independent protection
against sustained compute overload.

## Physical acceptance results

The final long run covered 254,629 128-sample blocks, approximately 11 minutes.
Both reverbs and the realistic maximum application workload described above
were active.

| Measurement | Result |
| --- | ---: |
| Average execute / render / fill / total | 72 / 803 / 859 / 1,739 us |
| Maximum execute / render / fill / total | 1,723 / 1,625 / 1,134 / 4,276 us |
| Blocks individually over 2.667 ms | 5,394 |
| Unpaced I2S writes | 12,153 |
| Maximum unrepaid render debt | 1,610 us |
| Scheduler overload yields | 0 |
| Reverb room 0 average / maximum | 109 / 171 us |
| Reverb room 1 average / maximum | 115 / 195 us |
| Reverb deadline misses | 0 |
| Internal RAM free / largest block | 86,576 / 53,248 bytes |
| PSRAM free | 32,724,680 bytes |

The significant acceptance value is the 1.610 ms maximum debt, not the number
of individually over-budget blocks. It remains below the 2.667 ms additional
DMA capacity and returned to zero without an artificial yield. A deliberately
unrealistic stress case with four extra simultaneous held MIDI patches reached
6.683 ms debt; it usefully defines a boundary but is not the intended maximum
workload.

## DMA geometry and latency decision

AMY still renders 128 samples at 48 kHz. `dma_desc_num=2` and
`dma_frame_num=128` provide 256 frames in total. Compared with the previous
2 x 64 arrangement this adds one 128-frame block, or about 2.667 ms, of fixed
output latency. The user explicitly accepted this latency in exchange for
reliable full-workload behavior.

An event cap or automatic deferral by 2.667 ms was rejected. It would change
musical ordering and timing and would make overload policy visible to callers.
The current solution leaves sequencer semantics exact and buffers compute
jitter only at the audio transport boundary.

## Board-profile incident

One diagnostic build accidentally used the `v3` silicon profile and was forced
onto the physical revision-1.3 chip. It boot-looped with an illegal instruction.
Rebuilding with `./build_firmware.sh --profile v1` restored correct operation.
Never use esptool `--force` to cross the ESP32-P4 silicon ABI boundary:

- `v1` is for chip revisions 1.0 through 1.99 and is physically verified;
- `v3` is for revision 3.1 and later and is compile-only until the newer board
  is tested.

Release artifacts intentionally contain separate `v1/` and `v3/` images.

## Approaches investigated but not adopted

- Skipping silent reverbs saves time in a test but cannot guarantee later use.
- Four historical per-bus reverbs are both musically unnecessary here and too
  expensive; weighted sends to two shared spaces are the generic solution.
- Moving long delay tails to PSRAM costs much more than it saves.
- GDMA/2D-DMA adds copying and synchronization but cannot accelerate the
  recursive delay/LPF dependency.
- SIMD across four LPFs gave little benefit because memory access and the
  recursive scalar dependency dominate; changing AMY's 32-bit audio path to
  16 bit was rejected because normalization would be content-dependent.
- Pre-parsing every stored wire event into `amy_event` would consume substantial
  memory and make cancellation/generation validity more complex. It is not
  justified while measured debt remains inside the DMA budget.
- A one-block scheduler yield is not a portable substitute for explicit debt:
  its duration follows `configTICK_RATE_HZ`, not the audio block duration.

## Verification and maintenance contract

- `make ctest` passes at AMY commit `e9a96c20`.
- The first release build exposed a diagnostics-only portability error:
  GCC's `__sync_synchronize()` was used by generic shared-reverb snapshots but
  is not provided by MSVC. The final commit routes the same full memory fence
  through `MemoryBarrier()` on Windows and the GCC intrinsic elsewhere. This
  changes neither audio nor snapshot semantics.
- The ESP-IDF 6.0.2 `v1` image compiles and links that exact commit with
  Gamma9001; application size is `0x4b2940`, leaving 41% of the 8 MiB app
  partition.
- The P4 production configuration is 128-sample AMY blocks and 2 x 128 DMA
  frames. Tests must reject a silent return to 2 x 64.
- Release builds must pin both the immutable AMY commit and matching release
  branch. `prepare_amy.sh` must not patch AMY after checkout.
- Generic sequence scheduling and shared reverb send/return behavior must be
  built into AMY on every supported platform. Fixed memory regions, core
  assignment, I2S pacing and these deferred target counters are ESP-specific.
- Future performance decisions should use maximum unrepaid debt together with
  average and maximum stage times. A raw count of blocks above 2.667 ms is not
  sufficient evidence of audible underrun when buffering is present.
