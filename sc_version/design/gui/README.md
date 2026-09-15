# GUI design

Status: authoritative category index
Owner: Qt/QML presentation
Applies to: `sc_version`
Last verified: 2026-09-15

`interaction.md` owns shared mouse/touch/keyboard, slider and visual-cost
decisions. Current screen behavior is executable in QML and the frontend/QML
tests; completed migration verification is recorded in
[`../sc/TO_FIX_VERIFICATION.md`](../sc/TO_FIX_VERIFICATION.md). Engine timing
and nodes never leak into QML.
