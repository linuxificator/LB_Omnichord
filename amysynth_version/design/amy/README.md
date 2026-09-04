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
