# ESP32-P4 full-width reverb LPF parallelization experiment

Status: measured; candidate rejected
Date: 2026-09-07
Target: Waveshare ESP32-P4 revision 1.3, CPU 360 MHz, 32 MiB PSRAM at
200 MHz
AMY scalar baseline: `9306a2cb1c2488264e384bb534264f039fb60b8c`
Temporary AMY experiment commits: `255aa5c2` (four lanes) and `b8a8076b`
(two pairs)

## Question

Can AMY's four independent one-pole filters inside one reverb be calculated
in parallel on ESP32-P4 without changing the 32-bit Q8.23 audio,
coefficient, or state representation?

The experiment deliberately did not truncate or normalize samples to 16 bits.
Such a conversion would require an application-dependent choice of scale and
could discard a quiet signal that is amplified later in a synth chain.

## Controlled A/B setup

All images used the ESP32-P4 `v1` profile, AMY block size 128 at 48 kHz, the
same load diagnostics, and internal SRAM for reverb delay networks. Four sine
voices were kept running on buses 0 through 3 and only buses 0 and 1 had
reverb enabled:

```text
v0w0f130.81l0.2y0Z
v1w0f196.00l0.2y1Z
v2w0f261.63l0.2y2Z
v3w0f329.63l0.2y3Z
h0.5,0.5,0.5y0Z
h0.5,0.5,0.5y1Z
```

Commands travelled through the real 1 Mbit/s LP-UART path from the Raspberry
Pi. Each result below is a stable average over about 750 128-sample blocks.
Transient command/allocation windows were excluded.

## Candidates

1. Scalar baseline: the existing four sequential `LPF()` calls.
2. Four-lane scheduling: expose the same three full-width fixed-point
   multiplies for all four filters stage by stage.
3. Paired scheduling: do filters 1/2 together and then filters 3/4 together,
   reducing the intended live-register pressure.

Every candidate kept the operation order within each filter and continued to
use `SMULR6`, which is a signed 32x32-to-64 multiplication followed by the
Q8.23 shift on this target.

## Physical result

Stable average time per block, in microseconds:

| Implementation | Execute | Render | Fill | Total | Delta total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Existing scalar | 85-86 | 125 | 281 | 495-496 | baseline |
| Four filters grouped | 85-86 | 125 | 284 | 499 | +3 to +4 |
| Two pairs grouped | 85-86 | 125 | 282-283 | 497-498 | +2 |

Repeated reporting windows produced the same ordering. The small regression
is therefore larger than the one-microsecond reporting resolution and is not
a single-window anomaly.

The compiler output explains the result:

| Property of `stereo_reverb()` | Scalar | Four lanes | Two pairs |
| --- | ---: | ---: | ---: |
| Stack frame | 240 bytes | 256 bytes | 256 bytes |
| Disassembly lines | 465 | 472 | 472 |
| `mul`/`mulh` instructions | 26 | 26 | 26 |

Grouping exposes independent source operations, but GCC already schedules the
P4 scalar multiplier adequately. The rewritten loop adds register pressure,
spills, and instructions without reducing the number of full-width
multiplications.

## Why Xai/PIE does not rescue this full-width path

The physical instruction probe confirmed that Xai/PIE is available on the
revision-1.3 target and that `ESP.VMUL.S32.S16xS16` operates as documented.
Despite its name, this is eight signed **16x16** multiplications producing
32-bit results. Xai/PIE does not provide a four-lane signed
32x32-to-64 multiply corresponding to AMY's `SMULR6`.

Using Xai only for the additions/subtractions would require repeatedly packing
four unrelated delay outputs into a vector, extracting four lanes for scalar
full-width multiplies, and inserting them again. That adds more scalar/vector
moves than the vector additions remove. Splitting each 32-bit operand into
16-bit limbs is mathematically possible, but it needs multiple partial
products, sign/carry correction, 64-bit recombination, and accumulator
stores. It would no longer be the small, low-risk LPF optimization being
tested, and its instruction/memory cost is unlikely to beat the native scalar
`mul`/`mulh` pair.

## Decision

Do not merge either grouped implementation. The existing scalar LPF is faster
for the required full-width Q8.23 contract. No 16-bit variant was implemented
or evaluated.

For this workload the useful optimization direction remains architectural:
use two shared reverb networks in internal SRAM instead of many per-bus
networks. If arithmetic is revisited, first add a cycle-level isolated
benchmark and require both bit-exact output and a material whole-reverb speed
gain before changing AMY.

The experimental AMY commits are intentionally confined to a temporary/local
experiment branch and are not part of the AMY fix or release branches.
