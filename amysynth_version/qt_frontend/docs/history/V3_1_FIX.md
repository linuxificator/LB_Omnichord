# v3.1 startup fix

v3 shipped with an inconsistent `defaults.json`: it still named the removed
Sonic Pi synth keys `prophet`, `pluck`, and `fm`, while the runtime catalogue
contains AMY keys only.

v3.1 fixes the packaged defaults to:

- chord: `juno_004` — Juno A15 Moving Strings
- strum: `juno_028` — Juno A45 Koto
- bass: `dx7_143` — the catalogue's configured default bass patch

Startup is also defensive now: legacy Sonic Pi keys are passed through the
existing compatibility map, and any genuinely unknown key falls back to the
corresponding default from `synths.json` with a warning instead of terminating
the application.
