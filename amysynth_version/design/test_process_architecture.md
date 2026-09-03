# Test process and cross-platform architecture

Status: authoritative architecture and testing contract
Owner: application architecture and release acceptance
Applies to: unit, integration, package and five-platform release tests
Last verified: 2026-09-03

## Purpose

Tests must prove the architecture users run without turning the production
application into its own test harness. A test is weaker when its input sender,
test decisions and assertions execute inside the system under test: it can
bypass process, operating-system, transport, packaging and lifecycle failures.
It also makes production code carry behavior that exists only for CI.

## Production/test boundary

Production application modules and shipped runtime packages must not contain:

- integration/package test drivers or assertion logic;
- synthetic MIDI, OSC, pointer or musical input generation used only by tests;
- expected test values, checkpoint sequences or pass/fail decisions;
- a test-only listener, command-line mode, marker file or status-file protocol;
- environment variables whose only consumer is an integration/package test;
- branches that alter normal application behavior solely because CI is active.

Normal production observability is allowed when it is useful to users and
operators independently of tests: bounded logs, capability/lifecycle state,
health reporting and documented diagnostics. A test may observe those public
surfaces. It may not add a hidden product endpoint merely to make an assertion
easy.

Unit tests are the exception at the object boundary. They may instantiate a
class, supply a fake port, call a public or deliberately narrow internal
method, and inspect returned state in the same process. That does not authorize
shipping the fake, injector or test orchestration in `code/`.

## Process separation for integration and package tests

For an integration or package input test, the controller/sender and the
Omnichord run as separate operating-system processes. The sender uses the same
external boundary as a real peer:

- OSC uses a real UDP datagram sent by a process other than the Omnichord;
- raw MIDI uses a virtual/native MIDI endpoint owned and written by another
  process;
- AMY commands cross the normal serial, Unix socket or named-pipe boundary;
- UI automation uses an external automation/accessibility boundary when the
  target platform provides one.

The test controller owns setup, readiness, timeout, assertions and teardown.
The Omnichord starts through its ordinary production entry point with ordinary
configuration. A receiver that sends its own stimulus, calls an `inject*`
slot, asserts its own model or exits because a test passed is not an
integration proof, even if one internal hop uses a real kernel socket.

When physical hardware cannot exist on hosted CI, use the closest native
virtual endpoint and label the evidence precisely. Loopback proves a network
stack and process boundary, not a firewall, external host or physical cable.
A parser pipe proves portable MIDI parsing, not CoreMIDI, WinMM or Android MIDI.
An unimplemented platform capability must be tested and reported as
unavailable; simulation must never be relabelled as physical support.

## One semantic contract on every platform

Supported behavior has one platform-neutral test contract. Every target runs
the same scenario names, stimulus meaning, observable outcomes and failure
rules. Platform-specific setup may differ, but it must not silently reduce the
assertions. A release summary must make unsupported or physically unverified
capabilities visible rather than calling unequal evidence equivalent.

Examples:

- every platform receiving OSC proves external-process UDP, message identity,
  controller-model delivery and clean shutdown;
- every platform selects only its relevant MIDI capability data;
- a platform with a native MIDI adapter proves external-process Note, CC,
  button/Pitch Bend input through that adapter;
- a platform without such an adapter proves explicit unavailable status and
  does not run a simulated event test under the native-adapter scenario name.

## Generic versus platform-specific tests

Portable and native concerns must be separate in both source layout and CI:

- generic contract tests contain no OS-name branches and run unchanged on all
  supported targets;
- platform test adapters own native endpoint creation, permissions, launch
  syntax and capability expectations;
- shared assertions and scenario definitions are imported by platform tests
  rather than copied into workflow scripts;
- platform tests may skip only through explicit capability data with a visible
  reason; broad exception handling or runner-name conditionals are not skips;
- package tests consume the final artifact and do not import its production
  classes into the controller process as a substitute for launching it.

Recommended layout:

```text
tests/
  contracts/          # platform-neutral scenario definitions/assertions
  integration/        # multi-process source/runtime tests
  platform/
    linux/
    macos/
    windows/
    android/
  support/            # test-only senders, probes and orchestration
```

The exact directories may evolve, but ownership must remain unambiguous.

## Release acceptance

Every release-platform job records which generic contracts and which native
adapter contracts it ran. The final gate rejects missing scenarios, unexpected
skips and reduced assertions. Test-only tools remain build inputs or CI
artifacts; they are not bundled into the user package.

Physical validation remains a separate evidence class. Hosted success may not
claim physical MIDI, touch, audio-route, firewall or latency behavior unless
that hardware path was actually exercised.

All package jobs feed their artifacts to
`qt_frontend/tests/support/package_evidence.py`. This is the sole owner of the
cross-platform scenario identifiers and pass/fail rules. It writes one JSON
manifest per artifact with distinct `regression`, `portable-integration`,
`package`, `package-integration` and, where present, `platform-native`
evidence classes. Shell, PowerShell and workflow files may prepare native
processes and collect files, but must not copy semantic checkpoint lists.

Package acceptance is compositional and labels each claim at its real
boundary:

- package audit proves shipped files, size policy and forbidden-runtime
  absence;
- QML scanner/prune evidence proves the reviewed QML module set;
- the portable input contract proves independent MIDI/OSC sender and receiver
  processes without claiming a native hardware adapter;
- normal screenshot capture proves that the final application artifact starts,
  loads QML, communicates with its separate AMY service and renders non-trivial
  frames;
- Android additionally uses external `adb input` and real Oboe capture;
- regression success supplies source-level gesture, state and native-capability
  contracts without embedding those test drivers in the product.

The repository screenshot mode is an explicitly supported production tool and
is allowed to stage deterministic display state inside the application. It is
not evidence of physical MIDI/OSC input and must never be reported as such.
