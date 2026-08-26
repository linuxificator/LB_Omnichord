from __future__ import annotations

import copy
import math
from typing import Any, Sequence

from control_limits import clamp_control_value


class SynthState:
    """Own one UI synth role's instrument selection and per-instrument values.

    The class is deliberately the single mutation point for synth state. UI
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
        self._default_selected_index = self._validate_index(selected_index)
        self._selected_index = self._default_selected_index
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
    def default_selected_index(self) -> int:
        return self._default_selected_index

    @property
    def selected_definition(self) -> Any:
        return self._definitions[self._selected_index]

    @property
    def selected_values(self) -> dict[str, float]:
        return self._values_by_synth[self._selected_index]

    def reset_to_defaults(self) -> None:
        """Restore catalogue values and this role's application synth choice."""
        self._selected_index = self._default_selected_index
        self._values_by_synth = self._default_values()

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
        # Copy performance/session state only. Each role keeps its own
        # application-default instrument for future sparse preset loads.
        self._selected_index = other._selected_index
        self._values_by_synth = copy.deepcopy(other._values_by_synth)

    def set_control(self, key: str, value: float) -> bool:
        return self.set_instrument_control(
            str(self.selected_definition.key),
            key,
            value,
        )

    def control_value(self, instrument: str, key: str) -> float | None:
        index = self._key_to_index.get(str(instrument))
        if index is None:
            return None
        definition = self._definitions[index]
        control = self._control_for(definition, str(key))
        if control is None:
            return None
        return float(self._values_by_synth[index][control.key])

    def set_instrument_control(
        self,
        instrument: str,
        key: str,
        value: float,
    ) -> bool:
        index = self._key_to_index.get(str(instrument))
        if index is None:
            return False
        definition = self._definitions[index]
        control = self._control_for(definition, str(key))
        if control is None:
            return False
        clamped = clamp_control_value(control.key, float(value))
        clamped = max(
            float(control.minimum),
            min(float(control.maximum), clamped),
        )
        values = self._values_by_synth[index]
        if math.isclose(
            clamped,
            float(values[control.key]),
            rel_tol=0.0,
            abs_tol=1e-4,
        ):
            return False
        values[control.key] = clamped
        return True

    def _overlay_parameters(
        self,
        values_by_synth: list[dict[str, float]],
        data: dict[str, Any],
    ) -> None:
        all_parameters = data.get("parameters", {})
        if not isinstance(all_parameters, dict):
            return

        for synth_index, definition in enumerate(self._definitions):
            stored_values = all_parameters.get(definition.key, {})
            if not isinstance(stored_values, dict):
                continue
            values = values_by_synth[synth_index]
            for control in definition.controls:
                if control.key not in stored_values:
                    continue
                try:
                    stored = float(stored_values[control.key])
                except (TypeError, ValueError):
                    continue
                # Legacy presets used negative values as "patch/default".
                if stored < 0.0 and float(control.default) >= 0.0:
                    continue
                try:
                    stored = clamp_control_value(control.key, stored)
                except ValueError:
                    continue
                values[control.key] = max(
                    float(control.minimum),
                    min(float(control.maximum), stored),
                )

    def load_preset(self, data: dict[str, Any]) -> None:
        """Replace this role with application defaults plus sparse overrides.

        Missing or unknown ``selected`` values always resolve to the role's
        application-default synth. Missing parameter values always resolve to
        the current catalogue default for that instrument.
        """
        default_key = str(
            self._definitions[self._default_selected_index].key
        )
        selected_key = str(data.get("selected", default_key))
        selected_index = self._key_to_index.get(
            selected_key,
            self._default_selected_index,
        )

        values_by_synth = self._default_values()
        self._overlay_parameters(values_by_synth, data)

        self._selected_index = selected_index
        self._values_by_synth = values_by_synth

    def reset_selected_from_preset(self, data: dict[str, Any]) -> bool:
        """Restore the current instrument without changing instrument selection.

        Sparse preset parameters are keyed by instrument. Missing values mean
        application catalogue defaults. This is the exact reset semantics used
        by the per-section UI reset buttons.
        """
        definition = self.selected_definition
        values_by_synth = self._default_values()
        self._overlay_parameters(values_by_synth, data)
        new_values = values_by_synth[self._selected_index]

        old_values = self.selected_values
        changed = any(
            not math.isclose(
                float(old_values.get(key, value)),
                float(value),
                rel_tol=0.0,
                abs_tol=1e-9,
            )
            for key, value in new_values.items()
        )
        if changed:
            self._values_by_synth[self._selected_index] = new_values
        return changed

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
                "unit": getattr(control, "unit", ""),
                "scale": getattr(control, "scale", "linear"),
            }
            for control in self.selected_definition.controls
            if control.group == group
        ]

    def transport_payload(self) -> dict[str, Any]:
        """Return the complete engine override state for the selected patch.

        The UI always has explicit numeric values, but AMY's factory patch is
        already the source of truth for controls whose application default is
        identical to the native patch value. Omitting those values avoids
        rewriting partial CtrlCoef lists such as the Juno VCF base frequency.
        Application corrections and user/preset edits remain explicit.
        """
        arguments: list[str | float] = []
        values = self.selected_values
        for control in self.selected_definition.controls:
            current = float(values[control.key])
            native = getattr(control, "native_default", None)
            if (
                native is not None
                and math.isclose(
                    current,
                    float(native),
                    rel_tol=0.0,
                    abs_tol=1e-9,
                )
            ):
                continue
            arguments.extend([control.key, current])
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
