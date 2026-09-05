# Flashing the ESP32-P4 release package

The release ZIP expands to one versioned directory. It contains `v1/` and
`v3/` firmware images because ESP32-P4 v1.x and v3.x silicon are not binary
compatible.

- Use `v1` for revision 1.x silicon, including the physically tested v1.3
  Waveshare ESP32-P4 Pico M.
- Use `v3` only for revision 3.x silicon. This profile is compile-tested but
  still requires physical validation.

Install Espressif `esptool`, connect the board, and use the script matching
your installed major version:

```bash
python flash_esptool_v4.py v1 /dev/ttyACM0
python flash_esptool_v5.py v1 /dev/ttyACM0
```

Replace `v1` with `v3` for newer silicon. Add `--dry-run` to validate the
selected files and show the exact command without opening the serial port.
Both scripts read the build-generated `flasher_args.json`; offsets and flash
settings are not duplicated in hand-maintained code.
