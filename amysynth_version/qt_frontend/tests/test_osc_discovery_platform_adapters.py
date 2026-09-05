from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from osc_discovery import NullOscServiceAdvertiser  # noqa: E402
from osc_discovery_platform_adapters import (  # noqa: E402
    create_osc_service_advertiser,
)


class OscDiscoveryPlatformAdapterTests(unittest.TestCase):
    def test_android_is_an_explicit_no_op_without_native_bridge(self) -> None:
        for runtime, qpa in (("android", ""), ("linux", "android")):
            with self.subTest(runtime=runtime, qpa=qpa):
                advertiser = create_osc_service_advertiser(
                    runtime_platform=runtime,
                    qpa_name=qpa,
                )
                self.assertIsInstance(advertiser, NullOscServiceAdvertiser)

    def test_supported_desktop_profiles_select_zeroconf(self) -> None:
        from osc_discovery_zeroconf import ZeroconfOscServiceAdvertiser

        for runtime in ("linux", "darwin", "win32"):
            with self.subTest(runtime=runtime):
                advertiser = create_osc_service_advertiser(
                    runtime_platform=runtime,
                )
                self.assertIsInstance(advertiser, ZeroconfOscServiceAdvertiser)
                advertiser.close()


if __name__ == "__main__":
    unittest.main()
