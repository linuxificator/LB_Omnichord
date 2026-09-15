from __future__ import annotations

import sys
from collections.abc import Callable

from PySide6.QtGui import QGuiApplication

from osc_discovery import OscServiceAdvertiser


OscServiceAdvertiserFactory = Callable[[], OscServiceAdvertiser]


def create_osc_service_advertiser(
    *,
    runtime_platform: str,
    qpa_name: str = "",
) -> OscServiceAdvertiser:
    """Select the discovery adapter once at the platform boundary."""

    del runtime_platform, qpa_name

    from osc_discovery_zeroconf import ZeroconfOscServiceAdvertiser

    return ZeroconfOscServiceAdvertiser()


def production_osc_service_advertiser() -> OscServiceAdvertiser:
    qpa_name = str(QGuiApplication.platformName()) if QGuiApplication.instance() is not None else ""
    return create_osc_service_advertiser(
        runtime_platform=sys.platform,
        qpa_name=qpa_name,
    )
