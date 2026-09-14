# v3.4 fixes

## Strum input

The strum pad now uses one unified `MultiPointTouchArea` for both touchscreen
and mouse input (`mouseEnabled: true`).  The separate `TapHandler` and
`DragHandler` from v3.3 were removed so they cannot compete for the pointer
grab on Qt 6/Wayland.  Event coordinates are read directly from the point
passed with each signal.

The area is still a `MultiPointTouchArea`, not a `MouseArea`, so another touch
can continue to hold a chord elsewhere in the application while the strum
finger is active.

The existing AMY debug logger is unchanged.  A successful press on the strum
pad should immediately create `/strum/note` and `n...i2Z` records in
`~/.omnichord/amy_debug.log`.

## Slider labels

When a control is still at its untouched factory-patch sentinel value, only
the parameter name is displayed.  The uninformative `PATCH` suffix is no
longer shown.  Moving the slider still shows the numeric override value.
