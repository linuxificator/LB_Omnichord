# LB Omnichord - Test history and failure archive

This document records known tests, failures, observations and fixes. It exists to prevent future agents from repeating unsuccessful approaches.

## Purpose

Before changing code, check whether the issue is already described here. Prefer reproducing the original failure boundary over redesigning components.

## Architecture validation tests

### Android/Godot AMY communication proof of concept

Goal:
- Verify that a client application can control AMY without embedding AMY.

Expected result:
- Android/Godot application and AMY service run as separate processes.
- Communication happens through the socket/wire protocol.

Failed approach:
- Trying to control AMY service lifetime from the client.

Resolution:
- Keep service ownership separate.

## Qt frontend tests

### Strum input test

Symptom:
- Chord buttons generated AMY commands.
- Strum interaction produced no sound.

Investigation:
- Added AMY command logging.
- Verified chord command generation.
- Determined that the failure was in the UI input path, not AMY synthesis.

Rule:
- Always check UI event generation before changing synth architecture.

### Instrument names

Symptom:
- Instrument names received meaningless PATCH suffixes.

Resolution:
- Remove implementation details from user-visible names.

## ESP32-P4 audio tests

### 48 kHz low latency audio

Validated configuration:
- AMY render block: 64 samples.
- I2S DMA: 2x32.
- No vTaskDelay in render path.

Observation:
- Removing scheduler delay was required to eliminate periodic distortion.

### Larger blocks / heavy patches

Observation:
- Complex patches with effects may require larger DMA buffers.
- Measure latency and underruns instead of assuming a change is harmless.

## SD sample streaming tests

Design assumptions tested:
- Fixed block reads.
- First chunk priority.
- Raw sample area separated from metadata filesystem.

Important lesson:
- Optimizing sustained throughput must not make first-note latency worse.

## General debugging procedure

1. Reproduce the issue.
2. Identify the failing boundary.
3. Add minimal logging or instrumentation.
4. Fix only the failing layer.
5. Re-test the original failure.

Never replace a working architecture because of a local defect.
