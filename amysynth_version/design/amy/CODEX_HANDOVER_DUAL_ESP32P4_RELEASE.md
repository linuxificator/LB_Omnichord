# Dual-profile ESP32-P4 release integration

Date: 2026-09-05

## Context

The Omnichord `rework/sequencer` branch pins AMY fork release
`releases/amy_omnichord_R20260905T104903` at immutable commit
`11f0c39fe8350e7a32b9a1c7b1114f4a7806d795`. That release combines the
Shorepine-facing reusable-sequence implementation with the fork integrations
needed by the application: runtime bus sizing, Gamma9001, socket/Android
services, configurable embedded audio geometry and larger sequence capacities.

The earlier ESP32-P4 work lived on a separate branch and still used the
superseded sequence-group configuration names. It has now been integrated into
the current Omnichord sequencer branch and migrated to:

- `max_sequencer_tags = 1280`;
- `max_sequence_events = 64`;
- `max_sequence_executions = 40`.

The P4 firmware also sets 336 oscillators, 16 Karplus-Strong buffers, 11 buses,
Gamma9001, and the physically established 48 kHz / 128-sample / 2 × 64-frame
audio geometry. Persistent pools use PSRAM; render and DMA scratch remain in
internal RAM.

## Source/configuration boundary

The firmware preparation does not rewrite AMY source literals for sample rate,
block size, I2S format or DMA dimensions. The AMY release exposes those as
compile-time hooks, and the generated ESP-IDF component supplies them as public
compile definitions. Public visibility is intentional: both the AMY component
and `main.c`, which includes `amy.h`, must see the same geometry.

Gamma9001's generated C blob is made inside the ignored AMY component checkout.
The source dataset remains authoritative and a multi-megabyte generated file is
not added to the Omnichord repository.

## Two silicon profiles

ESP-IDF treats pre-v3 and v3 ESP32-P4 silicon as binary-incompatible. CI now
builds both:

- `v1`: revision 1.0–1.99, including the physically tested revision 1.3 board;
- `v3`: revision 3.1–3.99, compile-tested until physical validation is done.

Pin assignments and UART baud are Kconfig-backed build settings rather than
constants in application code.

## Release artifact contract

The normal Omnichord release calls the reusable P4 workflow with profile
`all`. It publishes one asset named
`LB_Omnichord.R<date>T<time>.ESP32P4.zip`. Extracting the ZIP yields exactly one
directory with the matching release name. That directory contains:

- `v1/` and `v3/`, each with its own bootloader, partition table, application,
  merged image, `flasher_args.json`, checksums and build metadata;
- `RELEASE_FLASHING.md`;
- `flash_esptool_v4.py` for underscore-style commands/options;
- `flash_esptool_v5.py` for hyphen-style commands/options;
- shared standard-library-only argument handling.

The flashers consume the generated `flasher_args.json`. Flash offsets and
settings are not copied into hand-maintained scripts. `--dry-run` validates the
selected package and prints the exact command without opening a serial port.

## Diagnostic commits

- `9b7d4a3` — integrate the full Gamma9001 P4 firmware baseline;
- `8f493eb` — migrate the firmware to reusable-sequence configuration;
- `a01ff63` — add standalone dual-profile packaging;
- `2a792f2` — connect P4 firmware to full releases;
- `d76a889` — migrate packaged capacity metadata and tests;
- `d6fdf65` — package both profiles with portable old/new esptool flashers;
- `01159d5` — document the release and physical-validation boundary.

## Verification

The final local Omnichord `--suite all` run passed while verifying the exact
AMY release commit. Firmware contract tests cover Gamma9001, PSRAM, capacities,
profiles, audio geometry, old/new esptool syntax, and the versioned ZIP
topology. Hosted ESP-IDF builds remain the authority for actual P4 compilation;
physical I2S/LP-UART validation remains outside CI.

Hosted workflow run `33958471411` completed successfully for both `v1` and
`v3` at Omnichord commit `01159d5e688f3673bc42e205dbe7f15e1a14aa90`.
