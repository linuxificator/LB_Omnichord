"""Remove unrelated optional QtGui plugins from LB Omnichord packages."""

from __future__ import annotations

from pathlib import Path

from PyInstaller.utils.hooks.qt import add_qt6_dependencies


hiddenimports, binaries, datas = add_qt6_dependencies(__file__)


def is_product_plugin(binary: tuple[str, str]) -> bool:
    source = Path(binary[0])
    normalized = source.as_posix()
    if "/imageformats/" in normalized:
        return source.stem.casefold() in {
            "libqgif",
            "libqico",
            "libqjpeg",
            "libqsvg",
            "qgif",
            "qico",
            "qjpeg",
            "qsvg",
        }
    if "/platforminputcontexts/" in normalized:
        return "virtualkeyboard" not in source.name.casefold()
    return True


binaries = [binary for binary in binaries if is_product_plugin(binary)]
