#!/usr/bin/env python3
"""Derive a minimal, valid PySide6 Android wheel from a verified Qt wheel."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Iterable


PACKAGING = Path(__file__).resolve().parents[1]
MANIFEST = PACKAGING / "qt_runtime_manifest.json"
NEEDED = re.compile(r"Shared library: \[([^]]+)]")
ANDROID_PLUGINS = (
    "networkinformation/libplugins_networkinformation_qandroidnetworkinformation_",
    "platforms/libplugins_platforms_qtforandroid_",
)
ANDROID_JARS = frozenset(
    {
        "Qt6Android.jar",
        "Qt6AndroidBindings.jar",
        "Qt6AndroidNetwork.jar",
        "Qt6AndroidNetworkInformationBackend.jar",
        "Qt6AndroidQuick.jar",
    }
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def needed_libraries(readelf: str, path: Path) -> tuple[str, ...]:
    result = subprocess.run(
        [readelf, "-d", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return tuple(NEEDED.findall(result.stdout))


def native_closure(
    *,
    roots: Iterable[str],
    libraries: dict[str, Path],
    readelf: str,
) -> frozenset[str]:
    pending = list(roots)
    kept: set[str] = set()
    while pending:
        name = pending.pop()
        if name in kept:
            continue
        path = libraries.get(name)
        if path is None:
            raise ValueError(f"wheel does not contain native root {name}")
        kept.add(name)
        pending.extend(
            dependency
            for dependency in needed_libraries(readelf, path)
            if dependency in libraries and dependency not in kept
        )
    return frozenset(kept)


def qml_module_for(path: str, module_directories: frozenset[str]) -> str | None:
    relative = PurePosixPath(path).relative_to("PySide6/Qt/qml")
    parent = relative.parent
    while parent != PurePosixPath("."):
        candidate = parent.as_posix()
        if candidate in module_directories:
            return candidate
        parent = parent.parent
    return None


def _record(rows: Iterable[tuple[str, bytes]], record_name: str) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    for name, data in rows:
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=")
        writer.writerow((name, f"sha256={digest.decode('ascii')}", len(data)))
    writer.writerow((record_name, "", ""))
    return output.getvalue().encode("utf-8")


def prune_wheel(
    *,
    source: Path,
    output: Path,
    report: Path,
    readelf: str = "readelf",
) -> dict[str, object]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    modules = tuple(manifest["android_load_order"])
    allowed_qml = frozenset(manifest["qml_modules"])
    source_bytes = source.stat().st_size

    with zipfile.ZipFile(source) as archive, tempfile.TemporaryDirectory() as tmp:
        names = tuple(info.filename for info in archive.infolist() if not info.is_dir())
        module_directories = frozenset(
            PurePosixPath(name).parent.relative_to("PySide6/Qt/qml").as_posix()
            for name in names
            if name.startswith("PySide6/Qt/qml/") and name.endswith("/qmldir")
        )
        unknown_qml = allowed_qml - module_directories
        if unknown_qml:
            raise ValueError(f"reviewed QML modules missing from wheel: {sorted(unknown_qml)}")

        native_names = tuple(name for name in names if name.endswith(".so"))
        native_dir = Path(tmp)
        libraries: dict[str, Path] = {}
        archive.extractall(native_dir, members=native_names)
        for name in native_names:
            basename = PurePosixPath(name).name
            if basename in libraries:
                raise ValueError(f"duplicate Android native library name {basename}")
            libraries[basename] = native_dir / name

        binding_roots = {f"Qt{module}.abi3.so" for module in modules}
        binding_roots.add("libpyside6.abi3.so")
        if "Qml" in modules:
            binding_roots.add("libpyside6qml.abi3.so")
        qml_roots = {
            PurePosixPath(name).name
            for name in native_names
            if name.startswith("PySide6/Qt/qml/")
            and qml_module_for(name, module_directories) in allowed_qml
        }
        plugin_roots = {
            PurePosixPath(name).name
            for name in native_names
            if name.startswith("PySide6/Qt/plugins/")
            and any(fragment in name for fragment in ANDROID_PLUGINS)
        }
        qt_roots = {
            next(
                name
                for name in libraries
                if name.startswith(f"libQt6{module}_") and name.endswith(".so")
            )
            for module in modules
        }
        kept_native = native_closure(
            roots=binding_roots | qml_roots | plugin_roots | qt_roots,
            libraries=libraries,
            readelf=readelf,
        )

        record_names = [name for name in names if name.endswith(".dist-info/RECORD")]
        if len(record_names) != 1:
            raise ValueError(f"expected one wheel RECORD, found {record_names}")
        record_name = record_names[0]
        kept: list[tuple[str, bytes]] = []
        for name in names:
            path = PurePosixPath(name)
            basename = path.name
            keep = False
            if name == record_name:
                continue
            if name.endswith(".dist-info/METADATA") or name.endswith(".dist-info/WHEEL"):
                keep = True
            elif ".dist-info/licenses/" in name:
                keep = True
            elif path.parent == PurePosixPath("PySide6") and path.suffix == ".py":
                keep = True
            elif basename in kept_native:
                keep = True
            elif name.startswith("PySide6/Qt/qml/"):
                relative = path.relative_to("PySide6/Qt/qml")
                keep = relative.parent == PurePosixPath(".") or (
                    qml_module_for(name, module_directories) in allowed_qml
                )
            elif name.startswith("PySide6/jar/") and basename in ANDROID_JARS:
                keep = True
            elif name.startswith("PySide6/Qt/lib/") and name.endswith(
                "-android-dependencies.xml"
            ):
                keep = any(f"Qt6{module}_" in basename for module in modules)
            if keep:
                kept.append((name, archive.read(name)))

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as target:
        for name, data in sorted(kept):
            target.writestr(name, data)
        target.writestr(record_name, _record(sorted(kept), record_name))

    report_data: dict[str, object] = {
        "schema_version": 1,
        "source": source.name,
        "source_sha256": sha256(source),
        "source_bytes": source_bytes,
        "output": output.name,
        "output_sha256": sha256(output),
        "output_bytes": output.stat().st_size,
        "kept_member_count": len(kept) + 1,
        "kept_native_libraries": sorted(kept_native),
        "kept_qml_modules": sorted(allowed_qml),
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        json.dumps(report_data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report_data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--readelf", default=shutil.which("readelf") or "readelf")
    args = parser.parse_args()
    result = prune_wheel(
        source=args.source,
        output=args.output,
        report=args.report,
        readelf=args.readelf,
    )
    print(
        f"Pruned {result['source_bytes']} to {result['output_bytes']} bytes: "
        f"{args.output}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
