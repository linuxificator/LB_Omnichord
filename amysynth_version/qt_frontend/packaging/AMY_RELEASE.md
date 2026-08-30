# AMY release input contract

Every LB Omnichord build uses AMY from the fork release branch
`releases/amy_omnichord_R20260831T001253` at exact commit
`00157856312de89f6dc293f90efb1889f0ceff23`.

The branch name records the maintained AMY-for-Omnichord line. The commit SHA
is the immutable build input: CI checks that the commit belongs to the declared
branch, checks it out by SHA, verifies `HEAD`, and writes both values into every
published LB Omnichord release note. Branch movement therefore cannot make an
old LB release irreproducible.

This pin is shared by native AMY regression tests, Linux and Raspberry Pi
AppImages, the macOS application, the Windows named-pipe service, the Android
Oboe AAR and the Android audio analyzer. Every hosted service uses the
Gamma9001 profile: Python builds set `AMY_PCM_BANK=gamma9001`, while Windows
and Android generate, link and register the same full PCM blob. Updating one
hosted platform alone is a contract failure.

The serial ESP32-P4 firmware is a separate hardware target and remains pinned
to the preceding tiny-bank release until it has an explicit flash/storage
profile for the Gamma blob. It must not be described as compatible with this
Gamma configuration.

## Updating AMY

1. Fetch `shorepine/amy` and fast-forward the fork's `main` to shorepine
   `main`; never merge feature work into fork `main`.
2. Start the next `releases/amy_omnichord_R<YYYYMMDD>T<HHMMSS>` branch from the
   preceding Omnichord release branch.
3. Incorporate the verified new shorepine changes and required LB integration
   work. Include the fork's internal `work/codex_info` handoff material only on
   the internal release branch, never on a branch offered upstream.
4. Run the AMY native and platform tests, then update the branch and SHA
   together in both LB workflow files, this contract, and the platform docs.
5. Run all LB regression and package gates. Publication remains blocked until
   every supported platform succeeds.

Platform-specific packaging and service code must stay outside the Qt
application. A single startup preamble may discover an unavoidable private
platform endpoint, such as Android's app-private `amy.sock`; it must not add
platform-specific synthesis or UI behavior.
