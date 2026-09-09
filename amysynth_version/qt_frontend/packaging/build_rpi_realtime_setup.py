#!/usr/bin/env python3
"""Build one self-contained Raspberry Pi 4/5 realtime setup release asset."""

from __future__ import annotations

import argparse
import base64
import hashlib
import re
import textwrap
from pathlib import Path


HERE = Path(__file__).resolve().parent
FRONTEND = HERE.parent
TOOLS = FRONTEND / "tools" / "raspberry_pi"
RELEASE_PATTERN = re.compile(r"^R\d{14}$")
EMBEDDED_FILES = (
    ("rt_pi_config.py", 0o755),
    ("rt_pi_runtime.py", 0o755),
    ("lb-omnichord-performance.service", 0o644),
    ("lb-omnichord-rt-policy@.service", 0o644),
)


def asset_name(release_stamp: str) -> str:
    if RELEASE_PATTERN.fullmatch(release_stamp) is None:
        raise ValueError("release stamp must be R followed by 14 UTC digits")
    return f"LB_Omnichord.{release_stamp}.Pi4-Pi5-realtime-setup.sh"


def _encoded(path: Path) -> str:
    return "\n".join(
        textwrap.wrap(base64.b64encode(path.read_bytes()).decode("ascii"), 76)
    )


def render_installer(release_stamp: str) -> str:
    name = asset_name(release_stamp)
    sections = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        f"release_asset={name!r}",
        'install_root="/usr/local/lib/lb-omnichord-rt"',
        'unit_root="/etc/systemd/system"',
        'target_user="${SUDO_USER:-}"',
        "",
        "usage() {",
        "    echo \"Usage: sudo ./$release_asset [--user USER]\"",
        "}",
        "",
        "while [[ $# -gt 0 ]]; do",
        '    case "$1" in',
        '        --user) target_user="${2:-}"; shift 2 ;;',
        "        -h|--help) usage; exit 0 ;;",
        '        *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;',
        "    esac",
        "done",
        "",
        'if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then',
        '    echo "Run this setup with sudo." >&2',
        "    exit 1",
        "fi",
        'model="$(tr -d \'\\0\' </proc/device-tree/model 2>/dev/null || true)"',
        'case "$model" in',
        '    "Raspberry Pi 4"*|"Raspberry Pi 5"*) ;;',
        '    *) echo "This asset supports Raspberry Pi 4 and Pi 5; found: ${model:-unknown}." >&2; exit 1 ;;',
        "esac",
        'if [[ -z "$target_user" || "$target_user" == "root" ]]; then',
        '    echo "Could not infer the desktop user; pass --user USER." >&2',
        "    exit 1",
        "fi",
        'if [[ ! "$target_user" =~ ^[a-z_][a-z0-9_-]*[$]?$ ]] || ! id "$target_user" >/dev/null 2>&1; then',
        '    echo "Invalid local user: $target_user" >&2',
        "    exit 1",
        "fi",
        "",
        'temporary="$(mktemp -d)"',
        'trap \'rm -rf -- "$temporary"\' EXIT',
        "decode_file() {",
        '    local destination="$1" mode="$2"',
        '    base64 --decode > "$temporary/payload"',
        '    install -m "$mode" "$temporary/payload" "$destination"',
        "}",
        "",
        'install -d -m 755 "$install_root"',
    ]
    for file_name, mode in EMBEDDED_FILES:
        destination = (
            f'$unit_root/{file_name}'
            if file_name.endswith(".service")
            else f'$install_root/{file_name}'
        )
        marker = f"__LB_OMNICHORD_{file_name.upper().replace('.', '_').replace('@', 'AT')}__"
        sections.extend(
            (
                f'decode_file "{destination}" {mode:o} <<\'{marker}\'',
                _encoded(TOOLS / file_name),
                marker,
            )
        )
    sections.extend(
        (
            "",
            'python3 "$install_root/rt_pi_config.py" apply --profile audio-split',
            'python3 "$install_root/rt_pi_config.py" set-governor performance',
            "systemctl daemon-reload",
            "systemctl enable --now lb-omnichord-performance.service",
            'systemctl enable --now "lb-omnichord-rt-policy@$target_user.service"',
            "",
            'if python3 "$install_root/rt_pi_config.py" verify --profile audio-split >/dev/null; then',
            '    echo "Realtime boot profile is active; LB Omnichord is ready."',
            "else",
            '    echo "Realtime services are installed and enabled for $target_user."',
            '    echo "Reboot this Raspberry Pi, then start LB Omnichord again."',
            "fi",
            'echo "Rollback instructions: $install_root/rt_pi_config.py rollback --snapshot PATH"',
            "",
        )
    )
    return "\n".join(sections)


def build(release_stamp: str, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / asset_name(release_stamp)
    output.write_text(render_installer(release_stamp), encoding="utf-8")
    output.chmod(0o755)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum = output.with_name(f"{output.name}.sha256")
    checksum.write_text(f"{digest}  {output.name}\n", encoding="ascii")
    return output, checksum


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-stamp", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output, checksum = build(args.release_stamp, args.output_dir)
    print(output)
    print(checksum)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
