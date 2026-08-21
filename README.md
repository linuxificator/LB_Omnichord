# LB_Omnichord

**Luciel's Birthday Omnichord** is a touchscreen chord instrument built around Sonic Pi, a Qt Quick/PySide6 user interface and OSC.

![plot](./screenshots/lb_omnichord.png)

It started from the basic Omnichord idea: one hand selects chords, the other hand plays or strums over them. I did not try to make an exact software copy of a particular Suzuki Omnichord. The useful part of the concept is the separation between chord selection and the strum surface, and from there the instrument grew into something with its own synths, bass, rhythm section, presets and tuning systems.

This version was made as a birthday gift for Luciel.

The design is deliberately split in two:

```text
Qt Quick / Python
    touch UI
    chord and preset state
    synth/rhythm configuration
    tuning calculations
           |
           | OSC, normally localhost:4560
           v
Sonic Pi
    synths
    samples
    timing
    sustained/manual chord voices
    rhythm + chord + bass scheduling
```

Above is for the sonic pi version, you can find the original sonic pi version [here](./rpi_sonic_pi_version) 
Sonic pi works with supercollider as a synth, it can be a bit resource intensive, so I'm working on an amysynth version.
