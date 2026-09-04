# Codex-only AMY handovers

Status: index for AMY fork analysis and continuation work
Owner: LB Omnichord integration
Last updated: 2026-09-04

This directory is the home for AMY implementation audits, diagnostic trails
and continuation notes that are useful to LB Omnichord development but must not
be committed to a clean Shorepine-facing AMY branch. Authoritative LB behavior
remains in the parent design directory; public AMY documentation belongs in
AMY itself and must be written for AMY users rather than for this application.

Read these documents in order for current reusable-sequence work:

1. `CODEX_HANDOVER_SEQUENCER_SIMPLIFICATION.md` — implemented public model,
   branch and release map, LB integration and established constraints.
2. `CODEX_HANDOVER_SEQUENCER_SIMPLIFICATION_AUDIT.md` — differential audit
   against Shorepine main, compatibility impact, tests, defects and possible
   simplifications.
3. `CODEX_HANDOVER_REALTIME_SEQUENCE_PUBLICATION.md` — implemented
   publication/reclamation design, its route from COW and the remaining
   physical ESP32 timing proof.
4. `CODEX_HANDOVER_SEQUENCE_API_REVIEW_COMPLETION.md` — latest PR API feedback,
   final named-action syntax, compatibility evidence, completed host
   verification, immutable LB release and remaining work.
5. `CODEX_HANDOVER_SEQUENCE_FINAL_QUALITY_AUDIT.md` — final pre-merge
   differential audit, reproduced concurrency/slot-order defects and the
   ordered repair and re-audit plan.
6. `CODEX_HANDOVER_SEQUENCE_FINAL_QUALITY_REAUDIT.md` — completed repairs,
   additional compatibility/rollover findings, final host validation and the
   remaining target-only checks.

The repository-root `CODEX_HANDOFF.md` contains older socket, Android, Windows,
Gamma9001 and superseded nested/group-sequencer history. It is still useful
background, but its historical sections do not override current contracts.

Rules for future work:

- never copy this directory into an AMY upstream-offer or release branch;
- keep Omnichord musical policy out of AMY;
- distinguish measured behavior from proposed behavior;
- do not claim hard real-time safety from desktop tests alone;
- update the audit baseline and exact SHAs whenever the AMY branch changes;
- preserve a diagnostic Git trail with small commits when implementation work
  is authorized.
