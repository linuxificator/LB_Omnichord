# Dependency selection

Status: authoritative dependency policy
Owner: build and application architecture
Last verified: 2026-09-08

Use an established external Python package when it removes substantial,
non-domain implementation and is already maintained across every required
platform. Do not recreate a mature protocol, validation or packaging library.

Adoption requires evidence of active maintenance, broad use, suitable licence,
security posture, Python-version support and Linux/Raspberry Pi/macOS/Windows/
Android availability. A small or dormant project is not acceptable merely
because it saves initial code.

Direct runtime dependencies are declared in requirements and the exact release
inputs are recorded in `../../qt_frontend/packaging/release_inputs.json`.
Current deliberate choices include pyserial, fastjsonschema, python-osc,
zeroconf/ifaddr, PySide6 and PyInstaller. Requirements/configuration remain the
authority; this document does not duplicate their versions.

Every new dependency needs a dated assessment, tests at its owned boundary and
an update to notices, release evidence and package-size policy where relevant.

