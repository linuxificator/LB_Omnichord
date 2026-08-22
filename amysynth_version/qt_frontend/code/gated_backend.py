from __future__ import annotations

from typing import Any

from PySide6.QtCore import Property, Signal, Slot

from performance_backend import InstrumentBackend as PerformanceBackend
from program_amy import STRUM_GATE_ADDRESS


class InstrumentBackend(PerformanceBackend):
    """Performance backend with an optional original-style strum gate."""

    strumGateChanged = Signal()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._strum_gate_enabled = False
        self._strum_gate_attack = 0.20
        self._strum_gate_sustain = 0.50
        super().__init__(*args, **kwargs)

    @Property(bool, notify=strumGateChanged)
    def strumGateEnabled(self) -> bool:
        return self._strum_gate_enabled

    @Property(float, notify=strumGateChanged)
    def strumGateAttack(self) -> float:
        return self._strum_gate_attack

    @Property(float, notify=strumGateChanged)
    def strumGateSustain(self) -> float:
        return self._strum_gate_sustain

    def _send_strum_gate(self) -> None:
        self._client.send_message(
            STRUM_GATE_ADDRESS,
            {
                "enabled": self._strum_gate_enabled,
                "attack": self._strum_gate_attack,
                "sustain": self._strum_gate_sustain,
            },
        )

    @Slot()
    def toggleStrumGate(self) -> None:
        self._strum_gate_enabled = not self._strum_gate_enabled
        self.strumGateChanged.emit()
        self._send_strum_gate()

    @Slot(float)
    def setStrumGateAttack(self, value: float) -> None:
        value = max(0.0, min(1.0, float(value)))
        if abs(value - self._strum_gate_attack) < 1e-9:
            return
        self._strum_gate_attack = value
        self.strumGateChanged.emit()
        self._send_strum_gate()

    @Slot(float)
    def setStrumGateSustain(self, value: float) -> None:
        value = max(0.0, min(1.0, float(value)))
        if abs(value - self._strum_gate_sustain) < 1e-9:
            return
        self._strum_gate_sustain = value
        self.strumGateChanged.emit()
        self._send_strum_gate()

    def send_initial_state(self) -> None:
        super().send_initial_state()
        self._send_strum_gate()
        self.strumGateChanged.emit()
