from __future__ import annotations

import json
import os
import pty
import subprocess
import sys
import tempfile
import time
import tty
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MidiCcQtIntegrationTests(unittest.TestCase):
    def test_real_midi_bytes_fit_bar_and_replace_true_lru(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            config_dir = temp / ".omnichord" / "config"
            config_dir.mkdir(parents=True)
            config = json.loads(
                (ROOT / "config" / "amy_config.json").read_text(encoding="utf-8")
            )
            midi_master, midi_slave = pty.openpty()
            amy_master, amy_slave = pty.openpty()
            tty.setraw(midi_slave)
            config["midi_input"]["device_glob"] = os.ttyname(midi_slave)
            config_dir.joinpath("amy_config.json").write_text(
                json.dumps(config), encoding="utf-8"
            )
            preset_dir = temp / ".omnichord" / "omni_presets"
            preset_dir.mkdir(parents=True)
            preset = json.loads(
                (
                    ROOT
                    / "instruments"
                    / "default_presets"
                    / "p1.json"
                ).read_text(encoding="utf-8")
            )
            preset["midi_control_bindings"] = [
                {
                    "channel": 1,
                    "controller": 74,
                    "target": {
                        "screen": "omni",
                        "kind": "reverb_level",
                    },
                }
            ]
            preset_dir.joinpath("p1.json").write_text(
                json.dumps(preset), encoding="utf-8"
            )
            inactive_preset = json.loads(
                (
                    ROOT
                    / "instruments"
                    / "default_presets"
                    / "p2.json"
                ).read_text(encoding="utf-8")
            )
            inactive_preset["midi_control_bindings"] = [
                {
                    "channel": 1,
                    "controller": 75,
                    "target": {
                        "screen": "omni",
                        "kind": "reverb_liveness",
                    },
                }
            ]
            preset_dir.joinpath("p2.json").write_text(
                json.dumps(inactive_preset), encoding="utf-8"
            )
            log = temp / "midi-cc.jsonl"
            env = dict(
                os.environ,
                HOME=str(temp),
                QT_QPA_PLATFORM="offscreen",
                QT_QUICK_BACKEND="software",
                OMNICHORD_TEST_MIDI_CC_LOG=str(log),
            )
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(ROOT / "code" / "main.py"),
                    "--serial-port",
                    os.ttyname(amy_slave),
                    "--software-renderer",
                ],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            try:
                deadline = time.monotonic() + 10.0
                while time.monotonic() < deadline and process.poll() is None:
                    if log.is_file() and '"event":"layout"' in log.read_text(
                        encoding="utf-8"
                    ):
                        break
                    time.sleep(0.05)

                def change(controller: int, start: int = 0) -> None:
                    os.write(
                        midi_master,
                        bytes((0xB0, controller, start, 0xB0, controller, start + 1)),
                    )

                if process.poll() is None and log.is_file():
                    change(74, 0)
                    change(75, 0)
                    for controller in range(32):
                        change(controller)
                    time.sleep(0.5)
                    change(0, 1)  # make CC0 newest before forcing another replacement
                    change(99)
                    time.sleep(0.5)
            finally:
                if process.poll() is None:
                    process.terminate()
                output, _ = process.communicate(timeout=3)
                os.close(midi_master)
                os.close(midi_slave)
                os.close(amy_master)
                os.close(amy_slave)

            self.assertNotIn("TypeError", output)
            self.assertNotIn("QQmlApplicationEngine failed", output)
            self.assertNotIn("Cannot assign to non-existent property", output)
            self.assertNotIn("Required property", output)
            self.assertTrue(log.is_file(), output)
            records = [
                json.loads(line)
                for line in log.read_text(encoding="utf-8").splitlines()
            ]
            layouts = [item for item in records if item["event"] == "layout"]
            changes = [item for item in records if item["event"] == "change"]
            indicator_states = [
                item for item in records if item["event"] == "indicator-state"
            ]
            self.assertTrue(layouts)
            self.assertTrue(indicator_states)
            full = max(layouts, key=lambda item: item["count"])
            self.assertLessEqual(full["count"], full["capacity"], full)
            self.assertLessEqual(
                full["lastRight"],
                full["barX"] + full["barWidth"],
                full,
            )
            self.assertTrue(any(item["evicted"] is not None for item in changes))
            self.assertTrue(
                any(
                    item["evicting"]
                    for record in indicator_states
                    for item in record["items"]
                )
            )
            last = changes[-1]
            self.assertEqual(last["controller"], 99)
            capacity = last["capacity"]
            self.assertEqual(last["evicted"], [1, 33 - capacity])
            applied = [item for item in records if item["event"] == "apply"]
            self.assertTrue(applied)
            self.assertEqual(
                applied[-1]["target"],
                "omni:reverb_level",
            )
            self.assertAlmostEqual(float(applied[-1]["mappedValue"]), 0.02)
            self.assertNotIn(
                "omni:reverb_liveness",
                {item["target"] for item in applied},
            )
            locations = [
                item for item in records if item["event"] == "binding-location"
            ]
            self.assertTrue(
                any(
                    item["screen"] == "omni"
                    and item["preset"] == 1
                    and item["active"]
                    for item in locations
                )
            )
            self.assertEqual(
                [
                    item
                    for item in locations
                    if (
                        item["screen"] == "omni"
                        and item["preset"] == 2
                        and not item["active"]
                    )
                ],
                [
                    {
                        "event": "binding-location",
                        "channel": 1,
                        "controller": 75,
                        "sourceType": "cc",
                        "screen": "omni",
                        "preset": 2,
                        "active": False,
                    }
                ],
            )


if __name__ == "__main__":
    unittest.main()
