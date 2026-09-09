from __future__ import annotations

from typing import Any

import amy_transport as base
from config_loader import ResolvedAmyConfig
from synth_programs import SynthProgram, resolve_program
from tb303 import PROGRAM_KIND as TB303_PROGRAM_KIND
from tb303 import SEQUENCE_PARAMETER_KEYS as TB303_SEQUENCE_PARAMETER_KEYS
from tb303 import Tb303Parameters, compile_voice_commands


KS_WAVE = 6
KS_DECAY_CONTROL = "ks_feedback"
REVERB_LEVEL_MAX = 3.0
DRUM_PREVIEW_SAMPLES = (
    "drum_bass_hard",
    "drum_tom_lo_soft",
    "drum_snare_hard",
    "drum_tom_mid_soft",
    "drum_tom_hi_soft",
    "drum_cymbal_closed",
    "drum_cymbal_open",
    "perc_bell",
)


class ProgramAmySerialClient(base.AmySerialClient):
    """AMY client whose instrument identity is a SynthProgram, not a patch id."""

    def _program(self, role: str) -> SynthProgram | None:
        # Several transport unit tests deliberately exercise methods on a
        # partially constructed client. The generalized layer must remain a
        # transparent extension in that case, not make the old low-level
        # contracts depend on full application configuration.
        config = getattr(self, "resolved_config", None)
        selected = getattr(self, "selected_synth", None)
        if not isinstance(config, ResolvedAmyConfig) or not isinstance(selected, dict):
            return None
        key = selected.get(role)
        if key is None:
            return None
        return resolve_program(str(key), config)

    def preview_drum(self, preview_index: int) -> None:
        """Add one Drum Kit 0 preview hit without changing drum configuration."""
        name = DRUM_PREVIEW_SAMPLES[
            max(0, min(len(DRUM_PREVIEW_SAMPLES) - 1, int(preview_index)))
        ]
        hit = self.resolved_config.drums.sample(name)
        if hit is None:
            return
        gain = max(0.0, self.resolved_config.drums.velocity_gain)
        self._wire(
            f"p{hit.preset}n{self._f(float(hit.note))}"
            f"l{self._f(gain)}i{self.synth_id['drums']}Z"
        )

    def _set_reverb(self, value: Any) -> None:
        """Accept the Omnichord's extended 0..3 wet-return gain range."""
        if not isinstance(value, dict):
            return
        updated = {
            "level": max(
                0.0,
                min(
                    REVERB_LEVEL_MAX,
                    float(value.get("level", self.reverb["level"])),
                ),
            ),
            "liveness": max(
                0.0,
                min(1.0, float(value.get("liveness", self.reverb["liveness"]))),
            ),
            "damping": max(
                0.0,
                min(1.0, float(value.get("damping", self.reverb["damping"]))),
            ),
            "drums": bool(value.get("drums", self.reverb["drums"])),
        }
        if updated == self.reverb:
            return
        self.reverb = updated
        self._apply_reverb_buses()

    def _set_rhythm_config(self, payload_text: str) -> None:
        """Use the common reusable-sequence transport for every synth program."""
        super()._set_rhythm_config(payload_text)

    def _configure_program_one(
        self, role: str, synth: int, program: SynthProgram
    ) -> None:
        self._bump_synth_generation(synth)
        self._wire(f"l0i{synth}Z")
        voices = self._voice_count_for_synth(synth)
        bus = self._bus_for_synth(synth)

        # Explicit voice geometry makes a physical model no different from a
        # ROM patch to AMY's synth allocator. Re-stating it is intentional:
        # the previous program may have been a 6-osc Juno or 8-osc DX7 voice.
        flag_fields = self._synth_flag_fields(synth)
        self._wire(
            f"i{synth}iv{voices}in{program.oscs_per_voice}"
            f"iy{bus}{flag_fields}Z"
        )
        self._configured_synths.add(synth)
        guard_ms = self.resolved_config.performance.synth_alloc_guard_ms
        self.writer.delay(max(0.0, guard_ms) / 1000.0)
        if program.kind == "karplus_strong":
            wave = KS_WAVE if program.wave is None else int(program.wave)
            feedback = 0.985 if program.feedback is None else program.feedback
            self._wire(f"v0w{wave}b{self._f(feedback)}i{synth}Z")
        elif program.kind == TB303_PROGRAM_KIND:
            parameters = Tb303Parameters.from_mapping(self.synth_params[role])
            for command in compile_voice_commands(
                synth=synth,
                parameters=parameters,
                selected_keys=(),
                initialize=True,
            ):
                self._wire(command)
        else:
            raise ValueError(f"unsupported non-ROM program {program.kind!r}")

        self._route_synth_bus(synth)
        level = self._output_level(role)
        self._wire(f"i{synth}iV{self._f(level)}Z")
        self._apply_reverb_bus(bus)

    def _program_param_commands(
        self,
        role: str,
        synth: int,
        program: SynthProgram,
        parameter_keys: set[str] | None = None,
    ) -> list[str]:
        if program.kind == "karplus_strong":
            if parameter_keys is not None and KS_DECAY_CONTROL not in parameter_keys:
                return []
            feedback = self.synth_params[role].get(
                KS_DECAY_CONTROL,
                0.985 if program.feedback is None else program.feedback,
            )
            feedback = max(0.0, min(0.9999, float(feedback)))
            return [f"v0b{self._f(feedback)}i{synth}Z"]
        if program.kind == TB303_PROGRAM_KIND:
            return list(
                compile_voice_commands(
                    synth=synth,
                    parameters=Tb303Parameters.from_mapping(
                        self.synth_params[role]
                    ),
                    selected_keys=parameter_keys,
                )
            )
        return []

    def _strum_note_on(self, note: float) -> None:
        program = self._program("strum")
        if program is not None and program.kind == "karplus_strong":
            raw = self.resolved_config.synth_program(program.key) or {}
            start = float(raw.get("high_note_start", 60.0))
            full = max(start + 1.0, float(raw.get("high_note_full", 96.0)))
            maximum = max(1.0, float(raw.get("high_note_gain", 1.0)))
            amount = max(0.0, min(1.0, (float(note) - start) / (full - start)))
            level = (
                self._output_level("strum")
                * (1.0 + amount * (maximum - 1.0))
            )
            self._wire(f"i{self.synth_id['strum']}iV{self._f(level)}Z")
        super()._strum_note_on(note)

    def _configure_synth(self, role: str) -> None:
        program = self._program(role)
        if program is None or program.is_rom_patch:
            super()._configure_synth(role)
            return
        for synth in self._role_synth_ids(role):
            self._configure_program_one(role, synth, program)
            for command in self._program_param_commands(role, synth, program):
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
        for synth in self._role_synth_ids(role):
            for command in self._program_param_commands(
                role,
                synth,
                program,
                parameter_keys,
            ):
                self._wire(command)

    def _bass_sequence_parameters(self) -> Tb303Parameters | None:
        program = self._program("bass")
        if program is None or program.kind != TB303_PROGRAM_KIND:
            return None
        return Tb303Parameters.from_mapping(self.synth_params["bass"])

    def _apply_synth_state(
        self,
        role: str,
        name: str,
        params: dict[str, float],
        *,
        force_patch: bool = False,
    ) -> None:
        config = getattr(self, "resolved_config", None)
        if not isinstance(config, ResolvedAmyConfig):
            super()._apply_synth_state(
                role, name, params, force_patch=force_patch
            )
            return

        program = resolve_program(str(name), config)
        if program is None:
            print(f"AMY warning: refusing unknown synth program {name!r}", flush=True)
            return
        old_name = self.selected_synth[role]
        old_program = resolve_program(old_name, config)
        old_is_tb303 = (
            old_program is not None and old_program.kind == TB303_PROGRAM_KIND
        )
        new_is_tb303 = program.kind == TB303_PROGRAM_KIND

        if program.is_rom_patch:
            super()._apply_synth_state(
                role, name, params, force_patch=force_patch
            )
            if role == "bass" and self.rhythm_running and old_is_tb303:
                self._replace_lane("bass")
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
        if (
            role == "bass"
            and self.rhythm_running
            and (
                old_is_tb303 != new_is_tb303
                or (
                    new_is_tb303
                    and bool(
                        (changed_keys | removed_keys)
                        & TB303_SEQUENCE_PARAMETER_KEYS
                    )
                )
            )
        ):
            self._replace_lane("bass")


class ProgramAmySocketClient(ProgramAmySerialClient):
    """Program-aware wire client for an external local AMY service."""

    def __init__(
        self,
        config: dict[str, Any] | None,
        addresses: dict[str, str],
        socket_path: str,
        resolved_config: ResolvedAmyConfig | None = None,
    ) -> None:
        super().__init__(
            config=config,
            addresses=addresses,
            resolved_config=resolved_config,
            writer_factory=lambda debug_log: base._UnixSocketWriter(
                socket_path,
                debug_log,
            ),
        )


class ProgramAmyLocalClient(ProgramAmySerialClient):
    """Program-aware client for Qt's native local IPC transport."""

    def __init__(
        self,
        config: dict[str, Any] | None,
        addresses: dict[str, str],
        server_name: str,
        resolved_config: ResolvedAmyConfig | None = None,
    ) -> None:
        super().__init__(
            config=config,
            addresses=addresses,
            resolved_config=resolved_config,
            writer_factory=lambda debug_log: base._QtLocalSocketWriter(
                server_name,
                debug_log,
            ),
        )
