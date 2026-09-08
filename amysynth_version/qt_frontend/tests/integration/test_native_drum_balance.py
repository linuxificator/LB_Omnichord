#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FRONTEND / "code"))
sys.path.insert(0, str(FRONTEND / "tests"))

from drum_fill_balance import build_report, validate_report  # noqa: E402


class NativeDrumBalanceTests(unittest.TestCase):
    def test_all_gamma9001_fills_meet_the_measured_balance_contract(self) -> None:
        report = build_report()
        fill_count = sum(len(fills) for fills in report.values())
        self.assertEqual(fill_count, 270)
        self.assertEqual(validate_report(report), [])


if __name__ == "__main__":
    unittest.main()
