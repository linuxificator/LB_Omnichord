# Cross-platform packaging

Status: authoritative packaging summary
Owner: release architecture
Last verified: 2026-09-08

The release matrix produces Linux x86_64 and Raspberry Pi aarch64 AppImages,
macOS arm64 DMG, native Windows x86_64 zip, Android arm64 APK and the dual-
profile P4 firmware ZIP. Application packages preserve the frontend/AMY
process boundary: Unix socket, Windows named pipe, Android private socket or
ESP32 serial.

PySide6/Qt accounts for most desktop/mobile package size; it is not application
source bloat. Packaging uses an explicit Qt/QML allowlist, audited package-size
ceilings and exact release inputs. Build evidence, SBOM and Sigstore bundles
are separate from runtime payloads. Production platform signing remains a
decision-gated task.

`main` releases are serialized and never cancelled. A post-release screenshot
commit contains only README/image changes and the explicit `skip-rebuild`
marker. Partial workflows may diagnose a platform fix, but the final release
must always complete the full matrix.

