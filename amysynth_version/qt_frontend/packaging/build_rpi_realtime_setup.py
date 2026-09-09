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
    ("install_realtime_profile.sh", 0o755),
    ("rt_pi_config.py", 0o755),
    ("lb-omnichord-performance.service", 0o644),
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
        'temporary="$(mktemp -d)"',
        'trap \'rm -rf -- "$temporary"\' EXIT',
        "decode_file() {",
        '    local destination="$1" mode="$2" expected="$3"',
        '    base64 --decode > "$temporary/payload"',
        '    if ! printf "%s  %s\\n" "$expected" "$temporary/payload" | sha256sum --check --status -; then',
        '        echo "Embedded setup payload failed its integrity check." >&2',
        "        exit 1",
        "    fi",
        '    install -m "$mode" "$temporary/payload" "$destination"',
        "}",
    ]
    for file_name, mode in EMBEDDED_FILES:
        digest = hashlib.sha256((TOOLS / file_name).read_bytes()).hexdigest()
        marker = f"__LB_OMNICHORD_{file_name.upper().replace('.', '_').replace('@', 'AT')}__"
        sections.extend(
            (
                f'decode_file "$temporary/{file_name}" {mode:o} {digest} <<\'{marker}\'',
                _encoded(TOOLS / file_name),
                marker,
            )
        )
    sections.extend(
        (
            "",
            'LB_OMNICHORD_RELEASE_ASSET="$release_asset" \\',
            '    "$temporary/install_realtime_profile.sh" "$@"',
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
