from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def parse_synths_markdown(
    path: Path,
) -> dict[str, dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    result: dict[str, dict[str, str]] = {}

    for section in re.split(
        r"^## ",
        text,
        flags=re.MULTILINE,
    )[1:]:
        _, remainder = section.split("\n", 1)
        key_match = re.search(
            r"^### Key:\n\s+:([^\s]+)",
            remainder,
            flags=re.MULTILINE,
        )

        if not key_match:
            continue

        defaults: dict[str, str] = {}

        for option_match in re.finditer(
            r"^  \* ([A-Za-z0-9_]+):\n"
            r"(.*?)(?=^  \* |^## |\Z)",
            remainder,
            flags=re.MULTILINE | re.DOTALL,
        ):
            default_match = re.search(
                r"^    - default: (.*)$",
                option_match.group(2),
                flags=re.MULTILINE,
            )

            if default_match:
                defaults[option_match.group(1)] = (
                    default_match.group(1).strip()
                )

        result[key_match.group(1)] = defaults

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh synth defaults in synths.json from "
            "Sonic Pi's generated synths.md"
        )
    )
    parser.add_argument("synths_markdown", type=Path)
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path(__file__).with_name(
            "synths.json"
        ),
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
    )
    args = parser.parse_args()

    source_defaults = parse_synths_markdown(
        args.synths_markdown
    )
    catalog = json.loads(
        args.catalog.read_text(encoding="utf-8")
    )

    changes = 0

    for synth in catalog["synths"]:
        synth_key = synth["key"]

        if synth_key not in source_defaults:
            raise SystemExit(
                f"Missing synth :{synth_key} "
                f"in source metadata"
            )

        for control in synth["controls"]:
            control_key = control["key"]

            try:
                raw_default = source_defaults[
                    synth_key
                ][control_key]
                new_default = float(raw_default)
            except KeyError:
                raise SystemExit(
                    f"Missing control {control_key!r} "
                    f"for synth :{synth_key}"
                )
            except ValueError:
                raise SystemExit(
                    f"Default for "
                    f"{synth_key}.{control_key} "
                    f"is not numeric: {raw_default!r}"
                )

            old_default = float(
                control["default"]
            )

            if old_default != new_default:
                print(
                    f"{synth_key}.{control_key}: "
                    f"{old_default} -> {new_default}"
                )
                control["default"] = new_default
                changes += 1

    if changes == 0:
        print(
            "Catalog defaults already match "
            "the Sonic Pi metadata."
        )
    elif args.check_only:
        print(
            f"{changes} default value(s) "
            f"would change."
        )
    else:
        backup = args.catalog.with_suffix(
            args.catalog.suffix + ".bak"
        )
        backup.write_text(
            args.catalog.read_text(
                encoding="utf-8"
            ),
            encoding="utf-8",
        )
        args.catalog.write_text(
            json.dumps(
                catalog,
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"Updated {args.catalog}")
        print(f"Backup: {backup}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
