from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtWidgets import QApplication, QFileDialog


SAMPLE_DIRECTORY_NAME = "VSCO-2-CE"


def choose_sample_root(default_root: Path) -> Path | None:
    """Ask for a parent directory through Qt's platform-native dialog."""

    suggested = default_root.expanduser().resolve()
    initial_parent = suggested.parent
    application = QApplication.instance()
    owns_application = application is None
    if application is None:
        application = QApplication(["LB Omnichord sample location"])
    selected = QFileDialog.getExistingDirectory(
        None,
        "Choose the parent folder for LB Omnichord samples",
        str(initial_parent),
        QFileDialog.Option.ShowDirsOnly,
    )
    if owns_application:
        application.quit()
    if not selected:
        return None
    return Path(selected).expanduser().resolve() / SAMPLE_DIRECTORY_NAME


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 1:
        print("usage: sample_location_dialog.py DEFAULT_SAMPLE_ROOT", file=sys.stderr)
        return 2
    selected = choose_sample_root(Path(arguments[0]))
    if selected is None:
        return 3
    print(selected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
