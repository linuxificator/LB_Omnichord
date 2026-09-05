#!/usr/bin/env python3
"""Generate the complete AMY balance sweep and analyse captured WAV files.

The plan is transport-neutral and can be replayed against the pinned native
AMY service or the ESP32-P4 serial target. One WAV per plan item is expected.
"""
from __future__ import annotations

import argparse
import json
import math
import struct
import wave
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
NOTES = (40, 60, 84)


def build_plan() -> list[dict[str, object]]:
    catalog = json.loads((ROOT / "instruments" / "synths.json").read_text())
    config = json.loads((ROOT / "config" / "amy_config.json").read_text())
    synths = list(catalog["synths"])
    synths.append({"key": "physical_strings", "label": "Ph. Strings"})
    compatibility = config.get("patch_compatibility", {})
    instrument_levels = config.get("instrument_levels", {})
    from amy_transport import AmySerialClient
    from config_loader import load_resolved_amy_config
    command_builder = AmySerialClient.__new__(AmySerialClient)
    command_builder.resolved_config = load_resolved_amy_config(
        ROOT / "config" / "amy_config.json"
    )
    command_builder.patch_map = {
        **{f"juno_{patch:03d}": patch for patch in range(128)},
        **{f"dx7_{patch:03d}": patch for patch in range(128, 256)},
    }
    command_builder.selected_synth = {"strum": ""}
    command_builder.synth_params = {"strum": {}}
    plan = []
    for definition in synths:
        key = str(definition["key"])
        if key.startswith("juno_"):
            patch = int(key[5:])
        elif key.startswith("dx7_"):
            patch = int(key[4:])
        else:
            patch = None
        setup = (
            ["i2iv2in1iy2Z", "v0w6b0.985i2Z", "i2iy2Z"]
            if patch is None
            else [f"K{patch}i2iv2iy2Z"]
        )
        multiplier = float(instrument_levels.get(key, 1.0))
        setup.append(f"i2iV{0.5 * multiplier:.9g}Z")
        if patch is not None:
            setup.extend(command_builder._patch_compatibility_commands(patch, 2))
            params = {}
            for control in definition.get("controls", []):
                native = control.get("native_default")
                if native is not None and not math.isclose(
                    float(control["default"]), float(native), abs_tol=1e-9
                ):
                    params[str(control["key"])] = float(control["default"])
            command_builder.selected_synth["strum"] = key
            command_builder.synth_params["strum"] = params
            setup.extend(command_builder._param_commands_for_synth("strum", 2))
        plan.append({
            "key": key,
            "label": definition["label"],
            "setup": setup,
            "compatibility": compatibility.get(str(patch), {}),
            "notes": [
                {
                    "note": note,
                    "level": 0.5 * multiplier * (
                        1.0
                        + (
                            float(config["synth_programs"]["physical_strings"].get("high_note_gain", 1.0)) - 1.0
                        ) * max(0.0, min(1.0, (note - 60) / 36.0))
                        if key == "physical_strings" else 1.0
                    ),
                    "on": f"n{note}l1i2Z",
                    "off": f"n{note}l0i2Z",
                }
                for note in NOTES
            ],
            "wav": f"{key}.wav",
        })
    return plan


def render_plan(plan: list[dict[str, object]], wav_dir: Path) -> dict[str, object]:
    import amy
    import numpy as np

    wav_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {}
    for item in plan:
        amy.send_wire("r0Z")
        amy.render(0.05)
        for command in item["setup"]:
            amy.send_wire(str(command))
        amy.render(0.05)
        sections = []
        metrics = {}
        for note in item["notes"]:
            amy.send_wire(f"i2iV{note['level']:.9g}Z")
            amy.send_wire(str(note["on"]))
            audio = amy.render(1.0)
            amy.send_wire(str(note["off"]))
            tail = amy.render(0.35)
            section = np.concatenate((audio, tail), axis=0)
            sections.append(section)
            peak = float(np.max(np.abs(section)))
            rms = float(np.sqrt(np.mean(section * section)))
            metrics[str(note["note"])] = {
                "rms_dbfs": round(20 * math.log10(max(rms, 1e-12)), 3),
                "peak_dbfs": round(20 * math.log10(max(peak, 1e-12)), 3),
                "crest_db": round(20 * math.log10(max(peak / max(rms, 1e-12), 1e-12)), 3),
                "clipped_samples": int(np.count_nonzero(np.abs(section) >= 0.999969)),
            }
        combined = np.concatenate(sections, axis=0)
        pcm = np.asarray(np.clip(combined, -1.0, 0.999969) * 32768.0, dtype="<i2")
        path = wav_dir / str(item["wav"])
        with wave.open(str(path), "wb") as target:
            target.setnchannels(2)
            target.setsampwidth(2)
            target.setframerate(44100)
            target.writeframes(pcm.tobytes())
        report[str(item["key"])] = metrics
    return report


def wav_metrics(path: Path) -> dict[str, float | int]:
    with wave.open(str(path), "rb") as source:
        width = source.getsampwidth()
        if width != 2:
            raise ValueError(f"{path}: expected 16-bit PCM, got {width * 8}-bit")
        raw = source.readframes(source.getnframes())
    samples = struct.unpack(f"<{len(raw) // 2}h", raw)
    peak = max((abs(value) for value in samples), default=0) / 32768.0
    rms = math.sqrt(sum(value * value for value in samples) / max(1, len(samples))) / 32768.0
    return {
        "rms_dbfs": round(20 * math.log10(max(rms, 1e-12)), 3),
        "peak_dbfs": round(20 * math.log10(max(peak, 1e-12)), 3),
        "crest_db": round(20 * math.log10(max(peak / max(rms, 1e-12), 1e-12)), 3),
        "clipped_samples": sum(abs(value) >= 32767 for value in samples),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=Path("instrument-balance-plan.json"))
    parser.add_argument("--wav-dir", type=Path)
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--report", type=Path, default=Path("instrument-balance-report.json"))
    args = parser.parse_args()
    plan = build_plan()
    args.plan.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    if args.render:
        if not args.wav_dir:
            parser.error("--render requires --wav-dir")
        report = render_plan(plan, args.wav_dir)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    elif args.wav_dir:
        report = {
            item["key"]: wav_metrics(args.wav_dir / str(item["wav"]))
            for item in plan
        }
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
