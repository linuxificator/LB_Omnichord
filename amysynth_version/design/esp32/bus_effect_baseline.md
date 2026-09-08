# ESP32-P4 classic bus-effect baseline

Status: measured decision record
Owner: ESP32-P4 audio integration
Last verified: 2026-09-08
Physical target: Waveshare ESP32-P4 Pico M, chip revision 1.3

## Question

The shared-room implementation adds weighted subsets of existing AMY buses.
After replacing its separate mixer loop with the existing AMY-style bus-add
operation, diagnostics still attributed about 500 us per 128-sample block to
`bus_fx`. The remaining question was whether that time was introduced by the
new routing or was already the cost of AMY's ordinary per-bus effects.

## Independent baseline

The control firmware was built in an isolated temporary tree from AMY commit
`ccba3f5` (`esp32: only yield past-overload when rendering actually can't keep
up`), taken from the original physically working
`~/projects/amy-p4-test/components/amy` project. It predates the sequence-group
and shared-room implementation.

Only timing counters were added around the existing dual-core join, complete
serial bus-effect loop, individual EQ/chorus/echo/reverb calls, final output
mix and complete render iteration. Counters were accumulated during realtime
processing and printed later from the lower-priority UART command task. No
effect, routing or synthesis behavior was changed.

The clean checkout required the original six build adjustments recorded in
`~/projects/amy_log_from_0`:

- 128-sample blocks instead of 256;
- a matching block-size bit count of 7;
- 48 kHz instead of 44.1 kHz;
- Philips I2S framing instead of MSB framing;
- current FreeRTOS signatures for the MIDI and fill-buffer tasks.

I2S remained a 32-bit path. The temporary baseline did not copy a later
explicit DMA-ring setting. That does not affect the measured DSP-stage times,
which end before the blocking I2S write; DMA pacing counters were therefore
excluded from the comparison.

## Reproducible load

Both firmwares received the same commands from a separate Python process on
the Raspberry Pi through the production 1 Mbit/s LP-UART path. The setup used
eleven active buses, nine loaded instruments and the bus-effect state observed
in the complete Omnichord workload:

- EQ on buses 1 through 6;
- chorus on buses 2, 3, 4, 6 and 7;
- no echo;
- no legacy per-bus reverb;
- no shared room during this isolated comparison.

Every configured effect kept processing in both the silent and sounding
phases. This measurement does not depend on skipping silent effects.

## Results

All times are average microseconds per 128-sample block. The realtime budget
at 48 kHz is 2,666 us.

| Firmware and phase | Effect work | Bus wall time | Fill | Complete render | Misses |
|---|---:|---:|---:|---:|---:|
| Classic AMY, no notes | 492 | 492 serial | 664 | 831 | 0 |
| Classic AMY, nine instruments | 495 | 495 serial | 672 | 1,854 | 0 |
| Current AMY, no notes | 483 summed | 294 parallel | 463 | 645 | 0 |
| Current AMY, nine instruments | 501 summed | 311 parallel | 493 | 1,824 | 0 |

In the classic sounding run, the component counters reported approximately:

- six EQ calls per block at 52 us each: 312 us;
- five chorus calls per block at 33 us each: 165 us;
- no echo or reverb calls.

Those calls account for nearly all of the measured 495 us classic effect
loop. Adding audible instruments changed the classic bus-effect average by
only 3 us while increasing complete render time by more than 1 ms.

The current `fx` number is deliberately a sum of work performed by both cores;
`buses` is the elapsed wall time after both subsets join. Comparing the summed
501 us with the 311 us wall time shows that the existing effect work is being
parallelized rather than skipped. The current fill phase is about 179 us
shorter than the classic sounding baseline.

## Decision

The approximately 500 us of EQ and chorus work is an existing AMY DSP cost,
not overhead introduced by weighted bus subsets or shared-room routing. The
subset implementation successfully reuses AMY's bus-add concept and reduces
elapsed fill time by distributing complete bus chains over both cores.

No further attempt will be made here to optimize the established EQ or chorus
algorithms. Their cost is treated as the practical ceiling for this particular
six-EQ/five-chorus configuration. Future capacity work should instead measure
the chosen synth patches, oscillator count and event bursts, without charging
their cost to the subset mixer.
