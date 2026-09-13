#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FRONTEND / "code"))
sys.path.insert(0, str(FRONTEND / "tests"))

from instrument_balance import (  # noqa: E402
    build_plan,
    render_plan,
    validate_render_report,
)


class NativeInstrumentBalanceTests(unittest.TestCase):
    def test_every_instrument_and_register_is_audible_and_unclipped(self) -> None:
        plan = build_plan()
        with tempfile.TemporaryDirectory() as directory:
            report = render_plan(plan, Path(directory), gate_seconds=0.5)
        self.assertEqual(validate_render_report(report), [])


if __name__ == "__main__":
    unittest.main()
