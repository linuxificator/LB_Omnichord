# Design Principles

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
