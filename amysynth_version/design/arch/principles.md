# Design Principles

Status: authoritative baseline contract
Owner: application architecture
Applies to: active `amysynth_version` implementation
Last verified: 2026-09-03

## Wire protocol boundary

The Qt application only produces AMY wire commands. It must never depend on whether AMY runs locally or on ESP32.

The transport layer may be changed:

Qt -> application logic -> AMY wire commands -> transport -> AMY

Local AMY execution and ESP32 serial execution must consume the same command stream.

## Separation of responsibilities

OMNI performance and MIDI player functionality are separate subsystems. Shared behavior is limited to explicitly defined interfaces such as tuning and current chord preview.

## No hidden state changes

Changing screens must not change musical state. UI navigation and audio state are independent.

## Hardware portability

Moving from host AMY to ESP32 AMY must not change musical behavior.

Desktop portability follows the same rule. Linux, macOS and native Windows may
use different local socket framing and native audio backends, but the Qt
frontend remains the same wire-only client. A platform-specific AMY Python
extension is an implementation choice for a service, never a frontend
dependency.

## Simplicity

New abstractions are added only when they reduce coupling or prevent regressions.

Do not "headbang": do not keep extending and repairing a difficult custom
mechanism when its complexity is evidence that the design direction is wrong.
Stop, restate the actual requirement, and re-evaluate the operating system,
framework and library mechanisms already intended to solve it. A custom
protocol, daemon or state machine needs evidence that the standard mechanism
cannot satisfy the requirement; sunk implementation effort is not evidence.

## Native platform mechanisms first

For Linux integration, first identify and use the mechanism already owned by
the Linux kernel or the relevant standard subsystem: for example PAM resource
limits, systemd unit policy, PipeWire configuration, udev, D-Bus or the normal
freedesktop interface. Assume a general systems problem has an established
solution until investigation shows otherwise. Preserve that solution's normal
authority and lifecycle instead of copying it into application code. Keep
platform-specific composition in adapters and packaging so the portable
application remains identical on every platform.

## Extend existing AMY concepts first

AMY-side integration work must reuse existing AMY concepts, data structures,
APIs and render paths wherever they can express the required behavior. A new
parallel subsystem is justified only when the existing design demonstrably
cannot provide the required semantics or realtime performance.

In particular, routing and effect inputs should be expressed as variants of
the existing bus summation model. Shared reverb inputs use one reusable
weighted subset-mix operation; they must not grow a separate application-
specific mixer architecture. Platform acceleration may replace the mix
kernel, but not its portable semantics.

## Code-quality non-regression

Bug fixes must preserve the architectural and code-quality improvements already
recorded in this design tree. In particular, a platform-specific symptom does
not justify platform-specific application behavior when the affected framework
primitive is shared. Reproduce the behavior at the narrowest shared boundary,
add a behavioral regression test, and fix that shared boundary without adding
duplicate input policy, cross-layer state ownership or source-text assertions.

Production application modules must not contain integration/package test
drivers, synthetic input generators, expected test outcomes or test-only
status protocols. Unit tests may directly exercise narrow objects, but an
integration or package sender/controller runs in a separate process and uses a
normal production boundary. Cross-platform tests apply one portable semantic
contract everywhere and isolate unavoidable native setup and capability
expectations in named platform test adapters. The complete rules are owned by
[`test_processes.md`](test_processes.md).
