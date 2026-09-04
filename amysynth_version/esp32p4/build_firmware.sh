#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
profile="${ESP32P4_PROFILE:-v1}"
prepare=1

usage() {
    echo "usage: $0 [--profile v1|v3] [--skip-prepare]" >&2
}

while (($#)); do
    case "$1" in
        --profile)
            [[ $# -ge 2 ]] || { usage; exit 2; }
            profile="$2"
            shift 2
            ;;
        --skip-prepare)
            prepare=0
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            usage
            exit 2
            ;;
    esac
done

case "$profile" in
    v1) default_label="waveshare-pico-m-v1" ;;
    v3) default_label="waveshare-pico-m-v3" ;;
    *) echo "unsupported ESP32-P4 profile: $profile (expected v1 or v3)" >&2; exit 2 ;;
esac

require_integer() {
    local name="$1"
    local value="$2"
    if [[ ! "$value" =~ ^[0-9]+$ ]]; then
        echo "$name must be an unsigned integer, got: $value" >&2
        exit 2
    fi
}

lrck="${ESP32P4_I2S_LRCK_GPIO:-16}"
dout="${ESP32P4_I2S_DOUT_GPIO:-17}"
bclk="${ESP32P4_I2S_BCLK_GPIO:-18}"
uart_rx="${ESP32P4_UART_RX_GPIO:-15}"
uart_baud="${ESP32P4_UART_BAUD:-1000000}"
board_label="${ESP32P4_BOARD_LABEL:-$default_label}"

for pair in \
    "ESP32P4_I2S_LRCK_GPIO:$lrck" \
    "ESP32P4_I2S_DOUT_GPIO:$dout" \
    "ESP32P4_I2S_BCLK_GPIO:$bclk" \
    "ESP32P4_UART_RX_GPIO:$uart_rx" \
    "ESP32P4_UART_BAUD:$uart_baud"; do
    require_integer "${pair%%:*}" "${pair#*:}"
done
if [[ ! "$board_label" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "ESP32P4_BOARD_LABEL may contain only letters, digits, dot, underscore, and dash" >&2
    exit 2
fi

build_dir="$project_dir/build/$profile"
mkdir -p "$build_dir"
override_defaults="$build_dir/sdkconfig.defaults.generated"
printf '%s\n' \
    "CONFIG_OMNICHORD_P4_BOARD_PROFILE=\"$board_label\"" \
    "CONFIG_OMNICHORD_P4_I2S_LRCK_GPIO=$lrck" \
    "CONFIG_OMNICHORD_P4_I2S_DOUT_GPIO=$dout" \
    "CONFIG_OMNICHORD_P4_I2S_BCLK_GPIO=$bclk" \
    "CONFIG_OMNICHORD_P4_UART_RX_GPIO=$uart_rx" \
    "CONFIG_OMNICHORD_P4_UART_BAUD=$uart_baud" \
    > "$override_defaults"

if ((prepare)); then
    bash "$project_dir/prepare_amy.sh"
fi

sdkconfig="$build_dir/sdkconfig"
defaults="$project_dir/sdkconfig.defaults;$project_dir/sdkconfig.defaults.$profile;$override_defaults"

idf.py -B "$build_dir" \
    -D "SDKCONFIG=$sdkconfig" \
    -D "SDKCONFIG_DEFAULTS=$defaults" \
    build
idf.py -B "$build_dir" merge-bin -o merged-flash.bin -f raw

echo "Built ESP32-P4 $profile image: $build_dir/merged-flash.bin"
