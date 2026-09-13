#!/usr/bin/env bash
set -euo pipefail

frontend_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "$frontend_dir/../.." && pwd)"
sc_dir="$frontend_dir/../supercollider"
sc_config="$frontend_dir/config/supercollider.json"

if [[ -n "${OMNICHORD_VENV:-}" ]]; then
    venv_dir="$OMNICHORD_VENV"
else
    venv_dir="$repo_dir/.venv"
fi
if [[ ! -x "$venv_dir/bin/python" ]]; then
    echo "Creating source environment: $venv_dir"
    if ! python3 -m venv "$venv_dir"; then
        echo "Could not create $venv_dir; install python3-venv and retry." >&2
        exit 1
    fi
fi

venv_python="$venv_dir/bin/python"
requirements_file="$frontend_dir/requirements.txt"

# This is a source-checkout convenience boundary, not a packaged application
# startup path. Only a missing or incompatible environment triggers install.
if ! "$venv_python" -m pip install \
    --disable-pip-version-check \
    --dry-run \
    --no-deps \
    --no-index \
    -r "$requirements_file" >/dev/null 2>&1; then
    echo "Installing source requirements into $venv_dir"
    "$venv_python" -m pip install \
        --disable-pip-version-check \
        -r "$requirements_file"
fi

"$venv_python" -m pip check

if ! command -v sclang >/dev/null 2>&1; then
    echo "SuperCollider language runtime (sclang) is not installed." >&2
    exit 1
fi
if ! command -v scsynth >/dev/null 2>&1; then
    echo "SuperCollider audio server (scsynth) is not installed." >&2
    exit 1
fi

# Ubuntu's SuperCollider server links to JACK.  On a PipeWire desktop it must
# use PipeWire's JACK compatibility shim.  Without it libjack may launch a raw
# jackd which competes for the physical ALSA card and disrupts desktop audio.
sc_launcher=()
if systemctl --user is-active --quiet pipewire.service 2>/dev/null; then
    if ! command -v pw-jack >/dev/null 2>&1; then
        echo "PipeWire is active, but pw-jack is unavailable." >&2
        echo "Install the distribution package 'pipewire-jack'; refusing to start raw jackd." >&2
        exit 1
    fi
    sc_launcher=(pw-jack)
fi

export OMNICHORD_SC_PORT
export OMNICHORD_SC_SAMPLE_RATE
export OMNICHORD_SC_BLOCK_SIZE
export OMNICHORD_SC_MAX_NODES
export OMNICHORD_SC_MEM_KIB
export OMNICHORD_SC_VSCO_ROOT
export OMNICHORD_SC_SAMPLE_RAM_MIB
OMNICHORD_SC_PORT="$("$venv_python" "$frontend_dir/code/supercollider_config.py" "$sc_config" language.port)"
OMNICHORD_SC_SAMPLE_RATE="$("$venv_python" "$frontend_dir/code/supercollider_config.py" "$sc_config" server.sample_rate)"
OMNICHORD_SC_BLOCK_SIZE="$("$venv_python" "$frontend_dir/code/supercollider_config.py" "$sc_config" server.block_size)"
OMNICHORD_SC_MAX_NODES="$("$venv_python" "$frontend_dir/code/supercollider_config.py" "$sc_config" server.max_nodes)"
OMNICHORD_SC_MEM_KIB="$("$venv_python" "$frontend_dir/code/supercollider_config.py" "$sc_config" server.realtime_memory_kib)"
OMNICHORD_SC_VSCO_ROOT="$("$venv_python" "$frontend_dir/code/supercollider_config.py" "$sc_config" samples.vsco_root)"
OMNICHORD_SC_SAMPLE_RAM_MIB="$("$venv_python" "$frontend_dir/code/supercollider_config.py" "$sc_config" samples.ram_budget_mib)"

# A dedicated process group gives this source supervisor exact ownership of
# both sclang and the scsynth child it boots. It never kills another user's
# unrelated SuperCollider process by executable name.
setsid "${sc_launcher[@]}" sclang -D "$sc_dir/bootstrap.scd" &
sc_process_group=$!

cleanup() {
    kill -TERM -- "-$sc_process_group" 2>/dev/null || true
    wait "$sc_process_group" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

sleep 0.2
kill -0 "$sc_process_group" 2>/dev/null || {
    wait "$sc_process_group"
    exit 1
}

"$venv_python" "$frontend_dir/code/main.py" "$@"
