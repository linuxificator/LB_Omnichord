# LB Omnichord - Codex Project Context

## Purpose of this document

This document is the authoritative context for coding agents working on LB Omnichord. It is not a suggestion list. Architectural decisions in this file must be preserved unless the user explicitly requests a redesign.

## Absolute rules

1. Do not replace working architecture with a different architecture to solve a local bug.
2. Do not embed AMY into the UI application.
3. Do not import the AMY Python library into the Qt frontend as a shortcut.
4. AMY is a separate synthesizer component. The interface boundary is the AMY wire protocol.
5. Do not add service lifecycle control from UI clients. The Godot/Android reference proves the correct model: separate processes communicating through the protocol boundary.
6. When a bug appears, find the failing boundary first: UI event, command generation, transport, AMY parsing, rendering, audio output.

## Project evolution

The project started as a Sonic Pi based Omnichord. Sonic Pi code remains historical and must not be modified unless explicitly requested.

The active direction is the AMY based implementation:

- Qt frontend for user interaction.
- AMY synthesizer as independent engine.
- AMY wire messages as transport format.
- Socket or serial transport between components.

## AMY architecture

AMY is capable of being embedded, but embedding is not the chosen architecture for LB Omnichord.

Chosen architecture:

```
Qt UI / Android / Godot
        |
        | AMY wire protocol
        | socket or serial transport
        v
AMY service
        |
        v
Audio output
```

Do not change this to:

```
Qt Python application
        |
        import amy
        |
        audio engine
```

The AMY repository documents wire messages specifically for communication between separate programs that are not linked together.

## Android/Godot reference

The Android/Godot proof of concept is an architectural reference.

Rules:

- The AMY service is independent.
- The client does not start or stop the service.
- Communication happens through the existing interface.
- Debug communication problems at the protocol boundary.

Never add AmyService.start(), stop logic, or equivalent coupling inside the client application.

## UI direction

Active UI:

- Qt based frontend.
- Touch capable.
- Mouse support for desktop testing.
- Omnichord interaction model:
  - chord selection area
  - strum surface
  - rhythm controls
  - instrument/patch selection

Important existing behavior:

- Strum input must generate AMY commands.
- If strum fails, verify UI event generation before touching AMY.
- Debug logs of generated AMY wire commands are preferred.

Do not add meaningless labels such as PATCH suffixes to user visible instrument names.

## Hardware direction

Target platform:

- ESP32-P4 Pico M.
- Dual HP cores for AMY.
- LP core may receive UART protocol messages.
- 32 MB PSRAM.

Audio baseline:

- 48 kHz sample rate.
- 64 sample AMY render blocks.
- Proven low latency configuration uses I2S DMA 2x32.
- Do not add delays into the render path.

PCM5102A wiring:

- GPIO16 -> LRCK
- GPIO17 -> DIN
- GPIO18 -> BCK
- SCK -> GND

## SD/sample streaming direction

Sample streaming is optimized for predictable latency.

Design:

- Metadata filesystem may exist at startup.
- Runtime streaming uses raw fixed block reads.
- First chunk latency has priority.
- Approximately 16 kB initial fetch unit.
- Background reads must not block a new first-chunk request.

## Engineering style

Always:

- verify paths and APIs;
- distinguish facts from hypotheses;
- preserve working code;
- test the actual boundary that fails;
- avoid unnecessary abstractions.

If information conflicts, use CODEX_UNCERTAINTIES.md and do not invent a solution.
