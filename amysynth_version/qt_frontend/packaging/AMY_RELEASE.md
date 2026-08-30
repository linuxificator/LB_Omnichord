# AMY release input contract

Every LB Omnichord build uses AMY from the fork release branch
`releases/amy_omnichord_R20260830T220021` at exact commit
`32f3a68861a68979ceb715cf32e0322e8614365b`.

The branch name records the maintained AMY-for-Omnichord line. The commit SHA
is the immutable build input: CI checks that the commit belongs to the declared
branch, checks it out by SHA, verifies `HEAD`, and writes both values into every
published LB Omnichord release note. Branch movement therefore cannot make an
old LB release irreproducible.

This pin is shared by native AMY regression tests, Linux and Raspberry Pi
AppImages, the macOS application, the Windows named-pipe service, the Android
Oboe AAR and the Android audio analyzer. Updating one platform alone is a
contract failure.

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
