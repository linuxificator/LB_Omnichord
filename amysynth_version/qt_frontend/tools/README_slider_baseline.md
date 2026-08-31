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
