from __future__ import annotations

import math
from typing import Any, Callable

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest


def _visual_items(item: Any) -> list[Any]:
    items = [item]
    for child in item.childItems():
        items.extend(_visual_items(child))
    return items


def exercise_chord_input(
    app: QGuiApplication,
    window: Any,
    backend: Any,
    checkpoint: Callable[[str], None],
) -> None:
    """Drive a quick tap and hold through the real packaged QML event path."""

    items = _visual_items(window.contentItem())
    button = next(
        (
            item
            for item in items
            if item.objectName() == "chordButton_0_0"
        ),
        None,
    )
    if button is None:
        chord_names = sorted(
            item.objectName()
            for item in items
            if item.objectName().startswith("chordButton_")
        )
        raise RuntimeError(
            "packaged QML chord button was not found; "
            f"available chord objects: {chord_names}"
        )

    def require(condition: bool, message: str) -> None:
        if not condition:
            raise RuntimeError(message)

    scene_position = button.mapToScene(
        QPointF(
            float(button.property("width")) / 2.0,
            float(button.property("height")) / 2.0,
        )
    ).toPoint()
    key = (0, 0)

    # Use valid full-scale application controls for the audio gate.  This is
    # still the normal LB backend and wire translation, not a raw AMY test
    # tone; it keeps quiet patches such as juno_004 above the package gate
    # without weakening that gate for every platform.
    backend.setChordVolume(1.0)
    backend.setMasterVolume(1.0)
    require(
        math.isclose(float(backend.chordVolume), 1.0, abs_tol=1e-4)
        and math.isclose(float(backend.masterVolume), 1.0, abs_tol=1e-4),
        "package smoke could not select full application audio levels",
    )
    checkpoint("smoke-audio-levels-full")

    # Make hold takeover observable without starting transport. Both chord
    # gestures below still enter exclusively through Qt/QML.
    if int(backend.chordGateState) != 1:
        backend.toggleChordGate()

    QTest.mousePress(
        window,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        scene_position,
    )
    app.processEvents()
    require(
        bool(button.property("touchActive")),
        "QML did not observe the chord-button press",
    )
    require(
        int(backend.activeRowIndex) == 0
        and int(backend.activeRootSemitone) == 0,
        "chord-button press did not select the active chord",
    )
    require(
        bool(button.property("selected")),
        "active chord did not publish its selected border state",
    )
    checkpoint("qml-chord-press-observed")
    checkpoint("active-chord-visible")

    QTest.mouseRelease(
        window,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        scene_position,
    )
    app.processEvents()
    require(
        not bool(button.property("touchActive")),
        "QML quick tap remained visually pressed after release",
    )
    require(
        key not in backend._pressed_chords,
        "quick tap did not release the manual chord",
    )
    require(
        bool(button.property("selected")),
        "active chord border disappeared after a quick tap",
    )
    checkpoint("qml-chord-tap-released")

    QTest.mousePress(
        window,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        scene_position,
    )
    QTest.qWait(
        int(app.styleHints().mousePressAndHoldInterval())
        + 100
    )
    require(
        bool(button.property("touchActive")),
        "held QML chord lost its physical pressed state",
    )
    require(
        key in backend._promoted_chords
        and int(backend.rhythmChordActivity) == 0,
        "held QML chord was not promoted to accompaniment takeover",
    )
    checkpoint("qml-chord-hold-promoted")

    QTest.mouseRelease(
        window,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        scene_position,
    )
    app.processEvents()
    require(
        not bool(button.property("touchActive")),
        "held QML chord remained visually pressed after release",
    )
    require(
        key not in backend._pressed_chords
        and int(backend.rhythmChordActivity) > 0,
        "held QML chord did not stop immediately and restore accompaniment",
    )
    checkpoint("qml-chord-hold-released")
