from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import (
    QGuiApplication,
    QInputDevice,
    QPointingDevice,
)
from PySide6.QtQml import QQmlApplicationEngine


APP_DIR = Path(__file__).resolve().parent


def describe_devices() -> None:
    print("Qt input devices:")

    for device in QInputDevice.devices():
        maximum_points = "-"

        if isinstance(device, QPointingDevice):
            maximum_points = str(
                device.maximumPoints()
            )

        print(
            "  "
            f"name={device.name()!r} "
            f"type={device.type().name} "
            f"max_points={maximum_points} "
            f"seat={device.seatName()!r}"
        )


def main() -> int:
    app = QGuiApplication(sys.argv)
    describe_devices()

    engine = QQmlApplicationEngine()
    engine.load(
        QUrl.fromLocalFile(
            str(APP_DIR / "TouchTest.qml")
        )
    )

    if not engine.rootObjects():
        return 1

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
