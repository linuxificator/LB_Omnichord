# Shared reverb rooms: ESP32-P4 implementation and physical proof

Status: integrated and physically validated with the complete LB workload
Date: 2026-09-08
AMY branch: `rework/shared-reverb`
AMY release commit: `b959b86ec23769976572b93f476ec18fe374a723`
LB firmware branch: `rework/shared-reverb`
LB firmware commit: `286734d270323be5d9df85b3b6a1063c3c01734d`
Physical target: Waveshare ESP32-P4 revision 1.3, CPU 360 MHz, 32 MiB
PSRAM at 200 MHz

## Requirement and boundary

The application needs two acoustic spaces, not one reverb instance for every
AMY bus:

- Omnichord buses 0 through 3 send to shared processor 0;
- MIDI buses 4 through 10 send to shared processor 1;
- every bus has an independent weighted send, where zero excludes it;
- the dry bus remains in the normal mix;
- musical policy (which bus belongs to which space and whether drums are
  included) remains in LB Omnichord rather than AMY.

AMY keeps historical per-bus `h...` behavior unchanged. Shared processors are
opt-in through `amy_config_t.max_reverb_rooms`; its default remains zero.

## AMY interface under evaluation

The provisional Python API is:

```python
amy.send(reverb_room=[0, 0.7, 0.85, 0.5, 3000])
amy.send(bus=2, reverb_send=[0, 0.6])
```

The matching provisional wire commands stay inside the existing `h` effect
family:

```text
hR0,0.7,0.85,0.5,3000Z
hS0,0.6y2Z
```

`hR` configures one shared processor as room, return level, liveness, damping
and crossover frequency. `hS` selects the processor and weighted send for one
bus. The word `room` is provisional and can be renamed without changing the
architecture.

## Realtime implementation

- Each processor owns a caller-supplied arena containing the reverb state,
  one stereo block and every delay-line object and sample.
- The ESP32-P4 firmware reserves `0x4ff60000..0x4ff7ffff` and
  `0x4ff80000..0x4ff9ffff` at linker/startup time with
  `SOC_RESERVE_MEMORY_REGION`.
- These are two complete, naturally aligned 128 KiB internal-SRAM banks. They
  are never registered with the capability heap, so later allocation or DMA
  setup cannot consume them.
- Physical startup reported only the remaining `0x4ff40000..0x4ff5ffff`
  high-SRAM bank to the heap, proving both reservations took effect.
- Each P4 reverb consumes 111,888 of its 131,072-byte arena.
- Processor 0 reuses AMY's core-0 render worker after oscillator rendering;
  processor 1 runs on the core-1 fill task. The existing semaphore is also the
  join. No extra realtime task, stack, allocation, queue or print exists.
- A processor with return level zero skips its delay walk. Once enabled it
  keeps processing silent input so its existing tail decays naturally.
- Timing is accumulated with sequence-lock snapshots. `?loadZ` or
  `?reverbZ` prints it later from the lower-priority LP-UART command task, not
  from either audio task.

## Synthetic physical workload

Each run started from a hardware reset. Commands were sent from the Raspberry
Pi through the real 1 Mbit/s LP UART, paced 30 ms apart to avoid overflowing
the finite LP receive ring. Four one-voice synths used four separate buses:

```text
K1i0iv1y0Z
n48l0.25i0Z
K2i1iv1y1Z
n55l0.25i1Z
K3i2iv1y4Z
n60l0.25i2Z
K4i3iv1y5Z
n64l0.25i3Z
```

The shared configuration was:

```text
hR0,0.7,0.85,0.5,3000Z
hR1,0.7,0.85,0.5,3000Z
hS0,1y0Z
hS0,1y1Z
hS1,1y4Z
hS1,1y5Z
```

The control image for shared PSRAM allocation was built in a detached
temporary worktree. It retained the same two excluded SRAM banks, firmware,
synths, routing and commands; only the two arena pointers were changed to
`NULL`. This isolates storage location without giving the PSRAM build extra
heap capacity.

## Results

All values are microseconds per 128-sample block at 48 kHz. The hard block
budget is 2666.7 microseconds. Averages cover about 5,300 blocks, including a
short disabled startup interval, so comparisons use identical startup and
reporting procedure.

| Workload | Execute avg | Render avg | Fill avg | Total avg | Total max |
| --- | ---: | ---: | ---: | ---: | ---: |
| Four synths, shared processors disabled | 86 | 341 | 318 | 748 | 1109 |
| Same synths, two shared processors in PSRAM | 104 | 401 | 544 | 1053 | 1824 |
| Same synths, two shared processors in dedicated SRAM | 86 | 344 | 436 | 870 | 1261 |
| Same synths, four historical per-bus reverbs in PSRAM | 122 | 528 | 982 | 1637 | 4064 |

Per-processor diagnostics for the two-room A/B:

| Storage | Processor 0 avg/max | Processor 1 avg/max | Parallel stage avg/max |
| --- | ---: | ---: | ---: |
| PSRAM | 214 / 261 | 218 / 262 | 208 / 295 |
| dedicated SRAM | 109 / 187 | 109 / 114 | 107 / 212 |

Core masks proved processor 0 ran only on core 0 (`0x1`) and processor 1 only
on core 1 (`0x2`). Neither processor recorded a reverb deadline miss.

Derived observations:

- dedicated SRAM roughly halves each reverb's measured DSP time;
- it saves 183 microseconds, or about 17%, on the complete two-room workload
  compared with the otherwise identical PSRAM image;
- two SRAM rooms add only about 122 microseconds to this four-synth baseline;
- four historical per-bus PSRAM reverbs exceeded the block deadline at least
  once (`4064` microseconds), while the two-room SRAM maximum retained about
  1.4 ms margin;
- the parallel-stage time follows the slower room rather than their sum, so
  the intended core split is effective.

## Decision and remaining work

The two-room, two-exclusive-bank design is practical on the physical v1.3
target and is substantially safer than per-bus reverbs. The production
firmware uses the dedicated-SRAM form; the PSRAM image was measurement-only.

The integration steps below have been completed. The later full-workload run
did expose a separate 10 ms scheduler-yield problem. Its diagnosis, fix and
long physical acceptance measurement are recorded in
`CODEX_HANDOVER_ESP32P4_RENDER_JITTER_AND_DMA_DEBT.md`.

Completed integration contract:

1. Change LB Omnichord's two transport-facing reverb controllers to configure
   one shared processor each and send their buses to it.
2. Preserve the existing user behavior: Omnichord drums and MIDI drums use a
   zero send unless the corresponding DRM control is enabled.
3. Add command-plan and integration tests proving there are exactly two
   processor configurations, every bus has the intended route, and no
   historical per-bus `h...` command remains in the application path.
4. Rebuild and run desktop tests against the pinned AMY commit.
5. Flash the production SRAM image again and perform full Omnichord audio and
   load acceptance; synthetic timing proves the DSP architecture but not the
   complete application's peak load.

Do not copy this Codex handover into the AMY repository. Public AMY docs should
describe only the generic opt-in send/return facility and its API.
