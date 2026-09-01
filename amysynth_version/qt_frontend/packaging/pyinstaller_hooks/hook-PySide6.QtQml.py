"""Collect only LB Omnichord's reviewed Qt QML runtime modules."""

from __future__ import annotations

import json
from pathlib import Path, PurePath

from PyInstaller.utils.hooks.qt import add_qt6_dependencies, pyside6_library_info


PACKAGING_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PACKAGING_ROOT / "qt_runtime_manifest.json"

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
binaries = [
    binary
    for binary in binaries
    if "/qmltooling/" not in Path(binary[0]).as_posix()
]

manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
qml_root_value = pyside6_library_info.location.get("QmlImportsPath") or (
    pyside6_library_info.location.get("Qml2ImportsPath")
)
if not qml_root_value:
    raise RuntimeError("PySide6 reports no QML imports directory")
qml_root = Path(qml_root_value).resolve()
qml_destination = PurePath(pyside6_library_info.qt_rel_dir) / "qml"

for relative_name in manifest["qml_modules"]:
    qml_directory = qml_root / relative_name
    qmldir = qml_directory / "qmldir"
    if not qmldir.is_file():
        raise FileNotFoundError(f"reviewed QML module is unavailable: {qmldir}")
    plugin_binaries, plugin_data = pyside6_library_info._process_qml_plugin(
        qmldir
    )
    destination = str(qml_destination / relative_name)
    binaries += [(str(path), destination) for path in plugin_binaries]
    datas += [(str(path), destination) for path in plugin_data]
