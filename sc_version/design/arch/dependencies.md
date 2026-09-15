# Dependency selection

Status: authoritative dependency policy
Owner: build and application architecture
Applies to: `sc_version`
Last verified: 2026-09-15

Use an established external package when it replaces substantial non-domain
code and is actively maintained on every required platform. Assess adoption,
maintenance, licence, security and supported Python/platform versions; do not
trade a small local implementation for an obscure dependency.

Requirements files and `qt_frontend/packaging/python_dependency_groups.json`
are the authority. Current direct runtime dependencies cover PySide6,
fastjsonschema, python-osc and Zeroconf; source audio tools add NumPy and
SoundFile, and builds add PyInstaller. Commit-pinned sample snapshots use the
Python standard-library HTTPS and tar readers. A new dependency requires a
dated assessment, boundary tests, notices and package audit updates.
