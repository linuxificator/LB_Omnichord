from __future__ import annotations

import threading
from typing import Any

import amy_transport as base
from synth_programs import SynthProgram, resolve_program


STRUM_GATE_ADDRESS = "/strum/gate"
KS_WAVE = 6


class ProgramAmySerialClient(base.AmySerialClient):
    """AMY client whose instrument identity is a SynthProgram, not a patch id."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._strum_gate_enabled = False
        self._strum_gate_attack = 0.20
        self._strum_gate_sustain = 0.50
        self._strum_gate_generation = 0
        self._strum_gate_level = 1.0
        super().__init__(*args, **kwargs)

    def _program(self, role: str) -> SynthProgram | None:
        # Several transport unit tests deliberately exercise methods on a
        # partially constructed client.  The generalized layer must remain a
        # transparent extension in that case, not make the old low-level
        # contracts depend on full application configuration.
        config = getattr(self, "config", None)
        selected = getattr(self, "selected_synth", None)
        if not isinstance(config, dict) or not isinstance(selected, dict):
            return None
        key = selected.get(role)
        if key is None:
            return None
        return resolve_program(str(key), config)

    def _configure_physical_one(
        self, role: str, synth: int, program: SynthProgram
    ) -> None:
        self._bump_synth_generation(synth)
        self._wire(f"l0i{synth}Z")
        voices = self._voice_count_for_synth(synth)
        bus = self._bus_for_synth(synth)

        # Explicit voice geometry makes a physical model no different from a
        # ROM patch to AMY's synth allocator. Re-stating it is intentional:
        # the previous program may have been a 6-osc Juno or 8-osc DX7 voice.
        self._wire(f"i{synth}iv{voices}in{program.oscs_per_voice}iy{bus}Z")
        self._configured_synths.add(synth)
        guard_ms = float(
            self.config.get("performance", {}).get(
                "synth_alloc_guard_ms", 10.0
            )
        )
        self.writer.delay(max(0.0, guard_ms) / 1000.0)

        if program.kind == "karplus_strong":
            wave = KS_WAVE if program.wave is None else int(program.wave)
            feedback = 0.985 if program.feedback is None else program.feedback
            self._wire(f"v0w{wave}b{self._f(feedback)}i{synth}Z")
        else:
            raise ValueError(f"unsupported non-ROM program {program.kind!r}")

        self._route_synth_bus(synth)
        self._wire(f"i{synth}iV{self._f(self.volume[role])}Z")
        self._apply_reverb_bus(bus)

    def _physical_param_commands(
        self, role: str, synth: int, program: SynthProgram
    ) -> list[str]:
        if program.kind != "karplus_strong":
            return []
        feedback = self.synth_params[role].get(
            "feedback",
            0.985 if program.feedback is None else program.feedback,
        )
        feedback = max(0.0, min(0.9999, float(feedback)))
        return [f"v0b{self._f(feedback)}i{synth}Z"]

    def _configure_synth(self, role: str) -> None:
        program = self._program(role)
        if program is None or program.is_rom_patch:
            super()._configure_synth(role)
            return
        for synth in self._role_synth_ids(role):
            self._configure_physical_one(role, synth, program)
            for command in self._physical_param_commands(role, synth, program):
                self._wire(command)

    def _apply_supported_params(
        self,
        role: str,
        parameter_keys: set[str] | None = None,
    ) -> None:
        program = self._program(role)
        if program is None or program.is_rom_patch:
            super()._apply_supported_params(role, parameter_keys)
            return
        if parameter_keys is not None and "feedback" not in parameter_keys:
            return
        for synth in self._role_synth_ids(role):
            for command in self._physical_param_commands(role, synth, program):
                self._wire(command)

    def _apply_synth_state(
        self,
        role: str,
        name: str,
        params: dict[str, float],
        *,
        force_patch: bool = False,
    ) -> None:
        config = getattr(self, "config", None)
        if not isinstance(config, dict):
            super()._apply_synth_state(
                role, name, params, force_patch=force_patch
            )
            return

        program = resolve_program(str(name), config)
        if program is None:
            print(f"AMY warning: refusing unknown synth program {name!r}", flush=True)
            return
        if program.is_rom_patch:
            super()._apply_synth_state(
                role, name, params, force_patch=force_patch
            )
            return

        old_params = dict(self.synth_params[role])
        new_params = dict(params)
        changed_keys = self._changed_param_keys(old_params, new_params)
        removed_keys = set(old_params) - set(new_params)
        name_changed = force_patch or self.selected_synth[role] != str(name)

        if role == "strum" and name_changed:
            self._cancel_strum_tail()
            self._wire(f"l0i{self.synth_id['strum']}Z")
        if role == "chord" and (name_changed or removed_keys):
            self._wire(f"l0i{self.synth_id['rhythm_chord']}Z")

        self.selected_synth[role] = str(name)
        self.synth_params[role] = new_params
        patch_required = name_changed or bool(removed_keys)
        if patch_required:
            self._configure_synth(role)
        elif changed_keys:
            self._apply_supported_params(role, changed_keys)

        if role == "chord" and patch_required:
            self._restore_manual_chord_after_patch()

    # ------------------------------------------------------------------
    # Original-Omnichord-style strum gate
    # ------------------------------------------------------------------

    def _emit_strum_gate_level(self, level: float) -> None:
        self._strum_gate_level = max(0.0, min(1.0, float(level)))
        synth = self.synth_id["strum"]
        effective = self.volume["strum"] * self._strum_gate_level
        self._wire(f"i{synth}iV{self._f(effective)}Z")

    def _schedule_gate_level(
        self,
        generation: int,
        delay_s: float,
        level: float,
        *,
        final: bool = False,
    ) -> None:
        def apply() -> None:
            if generation != self._strum_gate_generation:
                return
            self._emit_strum_gate_level(level)
            if not final:
                return
            synth = self.synth_id["strum"]
            with self._strum_lock:
                if generation != self._strum_gate_generation:
                    return
                self._strum_active_notes.clear()
            self._wire(f"l0i{synth}Z")

        timer = threading.Timer(max(0.0, delay_s), apply)
        timer.daemon = True
        timer.start()

    def _set_strum_gate(self, value: Any) -> None:
        if not isinstance(value, dict):
            return
        was_enabled = self._strum_gate_enabled
        self._strum_gate_enabled = bool(value.get("enabled", was_enabled))
        self._strum_gate_attack = max(
            0.0,
            min(1.0, float(value.get("attack", self._strum_gate_attack))),
        )
        self._strum_gate_sustain = max(
            0.0,
            min(1.0, float(value.get("sustain", self._strum_gate_sustain))),
        )
        if was_enabled and not self._strum_gate_enabled:
            self._strum_gate_generation += 1
            self._emit_strum_gate_level(1.0)

    def _cancel_strum_tail(self) -> None:
        self._strum_gate_generation += 1
        super()._cancel_strum_tail()

    def _set_volume(self, role: str, value: Any) -> None:
        if role != "strum" or not self._strum_gate_enabled:
            super()._set_volume(role, value)
            return
        level = max(0.0, min(1.0, float(value)))
        self.volume[role] = level
        self._emit_strum_gate_level(self._strum_gate_level)

    def _strum_note_on(self, note: float) -> None:
        if not self._strum_gate_enabled:
            super()._strum_note_on(note)
            return

        synth = self.synth_id["strum"]
        midi_key = int(round(note))
        self._strum_gate_generation += 1
        generation = self._strum_gate_generation

        with self._strum_lock:
            duplicate_index = next(
                (
                    i
                    for i, old_note in enumerate(self._strum_active_notes)
                    if int(round(old_note)) == midi_key
                ),
                None,
            )
            if duplicate_index is not None:
                old = self._strum_active_notes.pop(duplicate_index)
                self._wire(f"n{self._f(old)}l0i{synth}Z")

            max_live = max(1, self.voice_count["strum"])
            while len(self._strum_active_notes) >= max_live:
                old = self._strum_active_notes.pop(0)
                self._wire(f"n{self._f(old)}l0i{synth}Z")

            # The gate is outside the selected timbre: every ROM patch and the
            # physical-string program therefore receives the same Omnichord
            # articulation without rewriting its native oscillator envelopes.
            self._emit_strum_gate_level(0.0)
            self._wire(f"n{self._f(note)}l1i{synth}Z")
            self._strum_active_notes.append(note)

        # Normalized UI knobs map to an RC-like opening and decay. Attack is
        # deliberately much shorter than sustain: 0..300 ms and 60..1600 ms.
        attack_s = 0.300 * self._strum_gate_attack
        sustain_s = 0.060 + 1.540 * self._strum_gate_sustain

        attack_steps = 6 if attack_s > 0.001 else 1
        for step in range(1, attack_steps + 1):
            frac = step / attack_steps
            self._schedule_gate_level(generation, attack_s * frac, frac)

        decay_steps = 10
        for step in range(1, decay_steps + 1):
            frac = step / decay_steps
            self._schedule_gate_level(
                generation,
                attack_s + sustain_s * frac,
                1.0 - frac,
                final=(step == decay_steps),
            )

    def send_message(self, address: str, value: Any) -> None:
        if str(address) == STRUM_GATE_ADDRESS:
            self._set_strum_gate(value)
            return
        super().send_message(address, value)


class ProgramAmyLocalClient(ProgramAmySerialClient):
    def __init__(
        self,
        config: dict[str, Any],
        addresses: dict[str, str],
    ) -> None:
        super().__init__(
            config=config,
            addresses=addresses,
            writer_factory=base._LocalAmyWriter,
        )
