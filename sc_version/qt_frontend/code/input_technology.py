from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


InputTechnologyState = Literal["unavailable", "listening", "activity"]


@dataclass(frozen=True, slots=True)
class InputTechnologyStatus:
    """Transport-neutral status projected into the shared input-tech row."""

    key: str
    label: str
    state: InputTechnologyState
    reason: str
    protocol: str = "midi"
    idle_led_visible: bool = True

    @property
    def available(self) -> bool:
        return self.state in ("listening", "activity")

    def presentation(self) -> dict[str, object]:
        return {
            "key": self.key,
            "label": self.label,
            "state": self.state,
            "available": self.available,
            "reason": self.reason,
            "protocol": self.protocol,
            "idleLedVisible": self.idle_led_visible,
        }
