# ESP32-P4 reverb memory baseline

Status: physical target measurement complete
Date: 2026-09-07
AMY baseline: `f3d72dfcec453a274d726869d5bf32533c3cca3b`
Diagnostic commit: `9306a2cb1c2488264e384bb534264f039fb60b8c`
Target: Waveshare ESP32-P4 revision 1.3, CPU 360 MHz, 32 MiB PSRAM at
200 MHz

## Purpose

This measurement separates the cost of four continuously sounding synth
voices from the additional cost of four independent AMY reverbs. It then
changes only the storage location of those four reverb delay networks, from
PSRAM to internal SRAM.

The second and third measurements both include the same four live synth
voices. The third measurement is not a reverb-only workload.

## Fixed configuration

- AMY sample rate: 48 kHz
- AMY block size: 128 samples
- audio-block deadline: 2666.7 microseconds
- four AMY buses
- one continuous sine oscillator per bus
- oscillator frequencies: 130.81, 196.00, 261.63 and 329.63 Hz
- oscillator velocity: 0.2
- four identical reverb settings: level 0.5, liveness 0.5, damping 0.5
- commands entered through the real 1 Mbit/s LP-UART wire-command path from
  the Raspberry Pi
- reporting windows: approximately two seconds / 748 audio blocks

Wire workload:

```text
v0w0f130.81l0.2y0Z
v1w0f196.00l0.2y1Z
v2w0f261.63l0.2y2Z
v3w0f329.63l0.2y3Z

h0.5,0.5,0.5y0Z
h0.5,0.5,0.5y1Z
h0.5,0.5,0.5y2Z
h0.5,0.5,0.5y3Z
```

## Results

Stable average times per 128-sample block, in microseconds:

| Workload | Execute | Render | Fill | Total | Deadline use |
| --- | ---: | ---: | ---: | ---: | ---: |
| Four synths, no reverb | 84-85 | 123-124 | 71 | 283-284 | 10.6% |
| Same synths + four PSRAM reverbs | 104-105 | 160-161 | 733 | 1001-1003 | 37.6% |
| Same synths + four internal-SRAM reverbs | 84-85 | 126 | 623 | 837-838 | 31.4% |

Representative stable maximum totals were about 548 microseconds dry, 1360
to 1405 microseconds with PSRAM reverbs, and 1100 to 1103 microseconds with
internal-SRAM reverbs. Transient command/allocation windows were excluded from
the stable averages.

Derived values using the central stable results:

- four PSRAM reverbs add about 719 microseconds to the dry workload;
- four SRAM reverbs add about 554 microseconds;
- PSRAM therefore adds about 165 microseconds per block relative to SRAM;
- the complete PSRAM-reverb workload is about 19.7% slower than the equivalent
  SRAM-reverb workload;
- the incremental reverb cost is about 29.8% higher in PSRAM than in SRAM;
- about 23% of the PSRAM reverb overhead is attributable to the observed
  PSRAM placement penalty; most of the reverb cost remains DSP work that is
  also present with internal SRAM.

The PSRAM effect is not confined to `amy_fill_buffer()`. Relative to the SRAM
run, the PSRAM run spends about 20 extra microseconds in delta execution, 35
extra microseconds in rendering and 110 extra microseconds in fill. This is
consistent with cache/PSRAM working-set interference carrying across audio
blocks.

## SRAM capacity finding

Each AMY reverb has 27,648 `SAMPLE` entries, or exactly 108 KiB of sample data
when `SAMPLE` is 32 bits. On this build, four successfully allocated networks
reduced reported internal heap by 458,912 bytes including delay-line objects
and allocator overhead. Only 11,952 internal bytes remained, with a largest
free block of 4096 bytes.

The production-sized build cannot hold four such networks in internal SRAM
without moving or reducing other reservations. Four buses and four patch-0
instruments were also tested: dry time was about 628 microseconds, four PSRAM
reverbs produced about 1690 microseconds, but only three SRAM reverbs fitted.
Patch 0 itself creates delay/effect allocations governed by the same delay
memory capability, so it is not a clean reverb-memory comparison.

For the controlled comparison only, the following identical accommodations
were applied to both images:

- the sleeping UART-forwarder stack was allocated in PSRAM;
- AMY render and fill task stacks were reduced to 2 KiB after measuring their
  high-water marks;
- unused audio-input buffers were allocated outside internal SRAM;
- the AMY bus count was reduced to the four buses exercised by the test.

At full four-reverb load the measured remaining stack margins were 1312-1392
bytes for render and 888 bytes for fill. These values prove this focused run,
not general production safety. The reduced stacks and input-buffer adjustment
exist only in the temporary measurement checkout and are not part of the AMY
fix branch.

## Conclusions

PSRAM is a significant and measurable contributor, but it is not the sole or
even majority reverb cost in this controlled workload. Moving all four delay
networks to SRAM saves about 165 microseconds per block, while the remaining
four-reverb overhead is about 554 microseconds.

This weakens the earlier hypothesis that PSRAM alone is the reverb bottleneck.
A practical production design should first reduce the number of independent
reverb networks (for example, shared send buses) and then consider placement
or cache-locality optimizations. Four complete internal-SRAM reverbs leave too
little memory margin for the full Omnichord configuration.

## Repository state

The real AMY branch `fix/esp32p4-audio-runtime` is based directly on the latest
Omnichord AMY release and contains only compile-time guarded ESP load
instrumentation. The memory-placement and stack-size accommodations above were
made in `/tmp/lb-p4-baseline` and must not be copied into a production branch
without broader stress and stack testing.

## Physical reset path

The Raspberry Pi GPIO18 output is wired to ESP32-P4 `EN`. A clean target reset
can therefore be performed remotely on the Pi without cycling USB:

```bash
pinctrl set 18 op dl
pinctrl set 18 op dh
```

Keep the low pulse brief and always restore the output high. This is useful
when a measurement must start from a clean heap and effect state.
