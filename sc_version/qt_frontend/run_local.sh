#!/usr/bin/env bash
set -euo pipefail

frontend_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "$frontend_dir/../.." && pwd)"
shipped_sc_config="$frontend_dir/config/supercollider.json"
frontend_args=()
sample_args=()
while (($#)); do
    case "$1" in
        --sample-root)
            (($# >= 2)) || {
                echo "--sample-root requires a path" >&2
                exit 2
            }
            ((${#sample_args[@]} == 0)) || {
                echo "--sample-root may be supplied only once" >&2
                exit 2
            }
            sample_args=(--sample-root "$2")
            shift 2
            ;;
        *)
            frontend_args+=("$1")
            shift
            ;;
    esac
done

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

export OMNICHORD_RELEASE_NAME="$(
    "$venv_python" -c \
        'from pathlib import Path; import sys; sys.path.insert(0, sys.argv[1]); from release_identity import read_release_name; print(read_release_name(Path(sys.argv[2])))' \
        "$frontend_dir/code" "$frontend_dir/release_identity.json"
)"

# Source runs use the same per-user configuration and sample-repository
# preparation as frozen packages. The Python implementation bundles cleanly
# and never assumes a system Git executable.
sc_config="$(
    "$venv_python" "$frontend_dir/code/sample_repository.py" \
        "$shipped_sc_config" "${sample_args[@]}"
)"
export OMNICHORD_SC_CONFIG="$sc_config"

# Source and frozen runs share one Python supervisor. It owns the private
# sclang/Supernova process group, PipeWire policy, startup port check, signal
# handling and bounded shutdown; the shell contains no second lifecycle model.
exec "$venv_python" "$frontend_dir/code/supercollider_source_entry.py" \
    "${frontend_args[@]}"
