#!/usr/bin/env bash
set -euo pipefail

frontend_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "$frontend_dir/../.." && pwd)"
release_inputs="$frontend_dir/packaging/release_inputs.py"
amy_pcm_bank="$(python3 "$release_inputs" amy-values --field pcm_bank)"
amy_release_branch="$(python3 "$release_inputs" amy-values --field release_branch)"
amy_commit="$(python3 "$release_inputs" amy-values --field commit)"
amy_root="${OMNICHORD_AMY_ROOT:-$repo_dir/.amy/$amy_commit}"

if [[ -n "${OMNICHORD_VENV:-}" ]]; then
    venv_dir="$OMNICHORD_VENV"
else
    venv_dir="$repo_dir/.venv"
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

if [[ ! -x "$venv_dir/bin/python" ]]; then
    echo "Python virtualenv not found: $venv_dir" >&2
    echo "Run ./run_local.sh once to create and provision it automatically." >&2
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

venv_python="$venv_dir/bin/python"
AMY_PCM_BANK="$amy_pcm_bank" "$venv_python" -m pip install \
    --no-deps \
    --force-reinstall \
    --no-cache-dir \
    "$amy_root"

amy_so="$("$venv_python" -c 'import c_amy; print(c_amy.__file__)')"
"$venv_python" - "$amy_so" <<'PY'
import ctypes
import sys

library = ctypes.CDLL(sys.argv[1])
for symbol in ("amy_set_gamma9001_pcm", "gamma9001_pcm_data"):
    try:
        getattr(library, symbol)
    except AttributeError as exc:
        raise SystemExit(f"AMY verification failed: {symbol} is absent") from exc
PY
"$venv_python" - "$amy_so" "$venv_dir/.lb-omnichord-amy" \
    "$amy_commit:$amy_pcm_bank" <<'PY'
import hashlib
import sys
from pathlib import Path

extension = Path(sys.argv[1])
stamp = Path(sys.argv[2])
contract = sys.argv[3]
digest = hashlib.sha256(extension.read_bytes()).hexdigest()
temporary = stamp.with_name(f".{stamp.name}.tmp")
temporary.write_text(f"{contract}\n{digest}\n", encoding="utf-8")
temporary.replace(stamp)
PY
echo "AMY installed from $amy_release_branch at $amy_commit with $amy_pcm_bank: $amy_so"
