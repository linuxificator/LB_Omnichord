#!/usr/bin/env bash
set -euo pipefail

frontend_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "$frontend_dir/../.." && pwd)"
socket_path="${OMNICHORD_AMY_SOCKET:-$HOME/.omnichord/amy.sock}"
release_inputs="$frontend_dir/packaging/release_inputs.py"
amy_pcm_bank="$(python3 "$release_inputs" amy-values --field pcm_bank)"
amy_commit="$(python3 "$release_inputs" amy-values --field commit)"

transport_mode="socket"
application_args=()
for argument in "$@"; do
    if [[ "$argument" == "--serial" ]]; then
        transport_mode="serial"
    else
        application_args+=("$argument")
    fi
done

if [[ -n "${OMNICHORD_VENV:-}" ]]; then
    venv_dir="$OMNICHORD_VENV"
else
    venv_dir="$repo_dir/.venv"
fi
amy_root="${OMNICHORD_AMY_ROOT:-$repo_dir/.amy/$amy_commit}"

if [[ ! -x "$venv_dir/bin/python" ]]; then
    echo "Creating source environment: $venv_dir"
    if ! python3 -m venv "$venv_dir"; then
        echo "Could not create $venv_dir; install python3-venv and retry." >&2
        exit 1
    fi
fi

venv_python="$venv_dir/bin/python"
requirements_file="$frontend_dir/requirements-source.txt"
if [[ "$transport_mode" == "serial" ]]; then
    requirements_file="$frontend_dir/requirements.txt"
fi

# This is a source-checkout convenience boundary, not a packaged application
# startup path. Verify the frontend plus pinned AMY's declared Python
# dependencies without consulting a package index; only a missing or
# incompatible environment triggers installation.
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

if [[ "$transport_mode" == "serial" ]]; then
    "$venv_python" -m pip check
    exec "$venv_python" "$frontend_dir/code/main.py" \
        "${application_args[@]}"
fi

amy_stamp="$venv_dir/.lb-omnichord-amy"
amy_contract="$amy_commit:$amy_pcm_bank"

amy_contract_is_current() {
    [[ -f "$amy_stamp" ]] || return 1
    IFS= read -r stamped_contract < "$amy_stamp" || return 1
    stamped_hash="$(sed -n '2p' "$amy_stamp")"
    [[ "$stamped_contract" == "$amy_contract" ]] || return 1
    amy_extension="$("$venv_python" -c 'import c_amy; print(c_amy.__file__)' 2>/dev/null)" \
        || return 1
    [[ -f "$amy_extension" ]] || return 1
    actual_hash="$($venv_python - "$amy_extension" <<'PY'
import hashlib
import sys
from pathlib import Path

print(hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest())
PY
)"
    [[ "$stamped_hash" == "$actual_hash" ]] || return 1
    "$venv_python" - "$amy_extension" <<'PY' >/dev/null 2>&1
import ctypes
import sys

library = ctypes.CDLL(sys.argv[1])
getattr(library, "amy_set_gamma9001_pcm")
getattr(library, "gamma9001_pcm_data")
PY
}

if ! amy_contract_is_current; then
    echo "Provisioning pinned $amy_pcm_bank AMY service in $venv_dir"
    OMNICHORD_VENV="$venv_dir" \
    OMNICHORD_AMY_ROOT="$amy_root" \
        "$frontend_dir/prepare_local_amy.sh" --checkout
    amy_contract_is_current || {
        echo "AMY service verification failed after provisioning." >&2
        exit 1
    }
fi

# Run this after AMY provisioning as well: the installed AMY distribution has
# its own dependency metadata, which is absent on a completely fresh venv
# during the earlier requirements check.
"$venv_python" -m pip check

"$venv_python" "$frontend_dir/code/local_amy_service.py" \
    --socket "$socket_path" \
    --config "$frontend_dir/config/amy_config.json" &
amy_service_pid=$!

cleanup() {
    kill "$amy_service_pid" 2>/dev/null || true
    wait "$amy_service_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

for _attempt in $(seq 1 100); do
    [[ -S "$socket_path" ]] && break
    kill -0 "$amy_service_pid" 2>/dev/null || {
        wait "$amy_service_pid"
        exit 1
    }
    sleep 0.05
done

if [[ ! -S "$socket_path" ]]; then
    echo "AMY service did not create socket: $socket_path" >&2
    exit 1
fi

frontend_launcher=()
if "$venv_python" "$frontend_dir/code/raspberry_pi_realtime.py" apply \
    --service-pid "$amy_service_pid"; then
    if command -v taskset >/dev/null 2>&1; then
        frontend_launcher=(taskset -c 0-1)
    fi
fi

OMNICHORD_AMY_SERVICE_PID="$amy_service_pid" \
"${frontend_launcher[@]}" "$venv_python" "$frontend_dir/code/main.py" \
    --amy-socket "$socket_path" \
    "${application_args[@]}"
