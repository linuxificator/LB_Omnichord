#!/usr/bin/env bash
set -euo pipefail

frontend_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "$frontend_dir/../.." && pwd)"
venv_dir="${OMNICHORD_VENV:-$repo_dir/../omnichord-env}"
amy_root="${OMNICHORD_AMY_ROOT:-$repo_dir/../amyfork/amy}"
amy_release="releases/amy_omnichord_R20260831T001253"
amy_commit="00157856312de89f6dc293f90efb1889f0ceff23"

if [[ ! -f "$venv_dir/bin/activate" ]]; then
    echo "Python virtualenv not found: $venv_dir" >&2
    exit 1
fi
if [[ ! -f "$amy_root/setup.py" ]]; then
    echo "AMY source checkout not found: $amy_root" >&2
    exit 1
fi
actual_commit="$(git -C "$amy_root" rev-parse HEAD)"
if [[ "$actual_commit" != "$amy_commit" ]]; then
    echo "AMY checkout must be $amy_release at $amy_commit; found $actual_commit" >&2
    exit 1
fi
if ! grep -q "AMY_PCM_BANK" "$amy_root/setup.py"; then
    echo "AMY checkout does not support AMY_PCM_BANK=gamma9001" >&2
    exit 1
fi

. "$venv_dir/bin/activate"
AMY_PCM_BANK=gamma9001 python -m pip install \
    --no-deps \
    --force-reinstall \
    --no-cache-dir \
    "$amy_root"

amy_so="$(python -c 'import c_amy; print(c_amy.__file__)')"
if ! nm -D "$amy_so" | grep 'amy_set_gamma9001_pcm' >/dev/null || \
   ! nm -D "$amy_so" | grep 'gamma9001_pcm_data' >/dev/null; then
    echo "AMY verification failed: Gamma9001 PCM symbols are missing" >&2
    exit 1
fi
echo "AMY $amy_release at $amy_commit installed with Gamma9001 PCM bank: $amy_so"
