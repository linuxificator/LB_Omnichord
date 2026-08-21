# Flashing the CI-built ESP32-P4 firmware

The GitHub Actions ESP32-P4 build publishes a portable `esp32p4-firmware` artifact. It contains the application, bootloader, partition table, ESP-IDF flash argument files, `flasher_args.json`, a merged flash image, and `BUILD_INFO` identifying the exact source commit.

Do not copy a GitHub runner's complete `build/` directory to another machine and run `idf.py flash` from it. ESP-IDF's CMake/Ninja build files contain runner-specific absolute paths, and `idf.py flash` is a build-system target that automatically checks/builds dependencies. ESP-IDF documents `flash_project_args` plus `esptool` as the portable way to flash already-built binaries.

`flash_ci.sh` automates that portable path and refuses to flash an artifact that does not match the currently checked-out Git commit.

## One-time prerequisites

Load the ESP-IDF 6.0.2 environment used by this project:

```bash
. "$HOME/esp/esp-idf/export.sh"
```

Install the Ubuntu GitHub CLI package if needed:

```bash
sudo apt update
sudo apt install gh
```

Authenticate once:

```bash
gh auth login
```

## Pull and flash

Check out the firmware branch and update it:

```bash
git checkout esp32p4-reproducible-build
git pull
cd amysynth_version/esp32p4
```

Then flash the CI firmware for exactly that checked-out commit:

```bash
bash flash_ci.sh /dev/ttyACM0
```

The helper:

1. reads the current Git `HEAD` commit;
2. finds a successful `esp32p4-build.yml` run for exactly that commit;
3. downloads its `esp32p4-firmware` artifact into a temporary directory;
4. verifies the artifact `BUILD_INFO` commit matches local `HEAD`;
5. verifies the required bootloader, partition-table, application, and flash metadata files are present;
6. uses the `esptool` Python module from the loaded ESP-IDF environment with the artifact's `flash_project_args`;
7. removes the temporary artifact after flashing.

If `/dev/ttyACM0` is already exported as `ESPPORT`, the port argument can be omitted:

```bash
export ESPPORT=/dev/ttyACM0
bash flash_ci.sh
```

An optional baud rate can be supplied as the second argument or via `ESPBAUD`:

```bash
bash flash_ci.sh /dev/ttyACM0 921600
```

No AMY checkout, patching, CMake configuration, or local firmware compilation is performed by `flash_ci.sh`.

## Manual artifact flashing

If the artifact is downloaded manually from GitHub Actions and extracted into a directory, load the ESP-IDF environment, enter the extracted artifact directory, and run:

```bash
python -m esptool --chip esp32p4 --port /dev/ttyACM0 write-flash @flash_project_args
```

`BUILD_INFO` records the repository commit, workflow run, ESP-IDF version, and target used to create the artifact.
