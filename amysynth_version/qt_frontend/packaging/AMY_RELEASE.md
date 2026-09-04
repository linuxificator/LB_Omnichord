# AMY release input contract

Status: authoritative external-component release contract
Owner: AMY fork integration and five-platform packaging
Applies to: native tests, desktop services, Android Oboe and ESP32-P4
Last verified: 2026-09-04

Every LB Omnichord build uses AMY from the fork release branch
`releases/amy_omnichord_R20260904T194050` at exact commit
`f710148089b7e58f6c101be2b190e58f79521aa6`.

The machine authority for those values is `release_inputs.json` beside this
document. Workflows and the ESP32 preparation script load it through
`release_inputs.py`; they must not repeat a fallback branch or commit literal.
The same manifest also names the exact five release packages and reviewed
desktop Python constraint inputs.

The branch name records the maintained AMY-for-Omnichord line. The commit SHA
is the immutable build input: CI checks that the commit belongs to the declared
branch, checks it out by SHA, verifies `HEAD`, and writes both values into every
published LB Omnichord release note. Branch movement therefore cannot make an
old LB release irreproducible.

This pin is shared by native AMY regression tests, Linux and Raspberry Pi
AppImages, the macOS application, the Windows named-pipe service, the Android
Oboe AAR and the Android audio analyzer. Updating one platform alone is a
contract failure.

Native regressions build `AMY_PCM_BANK=gamma9001`, matching the hosted release
packages. They require both the Gamma9001 registration and linked-data symbols,
and use the fork's `c_amy.live(audio=False, ...)` mode. This preserves the
production sizing configuration while making the test bridge the only AMY
clock and sample consumer; a background miniaudio callback cannot steal the
block whose peak is being asserted.

The ESP32-P4 image remains a separately declared Tiny-bank target until its
flash/storage profile can hold Gamma9001. That hardware exception must never be
used to silently select Tiny for Linux, Raspberry Pi, macOS, Windows or Android.

## Updating AMY

1. Fetch `shorepine/amy` and fast-forward the fork's `main` to shorepine
   `main`; never merge feature work into fork `main`.
2. Complete and test generic work on its clean upstream-directed branch, with
   no downstream project material on that branch.
3. Start `releases/amy_omnichord_R<YYYYMMDD>T<HHMMSS>` from that clean commit,
   then layer only the required socket, Android, PCM-bank and capacity profile.
   Never merge abandoned experiments or internal handoff material into the
   upstream-directed branch.
4. Run the AMY native and platform tests, then update the branch and SHA
   together in `release_inputs.json`, this contract, and the platform docs.
   The workflow/static tests reject reintroducing copies of the active pin.
5. Run all LB regression and package gates. Publication remains blocked until
   every supported platform succeeds.

Platform-specific packaging and service code must stay outside the Qt
application. A single startup preamble may discover an unavoidable private
platform endpoint, such as Android's app-private `amy.sock`; it must not add
platform-specific synthesis or UI behavior.
