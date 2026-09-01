#!/usr/bin/env bash
set -euo pipefail

frontend_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "$frontend_dir/../.." && pwd)"
venv_dir="${OMNICHORD_VENV:-$repo_dir/../omnichord-env}"
socket_path="${OMNICHORD_AMY_SOCKET:-$HOME/.omnichord/amy.sock}"

if [[ ! -f "$venv_dir/bin/activate" ]]; then
    echo "Python virtualenv not found: $venv_dir" >&2
    exit 1
fi

. "$venv_dir/bin/activate"

# The AMY service is provisioned separately from the frontend runtime.  Only
# validate its PCM-bank contract here; never build or install AMY while
# launching the wire-protocol client and service processes.
amy_extension="$(python -c 'import c_amy; print(c_amy.__file__)')"
if ! nm -D "$amy_extension" | grep 'amy_set_gamma9001_pcm' >/dev/null \
    || ! nm -D "$amy_extension" | grep 'gamma9001_pcm_data' >/dev/null; then
    echo "AMY service does not contain the required Gamma9001 PCM bank: $amy_extension" >&2
    echo "Provision the service separately with ./prepare_local_amy.sh before launching." >&2
    exit 1
fi

python "$frontend_dir/code/local_amy_service.py" \
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

python "$frontend_dir/code/main.py" \
    --amy-socket "$socket_path" \
    "$@"
