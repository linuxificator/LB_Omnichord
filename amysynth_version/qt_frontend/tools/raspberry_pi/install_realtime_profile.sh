#!/usr/bin/env bash
set -euo pipefail

source_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
install_root="/usr/local/lib/lb-omnichord-rt"
unit_root="/etc/systemd/system"
limits_file="/etc/security/limits.d/95-lb-omnichord-realtime.conf"
display_name="${LB_OMNICHORD_RELEASE_ASSET:-$(basename -- "$0")}"
target_user="${SUDO_USER:-}"

usage() {
    echo "Usage: sudo ./$display_name [--user USER]"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --user)
            if [[ $# -lt 2 ]]; then
                echo "--user requires a user name." >&2
                usage >&2
                exit 2
            fi
            target_user="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "Run this setup with sudo." >&2
    exit 1
fi

model="$(tr -d '\0' </proc/device-tree/model 2>/dev/null || true)"
case "$model" in
    "Raspberry Pi 4"*|"Raspberry Pi 5"*) ;;
    *)
        echo "This setup supports Raspberry Pi 4 and Pi 5; found: ${model:-unknown}." >&2
        exit 1
        ;;
esac

if [[ -z "$target_user" || "$target_user" == "root" ]]; then
    echo "Could not infer the desktop user; pass --user USER." >&2
    exit 1
fi
if [[ ! "$target_user" =~ ^[a-z_][a-z0-9_-]*[$]?$ ]] || ! id "$target_user" >/dev/null 2>&1; then
    echo "Invalid local user: $target_user" >&2
    exit 1
fi

required_files=(
    rt_pi_config.py
    lb-omnichord-performance.service
)
for required_file in "${required_files[@]}"; do
    if [[ ! -f "$source_root/$required_file" ]]; then
        echo "Missing setup payload: $source_root/$required_file" >&2
        exit 1
    fi
done

install -d -m 755 "$install_root"
install -m 755 \
    "$source_root/rt_pi_config.py" \
    "$source_root/install_realtime_profile.sh" \
    "$install_root/"
install -m 644 \
    "$source_root/lb-omnichord-performance.service" \
    "$unit_root/"

limits_temporary="$(mktemp)"
trap 'rm -f -- "$limits_temporary"' EXIT
printf '%s - rtprio 80\n' "$target_user" >"$limits_temporary"
install -d -m 755 /etc/security/limits.d
install -m 644 "$limits_temporary" "$limits_file"

# Remove the superseded experimental watcher from an earlier development
# version. The normal launch wrapper now configures its exact AMY child once.
systemctl disable --now "lb-omnichord-rt-policy@$target_user.service" \
    >/dev/null 2>&1 || true
rm -f -- "$unit_root/lb-omnichord-rt-policy@.service"
rm -f -- "$install_root/rt_pi_runtime.py"

python3 "$install_root/rt_pi_config.py" apply --profile audio-split
python3 "$install_root/rt_pi_config.py" set-governor performance
systemctl daemon-reload
systemctl enable --now lb-omnichord-performance.service

echo "Realtime permission and the performance governor are configured for $target_user."
echo "Reboot this Raspberry Pi so the boot profile and new login limit are active."
echo "Rollback instructions: $install_root/rt_pi_config.py rollback --snapshot PATH"
