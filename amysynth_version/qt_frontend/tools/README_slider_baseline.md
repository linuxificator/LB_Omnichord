# Simple slider baseline

`simple_slider_baseline.py` is a diagnostic app for the slider-drag regression.

It deliberately uses only the current repository's Python/PySide6/Qt/QML stack
and a plain Qt Quick `Slider`. It does not import the LB Omnichord backend,
AMY, MIDI code, custom slider components, scaling layout, presets or release
packaging.

Run it from the Qt frontend directory with the same environment used for the
main app:

```bash
cd /home/jeroen/omnichord/LB_Omnichord/amysynth_version/qt_frontend
/home/jeroen/omnichord/omnichord-env/bin/python tools/simple_slider_baseline.py
```

If no window appears, retry with an explicit platform, matching the same
diagnostic options supported by the main app:

```bash
/home/jeroen/omnichord/omnichord-env/bin/python tools/simple_slider_baseline.py --x11
/home/jeroen/omnichord/omnichord-env/bin/python tools/simple_slider_baseline.py --wayland
```

The baseline prints the selected Qt platform and display environment before it
enters the Qt event loop. `Ctrl-C`, `Ctrl-\` and `kill` should now quit cleanly.

Baseline check:

1. Put the mouse cursor on the round slider handle.
2. Press and hold the left mouse button.
3. Drag horizontally without releasing.

Expected behavior: the handle follows the mouse continuously and the move count
increases while dragging.

Interpretation:

- If this minimal app also fails, the issue is below LB Omnichord's UI code:
  current PySide6/Qt/QML, platform plugin, compositor/input stack or environment.
- If this minimal app works, the regression is in LB Omnichord's QML/component
  structure, not in the base Qt slider.

After the plain baseline works, run the custom component baseline:

```bash
/home/jeroen/omnichord/omnichord-env/bin/python tools/custom_slider_baseline.py
```

Use the same mouse-hold-and-drag test. This version uses only
`gui/LabeledSlider.qml`. If the plain baseline works but this custom baseline
does not, the bug is in the custom slider component. If both work, the bug is in
the full Omnichord layout or one of its surrounding controls.

If both plain and custom baselines work, run the layout baseline:

```bash
/home/jeroen/omnichord/omnichord-env/bin/python tools/layout_slider_baseline.py
```

This adds the real app's outer shape: a `Flickable` viewport and scaled
`contentArea`, but still no backend, AMY or MIDI. It has an immediate-echo
slider and a delayed-echo slider. If this fails, the bug is in viewport/layout
pointer handling. If it works, the remaining suspect is full-app runtime state
feedback or another surrounding full-app control.
