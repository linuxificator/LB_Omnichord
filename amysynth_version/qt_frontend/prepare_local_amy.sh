#!/usr/bin/env bash
set -euo pipefail

frontend_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "$frontend_dir/../.." && pwd)"
venv_dir="${OMNICHORD_VENV:-$repo_dir/../omnichord-env}"
amy_root="${OMNICHORD_AMY_ROOT:-$repo_dir/../amyfork/amy}"

if [[ ! -f "$venv_dir/bin/activate" ]]; then
    echo "Python virtualenv not found: $venv_dir" >&2
    exit 1
fi
if [[ ! -f "$amy_root/setup.py" ]]; then
    echo "AMY source checkout not found: $amy_root" >&2
    exit 1
fi
if ! grep -q "AMY_PCM_BANK" "$amy_root/setup.py"; then
    echo "AMY checkout does not support AMY_PCM_BANK=tiny" >&2
    exit 1
fi

. "$venv_dir/bin/activate"
AMY_PCM_BANK=tiny python -m pip install \
    --no-deps \
    --force-reinstall \
    --no-cache-dir \
    "$amy_root"

amy_so="$(python -c 'import c_amy; print(c_amy.__file__)')"
if nm -D "$amy_so" | grep -Eq 'gamma9001|amy_set_gamma'; then
    echo "AMY verification failed: Gamma9001 symbols are still present" >&2
    exit 1
fi
echo "AMY installed with ESP32-compatible tiny PCM bank: $amy_so"
