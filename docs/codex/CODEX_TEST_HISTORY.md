# LB Omnichord - Test history and failure archive

This file is a historical engineering log for Codex. Its purpose is to prevent repeating failed approaches and to preserve why fixes were chosen.

## Rule for future debugging

Do not jump to architecture changes. Find the failing boundary:

UI input -> UI state -> AMY wire command -> transport -> AMY parser -> render -> audio output.

A working boundary must not be replaced while debugging another boundary.

# Architecture tests

## Android / Godot proof of concept

Purpose:
Validate that AMY can be used as an independent service.

Expected architecture:

Client process
    |
    | socket / wire protocol
    |
AMY service

Important failure:
The client attempted to manage AMY service lifetime.

Fix:
Restore process separation. The client sends commands only.

Lesson:
Never add start/stop coupling to clients.

# Qt frontend tests

## Chord command generation

Observed:
Chord interaction generated expected AMY commands.

Conclusion:
The AMY path was functioning.

## Strum input failure

Symptom:

- Chords played correctly.
- Touch and mouse interaction with strum surface produced no sound.

Wrong direction avoided:
Changing AMY architecture.

Investigation:

- Added AMY debug command logging.
- Compared chord and strum paths.
- Determined that the failure was before synthesis.

Resolution approach:
Fix the UI event path.

Lesson:
A missing UI event is not a synth problem.

## Instrument naming issue

Symptom:
User-visible names contained technical PATCH suffixes.

Cause:
Internal AMY patch terminology leaked into the UI.

Fix:
Keep implementation details out of user-facing text.

# AMY / ESP32-P4 tests

## Audio latency baseline

Validated:

- 48 kHz audio.
- 64 sample render blocks.
- I2S DMA 2x32.
- No scheduler delay in render loop.

Problem:
Periodic distortion occurred when scheduling delays were introduced.

Fix:
Remove vTaskDelay from the audio render path.

Measured result:
The 64 sample configuration became stable with very low latency.

## Heavy patch testing

Observation:
Effects-heavy patches can require different DMA settings.

Rule:
Do measurements before changing the audio pipeline.

# SD/sample streaming design tests

Validated design principles:

- Runtime sample access should avoid filesystem overhead.
- Fixed block reads are preferred.
- First chunk latency is more important than maximum throughput.

Failure mode avoided:
Long background reads delaying the first part of a new sample.

# Historical architecture mistakes to avoid

## Embedding AMY into GUI

Attempt:
Use Python AMY bindings directly from the GUI.

Why rejected:

- Breaks process separation.
- Couples UI and audio engine.
- Makes Android/Godot reference architecture invalid.

Correct design:
AMY remains a separate wire-protocol endpoint.

## Replacing components to solve local bugs

Pattern observed:
A local issue led to proposals for new frameworks or different ownership models.

Correct approach:
Instrument the failing boundary first.

# Remaining tests to document when performed

- Complete Qt visual regression test.
- Patch browser behavior test.
- Rhythm interaction test.
- MIDI input test.
- ESP32-P4 UART transport test.
- SD-card benchmark results.
