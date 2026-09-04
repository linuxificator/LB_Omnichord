# Flashing a CI-built ESP32-P4 image

The standalone `esp32p4-build.yml` workflow publishes one portable artifact
per silicon ABI: `esp32p4-firmware-v1` and `esp32p4-firmware-v3`. The default
v1 image supports ESP32-P4 revision 1.0 through 1.99 and is the correct image
for the board which reported revision 1.3. Never flash it on v3.x silicon.

Each artifact contains the application, bootloader, partition table, ESP-IDF
flash arguments, a merged image, ELF/map diagnostics, SHA-256 checksums and a
`BUILD_INFO` file naming the exact LB Omnichord commit, AMY release and profile.
Do not download a runner's complete build directory: CMake and Ninja output
contains runner-specific absolute paths.

## Flash the artifact matching a checkout

Load ESP-IDF 6.0.2 and authenticate the GitHub CLI once:

```bash
. "$HOME/esp/esp-idf/export.sh"
gh auth login
```

Then check out and pull the firmware branch, and run:

```bash
cd amysynth_version/esp32p4
ESP32P4_PROFILE=v1 ./flash_ci.sh /dev/ttyACM0
```

The helper finds a successful standalone workflow run for the exact checked-out
commit, downloads the matching profile, validates `BUILD_INFO`, verifies all
required files and invokes esptool with `flash_project_args`. Set
`ESP32P4_PROFILE=v3` only for a revision 3.x board. `ESPPORT` and `ESPBAUD` may
be used instead of positional port and baud arguments.

## Flash a manually downloaded artifact

Verify the package and flash either its component images:

```bash
sha256sum --check SHA256SUMS
python -m esptool --chip esp32p4 --port /dev/ttyACM0 \
  write-flash @flash_project_args
```

or its merged image at offset zero:

```bash
python -m esptool --chip esp32p4 --port /dev/ttyACM0 \
  write-flash 0x0 LB_Omnichord-ESP32P4-v1-merged.bin
```

The merged image is configured for 32 MB flash. After flashing, reset and
monitor the board. The expected log names the selected build profile, detected
chip revision, PSRAM size, AMY 48 kHz / 64-sample configuration and LP-UART
GPIO/baud before reporting readiness for native AMY commands.
