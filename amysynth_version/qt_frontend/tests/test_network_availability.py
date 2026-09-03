from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from network_availability import (  # noqa: E402
    NetworkInterfaceState,
    listener_network_available,
)


def interface(
    address: str,
    *,
    up: bool = True,
    running: bool = True,
    loopback: bool = False,
) -> NetworkInterfaceState:
    return NetworkInterfaceState((address,), up, running, loopback)


class NetworkAvailabilityTests(unittest.TestCase):
    def test_loopback_listener_never_requires_an_external_network(self) -> None:
        self.assertTrue(listener_network_available("127.0.0.1", ()))

    def test_wildcard_requires_a_running_non_loopback_ipv4_interface(self) -> None:
        loopback = interface("127.0.0.1", loopback=True)
        down = interface("192.168.1.20", up=False, running=False)
        self.assertFalse(listener_network_available("0.0.0.0", (loopback, down)))
        self.assertTrue(
            listener_network_available(
                "0.0.0.0",
                (loopback, interface("192.168.1.20")),
            )
        )

    def test_specific_listener_requires_that_address_on_a_running_interface(self) -> None:
        interfaces = (
            interface("192.168.1.20"),
            interface("10.0.0.8", running=False),
        )
        self.assertTrue(listener_network_available("192.168.1.20", interfaces))
        self.assertFalse(listener_network_available("10.0.0.8", interfaces))


if __name__ == "__main__":
    unittest.main()
