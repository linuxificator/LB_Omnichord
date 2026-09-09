# Raspberry Pi realtime architecture review

Status: current focused review
Owner: platform integration and application architecture
Last verified: 2026-09-09

## Scope

This review covers only the optional dedicated-Pi realtime setup introduced on
`feature/rpi-realtime-setup`: startup inspection and warning, source/AppImage
wrapper integration, host installer, release asset and its tests. It does not
change AMY, musical behavior, wire commands or serial transport.

## Result

No actionable architecture or code-quality drift remains in this scope. The
portable frontend still knows only immutable runtime overrides and warning
text. Linux scheduler operations live in one Pi adapter; privileged host setup
lives in packaging tooling; AMY remains a separate exact wrapper-owned child.

The final design uses existing authorities:

- PAM grants the selected login user `RLIMIT_RTPRIO=80`;
- per-user systemd unit drop-ins grant the same limit to PipeWire;
- PipeWire `module-rt` and `thread.affinity` own both `data-loop.0` threads;
- the existing launcher confines itself and its exact AMY child, identifies
  the active child worker once, and applies CPU3/FIFO70 only to that thread;
- the frontend reads the resulting AMY, frontend and PipeWire policies back;
- boot isolation and the performance governor remain reversible host policy.

There is no watcher daemon, registration socket, AMY name matching, repeated
process scan, custom lifecycle token or test-only production endpoint.

## Findings resolved during the review

1. The first design introduced a privileged watcher and private registration
   protocol. That was unnecessary complexity and was removed.
2. PipeWire was initially mutated by the wrapper. Its native systemd and
   `module-rt` configuration now own the policy instead.
3. `pipewire-pulse` resolves to the `pipewire` binary. Identity now comes from
   exact systemd unit `MainPID`, then executable, main-thread name and the one
   `data-loop.0` are validated.
4. `SCHED_RESET_ON_FORK` is preserved when an unprivileged owner changes its
   own child policy; readback compares the base scheduler separately.
5. Serial mode no longer reports missing host-AMY realtime state.
6. Unix-only modules are imported lazily, so Windows/macOS package imports are
   unaffected.
7. The boot-profile writer no longer creates a new rollback snapshot for an
   unchanged cmdline and preserves the original file mode.
8. The release-generated setup asset is syntax-checked, executes `--help`,
   verifies every embedded payload, rejects corruption and receives a separate
   signed build-provenance attestation.
9. The AppImage wrapper contract is tested behaviorally with a real child
   object/PID flow rather than by matching its source text.
10. The QML warning dialog has explicit geometry. Physical startup and a 120 Hz
    input run produced no binding-loop diagnostics.
11. Packaged host-tool execution no longer inherits AppImage/PyInstaller's
    private `LD_LIBRARY_PATH` or `LD_PRELOAD`. The adapter invokes canonical
    `/usr/bin/systemctl` while preserving the actual user-session environment.

## Test evidence

- Unit and quality suites pass locally.
- Generated release installer passes `bash -n`, payload-integrity validation
  and its executable `--help` contract.
- A clean Pi 4 reboot produced PAM/user and PipeWire limits of 80, PipeWire at
  CPU2/FIFO80, pipewire-pulse at CPU2/FIFO75 and no watcher service. The
  drop-ins live only in the selected user's normal configuration tree.
- Normal `run_local.sh` selected its exact AMY child callback at CPU3/FIFO70,
  kept other service/frontend work on CPUs 0-1 and showed no startup warning.
- A 20-second external 120 Hz uinput sweep retained all policies, reported no
  overload/dropout/binding-loop messages and ended with `throttled=0x0`.
- Physical serial-mode startup created no host AMY process and no false
  realtime warning.
- Complete GitHub run `34375905899` passed Linux x86_64, Raspberry Pi aarch64,
  Windows, macOS, both Android architectures and emulator, and both ESP32-P4
  board variants. Its checksum-verified Pi AppImage `R20260909161844` passed a
  physical post-reboot startup and an external 20-second 120 Hz touch sweep
  with no warning, overload, dropout, binding loop or throttling.

Every release remains gated by the normal unit/quality matrix. The aarch64
package job also exercises package startup and the shared 120 Hz visual-cost
contract; the final artifact should still receive the normal physical package
acceptance after its first release.

## Remaining non-blocking evidence

- Repeat the physical measurements on a Pi 5 when hardware is available.
- If a future AMY backend recreates its callback thread without restarting its
  service process, characterize that lifecycle before adding any reapplication
  mechanism. Current miniaudio service behavior keeps the callback stable, so
  a watcher is not justified.

## Method rule

The removed watcher is the concrete example behind the "headbanging" rule in
`principles.md`: repeated repair of complexity introduced by a custom design is
a signal to stop and return to existing platform mechanisms. On other systems,
first use their native equivalent; only if none exists should the Linux
ownership/lifecycle model be adapted behind a platform module.
