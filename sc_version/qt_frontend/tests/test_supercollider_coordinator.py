from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
SC_ROOT = ROOT.parent / "supercollider"
sys.path.insert(0, str(ROOT / "code"))

from engine_protocol import SequenceDefinition, SequenceEvent  # noqa: E402
from musical_sequence_plan import LanePlan  # noqa: E402
from resolved_config import resolve_amy_config_data  # noqa: E402
from supercollider_client import SuperColliderClient  # noqa: E402


@unittest.skipUnless(shutil.which("sclang"), "sclang is not installed")
class SuperColliderCoordinatorProcessTests(unittest.TestCase):
    def test_real_sclang_atomically_acknowledges_empty_lane(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.bind(("127.0.0.1", 0))
            port = int(probe.getsockname()[1])
        environment = dict(os.environ)
        environment["OMNICHORD_SC_PORT"] = str(port)
        process = subprocess.Popen(
            ["sclang", "-D", str(SC_ROOT / "tests" / "coordinator_service.scd")],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=environment,
        )
        output: list[str] = []
        try:
            assert process.stdout is not None
            watchdog = threading.Timer(10.0, process.terminate)
            watchdog.start()
            for line in process.stdout:
                output.append(line)
                if "LB_OMNICHORD_SC_COORDINATOR_READY" in line:
                    watchdog.cancel()
                    break
            else:
                watchdog.cancel()
                self.fail("sclang coordinator did not start:\n" + "".join(output))

            with tempfile.TemporaryDirectory() as temporary:
                config_path = Path(temporary) / "supercollider.json"
                config_path.write_text(
                    json.dumps(
                        {
                            "config_revision": 2,
                            "protocol_version": 1,
                            "language": {
                                "host": "127.0.0.1",
                                "port": port,
                                "startup_timeout_seconds": 2.0,
                                "message_payload_bytes": 1000,
                            },
                            "server": {
                                "sample_rate": 48000,
                                "block_size": 64,
                                "latency_seconds": 0.02,
                                "max_nodes": 4096,
                                "max_buffers": 8192,
                                "realtime_memory_kib": 262144,
                            },
                            "samples": {
                                "vsco_root": "/not-used",
                                "repository": "https://github.com/linuxificator/VSCO-2-CE.git",
                                "ram_budget_mib": 4096,
                            },
                        }
                    ),
                    encoding="utf-8",
                )
                raw = json.loads((ROOT / "config" / "amy_config.json").read_text())
                resolved = resolve_amy_config_data(
                    raw,
                    source_path=ROOT / "config" / "amy_config.json",
                    source_kind="shipped",
                )
                client = SuperColliderClient(
                    config=None,
                    addresses={},
                    resolved_config=resolved,
                    runtime_config_path=config_path,
                    asset_root=ROOT,
                )
                result = client.publish_lane(
                    LanePlan(
                        lane="process-test",
                        generation=1,
                        alignment_ticks=1,
                        definitions=(
                            SequenceDefinition(
                                definition_id="process-test/root",
                                revision=1,
                                kind="root",
                                lane="process-test",
                                period_ticks=48,
                                events=(),
                                source_identity="process-fixture",
                            ),
                        ),
                    )
                )
                self.assertEqual(result[0], "applied")
                self.assertEqual(result[1], 1)
                referenced = client.publish_lane(
                    LanePlan(
                        lane="string-reference",
                        generation=1,
                        alignment_ticks=1,
                        definitions=(
                            SequenceDefinition(
                                definition_id="string-reference/root",
                                revision=1,
                                kind="root",
                                lane="string-reference",
                                period_ticks=48,
                                events=(
                                    SequenceEvent(
                                        0,
                                        0,
                                        "launch",
                                        ("string-reference/finite",),
                                    ),
                                ),
                                source_identity="reference-fixture",
                            ),
                            SequenceDefinition(
                                definition_id="string-reference/finite",
                                revision=1,
                                kind="finite",
                                lane="string-reference",
                                period_ticks=0,
                                events=(),
                                source_identity="finite-fixture",
                            ),
                        ),
                    )
                )
                self.assertEqual(referenced[0], "applied")

                gated = client.publish_lane(
                    LanePlan(
                        lane="gate-order",
                        generation=1,
                        alignment_ticks=1,
                        definitions=(
                            SequenceDefinition(
                                definition_id="gate-order/control",
                                revision=1,
                                kind="root",
                                lane="gate-order",
                                period_ticks=48,
                                events=(
                                    SequenceEvent(0, 0, "launch", ("gate-order/a",)),
                                    SequenceEvent(0, 1, "launch", ("gate-order/b",)),
                                ),
                                source_identity="gate-control",
                            ),
                            SequenceDefinition(
                                definition_id="gate-order/a",
                                revision=1,
                                kind="finite",
                                lane="gate-order",
                                period_ticks=0,
                                events=(
                                    SequenceEvent(
                                        0,
                                        0,
                                        "gateBegin",
                                        ("snare", "gate-a", 1, "drumHit"),
                                    ),
                                ),
                                source_identity="gate-a",
                            ),
                            SequenceDefinition(
                                definition_id="gate-order/b",
                                revision=1,
                                kind="finite",
                                lane="gate-order",
                                period_ticks=0,
                                events=(
                                    SequenceEvent(
                                        0,
                                        0,
                                        "gateBegin",
                                        ("snare", "gate-b", 2, "drumHit"),
                                    ),
                                ),
                                source_identity="gate-b",
                            ),
                            SequenceDefinition(
                                definition_id="gate-order/drums",
                                revision=1,
                                kind="root",
                                lane="gate-order",
                                period_ticks=48,
                                events=tuple(
                                    SequenceEvent(
                                        tick,
                                        tick,
                                        "drumHit",
                                        (
                                            "snare",
                                            "sample.vsco.gm-styleperc",
                                            38,
                                            0.8,
                                            0,
                                        ),
                                    )
                                    for tick in range(3)
                                ),
                                source_identity="gate-drums",
                            ),
                        ),
                    )
                )
                self.assertEqual(gated[0], "applied")
                client._send_raw(
                    "/omni/v1/transport",
                    [client.session, client._next_message_id(), "start", 120.0],
                )
                time.sleep(0.15)
                client.close()
            process.wait(timeout=3.0)
            self.assertEqual(process.returncode, 0)
            assert process.stdout is not None
            output.extend(process.stdout.readlines())
            traces = [
                line.strip().split("|")
                for line in output
                if line.startswith("LB_OMNI_TRACE|")
            ]
            tick_zero_actions = [
                trace[5]
                for trace in traces
                if int(trace[1]) == 0 and trace[2].startswith("gate-order/")
            ]
            self.assertEqual(
                tick_zero_actions,
                ["launch", "gateBegin", "launch", "gateBegin", "drumHit"],
            )
            drum_suppression = [
                (int(trace[1]), trace[6])
                for trace in traces
                if trace[5] == "drumHit" and trace[2] == "gate-order/drums"
            ]
            self.assertEqual(
                drum_suppression[:3],
                [(0, "true"), (1, "true"), (2, "false")],
            )
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=3.0)
            if process.stdout is not None:
                process.stdout.close()


if __name__ == "__main__":
    unittest.main()
