from __future__ import annotations

import ipaddress
import socket
import threading

from zeroconf import IPVersion, ServiceInfo, Zeroconf

from network_availability import listener_network_available, qt_network_interfaces


OSC_DNS_SD_TYPE = "_osc._udp.local."
OSC_DISCOVERY_RETRY_SECONDS = 5.0


def _advertised_ipv4_addresses(listen_address: str) -> tuple[str, ...]:
    """Return usable IPv4 service addresses through Qt's portable inventory."""

    requested = ipaddress.IPv4Address(listen_address)
    if requested.is_loopback:
        return ()
    interfaces = qt_network_interfaces()
    if not requested.is_unspecified:
        return (
            (listen_address,)
            if listener_network_available(listen_address, interfaces)
            else ()
        )

    return tuple(
        sorted(
            {
                address
                for interface in interfaces
                if interface.is_up
                and interface.is_running
                and not interface.is_loopback
                for address in interface.addresses
                if address != "0.0.0.0"
            }
        )
    )


def _local_server_name() -> str:
    label = socket.gethostname().strip().rstrip(".").split(".", 1)[0]
    safe = "".join(
        character
        if character.isascii() and (character.isalnum() or character == "-")
        else "-"
        for character in label
    )
    safe = safe.strip("-") or "lb-omnichord"
    safe = safe.encode("utf-8")[:63].decode("utf-8", errors="ignore").rstrip("-")
    return f"{safe}.local."


class ZeroconfOscServiceAdvertiser:
    """Non-blocking DNS-SD publisher for an OSC UDP input service."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._closing = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self, *, service_name: str, listen_address: str, port: int) -> None:
        with self._lock:
            if self._thread is not None:
                return
            self._thread = threading.Thread(
                target=self._publish,
                args=(service_name, listen_address, int(port)),
                name="osc-dns-sd",
                daemon=True,
            )
            self._thread.start()

    def _publish(
        self,
        service_name: str,
        listen_address: str,
        port: int,
    ) -> None:
        while not self._closing.is_set():
            addresses = _advertised_ipv4_addresses(listen_address)
            if not addresses:
                self._closing.wait(OSC_DISCOVERY_RETRY_SECONDS)
                continue
            zeroconf: Zeroconf | None = None
            info: ServiceInfo | None = None
            registered = False
            try:
                zeroconf = Zeroconf(ip_version=IPVersion.V4Only, use_asyncio=False)
                info = ServiceInfo(
                    OSC_DNS_SD_TYPE,
                    f"{service_name}.{OSC_DNS_SD_TYPE}",
                    port=port,
                    properties={"txtvers": "1", "version": "1.0"},
                    server=_local_server_name(),
                    parsed_addresses=list(addresses),
                )
                if self._closing.is_set():
                    return
                zeroconf.register_service(info, allow_name_change=True)
                registered = True
                self._closing.wait()
            except Exception:
                # Discovery is a convenience capability. A multicast or
                # platform failure must never disable the OSC input socket.
                self._closing.wait(OSC_DISCOVERY_RETRY_SECONDS)
            finally:
                if zeroconf is not None:
                    if registered and info is not None:
                        try:
                            zeroconf.unregister_service(info)
                        except Exception:
                            pass
                    try:
                        zeroconf.close()
                    except Exception:
                        pass
            if registered:
                return

    def close(self) -> None:
        self._closing.set()
        with self._lock:
            thread = self._thread
            self._thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
