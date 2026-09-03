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


def _require_slider_geometry(slider: Any, items: list[Any]) -> None:
    track = next(
        (item for item in items if item.objectName() == "sliderTrack"),
        None,
    )
    fill = next(
        (item for item in items if item.objectName() == "sliderFill"),
        None,
    )
    handle = next(
        (item for item in items if item.objectName() == "sliderHandle"),
        None,
    )
    if track is None or fill is None or handle is None:
        raise RuntimeError("packaged slider visual items were not found")

    visual = float(slider.property("visualPosition"))
    expected_fill = visual * float(track.property("width"))
    expected_handle = float(slider.property("leftPadding")) + visual * (
        float(slider.property("availableWidth"))
        - float(handle.property("width"))
    )
    if not math.isclose(
        float(fill.property("width")),
        expected_fill,
        abs_tol=0.75,
    ):
        raise RuntimeError("packaged slider fill does not follow visualPosition")
    if not math.isclose(
        float(handle.property("x")),
        expected_handle,
        abs_tol=0.75,
    ):
        raise RuntimeError("packaged slider handle does not follow visualPosition")


def exercise_slider_input(
    app: QGuiApplication,
    window: Any,
    checkpoint: Callable[[str], None],
) -> None:
    """Drag a real visible parameter slider and verify its rendered geometry."""

    items = _visual_items(window.contentItem())
    candidates = [
        item
        for item in items
        if item.objectName() == "nativeSlider"
        and item.isVisible()
        and item.isEnabled()
        and float(item.property("width")) >= 40.0
        and item.parentItem() is not None
        and str(item.parentItem().property("traceKind")) == "parameter"
    ]
    if not candidates:
        raise RuntimeError("visible packaged parameter slider was not found")

    slider = candidates[0]
    slider_items = _visual_items(slider)
    handle = next(
        (item for item in slider_items if item.objectName() == "sliderHandle"),
        None,
    )
    if handle is None:
        raise RuntimeError("packaged slider handle was not found")

    initial = float(slider.property("value"))
    minimum = float(slider.property("from"))
    maximum = float(slider.property("to"))
    span = maximum - minimum
    if not math.isfinite(span) or span <= 0.0:
        raise RuntimeError("packaged slider has an invalid range")
    initial_visual = float(slider.property("visualPosition"))
    target_visual = 0.75 if initial_visual < 0.5 else 0.25

    start = handle.mapToScene(
        QPointF(
            float(handle.property("width")) / 2.0,
            float(handle.property("height")) / 2.0,
        )
    ).toPoint()
    target_x = (
        float(slider.property("leftPadding"))
        + target_visual
        * (
            float(slider.property("availableWidth"))
            - float(handle.property("width"))
        )
        + float(handle.property("width")) / 2.0
    )
    target = slider.mapToScene(
        QPointF(target_x, float(slider.property("height")) / 2.0)
    ).toPoint()

    QTest.mousePress(
        window,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        start,
    )
    app.processEvents()
    if not bool(slider.property("pressed")):
        raise RuntimeError("packaged slider did not retain the mouse press")
    QTest.mouseMove(window, target, delay=20)
    app.processEvents()
    moved = float(slider.property("value"))
    if abs(moved - initial) < span * 0.2:
        raise RuntimeError("packaged slider value did not follow the mouse drag")
    _require_slider_geometry(slider, slider_items)
    checkpoint("qml-slider-drag-visible")

    QTest.mouseRelease(
        window,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        target,
    )
    app.processEvents()
    if not math.isclose(
        float(slider.property("value")),
        moved,
        abs_tol=max(abs(span) * 0.001, 1e-6),
    ):
        raise RuntimeError("packaged slider returned to a stale value on release")
    _require_slider_geometry(slider, slider_items)
    checkpoint("qml-slider-release-visible")


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
    hold_deadline_ms = max(
        int(app.styleHints().mousePressAndHoldInterval())
        + 1500,
        3000,
    )
    waited_ms = 0
    while (
        waited_ms < hold_deadline_ms
        and not (
            key in backend._promoted_chords
            and int(backend.rhythmChordActivity) == 0
        )
    ):
        QTest.qWait(50)
        app.processEvents()
        waited_ms += 50
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
