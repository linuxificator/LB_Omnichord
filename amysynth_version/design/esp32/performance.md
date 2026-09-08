# ESP32-P4 realtime performance and shared reverb

Status: authoritative measured design record
Owner: ESP32-P4 audio integration
Last verified: 2026-09-08
Physical target: Waveshare ESP32-P4 Pico M, chip revision 1.3

## Current design

AMY renders 128 samples at 48 kHz. I2S uses two 128-frame DMA descriptors:
256 frames or 5.333 ms total buffering, with one additional 128-frame block
(2.667 ms) available to absorb render jitter.

The application uses two generic shared reverb rooms instead of one reverb per
bus. Every bus has an independent weighted send; a zero send excludes it. LB
routes Omnichord buses 0-3 to room 0 and MIDI buses 4-10 to room 1. That routing
policy is outside AMY.

The current per-room signal flow, including all delay taps, feedback lanes and
LPFs, is shown in [`reverb_signal_flow.svg`](reverb_signal_flow.svg).

On P4, each complete 111,888-byte reverb arena occupies its own exclusive,
naturally aligned 128 KiB internal-SRAM bank. Room 0 executes with core 0 and
room 1 with core 1 through the existing render/fill synchronization. No extra
realtime task, copy or allocation is introduced. Generic shared-room behavior
is available on every AMY platform; fixed addresses, core placement, I2S
pacing and target counters are ESP-specific.

Four-synth controlled measurements found two rooms in SRAM averaged about
870 us per block versus 1,053 us in PSRAM and 1,637 us for four historical
per-bus PSRAM reverbs. Each SRAM room averaged about 109 us. The useful gain
came from reducing processors, parallel room execution and removing PSRAM from
the recursive delay path—not from changing AMY's 32-bit sample format.

## Timing bottleneck and correction

The remaining dropout was an overload-recovery error. An isolated block above
2.667 ms with an unblocked DMA write called `vTaskDelay(1)`. At the configured
100 Hz FreeRTOS tick this slept about 10 ms and drained a 5.333 ms DMA ring.

The current code tracks cumulative unpaced render debt:

- an over-budget unpaced block adds only its excess;
- a cheaper unpaced block repays debt;
- a blocking I2S write proves the producer caught up and clears debt;
- only sustained debt of at least one scheduler tick invokes the emergency
  `vTaskDelay(1)` starvation escape.

That last delay is not audio-safe—the 10 ms tick exceeds the DMA ring. It is a
last resort for a workload already structurally unable to keep up, not normal
pacing. A future audio-safe yield would require actual DMA occupancy plus a
yield primitive shorter than available headroom.

The sequencer was also made cheaper without changing its behavior: completed
events are not rescanned, irrelevant classes are skipped, uniform periodic
definitions advance from their previous due position, active executions have
a bounded index and render-owned state uses render-suitable memory.

## Proven workload and planning envelope

The physical acceptance run covered 254,629 blocks (about 11 minutes) with
drums, fills, bass, sequenced chords, arpeggios, manual changes, both reverbs
and one held external MIDI patch:

- average execute/render/fill/total: 72/803/859/1,739 us;
- maximum total: 4,276 us;
- maximum unrepaid debt: 1,610 us;
- overload yields and reverb deadline misses: zero;
- internal RAM free/largest block: 86,576/53,248 bytes.

This leaves about 35% average timing headroom. A reasonable conservative
planning estimate is the proven complete workload plus roughly 25% additional
synthesis load. Depending on oscillator type, that is approximately 80-100
simple simultaneous oscillators or 40-60 expensive filtered/FM oscillators.
It is not a guarantee: patch cost matters more than the configured count.

The build provides 336 oscillator slots, 1,280 stored sequence identities, 64
events per definition and 40 concurrent executions. Those are memory/control
limits, not a promise that 336 expensive audible oscillators meet deadline.
Stored inactive definitions add negligible realtime load; active events and
sounding synthesis determine it. Keep the 40-execution hard limit distinct
from the conservative CPU envelope above.

## Rejected paths

- Four per-bus reverbs: unnecessary and too costly.
- Reverb tails or whole rooms in PSRAM: measurable recursive-access penalty.
- GDMA/2D-DMA: adds copies/synchronization and cannot remove feedback
  dependencies.
- Grouping four full-width LPFs or two pairs: physically measured 2-4 us
  slower; GCC already scheduled scalar 32x32 multiplies well.
- Xai/PIE 16x16 SIMD or a 16-bit audio path: wrong width and unacceptable
  scaling/quality risk.
- Skipping silent rooms: useful diagnostic, not worst-case capacity.
- Deferring sequencer events by one block: changes musical timing.
- Returning to 64-frame descriptors: insufficient jitter capacity.
