from __future__ import annotations

import ipaddress
from dataclasses import dataclass

from PySide6.QtNetwork import QAbstractSocket, QNetworkInterface


@dataclass(frozen=True, slots=True)
class NetworkInterfaceState:
    addresses: tuple[str, ...]
    is_up: bool
    is_running: bool
    is_loopback: bool


def listener_network_available(
    listen_address: str,
    interfaces: tuple[NetworkInterfaceState, ...],
) -> bool:
    """Return whether an IPv4 listener has its requested network available."""

    requested = ipaddress.IPv4Address(listen_address)
    if requested.is_loopback:
        return True
    usable = tuple(
        interface
        for interface in interfaces
        if interface.is_up
        and interface.is_running
        and not interface.is_loopback
        and interface.addresses
    )
    if requested.is_unspecified:
        return bool(usable)
    return any(str(requested) in interface.addresses for interface in usable)


def qt_network_interfaces() -> tuple[NetworkInterfaceState, ...]:
    """Snapshot Qt's cross-platform network-interface abstraction."""

    states: list[NetworkInterfaceState] = []
    flags = QNetworkInterface.InterfaceFlag
    ipv4 = QAbstractSocket.NetworkLayerProtocol.IPv4Protocol
    for interface in QNetworkInterface.allInterfaces():
        interface_flags = interface.flags()
        addresses = tuple(
            entry.ip().toString()
            for entry in interface.addressEntries()
            if entry.ip().protocol() == ipv4
        )
        states.append(
            NetworkInterfaceState(
                addresses=addresses,
                is_up=bool(interface_flags & flags.IsUp),
                is_running=bool(interface_flags & flags.IsRunning),
                is_loopback=bool(interface_flags & flags.IsLoopBack),
            )
        )
    return tuple(states)


def qt_listener_network_available(listen_address: str) -> bool:
    return listener_network_available(listen_address, qt_network_interfaces())
