# Codex handover: reusable-sequence simplification audit

Status: original audit plus implemented realtime-publication follow-up
Audit date: 2026-09-04
AMY feature branch: `rework/sequencer_simplification`
Feature head: `fca1579591cb4301d0f0583cc5ae8d8d2cb531aa`
Comparison base: Shorepine `main` at
`0fb0a00b5a9f9443d7e1f85261cc7e70a0adb76b`

## Post-audit implementation update

The table and coverage snapshot below describe the original audited head. The
authorized realtime follow-up adds 288 lines and removes 46 relative to that
head (net +242), including focused generation/root-reset tests and public AMY
documentation. The clean feature head is now
`b6f559a55d67f2d1dc4509a3e59fabca4fbfbd70`; its total diff against the same
Shorepine base is +1,746/-139 (net +1,607).

Commits `2669c3ae`, `b2a88659`, `7c98ad2b` and `b6f559a5` now exercise and implement the
previously missing COW path: candidate construction occurs outside the shared
render lock, publication is a checked pointer swap, and render-side final
releases use deferred intrusive reclamation. The exact rationale, transition
from the old COW and ESP32-P4 validation boundary are recorded in
`CODEX_HANDOVER_REALTIME_SEQUENCE_PUBLICATION.md`.

## Purpose

This records the review requested before replacing Shorepine AMY PR 1151. It
measures how much code the simplified reusable-sequence model adds, assesses
architecture and test quality, identifies concrete regressions and answers how
much the intentional tagged-event semantic change would break.

The audit does not authorize pushing a replacement PR or modifying an AMY
branch. All Codex-only evidence remains here in LB Omnichord.

## Change size

Against the audited Shorepine main commit, the branch changes 26 files:

| Area | Added | Removed | Net |
| --- | ---: | ---: | ---: |
| Handwritten runtime | 634 | 32 | +602 |
| Tests | 445 | 36 | +409 |
| Documentation | 359 | 21 | +338 |
| Generated bindings | 64 | 50 | +14 |
| Build integration | 2 | 0 | +2 |
| Total | 1,504 | 139 | +1,365 |

`src/sequencer.c` is the main implementation change at +480/-22, net +458.
With equivalent host build flags, the feature executable measured 6,616 bytes
more `.text` and 32 bytes more `.bss`, 6,648 bytes total, approximately 0.55%
of that host executable.

The previous `rework/sequencer` group design added about 578 net handwritten
runtime lines. The simplified public API therefore did not make the C core
smaller: it is about 24 net lines larger. It did, however, remove a second
public namespace, revision and execution identifiers, a fourth ticks field,
and the separate append operation. Tests and documentation became roughly 327
and 332 net lines smaller respectively. The principal simplification is the
user model and integration surface, not raw C line count.

## Architecture assessment

Strong decisions worth preserving:

- the existing sequencer tag is also the reusable-sequence identity;
- definition lifetime and execution lifetime are separated internally without
  exposing both as public concepts;
- active executions retain immutable snapshots;
- multiple finite executions of one tag may overlap;
- execution count and event count are bounded by startup configuration;
- stored inactive definitions are not scanned each tick;
- stored events reuse normal AMY wire payloads rather than a parallel event
  representation;
- sequence controls run before ordinary events on the same tick;
- alignment and finite gating remain generic and keep phase inside AMY;
- no Omnichord role, fill or instrument policy is present in the AMY branch.

The design is more maintainable at its public boundary than the discarded
group API. Internally it remains a substantial addition to a compact sequencer,
and the memory/publication path needs more work before it can claim bounded
real-time behavior.

Small safe simplification candidates, to evaluate with tests rather than apply
mechanically:

- store definition pointers directly instead of wrapping each in a one-field
  `stored_sequence_slot_t`;
- centralize repeated tag/range/error validation;
- remove any diagnostic special case that exists only for the retired `HA`
  syntax and use the generic invalid-`H` path;
- make composition validation strict and explicit;
- ignore the generated C test executable in `.gitignore`.

These might remove tens of lines. Removing immutable overlap, phase-preserving
gate behavior or bounded executions merely to reduce line count is not an
architectural improvement: it transfers timing or note state back to callers.

## Verification performed

The audited feature branch passed:

- `make ctest`;
- `python3 tests/test_sequence_api.py`;
- `make check-c-api`;
- GCC `-fanalyzer` for `src/sequencer.c`;
- `git diff --check`.

Instrumented C-test coverage for `src/sequencer.c` was:

- lines: 81.84% of 446;
- branches executed: 92.09% of 278;
- branches taken at least once: 75.90%;
- calls: 75.00%.

That is useful breadth, not proof of complete behavior or real-time safety.
The original coverage run did not call the copy-on-write clone helpers. That
gap is now closed by explicit append-while-active and three-overlapping-
generation tests. A new instrumented coverage percentage has not been recorded
after the change, so retain the original percentages only as historical
evidence.

Missing or incomplete proof:

- allocation-failure injection throughout candidate construction;
- cyclic control graphs and deterministic same-tick behavior;
- whether a future aligned stop/gate affects executions started after the
  control command but before the boundary;
- executable JavaScript and Godot behavior tests for the new semantics;
- maximum-load and ESP32 timing measurements;
- out-of-memory and failed-publication recovery;
- an ABI transition note for the two added `amy_config_t` fields.

## Concrete correctness findings

### Existing AMY examples and tests

AMY's own `amy/examples.py` contains four tagged events which currently expect
immediate tagged scheduling. Under the new definition semantics they create
stopped definitions and never play until explicitly started.

