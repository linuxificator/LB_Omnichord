#!/usr/bin/env bash
set -euo pipefail

frontend_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "$frontend_dir/../.." && pwd)"
release_inputs="$frontend_dir/packaging/release_inputs.py"
amy_pcm_bank="$(python3 "$release_inputs" amy-values --field pcm_bank)"
amy_release_branch="$(python3 "$release_inputs" amy-values --field release_branch)"
amy_commit="$(python3 "$release_inputs" amy-values --field commit)"
amy_root="${OMNICHORD_AMY_ROOT:-$repo_dir/../amyfork/amy}"

if [[ -n "${OMNICHORD_VENV:-}" ]]; then
    venv_dir="$OMNICHORD_VENV"
elif [[ -f "$frontend_dir/.venv/bin/activate" ]]; then
    venv_dir="$frontend_dir/.venv"
else
    venv_dir="$repo_dir/../omnichord-env"
fi

checkout_missing=false
case "${1:-}" in
    "") ;;
    --checkout) checkout_missing=true ;;
    *)
        echo "Usage: $0 [--checkout]" >&2
        exit 2
        ;;
esac

if [[ ! -f "$venv_dir/bin/activate" ]]; then
    echo "Python virtualenv not found: $venv_dir" >&2
    exit 1
fi
if [[ ! -f "$amy_root/setup.py" && "$checkout_missing" == true ]]; then
    if [[ -e "$amy_root" ]]; then
        echo "AMY checkout target exists but is not an AMY source tree: $amy_root" >&2
        exit 1
    fi
    mkdir -p "$(dirname -- "$amy_root")"
    python3 "$frontend_dir/packaging/checkout_amy.py" --destination "$amy_root"
fi
if [[ ! -f "$amy_root/setup.py" ]]; then
    echo "AMY source checkout not found: $amy_root" >&2
    echo "Run $0 --checkout to fetch the exact pinned release, or set OMNICHORD_AMY_ROOT." >&2
    exit 1
fi
if ! grep -q "AMY_PCM_BANK" "$amy_root/setup.py"; then
    echo "AMY checkout does not support AMY_PCM_BANK=$amy_pcm_bank" >&2
    exit 1
fi
actual_commit="$(git -C "$amy_root" rev-parse HEAD)"
if [[ "$actual_commit" != "$amy_commit" ]]; then
    echo "AMY checkout is $actual_commit, expected $amy_commit from $amy_release_branch" >&2
    exit 1
fi

. "$venv_dir/bin/activate"
AMY_PCM_BANK="$amy_pcm_bank" python -m pip install \
    --no-deps \
    --force-reinstall \
    --no-cache-dir \
    "$amy_root"

amy_so="$(python -c 'import c_amy; print(c_amy.__file__)')"
nm -D "$amy_so" | grep 'amy_set_gamma9001_pcm' >/dev/null || {
    echo "AMY verification failed: Gamma9001 registration is absent" >&2
    exit 1
}
nm -D "$amy_so" | grep 'gamma9001_pcm_data' >/dev/null || {
    echo "AMY verification failed: Gamma9001 PCM data is absent" >&2
    exit 1
}
echo "AMY installed from $amy_release_branch at $amy_commit with $amy_pcm_bank: $amy_so"
