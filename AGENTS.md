# LB Omnichord — Codex Agent Instructions

This file contains project-wide context and constraints for automated coding agents working on LB Omnichord.

## Primary engineering rule

Prefer the simplest architecture with clear separation of responsibilities. Do not introduce new abstraction layers, process coupling, frameworks, or architectural changes casually. Before adding complexity, determine whether it actually reduces total system complexity. Preserve the existing architecture unless a change is explicitly required.

Do not silently reinterpret an implementation task as an architecture redesign.

## Repository direction

- The active synthesizer implementation uses **AMY / amysynth**.
- The old **Sonic Pi implementation is retained as historical code and must not be modified** unless explicitly requested.
- Keep AMY-related code, instrument definitions, GUI components, tests, and platform-specific code logically separated.
- When moving files, update and verify all paths rather than duplicating files as a workaround.

## Current application architecture

The Omnichord UI and the AMY synthesizer service are separate components/processes where applicable and communicate through the AMY wire protocol over a socket or serial transport.

A particularly important rule for the Android/Godot proof of concept:

- The AMY service and Godot application are **separate processes**.
- Do not try to control service lifetime by adding calls such as `AmyService.start()` / stop logic inside the Godot application unless explicitly requested.
- The intended interface between the processes is the socket/wire-protocol boundary.
- Preserve this process separation when debugging communication problems.

There is also an existing AMY hello-world Android application that successfully plays through the service/socket path; use existing working paths as references rather than inventing a new architecture.

## ESP32-P4 AMY target

Primary MCU target: **ESP32-P4 Pico M**.

Relevant hardware characteristics:

- ESP32-P4 dual HP cores plus LP core.
- 32 MB PSRAM.
- AMY synthesis is intended to use the HP cores.
- The LP core is a candidate for low-overhead UART reception of AMY wire-protocol messages.

### Audio baseline

The proven low-latency baseline is:

- Sample rate: **48 kHz**.
- AMY render block: **64 samples**.
- I2S DMA configuration proven clean at this setting: **2 × 32 frames**.
- Removing `vTaskDelay()` from the render loop was essential; reintroducing scheduler delays into the audio render path can cause periodic distortion.
- Measured GPIO-to-audio latency with the working 64-sample setup is below approximately 2 ms.

Do not casually increase the block size or add blocking/delay behavior to the audio loop. If a heavier patch requires a different DMA configuration, measure the consequences rather than assuming it is harmless.

### External PCM5102A DAC

Confirmed working wiring on the ESP32-P4 Pico M:

- GPIO16 -> PCM5102A LRCK/LCK
- GPIO17 -> PCM5102A DIN
- GPIO18 -> PCM5102A BCK
- PCM5102A SCK -> GND

Do not change these assignments without an explicit hardware-design reason.

## AMY build notes

Development host convention used during ESP32-P4 work:

- ESP-IDF: `/home/jeroen/esp/esp-idf`
- AMY test project: `/home/jeroen/projects/amy-p4-test`

A previously required AMY ESP-IDF build correction was moving `esp_driver_uart` from `PRIV_REQUIRES` to `REQUIRES` in `components/amy/CMakeLists.txt`, because `amy_midi.h` includes `driver/uart.h`.

When fixing ESP-IDF build problems, prefer correct component dependency declarations over include-path hacks.

## SD-card / sample streaming design

The intended sample-streaming architecture is optimized for deterministic low initial latency rather than filesystem convenience.

- Runtime sample storage is primarily raw SD-card blocks.
- A small normal filesystem area may contain startup JSON/descriptive metadata.
- Runtime streaming should avoid ordinary filesystem traversal/access where possible.
- Samples are 48 kHz raw sample data, organized into fixed-length/zero-padded segments as appropriate.
- The critical cache unit / initial fetch is approximately **16 kB**.
- Always prioritize the **first chunk of a newly requested sample**, except where an already-playing sample has a hard playback deadline.
- Background continuation reads must not unnecessarily block new first-chunk requests.
- SD performance work should distinguish command/setup latency from sustained transfer bandwidth.

Negotiation/testing should use the card's actual capabilities rather than blindly assuming high-speed operation. Relevant SD commands include CMD8, ACMD41, CMD9 and CMD6.

The design has considered 100 MHz and 200 MHz SDMMC operation where hardware/card support allows it, but compatibility must be detected/verified.

### PSRAM allocation concept

A working design budget discussed for the 32 MB PSRAM is approximately:

- 16 MB: delay / chorus / reverb storage
- 12 MB: first-chunk sample cache
- 4 MB: cache/index metadata and related bulk structures

Keep latency-critical AMY computation in internal SRAM where practical; use PSRAM primarily for bulk storage such as samples and long effect buffers.

## Inter-processor / control communication

Earlier two-P4 designs considered an 8-bit unidirectional parallel data bus plus simple serial command/control. The design preference is for unidirectional interfaces where they materially simplify synchronization.

Do not add bidirectional buses or request/response coupling merely for architectural symmetry. Add reverse communication only when there is a concrete requirement.

For ESP32-P4 UART reception, keep in mind that the LP core may be useful for receiving AMY wire messages. A possible future hardware mechanism is routing an HP UART RTS or software-driven GPIO indication through the GPIO matrix to an LP-accessible GPIO; the abstract HP UART interrupt itself is not directly routed as a GPIO signal. Treat this as a design option requiring verification against the current ESP-IDF/P4 hardware documentation, not as already-implemented behavior.

## UI / Omnichord behavior

The active desktop/Raspberry Pi UI direction is Qt + AMY rather than Sonic Pi.

Important behavioral concepts include:

- chord buttons / chord activity
- strum interaction supporting mouse and touch
- rhythm/drum functionality
- instrument/patch selection
- AMY wire-command generation

For input bugs, verify the event path and emitted AMY commands before modifying synthesis architecture. Debug logging of generated AMY commands is preferred when it can distinguish UI-event failure from transport/synth failure.

Do not add meaningless display suffixes such as `PATCH` to instrument names merely because the underlying AMY object is a patch.

## Debugging and modification policy

When something fails:

1. Reproduce or inspect the existing failure path.
2. Identify which boundary fails: UI event, command generation, socket/serial transport, AMY parsing, rendering, DMA/I2S, etc.
3. Use logging or a minimal test at that boundary.
4. Fix the failing layer without redesigning unrelated layers.
5. Build/test after the change.

Do not respond to a localized bug by replacing the working transport, changing process ownership, or introducing a new framework.

When a known working reference implementation exists in the repository, compare against it first.

## Precision requirements

- Verify commands, paths, GPIO assignments, API signatures and ESP-IDF capabilities before changing code around them.
- Clearly distinguish verified behavior from hypotheses.
- Prefer exact technical explanations over generic troubleshooting lists.
- Preserve existing working code unless the requested task requires changing it.
- Do not claim a build, emulator test, hardware test, or runtime test succeeded unless it was actually executed and its result observed.

## Scope

These are project defaults, not permission to modify every subsystem. The current user request and the checked-out branch/task always determine the immediate scope. If a task conflicts with a design constraint above, call out the conflict rather than silently changing the architecture.

## Codex session handoff

If `CODEX_HANDOFF.md` exists at the repository root, read it before resuming an
unfinished task. It records operational state and commands, but does not
override this file or the current user's request.
