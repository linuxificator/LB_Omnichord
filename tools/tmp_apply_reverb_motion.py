#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONT = ROOT / "amysynth_version" / "qt_frontend"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one occurrence, found {count}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# ---------------------------------------------------------------------------
# defaults.json: one shared reverb, dry drums by default.
# ---------------------------------------------------------------------------
defaults_path = FRONT / "config" / "defaults.json"
defaults = json.loads(defaults_path.read_text(encoding="utf-8"))
defaults["effects"] = {
    "reverb_level": 0.0,
    "reverb_liveness": 0.5,
    "reverb_damping": 0.5,
    "reverb_drums": False,
}
defaults_path.write_text(json.dumps(defaults, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# amy_serial.py: exact-zero reverb, 3 controls, DRM bus toggle.
# ---------------------------------------------------------------------------
amy = FRONT / "code" / "amy_serial.py"
replace_once(
    amy,
    '''        self.reverb = {"main": 0.0, "percussion": 0.0}\n''',
    '''        self.reverb = {\n            "level": 0.0,\n            "liveness": 0.5,\n            "damping": 0.5,\n            "drums": False,\n        }\n''',
)
replace_once(
    amy,
    '''    _REVERB_OFF_WIRE_LEVEL = 0.001\n\n    def _apply_reverb_buses(self) -> None:\n        # Do not send h0 on a fresh engine.  On the ESP32-P4 an exact-zero\n        # reverb coefficient can produce low-frequency rumble; untouched AMY\n        # buses are already dry.\n        for lane in ("main", "percussion"):\n            level = self.reverb[lane]\n            if level > 0.0:\n                self._wire(\n                    f"y{self.bus_id[lane]}h{self._f(level)}Z"\n                )\n\n    def _set_reverb(self, lane: str, value: Any) -> None:\n        level = max(0.0, min(1.0, float(value)))\n        previous = self.reverb[lane]\n        if math.isclose(level, previous, rel_tol=0.0, abs_tol=1e-9):\n            return\n        self.reverb[lane] = level\n        bus = self.bus_id[lane]\n        wire_level = (\n            level\n            if level > 0.0\n            else self._REVERB_OFF_WIRE_LEVEL\n        )\n        self._wire(f"y{bus}h{self._f(wire_level)}Z")\n''',
    '''    def _reverb_command(self, bus: int, *, enabled: bool) -> str:\n        level = self.reverb["level"] if enabled else 0.0\n        return (\n            f"y{int(bus)}h{self._f(level)},"\n            f"{self._f(self.reverb['liveness'])},"\n            f"{self._f(self.reverb['damping'])}Z"\n        )\n\n    def _apply_reverb_buses(self) -> None:\n        # Bus 0 contains every melodic role; bus 1 contains only drums.\n        # An exact h0 is intentional: zero must be truly dry, not a small\n        # non-zero approximation.  Omitting the fourth reverb field leaves\n        # AMY's crossover setting unchanged.\n        self._wire(self._reverb_command(self.bus_id["main"], enabled=True))\n        self._wire(\n            self._reverb_command(\n                self.bus_id["percussion"],\n                enabled=bool(self.reverb["drums"]),\n            )\n        )\n\n    def _set_reverb(self, value: Any) -> None:\n        if not isinstance(value, dict):\n            return\n        updated = {\n            "level": max(0.0, min(1.0, float(value.get("level", self.reverb["level"])))),\n            "liveness": max(0.0, min(1.0, float(value.get("liveness", self.reverb["liveness"])))),\n            "damping": max(0.0, min(1.0, float(value.get("damping", self.reverb["damping"])))),\n            "drums": bool(value.get("drums", self.reverb["drums"])),\n        }\n        if updated == self.reverb:\n            return\n        self.reverb = updated\n        self._apply_reverb_buses()\n''',
)
replace_once(
    amy,
    '''        elif address == a["main_reverb"]:\n            self._set_reverb("main", value)\n        elif address == a["percussion_reverb"]:\n            self._set_reverb("percussion", value)\n''',
    '''        elif address == a["reverb"]:\n            self._set_reverb(value)\n''',
)


# ---------------------------------------------------------------------------
# main.py: one reverb state + preset values + tempo/pitch hold controls.
# ---------------------------------------------------------------------------
main = FRONT / "code" / "main.py"
replace_once(
    main,
    '''    mainReverbChanged = Signal()\n    percussionReverbChanged = Signal()\n''',
    '''    reverbLevelChanged = Signal()\n    reverbLivenessChanged = Signal()\n    reverbDampingChanged = Signal()\n    reverbDrumsIncludedChanged = Signal()\n''',
)
replace_once(
    main,
    '''        main_reverb_address: str,\n        percussion_reverb_address: str,\n''',
    '''        reverb_address: str,\n''',
)
replace_once(
    main,
    '''        self._main_reverb_address = main_reverb_address\n        self._percussion_reverb_address = percussion_reverb_address\n''',
    '''        self._reverb_address = reverb_address\n''',
)
replace_once(
    main,
    '''        effects = defaults.get("effects", {})\n        self._main_reverb = max(\n            0.0, min(1.0, float(effects.get("main_reverb", 0.0)))\n        )\n        self._percussion_reverb = max(\n            0.0, min(1.0, float(effects.get("percussion_reverb", 0.0)))\n        )\n''',
    '''        effects = defaults.get("effects", {})\n        self._reverb_level = max(\n            0.0, min(1.0, float(effects.get("reverb_level", 0.0)))\n        )\n        self._reverb_liveness = max(\n            0.0, min(1.0, float(effects.get("reverb_liveness", 0.5)))\n        )\n        self._reverb_damping = max(\n            0.0, min(1.0, float(effects.get("reverb_damping", 0.5)))\n        )\n        self._reverb_drums = bool(effects.get("reverb_drums", False))\n''',
)
replace_once(
    main,
    '''        self._rhythm_running = bool(\n            defaults["transport"]["rhythm_running"]\n        )\n\n        self._strum_last_index: int | None = None\n''',
    '''        self._rhythm_running = bool(\n            defaults["transport"]["rhythm_running"]\n        )\n\n        # Tempo nudge: 1 BPM every 100 ms = 10 BPM/s. A quick tap keeps\n        # running to a 20 BPM total change; a held button keeps going.\n        self._tempo_nudge_timer = QTimer(self)\n        self._tempo_nudge_timer.setInterval(100)\n        self._tempo_nudge_timer.timeout.connect(self._tempo_nudge_tick)\n        self._tempo_nudge_direction = 0\n        self._tempo_nudge_origin = self.rhythmTempo\n        self._tempo_nudge_pressed = False\n\n        # Pitch bend is deliberately transient. _tuning_reference remains the\n        # stored/preset A-reference; this offset returns to zero on release.\n        self._pitch_bend_timer = QTimer(self)\n        self._pitch_bend_timer.setInterval(100)\n        self._pitch_bend_timer.timeout.connect(self._pitch_bend_tick)\n        self._pitch_bend_direction = 0\n        self._pitch_bend_offset_hz = 0.0\n        self._pitch_bend_returning = False\n\n        self._strum_last_index: int | None = None\n''',
)
replace_once(
    main,
    '''    @Property(float, notify=mainReverbChanged)\n    def mainReverb(self) -> float:\n        return self._main_reverb\n\n    @Property(float, notify=percussionReverbChanged)\n    def percussionReverb(self) -> float:\n        return self._percussion_reverb\n''',
    '''    @Property(float, notify=reverbLevelChanged)\n    def reverbLevel(self) -> float:\n        return self._reverb_level\n\n    @Property(float, notify=reverbLivenessChanged)\n    def reverbLiveness(self) -> float:\n        return self._reverb_liveness\n\n    @Property(float, notify=reverbDampingChanged)\n    def reverbDamping(self) -> float:\n        return self._reverb_damping\n\n    @Property(bool, notify=reverbDrumsIncludedChanged)\n    def reverbDrumsIncluded(self) -> bool:\n        return self._reverb_drums\n''',
)
replace_once(
    main,
    '''    @Property(int, notify=tuningChanged)\n    def tuningReference(self) -> int:\n        return self._tuning_reference\n''',
    '''    @Property(int, notify=tuningChanged)\n    def tuningReference(self) -> int:\n        return int(round(self._effective_tuning_reference()))\n''',
)
replace_once(
    main,
    '''    @Slot(float)\n    def setMainReverb(self, value: float) -> None:\n        clamped = max(0.0, min(1.0, float(value)))\n        if abs(clamped - self._main_reverb) < 0.0001:\n            return\n        self._main_reverb = clamped\n        self.mainReverbChanged.emit()\n        self._client.send_message(self._main_reverb_address, clamped)\n\n    @Slot(float)\n    def setPercussionReverb(self, value: float) -> None:\n        clamped = max(0.0, min(1.0, float(value)))\n        if abs(clamped - self._percussion_reverb) < 0.0001:\n            return\n        self._percussion_reverb = clamped\n        self.percussionReverbChanged.emit()\n        self._client.send_message(self._percussion_reverb_address, clamped)\n''',
    '''    def _reverb_payload(self) -> dict[str, Any]:\n        return {\n            "level": self._reverb_level,\n            "liveness": self._reverb_liveness,\n            "damping": self._reverb_damping,\n            "drums": self._reverb_drums,\n        }\n\n    def _send_reverb_state(self) -> None:\n        self._client.send_message(self._reverb_address, self._reverb_payload())\n\n    @Slot(float)\n    def setReverbLevel(self, value: float) -> None:\n        clamped = max(0.0, min(1.0, float(value)))\n        if abs(clamped - self._reverb_level) < 0.0001:\n            return\n        self._reverb_level = clamped\n        self.reverbLevelChanged.emit()\n        self._send_reverb_state()\n\n    @Slot(float)\n    def setReverbLiveness(self, value: float) -> None:\n        clamped = max(0.0, min(1.0, float(value)))\n        if abs(clamped - self._reverb_liveness) < 0.0001:\n            return\n        self._reverb_liveness = clamped\n        self.reverbLivenessChanged.emit()\n        self._send_reverb_state()\n\n    @Slot(float)\n    def setReverbDamping(self, value: float) -> None:\n        clamped = max(0.0, min(1.0, float(value)))\n        if abs(clamped - self._reverb_damping) < 0.0001:\n            return\n        self._reverb_damping = clamped\n        self.reverbDampingChanged.emit()\n        self._send_reverb_state()\n\n    @Slot()\n    def toggleReverbDrums(self) -> None:\n        self._reverb_drums = not self._reverb_drums\n        self.reverbDrumsIncludedChanged.emit()\n        self._send_reverb_state()\n''',
)
replace_once(
    main,
    '''    def _tuning_note_offset(self) -> float:\n        # A-reference tuning is global and remains exactly as before.\n        return 12.0 * math.log2(\n            float(self._tuning_reference) / 440.0\n        )\n''',
    '''    def _effective_tuning_reference(self) -> float:\n        return max(\n            415.0,\n            min(466.0, float(self._tuning_reference) + self._pitch_bend_offset_hz),\n        )\n\n    def _tuning_note_offset(self) -> float:\n        return 12.0 * math.log2(\n            self._effective_tuning_reference() / 440.0\n        )\n''',
)
replace_once(
    main,
    '''    @Slot(int)\n    def setTuningReference(self, value: int) -> None:\n        clamped = max(415, min(466, int(value)))\n\n        if clamped == self._tuning_reference:\n            return\n\n        self._tuning_reference = clamped\n        self.tuningChanged.emit()\n        self._refresh_tuning_on_active_notes()\n''',
    '''    def _stop_pitch_bend(self) -> None:\n        self._pitch_bend_timer.stop()\n        self._pitch_bend_direction = 0\n        self._pitch_bend_returning = False\n\n    def _publish_pitch_bend(self) -> None:\n        self.tuningChanged.emit()\n        self._refresh_tuning_on_active_notes()\n\n    def _pitch_bend_tick(self) -> None:\n        previous = self._pitch_bend_offset_hz\n        if self._pitch_bend_returning:\n            if abs(previous) <= 1.0:\n                self._pitch_bend_offset_hz = 0.0\n                self._stop_pitch_bend()\n            else:\n                self._pitch_bend_offset_hz = previous - math.copysign(1.0, previous)\n        else:\n            candidate = previous + float(self._pitch_bend_direction)\n            base = float(self._tuning_reference)\n            self._pitch_bend_offset_hz = max(415.0 - base, min(466.0 - base, candidate))\n            if math.isclose(self._pitch_bend_offset_hz, previous, abs_tol=1e-9):\n                return\n        if not math.isclose(previous, self._pitch_bend_offset_hz, abs_tol=1e-9):\n            self._publish_pitch_bend()\n\n    @Slot(int)\n    def beginPitchBend(self, direction: int) -> None:\n        direction = 1 if int(direction) > 0 else -1\n        self._pitch_bend_direction = direction\n        self._pitch_bend_returning = False\n        if not self._pitch_bend_timer.isActive():\n            self._pitch_bend_timer.start()\n\n    @Slot()\n    def endPitchBend(self) -> None:\n        self._pitch_bend_direction = 0\n        if math.isclose(self._pitch_bend_offset_hz, 0.0, abs_tol=1e-9):\n            self._stop_pitch_bend()\n            return\n        self._pitch_bend_returning = True\n        if not self._pitch_bend_timer.isActive():\n            self._pitch_bend_timer.start()\n\n    @Slot(int)\n    def setTuningReference(self, value: int) -> None:\n        clamped = max(415, min(466, int(value)))\n        self._stop_pitch_bend()\n        self._pitch_bend_offset_hz = 0.0\n\n        if clamped == self._tuning_reference:\n            self.tuningChanged.emit()\n            return\n\n        self._tuning_reference = clamped\n        self.tuningChanged.emit()\n        self._refresh_tuning_on_active_notes()\n''',
)
replace_once(
    main,
    '''        effects: dict[str, float] = {}\n        if abs(self._main_reverb) > 1e-9:\n            effects["main_reverb"] = self._main_reverb\n        if abs(self._percussion_reverb) > 1e-9:\n            effects["percussion_reverb"] = self._percussion_reverb\n        if effects:\n            snapshot["effects"] = effects\n        return snapshot\n''',
    '''        snapshot["effects"] = {\n            "reverb_level": self._reverb_level,\n            "reverb_liveness": self._reverb_liveness,\n            "reverb_damping": self._reverb_damping,\n            "reverb_drums": self._reverb_drums,\n        }\n        return snapshot\n''',
)
replace_once(
    main,
    '''        effects = self._defaults.get("effects", {})\n        self._main_reverb = max(\n            0.0, min(1.0, float(effects.get("main_reverb", 0.0)))\n        )\n        self._percussion_reverb = max(\n            0.0, min(1.0, float(effects.get("percussion_reverb", 0.0)))\n        )\n''',
    '''        effects = self._defaults.get("effects", {})\n        self._reverb_level = max(0.0, min(1.0, float(effects.get("reverb_level", 0.0))))\n        self._reverb_liveness = max(0.0, min(1.0, float(effects.get("reverb_liveness", 0.5))))\n        self._reverb_damping = max(0.0, min(1.0, float(effects.get("reverb_damping", 0.5))))\n        self._reverb_drums = bool(effects.get("reverb_drums", False))\n''',
)
replace_once(
    main,
    '''        effects = data.get("effects", {})\n        if not isinstance(effects, dict):\n            effects = {}\n        default_effects = self._defaults.get("effects", {})\n        self._main_reverb = max(\n            0.0,\n            min(\n                1.0,\n                float(effects.get("main_reverb", default_effects.get("main_reverb", 0.0))),\n            ),\n        )\n        self._percussion_reverb = max(\n            0.0,\n            min(\n                1.0,\n                float(\n                    effects.get(\n                        "percussion_reverb",\n                        default_effects.get("percussion_reverb", 0.0),\n                    )\n                ),\n            ),\n        )\n''',
    '''        effects = data.get("effects", {})\n        if not isinstance(effects, dict):\n            effects = {}\n        default_effects = self._defaults.get("effects", {})\n        legacy_main = effects.get("main_reverb", default_effects.get("reverb_level", 0.0))\n        legacy_drum = effects.get("percussion_reverb", 0.0)\n        self._reverb_level = max(0.0, min(1.0, float(effects.get("reverb_level", legacy_main))))\n        self._reverb_liveness = max(0.0, min(1.0, float(effects.get("reverb_liveness", default_effects.get("reverb_liveness", 0.5)))))\n        self._reverb_damping = max(0.0, min(1.0, float(effects.get("reverb_damping", default_effects.get("reverb_damping", 0.5)))))\n        self._reverb_drums = bool(effects.get("reverb_drums", float(legacy_drum) > 0.0))\n''',
)
replace_once(
    main,
    '''        self.mainReverbChanged.emit()\n        self.percussionReverbChanged.emit()\n''',
    '''        self.reverbLevelChanged.emit()\n        self.reverbLivenessChanged.emit()\n        self.reverbDampingChanged.emit()\n        self.reverbDrumsIncludedChanged.emit()\n''',
)
replace_once(
    main,
    '''    @Slot(int)\n    def setRhythmIndex(self, rhythm_index: int) -> None:\n        if not 0 <= rhythm_index < len(self._rhythms):\n            return\n''',
    '''    @Slot(int)\n    def setRhythmIndex(self, rhythm_index: int) -> None:\n        self._stop_tempo_nudge()\n        if not 0 <= rhythm_index < len(self._rhythms):\n            return\n''',
)
replace_once(
    main,
    '''    @Slot(float)\n    def setRhythmTempo(self, value: float) -> None:\n        clamped = max(\n            40.0,\n            min(200.0, float(value)),\n        )\n\n        index = self._rhythm.selected_index\n        if abs(\n            clamped - self._rhythm.tempo_by_rhythm[index]\n        ) < 0.0001:\n            return\n\n        self._rhythm.tempo_by_rhythm[index] = clamped\n        self.rhythmControlsChanged.emit()\n        self._send_rhythm_config()\n''',
    '''    def _set_rhythm_tempo_value(self, value: float) -> bool:\n        clamped = max(40.0, min(200.0, float(value)))\n        index = self._rhythm.selected_index\n        if abs(clamped - self._rhythm.tempo_by_rhythm[index]) < 0.0001:\n            return False\n        self._rhythm.tempo_by_rhythm[index] = clamped\n        self.rhythmControlsChanged.emit()\n        self._send_rhythm_config()\n        return True\n\n    def _stop_tempo_nudge(self) -> None:\n        self._tempo_nudge_timer.stop()\n        self._tempo_nudge_direction = 0\n        self._tempo_nudge_pressed = False\n\n    def _tempo_nudge_tick(self) -> None:\n        current = self.rhythmTempo\n        changed = self._set_rhythm_tempo_value(\n            current + float(self._tempo_nudge_direction)\n        )\n        moved = abs(self.rhythmTempo - self._tempo_nudge_origin)\n        if (not changed) or (not self._tempo_nudge_pressed and moved >= 20.0 - 1e-9):\n            self._stop_tempo_nudge()\n\n    @Slot(int)\n    def beginTempoNudge(self, direction: int) -> None:\n        self._stop_tempo_nudge()\n        self._tempo_nudge_direction = 1 if int(direction) > 0 else -1\n        self._tempo_nudge_origin = self.rhythmTempo\n        self._tempo_nudge_pressed = True\n        self._tempo_nudge_timer.start()\n\n    @Slot()\n    def endTempoNudge(self) -> None:\n        if self._tempo_nudge_direction == 0:\n            return\n        self._tempo_nudge_pressed = False\n        if abs(self.rhythmTempo - self._tempo_nudge_origin) >= 20.0 - 1e-9:\n            self._stop_tempo_nudge()\n\n    @Slot(float)\n    def setRhythmTempo(self, value: float) -> None:\n        self._stop_tempo_nudge()\n        self._set_rhythm_tempo_value(value)\n''',
)
replace_once(
    main,
    '''        self._tuning_reference = max(\n            415,\n            min(466, int(tuning.get("reference_hz", DEFAULT_TUNING_REFERENCE))),\n        )\n''',
    '''        self._tuning_reference = max(\n            415,\n            min(466, int(tuning.get("reference_hz", DEFAULT_TUNING_REFERENCE))),\n        )\n        self._stop_pitch_bend()\n        self._pitch_bend_offset_hz = 0.0\n        self._stop_tempo_nudge()\n''',
)
# The later preset tuning load also needs to clear any temporary bend.
replace_once(
    main,
    '''            self._tuning_reference = max(\n                415,\n                min(\n                    466,\n                    int(\n                        tuning.get(\n                            "reference_hz",\n                            self._tuning_reference,\n                        )\n                    ),\n                ),\n            )\n\n        # Performance-state notes are deliberately never part of a preset.\n''',
    '''            self._tuning_reference = max(\n                415,\n                min(\n                    466,\n                    int(\n                        tuning.get(\n                            "reference_hz",\n                            self._tuning_reference,\n                        )\n                    ),\n                ),\n            )\n        self._stop_pitch_bend()\n        self._pitch_bend_offset_hz = 0.0\n        self._stop_tempo_nudge()\n\n        # Performance-state notes are deliberately never part of a preset.\n''',
)
replace_once(
    main,
    '''        self._client.send_message(\n            self._main_reverb_address,\n            self._main_reverb,\n        )\n        self._client.send_message(\n            self._percussion_reverb_address,\n            self._percussion_reverb,\n        )\n''',
    '''        self._send_reverb_state()\n''',
)
replace_once(
    main,
    '''    parser.add_argument(\n        "--main-reverb-address",\n        default="/effects/main/reverb",\n    )\n    parser.add_argument(\n        "--percussion-reverb-address",\n        default="/effects/percussion/reverb",\n    )\n''',
    '''    parser.add_argument(\n        "--reverb-address",\n        default="/effects/reverb",\n    )\n''',
)
replace_once(
    main,
    '''        "main_reverb": args.main_reverb_address,\n        "percussion_reverb": args.percussion_reverb_address,\n''',
    '''        "reverb": args.reverb_address,\n''',
)
replace_once(
    main,
    '''        main_reverb_address=args.main_reverb_address,\n        percussion_reverb_address=args.percussion_reverb_address,\n''',
    '''        reverb_address=args.reverb_address,\n''',
)


# ---------------------------------------------------------------------------
# Headless integration entry point follows the production address contract.
# ---------------------------------------------------------------------------
headless = FRONT / "tests" / "integration" / "headless_app.py"
replace_once(
    headless,
    '''        "main_reverb": args.main_reverb_address,\n        "percussion_reverb": args.percussion_reverb_address,\n''',
    '''        "reverb": args.reverb_address,\n''',
)
replace_once(
    headless,
    '''        main_reverb_address=args.main_reverb_address,\n        percussion_reverb_address=args.percussion_reverb_address,\n''',
    '''        reverb_address=args.reverb_address,\n''',
)


# ---------------------------------------------------------------------------
# UtilitySection: orange area extends into the left rail.
# ---------------------------------------------------------------------------
utility = FRONT / "gui" / "UtilitySection.qml"
replace_once(
    utility,
    '''    required property bool fullScreen\n\n    signal toggleFullscreenRequested()\n''',
    '''    required property bool fullScreen\n    property int leftExtension: 0\n\n    signal toggleFullscreenRequested()\n''',
)
replace_once(
    utility,
    '''    Rectangle {\n        x: 0\n        y: 0\n        width: root.tuningX + root.tuningWidth\n''',
    '''    Rectangle {\n        x: -root.leftExtension\n        y: 0\n        width: root.leftExtension + root.tuningX + root.tuningWidth\n''',
)


# ---------------------------------------------------------------------------
# Main.qml: header reverb panel, title space, orange/yellow left extensions,
# and stacked hold buttons.
# ---------------------------------------------------------------------------
qml = FRONT / "gui" / "Main.qml"
replace_once(
    qml,
    '''                Text {\n                    anchors.fill: parent\n                    anchors.leftMargin: 16\n                    anchors.rightMargin: 16\n\n                    text: headerTitleText\n''',
    '''                ReverbPanel {\n                    id: reverbPanel\n                    x: 0\n                    y: 0\n                    width: 360\n                    height: parent.height\n                    controller: backend\n                }\n\n                Text {\n                    x: reverbPanel.width + 12\n                    y: 0\n                    width: Math.max(0, window.strumX - x - 12)\n                    height: parent.height\n\n                    text: headerTitleText\n''',
)
# Remove the old two vertical reverb rail controls.
old_rail_start = '''            Rectangle {\n                x: 0\n                y: window.utilityY\n                width: window.leftRailWidth\n                height:\n                    window.sectionHeight * 2\n                    + window.sectionGap\n                radius: 12\n                color: "#f7dce6"\n                border.color: "#c98da5"\n                border.width: 1\n            }\n\n            VerticalVolume {\n                x: (window.leftRailWidth - window.leftSliderWidth) / 2\n                y: window.utilityY\n                width: window.leftSliderWidth\n                height: window.sectionHeight\n                currentValue: backend.mainReverb\n                panelColor: "#f2c8d8"\n                panelBorderColor: "#bd839b"\n                fillColor: "#d87fa5"\n                textColor: "#5c2840"\n                onEdited: (value) => backend.setMainReverb(value)\n            }\n\n            VerticalVolume {\n                x: (window.leftRailWidth - window.leftSliderWidth) / 2\n                y: window.rhythmY\n                width: window.leftSliderWidth\n                height: window.sectionHeight\n                currentValue: backend.percussionReverb\n                panelColor: "#f2c8d8"\n                panelBorderColor: "#bd839b"\n                fillColor: "#d87fa5"\n                textColor: "#5c2840"\n                onEdited: (value) => backend.setPercussionReverb(value)\n            }\n\n            Text {\n                x: 2\n                y: window.utilityY + 2\n                width: window.leftRailWidth - 4\n                text: "REV"\n                color: "#6b3048"\n                font.pixelSize: 9\n                font.bold: true\n                horizontalAlignment: Text.AlignHCenter\n            }\n\n            Text {\n                x: 2\n                y: window.rhythmY + 2\n                width: window.leftRailWidth - 4\n                text: "DRM REV"\n                color: "#6b3048"\n                font.pixelSize: 9\n                font.bold: true\n                horizontalAlignment: Text.AlignHCenter\n            }\n\n'''
replace_once(qml, old_rail_start, '')
replace_once(
    qml,
    '''                fullScreen:\n                    window.visibility\n                    === Window.FullScreen\n\n                onToggleFullscreenRequested:\n                    window.toggleFullscreenMode()\n            }\n''',
    '''                fullScreen:\n                    window.visibility\n                    === Window.FullScreen\n                leftExtension: window.leftRailWidth\n\n                onToggleFullscreenRequested:\n                    window.toggleFullscreenMode()\n            }\n\n            PresetResetButton {\n                x: (window.leftRailWidth - width) / 2\n                y: window.utilityY + 7\n                width: 42\n                height: 42\n                text: "UP"\n                panelColor: "#efb05c"\n                borderColor: "#a75d0a"\n                textColor: "#492606"\n                onPressedChanged: {\n                    if (pressed) backend.beginPitchBend(1)\n                    else backend.endPitchBend()\n                }\n            }\n\n            PresetResetButton {\n                x: (window.leftRailWidth - width) / 2\n                y: window.utilityY + window.sectionHeight - height - 7\n                width: 42\n                height: 42\n                text: "DWN"\n                panelColor: "#efb05c"\n                borderColor: "#a75d0a"\n                textColor: "#492606"\n                onPressedChanged: {\n                    if (pressed) backend.beginPitchBend(-1)\n                    else backend.endPitchBend()\n                }\n            }\n''',
)
replace_once(
    qml,
    '''            // Yellow ends at the percussion-volume control.\n            Rectangle {\n                x: window.contentX\n                y: window.rhythmY\n                width:\n                    window.volumeX\n                    + window.volumeWidth\n                    - window.contentX\n''',
    '''            // Yellow rhythm/drum family extends through the left control rail.\n            Rectangle {\n                x: 0\n                y: window.rhythmY\n                width:\n                    window.volumeX\n                    + window.volumeWidth\n''',
)
replace_once(
    qml,
    '''                InstrumentWatermarks {\n                    anchors.fill: parent\n                    family: "percussion"\n                    ink: "#b49317"\n                }\n            }\n\n            // Neutral grey bass-synth family, including B VOL.\n''',
    '''                InstrumentWatermarks {\n                    anchors.fill: parent\n                    family: "percussion"\n                    ink: "#b49317"\n                }\n            }\n\n            PresetResetButton {\n                x: (window.leftRailWidth - width) / 2\n                y: window.rhythmY + 7\n                width: 42\n                height: 42\n                text: "UP"\n                panelColor: "#f4dc78"\n                borderColor: "#aa8719"\n                textColor: "#4c3505"\n                onPressedChanged: {\n                    if (pressed) backend.beginTempoNudge(1)\n                    else backend.endTempoNudge()\n                }\n            }\n\n            PresetResetButton {\n                x: (window.leftRailWidth - width) / 2\n                y: window.rhythmY + window.sectionHeight - height - 7\n                width: 42\n                height: 42\n                text: "DWN"\n                panelColor: "#f4dc78"\n                borderColor: "#aa8719"\n                textColor: "#4c3505"\n                onPressedChanged: {\n                    if (pressed) backend.beginTempoNudge(-1)\n                    else backend.endTempoNudge()\n                }\n            }\n\n            // Neutral grey bass-synth family, including B VOL.\n''',
)


# ---------------------------------------------------------------------------
# Serial regression: exact zero and DRM routing.
# ---------------------------------------------------------------------------
serial_test = FRONT / "tests" / "integration" / "test_serial.py"
replace_once(
    serial_test,
    '''    def test_cold_start_guards_synth4_and_zero_reverb_is_not_sent(self) -> None:\n        with HeadlessApp(native_amy=False) as app:\n            app.bridge.wait_idle(timeout=10.0)\n            records = app.bridge.timed_lines()\n            lines = [line for line, _ in records]\n\n            self.assertNotIn("y0h0Z", lines)\n            self.assertNotIn("y1h0Z", lines)\n\n            k4_index = next(\n                i for i, line in enumerate(lines)\n                if line.startswith("K") and "i4iv" in line\n            )\n            next_synth4_index = next(\n                i for i in range(k4_index + 1, len(lines))\n                if "i4" in lines[i]\n            )\n            elapsed = records[next_synth4_index][1] - records[k4_index][1]\n            self.assertGreaterEqual(\n                elapsed,\n                0.008,\n                f"synth 4 post-allocation command arrived after only {elapsed:.4f}s",\n            )\n\n            start = app.bridge.count()\n            app.action("setPercussionReverb", 0.05)\n            app.bridge.wait_for_lines(["y1h0.05Z"], start=start, timeout=5.0)\n            start = app.bridge.count()\n            app.action("setPercussionReverb", 0.0)\n            app.bridge.wait_for_lines(["y1h0.001Z"], start=start, timeout=5.0)\n            self.assertEqual(float(app.query("percussionReverb")), 0.0)\n''',
    '''    def test_cold_start_guards_synth4_and_reverb_zero_is_exact(self) -> None:\n        with HeadlessApp(native_amy=False) as app:\n            app.bridge.wait_idle(timeout=10.0)\n            records = app.bridge.timed_lines()\n            lines = [line for line, _ in records]\n\n            self.assertIn("y0h0,0.5,0.5Z", lines)\n            self.assertIn("y1h0,0.5,0.5Z", lines)\n            self.assertFalse(any("h0.001" in line for line in lines))\n\n            k4_index = next(\n                i for i, line in enumerate(lines)\n                if line.startswith("K") and "i4iv" in line\n            )\n            next_synth4_index = next(\n                i for i in range(k4_index + 1, len(lines))\n                if "i4" in lines[i]\n            )\n            elapsed = records[next_synth4_index][1] - records[k4_index][1]\n            self.assertGreaterEqual(\n                elapsed,\n                0.008,\n                f"synth 4 post-allocation command arrived after only {elapsed:.4f}s",\n            )\n\n            start = app.bridge.count()\n            app.action("setReverbLevel", 0.4)\n            app.bridge.wait_for_lines(\n                ["y0h0.4,0.5,0.5Z", "y1h0,0.5,0.5Z"],\n                start=start, timeout=5.0,\n            )\n            self.assertFalse(bool(app.query("reverbDrumsIncluded")))\n\n            start = app.bridge.count()\n            app.action("toggleReverbDrums")\n            app.bridge.wait_for_lines(\n                ["y1h0.4,0.5,0.5Z"], start=start, timeout=5.0\n            )\n            self.assertTrue(bool(app.query("reverbDrumsIncluded")))\n\n            start = app.bridge.count()\n            app.action("setReverbLevel", 0.0)\n            app.bridge.wait_for_lines(\n                ["y0h0,0.5,0.5Z", "y1h0,0.5,0.5Z"],\n                start=start, timeout=5.0,\n            )\n            self.assertEqual(float(app.query("reverbLevel")), 0.0)\n''',
)

for path in (amy, main, headless):
    compile(path.read_text(encoding="utf-8"), str(path), "exec")

print("reverb/motion patch applied")
