# AMY Synth Omnichord Design Documentation

This directory is the design contract for the AMY Synth Omnichord implementation.

The documents define:

- architecture boundaries
- GUI behavior
- MIDI behavior
- AMY wire protocol usage
- preset ownership
- tuning rules
- testable use cases

Core rules:

- The Qt application produces AMY wire commands only.
- AMY transport may be local development or ESP32-P4 serial without changing behavior.
- OMNI and MIDI remain separate subsystems.
- Shared state is explicit; tuning is shared only when coupling is enabled.

When implementation and design differ, the difference must be documented before changing behavior.
