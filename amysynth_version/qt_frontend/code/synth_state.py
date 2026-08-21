from __future__ import annotations

import copy
import math
from typing import Any, Sequence


class SynthState:
    """Own one UI synth role's instrument selection and per-instrument values.

    The class is deliberately the single mutation point for synth state.  UI
    edits, preset loads, instrument switches, copying between roles and preset
    serialization all use these methods instead of modifying dictionaries in
    InstrumentBackend directly.
    """

    def __init__(self, definitions: Sequence[Any], selected_index: int) -> None:
        self._definitions = tuple(definitions)
        if not self._definitions:
            raise ValueError("SynthState requires at least one definition")
        self._key_to_index = {
            str(definition.key): index
            for index, definition in enumerate(self._definitions)
        }
        self._selected_index = self._validate_index(selected_index)
        self._values_by_synth = self._default_values()

    def _validate_index(self, index: int) -> int:
        value = int(index)
        if not 0 <= value < len(self._definitions):
            raise IndexError(value)
        return value

    @staticmethod
    def _control_for(definition: Any, key: str) -> Any | None:
        return next(
            (control for control in definition.controls if control.key == key),
            None,
        )

    def _default_values(self) -> list[dict[str, float]]:
        return [
            {
                str(control.key): float(control.default)
                for control in definition.controls
            }
            for definition in self._definitions
        ]

    @property
    def selected_index(self) -> int:
        return self._selected_index

    @property
    def selected_definition(self) -> Any:
        return self._definitions[self._selected_index]

    @property
    def selected_values(self) -> dict[str, float]:
        return self._values_by_synth[self._selected_index]

    def select(self, index: int) -> bool:
        try:
            value = self._validate_index(index)
        except IndexError:
            return False
        if value == self._selected_index:
            return False
        self._selected_index = value
        return True

    def copy_from(self, other: "SynthState") -> None:
        if tuple(definition.key for definition in self._definitions) != tuple(
            definition.key for definition in other._definitions
        ):
            raise ValueError("cannot copy synth state between different catalogs")
        self._selected_index = other._selected_index
        self._values_by_synth = copy.deepcopy(other._values_by_synth)

    def set_control(self, key: str, value: float) -> bool:
        definition = self.selected_definition
        control = self._control_for(definition, str(key))
        if control is None:
            return False
        clamped = max(
            float(control.minimum),
            min(float(control.maximum), float(value)),
        )
        values = self.selected_values
        if math.isclose(
            clamped,
            float(values[control.key]),
            rel_tol=0.0,
            abs_tol=1e-4,
        ):
            return False
        values[control.key] = clamped
        return True

    def load_preset(self, data: dict[str, Any]) -> None:
        """Replace this role with defaults plus sparse preset overrides."""
        selected_key = str(data.get("selected", self.selected_definition.key))
        selected_index = self._key_to_index.get(selected_key, self._selected_index)

        values_by_synth = self._default_values()
        all_parameters = data.get("parameters", {})
        if isinstance(all_parameters, dict):
            for synth_index, definition in enumerate(self._definitions):
                stored_values = all_parameters.get(definition.key, {})
                if not isinstance(stored_values, dict):
                    continue
                values = values_by_synth[synth_index]
                for control in definition.controls:
                    if control.key not in stored_values:
                        continue
                    stored = float(stored_values[control.key])
                    # Legacy presets used negative values as "patch/default".
                    if stored < 0.0 and float(control.default) >= 0.0:
                        continue
                    values[control.key] = max(
                        float(control.minimum),
                        min(float(control.maximum), stored),
                    )

        self._selected_index = selected_index
        self._values_by_synth = values_by_synth

    def control_model(self, group: str) -> list[dict[str, Any]]:
        values = self.selected_values
        return [
            {
                "key": control.key,
                "label": control.label,
                "value": values[control.key],
                "minimum": control.minimum,
                "maximum": control.maximum,
                "step": control.step,
                "decimals": control.decimals,
            }
            for control in self.selected_definition.controls
            if control.group == group
        ]

    def transport_payload(self) -> dict[str, Any]:
        arguments: list[str | float] = []
        values = self.selected_values
        for control in self.selected_definition.controls:
            arguments.extend([control.key, float(values[control.key])])
        return {
            "name": self.selected_definition.key,
            "params": arguments,
        }

    def sparse_overrides(self) -> dict[str, dict[str, float]]:
        result: dict[str, dict[str, float]] = {}
        for index, definition in enumerate(self._definitions):
            values = self._values_by_synth[index]
            changed: dict[str, float] = {}
            for control in definition.controls:
                current = float(values[control.key])
                if not math.isclose(
                    current,
                    float(control.default),
                    rel_tol=0.0,
                    abs_tol=1e-9,
                ):
                    changed[control.key] = current
            if changed:
                result[definition.key] = changed
        return result
