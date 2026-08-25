# LB Omnichord - Failure Archive

This document records failed approaches and lessons learned. Failed approaches must not be repeated unless explicitly requested.

## AMY embedded into UI

### Symptom
A coding agent tried to integrate AMY directly into the Python/Qt application.

### Why this was wrong
The selected architecture intentionally separates UI and synth engine.

### Correct approach
Keep AMY as an independent process/component and communicate using AMY wire protocol.

---

## Android/Godot lifecycle coupling

### Symptom
Attempts were made to start/stop AMY from the client application.

### Why this was wrong
The reference design uses independent processes.

### Correct approach
Clients communicate with the running AMY service; they do not own its lifecycle.

---

## Strum debugging

### Symptom
Chords generated sound but strum produced no sound.

### Wrong direction
Changing AMY integration or replacing architecture.

### Correct direction
Verify touch/mouse event -> command generation -> wire message -> transport.

---

## Rhythm/chord interaction

### Lesson
Rhythm is continuous state. Chord changes must not unintentionally reset rhythm timing.

---

## General rule

A local bug is not evidence that the architecture is wrong. Debug the failing boundary first.
