# Android platform contract

Status: authoritative platform summary

The Android arm64 package keeps the common Qt/Python frontend separate from the
native Gamma9001 AMY/Oboe service through an app-private socket. Android
lifecycle, audio and packaging code stays in adapters or the native wrapper;
the frontend emits the same AMY wire commands as every other platform.

Executable build details are in `../../../qt_frontend/INSTALL.md` and the
Android packaging sources below `../../../qt_frontend/packaging/android/`.