`amy/test.py` contains five such calls across `TestSequencer`,
`TestSequencedSynthDrums` and `TestSequencerOsc`. In the local audio runner all
three cases rendered silence at -100 dB. Other golden-audio mismatches in that
run were environment/reference issues and are not evidence about this change;
these three exact tagged-sequence failures are.

The branch must migrate its own examples and tests before it can claim a
coherent intentional breaking change.

### Shorepine Tulip compatibility

Tulip's `AMYSequenceEvent.update()` assigns a stable tag and repeatedly sends
`ticks=(tick, period, tag)`, relying on another write to replace the preceding
scheduled event. `remove()` sends the historical empty tagged cancellation.
The wrapper is used by the Tulip drum machine and web example and may also be
used by stored user sketches.

There are two distinct compatibility effects:

1. If only replacement changes to cumulative append, Tulip's initial unique
   events still work, but every dynamic `update()` leaves the old event in the
   definition as well as adding the new one.
2. With the full current stopped-definition model, initial tagged events also
   do nothing until the caller explicitly starts their tags.

Migrating Tulip therefore requires more than adding one start call. A live
dynamic edit needs a defined stop/reset/append/start sequence and a decision
about phase preservation. The migration is bounded because Tulip pins AMY as
a submodule and can be updated with it, but it is a meaningful first-party
breaking change and needs coordinated tests and release notes.

### Python payload validation

The Python API accepts a message such as:

```python
amy.message(ticks=(0, 0, 1), sequence_control=(2, 1, 1), synth=3)
```

and emits both the sequence-control payload and `i3`. The control parser does
not consume the trailing synth field. `sequence_control` should be standalone,
or combined only with the scheduling ticks which wrap it. Silent acceptance of
ignored payload is harder to diagnose than a clear validation error.

### Stop and note ownership

A reusable sequence can contain arbitrary AMY operations, not only notes. A
generic stop therefore cannot infer an inverse operation for everything it has
dispatched. Current leaf stop cancels future event dispatch; it does not create
a note-off. If a stopped leaf contains a later note-off for a long note, that
note may remain sounding.

The useful ownership property is narrower: stopping a parent can prevent new
child launches while finite note-pair children already running continue to
their stored note-offs. Documentation must not broaden this into a claim that
every stop automatically cleans up all note state.

## Compatibility conclusion

The answer to “how much would cumulative tags break?” is not “nothing” and not
“everything.” The cumulative default alone breaks dynamic replacement in a
central first-party Tulip wrapper. The full stopped-definition model also
breaks AMY's existing tagged examples/tests and initial Tulip scheduling.

That impact is concrete and bounded enough to migrate deliberately. It is not,
by itself, an argument against the cumulative default Dan Ellis proposed. A
responsible transition should:

1. state that tagged-event semantics intentionally change;
2. migrate AMY's examples and audio tests in the same change;
3. prepare and verify a corresponding Tulip wrapper/drum-machine update;
4. document phase behavior for a live update;
5. include release/migration notes rather than calling the change backward
   compatible.

If preserving Tulip's useful live-update behavior requires the caller to track
AMY clock, active execution or pending note state, that is evidence that the
public model still needs adjustment. It should not be hidden in a wrapper.

## Review response draft

The concise substance for the PR discussion is:

> I checked this against both AMY itself and Shorepine's first-party Tulip
> code. There are two separate compatibility effects. Changing repeated tags
> from replacement to accumulation breaks Tulip's `AMYSequenceEvent.update()`,
> because it deliberately reuses a stable tag; old and new events would both
> remain. The full stopped-definition model is a wider change: AMY's current
> tagged examples/tests and Tulip's initial scheduling would also need an
> explicit start. The impact is meaningful but bounded and migratable because
> AMY and Tulip can be updated together. My preference remains the cumulative
> default, but presented as an intentional breaking change with migrated AMY
> examples/tests, a coordinated Tulip wrapper update and release notes. If
> that migration forces the wrapper to mirror AMY clock, execution or note
> state merely to preserve live updates, I would treat that as evidence that
> the public model still needs refinement.

## Source trail

- Shorepine AMY PR 1151 discussion:
  <https://github.com/shorepine/amy/pull/1151>
- AMY examples at the audited main commit:
  <https://github.com/shorepine/amy/blob/0fb0a00b5a9f9443d7e1f85261cc7e70a0adb76b/amy/examples.py#L262-L271>
- AMY tests at the audited main commit:
  <https://github.com/shorepine/amy/blob/0fb0a00b5a9f9443d7e1f85261cc7e70a0adb76b/amy/test.py#L2029-L2064>
- Tulip sequence wrapper:
  <https://github.com/shorepine/tulipcc/blob/96454f9e6708882eaaa74469bca9fbc1051ae55c/tulip/shared/py/sequencer.py#L30-L83>
- Tulip drum-machine use:
  <https://github.com/shorepine/tulipcc/blob/96454f9e6708882eaaa74469bca9fbc1051ae55c/tulip/shared/py/drums.py#L280-L301>

## Next implementation order

1. Add OOM injection, simultaneous-writer, cycle and maximum-load tests.
2. Resolve and migrate AMY's own examples/tests and prepare a tested Tulip
   migration for the intentional tag-semantics change.
3. Run the physical ESP32-P4 timing and heap-retention measurements described
   in `CODEX_HANDOVER_REALTIME_SEQUENCE_PUBLICATION.md`.
4. Re-run binding and audio suites after any resulting change.
5. Only then update the Shorepine PR branch and discussion.
