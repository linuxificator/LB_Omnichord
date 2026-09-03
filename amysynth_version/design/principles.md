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

## Code-quality non-regression

Bug fixes must preserve the architectural and code-quality improvements already
recorded in this design tree. In particular, a platform-specific symptom does
not justify platform-specific application behavior when the affected framework
primitive is shared. Reproduce the behavior at the narrowest shared boundary,
add a behavioral regression test, and fix that shared boundary without adding
duplicate input policy, cross-layer state ownership or source-text assertions.
