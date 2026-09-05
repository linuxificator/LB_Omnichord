from __future__ import annotations

import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from osc_discovery_zeroconf import (  # noqa: E402
    OSC_DNS_SD_TYPE,
    ZeroconfOscServiceAdvertiser,
    _advertised_ipv4_addresses,
)
from network_availability import NetworkInterfaceState  # noqa: E402


class FakeZeroconf:
    instances: list[FakeZeroconf] = []
    created = threading.Event()

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.registered: list[tuple[object, bool]] = []
        self.unregistered: list[object] = []
        self.closed = False
        self.registration = threading.Event()
        self.instances.append(self)
        self.created.set()

    def register_service(self, info: object, *, allow_name_change: bool) -> None:
        self.registered.append((info, allow_name_change))
        self.registration.set()

    def unregister_service(self, info: object) -> None:
        self.unregistered.append(info)

    def close(self) -> None:
        self.closed = True


class OscDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeZeroconf.instances.clear()
        FakeZeroconf.created.clear()

    def test_publishes_standard_osc_dns_sd_record_and_closes_cleanly(self) -> None:
        with (
            patch(
                "osc_discovery_zeroconf._advertised_ipv4_addresses",
                return_value=("192.0.2.10", "198.51.100.4"),
            ),
            patch("osc_discovery_zeroconf.Zeroconf", FakeZeroconf),
            patch(
                "osc_discovery_zeroconf._local_server_name",
                return_value="studio.local.",
            ),
        ):
            advertiser = ZeroconfOscServiceAdvertiser()
            advertiser.start(
                service_name="LB Omnichord",
                listen_address="0.0.0.0",
                port=8000,
            )
            self.assertTrue(FakeZeroconf.created.wait(2.0))
            self.assertTrue(FakeZeroconf.instances[0].registration.wait(2.0))
            instance = FakeZeroconf.instances[0]
            info, allow_name_change = instance.registered[0]
            self.assertEqual(info.type, OSC_DNS_SD_TYPE)
            self.assertEqual(info.name, "LB Omnichord._osc._udp.local.")
            self.assertEqual(info.port, 8000)
            self.assertEqual(
                info.parsed_addresses(),
                ["192.0.2.10", "198.51.100.4"],
            )
            self.assertEqual(info.properties[b"txtvers"], b"1")
            self.assertEqual(info.properties[b"version"], b"1.0")
            self.assertTrue(allow_name_change)

            advertiser.close()

        self.assertEqual(instance.unregistered, [info])
        self.assertTrue(instance.closed)

    def test_advertises_only_usable_addresses_reachable_by_remote_clients(self) -> None:
        interfaces = (
            NetworkInterfaceState(("127.0.0.1",), True, True, True),
            NetworkInterfaceState(("192.0.2.30",), True, True, False),
            NetworkInterfaceState(("198.51.100.7",), True, False, False),
        )
        with patch(
            "osc_discovery_zeroconf.qt_network_interfaces",
            return_value=interfaces,
        ):
            self.assertEqual(
                _advertised_ipv4_addresses("0.0.0.0"),
                ("192.0.2.30",),
            )
            self.assertEqual(
                _advertised_ipv4_addresses("192.0.2.30"),
                ("192.0.2.30",),
            )
            self.assertEqual(_advertised_ipv4_addresses("198.51.100.7"), ())
            self.assertEqual(_advertised_ipv4_addresses("127.0.0.1"), ())

    def test_no_usable_interface_retries_quietly_until_close(self) -> None:
        with (
            patch(
                "osc_discovery_zeroconf._advertised_ipv4_addresses",
                return_value=(),
            ),
            patch("osc_discovery_zeroconf.Zeroconf", FakeZeroconf),
        ):
            advertiser = ZeroconfOscServiceAdvertiser()
            advertiser.start(
                service_name="LB Omnichord",
                listen_address="0.0.0.0",
                port=8000,
            )
            advertiser.close()

        self.assertEqual(FakeZeroconf.instances, [])

    def test_interface_appearing_after_start_is_advertised(self) -> None:
        with (
            patch(
                "osc_discovery_zeroconf._advertised_ipv4_addresses",
                side_effect=((), ("192.0.2.20",)),
            ),
            patch("osc_discovery_zeroconf.OSC_DISCOVERY_RETRY_SECONDS", 0.01),
            patch("osc_discovery_zeroconf.Zeroconf", FakeZeroconf),
        ):
            advertiser = ZeroconfOscServiceAdvertiser()
            advertiser.start(
                service_name="LB Omnichord",
                listen_address="0.0.0.0",
                port=8000,
            )
            self.assertTrue(FakeZeroconf.created.wait(2.0))
            self.assertTrue(FakeZeroconf.instances[0].registration.wait(2.0))
            advertiser.close()

        info, _allow_name_change = FakeZeroconf.instances[0].registered[0]
        self.assertEqual(info.parsed_addresses(), ["192.0.2.20"])


if __name__ == "__main__":
    unittest.main()
