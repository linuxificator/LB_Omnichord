#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONT = ROOT / "amysynth_version" / "qt_frontend"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one occurrence, found {count}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


amy = FRONT / "code" / "amy_serial.py"
replace_once(
    amy,
    '''\n\nclass _TaggedSequencerLane:\n''',
    '''\n\nclass _LocalAmyWriter(_SerialWriter):\n    """Use the same priority/generation queue against in-process AMY."""\n\n    def __init__(self, debug_log: _DebugLog | None = None) -> None:\n        from collections import deque\n\n        try:\n            import amy as amy_module  # type: ignore\n            import c_amy  # type: ignore\n        except ImportError as exc:\n            raise RuntimeError(\n                "Local AMY mode requires the upstream AMY Python package; "\n                "install it into this virtual environment with `pip install .` "\n                "from a shorepine/amy checkout."\n            ) from exc\n\n        self.debug_log = debug_log\n        self._amy = amy_module\n        self._c_amy = c_amy\n        # Current upstream live() owns the platform audio backend. Do not load\n        # AMY's default MIDI synths: the Omnichord allocates its own synths 0..4.\n        self._amy.live(default_synths=0)\n\n        self._high = deque()\n        self._low = deque()\n        self._lane_generation: dict[str, int] = {}\n        self._closed = False\n        self._condition = threading.Condition()\n        self._thread = threading.Thread(\n            target=self._run,\n            name="amy-local-writer",\n            daemon=True,\n        )\n        self._thread.start()\n\n    def _write(self, command: str, lane: str) -> None:\n        command = command.strip()\n        if not command.endswith("Z"):\n            command += "Z"\n        if self.debug_log is not None:\n            self.debug_log.write(f"TX-{lane}", command)\n        self._amy.send_wire(command)\n\n    def close(self) -> None:\n        with self._condition:\n            if self._closed:\n                return\n            for lane in list(self._lane_generation):\n                self._lane_generation[lane] += 1\n            self._low.clear()\n            self._closed = True\n            self._condition.notify_all()\n\n        self._thread.join(timeout=1.0)\n        self._c_amy.stop()\n\n\nclass _TaggedSequencerLane:\n''',
)
replace_once(
    amy,
    '''    def __init__(\n        self,\n        config: dict[str, Any],\n        addresses: dict[str, str],\n    ) -> None:\n''',
    '''    def __init__(\n        self,\n        config: dict[str, Any],\n        addresses: dict[str, str],\n        *,\n        writer_factory: Any | None = None,\n    ) -> None:\n''',
)
replace_once(
    amy,
    '''        serial_cfg = config["serial"]\n        self.writer = _SerialWriter(\n            str(serial_cfg["port"]),\n            int(serial_cfg["baud"]),\n            float(serial_cfg.get("write_timeout", 0.5)),\n            self.debug_log,\n        )\n''',
    '''        if writer_factory is None:\n            serial_cfg = config["serial"]\n            self.writer = _SerialWriter(\n                str(serial_cfg["port"]),\n                int(serial_cfg["baud"]),\n                float(serial_cfg.get("write_timeout", 0.5)),\n                self.debug_log,\n            )\n        else:\n            self.writer = writer_factory(self.debug_log)\n''',
)
text = amy.read_text(encoding="utf-8")
if "class AmyLocalClient(" not in text:
    text += '''\n\nclass AmyLocalClient(AmySerialClient):\n    """Run the unchanged Omnichord wire backend against local desktop AMY."""\n\n    def __init__(\n        self,\n        config: dict[str, Any],\n        addresses: dict[str, str],\n    ) -> None:\n        super().__init__(\n            config=config,\n            addresses=addresses,\n            writer_factory=_LocalAmyWriter,\n        )\n'''
    amy.write_text(text, encoding="utf-8")

main = FRONT / "code" / "main.py"
replace_once(
    main,
    '''from amy_serial import AmySerialClient, load_amy_config\n''',
    '''from amy_serial import AmyLocalClient, AmySerialClient, load_amy_config\n''',
)
replace_once(
    main,
    '''    parser.add_argument(\n        "--serial-baud",\n        type=int,\n        default=None,\n        help="Override serial.baud from amy_config.json.",\n    )\n\n    window_group = parser.add_mutually_exclusive_group()\n''',
    '''    parser.add_argument(\n        "--serial-baud",\n        type=int,\n        default=None,\n        help="Override serial.baud from amy_config.json.",\n    )\n    parser.add_argument(\n        "--local-amy",\n        action="store_true",\n        help=(\n            "Run AMY in this Python process using the installed upstream "\n            "amy/c_amy package instead of sending wire commands over UART."\n        ),\n    )\n\n    window_group = parser.add_mutually_exclusive_group()\n''',
)
replace_once(
    main,
    '''    print(\n        "AMY serial backend: "\n        f"{amy_config['serial']['port']} @ "\n        f"{amy_config['serial']['baud']} baud",\n        file=sys.stderr,\n        flush=True,\n    )\n\n    amy_client = AmySerialClient(\n        config=amy_config,\n        addresses=address_map,\n    )\n''',
    '''    if args.local_amy:\n        print(\n            "AMY backend: local in-process desktop AMY",\n            file=sys.stderr,\n            flush=True,\n        )\n        amy_client = AmyLocalClient(\n            config=amy_config,\n            addresses=address_map,\n        )\n    else:\n        print(\n            "AMY serial backend: "\n            f"{amy_config['serial']['port']} @ "\n            f"{amy_config['serial']['baud']} baud",\n            file=sys.stderr,\n            flush=True,\n        )\n        amy_client = AmySerialClient(\n            config=amy_config,\n            addresses=address_map,\n        )\n''',
)

for path in (amy, main):
    compile(path.read_text(encoding="utf-8"), str(path), "exec")

print("local AMY runtime patch applied")
