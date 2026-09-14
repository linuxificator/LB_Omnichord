#!/usr/bin/env python3
"""Flash a release image with the legacy esptool command-line syntax."""

from release_flash_common import main


if __name__ == "__main__":
    raise SystemExit(main(modern=False))
