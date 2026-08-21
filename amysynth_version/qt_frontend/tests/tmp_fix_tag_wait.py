#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

TEST = Path(__file__).resolve().parent / "integration" / "test_serial.py"
text = TEST.read_text(encoding="utf-8")
old = '''            start = app.bridge.count()\n            app.action("pressChord", 0, 0)\n            app.bridge.wait_idle(timeout=8.0)\n            delta = app.bridge.lines_since(start)\n\n            self.assertNotIn("zY0Z", delta)\n            self.assertNotIn("S4096Z", delta)\n            self.assertNotIn("zY1Z", delta)\n            cancellations = [line for line in delta if line.startswith("H0,0,")]\n            self.assertTrue(cancellations, delta)\n'''
new = '''            start = app.bridge.count()\n            app.action("pressChord", 0, 0)\n            # The localhost API returns before the asynchronous UART writer has\n            # necessarily emitted anything. Wait for the actual manual press,\n            # then for the targeted chord-tag clears; an idle-age heuristic can\n            # otherwise return while the output delta is still empty.\n            app.bridge.wait_for_lines(["l0i3Z"], start=start, timeout=8.0)\n            deadline = time.monotonic() + 8.0\n            while time.monotonic() < deadline:\n                delta = app.bridge.lines_since(start)\n                cancellations = [\n                    line for line in delta if line.startswith("H0,0,")\n                ]\n                if cancellations:\n                    break\n                time.sleep(0.01)\n            else:\n                self.fail(\n                    "manual chord hold did not clear the automatic-chord tag range; "\n                    "received:\\n" + "\\n".join(app.bridge.lines_since(start))\n                )\n            app.bridge.wait_idle(timeout=8.0)\n            delta = app.bridge.lines_since(start)\n\n            self.assertNotIn("zY0Z", delta)\n            self.assertNotIn("S4096Z", delta)\n            self.assertNotIn("zY1Z", delta)\n            cancellations = [line for line in delta if line.startswith("H0,0,")]\n            self.assertTrue(cancellations, delta)\n'''
count = text.count(old)
if count != 1:
    raise SystemExit(f"expected one serial wait block, found {count}")
TEST.write_text(text.replace(old, new, 1), encoding="utf-8")
compile(TEST.read_text(encoding="utf-8"), str(TEST), "exec")
