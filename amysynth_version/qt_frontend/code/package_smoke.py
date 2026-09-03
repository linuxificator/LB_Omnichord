from __future__ import annotations

import math
import socket
import time
from typing import Any, Callable

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest
from pythonosc.osc_message_builder import OscMessageBuilder

from midi_platform_profile import current_midi_tech_profile
from resolved_config import MidiInputConfig, OscInputConfig


_EXPECTED_MIDI_TECHNOLOGIES = {
    "linux": ("alsa_raw", "alsa_seq", "oss_midi"),
    "darwin": ("coremidi",),
    "win32": ("winmm",),
    "android": ("android_midi",),
}


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


def _wait_for(
    app: QGuiApplication,
    predicate: Callable[[], bool],
    message: str,
    *,
    timeout: float = 3.0,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        QTest.qWait(20)
    raise RuntimeError(message)


def _osc_datagram(address: str, value: bool | float) -> bytes:
    builder = OscMessageBuilder(address=address)
    builder.add_arg(value)
    return builder.build().dgram


def _verify_midi_package_input(
    player: Any,
    midi_config: MidiInputConfig,
    checkpoint: Callable[[str], None],
) -> None:
    profile = current_midi_tech_profile(midi_config.configured_profile)
    expected_midi = _EXPECTED_MIDI_TECHNOLOGIES.get(profile, ())
    technologies = list(player.midiInputTechs)
    actual_midi = tuple(
        str(item.get("key", ""))
        for item in technologies
        if str(item.get("protocol", "midi")) == "midi"
    )
    if actual_midi != expected_midi:
        raise RuntimeError(
            "packaged MIDI technology profile mismatch: "
            f"profile={profile!r}, expected={expected_midi!r}, actual={actual_midi!r}"
        )
    if profile != "linux" and any(
        str(item.get("state", "")) != "unavailable"
        for item in technologies
        if str(item.get("protocol", "midi")) == "midi"
    ):
        raise RuntimeError("an unbundled native MIDI bridge was reported as available")
    checkpoint("midi-input-profile-verified")

    # The package smoke cannot manufacture CoreMIDI/WinMM/Android hardware.
    # These public simulation slots do prove that each frozen package retains
    # the same MIDI CC/button-to-controller-model path after adapter selection.
    player.injectControl(16, 119, 24)
    player.injectControl(16, 119, 96)
    player.injectButton(16, 118, 127)
    player.injectButton(16, 118, 0)
    midi_controls = list(player.commonControls(-1))
    if not any(
        str(item.get("displayLabel", "")) == "CH16 CC119"
        and str(item.get("sourceProtocol", "")) == "midi"
        for item in midi_controls
    ):
        raise RuntimeError("packaged MIDI CC simulation did not reach the control model")
    checkpoint("midi-control-simulation-observed")
    if not any(
        str(item.get("displayLabel", "")) == "CH16 N118"
        and str(item.get("displayType", "")) == "note_button"
        and str(item.get("sourceProtocol", "")) == "midi"
        for item in midi_controls
    ):
        raise RuntimeError("packaged MIDI button simulation did not reach the control model")
    checkpoint("midi-button-simulation-observed")


def _exercise_osc_package_input(
    app: QGuiApplication,
    player: Any,
    osc_config: OscInputConfig,
    checkpoint: Callable[[str], None],
) -> None:
    if (
        not bool(osc_config.enabled)
        or not bool(osc_config.configured)
        or osc_config.listen_address is None
        or osc_config.listen_port is None
    ):
        raise RuntimeError("the shipped package has no enabled OSC listen endpoint")
    if str(player.oscInputState) != "ready":
        reason = str(player.oscInputFailureReason)
        raise RuntimeError(f"packaged OSC input is not ready: {reason}")

    listen_address = str(osc_config.listen_address)
    target_address = "127.0.0.1" if listen_address == "0.0.0.0" else listen_address
    target = (target_address, int(osc_config.listen_port))
    rotary_address = "/package-smoke/rotary"
    button_address = "/package-smoke/button"
    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # A continuous source intentionally needs a baseline and movement.
        sender.sendto(_osc_datagram(rotary_address, 0.25), target)
        QTest.qWait(20)

        def received_all() -> bool:
            sender.sendto(_osc_datagram(rotary_address, 0.75), target)
            sender.sendto(_osc_datagram(button_address, True), target)
            sender.sendto(_osc_datagram(button_address, False), target)
            controls = list(player.commonControls(-1))
            has_rotary = any(
                str(item.get("displayLabel", "")) == rotary_address
                and str(item.get("displayType", "")) == "osc"
                and str(item.get("sourceProtocol", "")) == "osc"
                for item in controls
            )
            has_button = any(
                str(item.get("displayLabel", "")) == button_address
                and str(item.get("displayType", "")) == "button"
                and str(item.get("sourceProtocol", "")) == "osc"
                for item in controls
            )
            osc_activity = any(
                str(item.get("key", "")) == "osc"
                and str(item.get("state", "")) == "activity"
                for item in player.midiInputTechs
            )
            return has_rotary and has_button and osc_activity

        _wait_for(
            app,
            received_all,
            "packaged OSC UDP input did not reach its control and activity models",
        )
    finally:
        sender.close()

    checkpoint("osc-udp-rotary-observed")
    checkpoint("osc-udp-button-observed")
    checkpoint("osc-tech-activity-observed")


def exercise_external_control_input(
    app: QGuiApplication,
    player: Any,
    midi_config: MidiInputConfig,
    osc_config: OscInputConfig,
    checkpoint: Callable[[str], None],
) -> None:
    """Exercise the packaged MIDI profile and real OSC UDP input boundary."""

    _verify_midi_package_input(player, midi_config, checkpoint)
    _exercise_osc_package_input(app, player, osc_config, checkpoint)


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
