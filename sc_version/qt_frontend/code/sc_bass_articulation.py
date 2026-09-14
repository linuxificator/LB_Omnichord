from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
from types import MappingProxyType

from bass_riffs import BassRiffDefinition, BassRiffEvent
from sc_music_catalog import ScMusicCatalog


@dataclass(frozen=True, slots=True)
class BassContext:
    profile: str
    family: str


class ScBassArticulationResolver:
    """Resolve neutral bass timing against the currently sounding drum context."""

    def __init__(self, contexts: dict[tuple[str, str], BassContext]) -> None:
        self._contexts = MappingProxyType(dict(contexts))

    def context(self, kit_id: str, rhythm_id: str) -> BassContext:
        key = (str(kit_id), str(rhythm_id))
        try:
            return self._contexts[key]
        except KeyError as exc:
            raise ValueError(f"unknown SC bass articulation context {key!r}") from exc

    @property
    def context_count(self) -> int:
        return len(self._contexts)

    def resolve(
        self,
        riff: BassRiffDefinition,
        *,
        kit_id: str,
        rhythm_id: str,
        percussion_activity: int,
        drum_catalog: ScMusicCatalog,
    ) -> BassRiffDefinition:
        context = self.context(kit_id, rhythm_id)
        level = max(1, min(5, int(percussion_activity)))
        arrangement = drum_catalog.arrangement(kit_id, rhythm_id)
        drums = arrangement.levels[level - 1]
        anchors = {
            event.tick
            for event in drums
            if {"low_primary", "backbeat_primary"}.intersection(
                event.semantic_roles
            )
        }
        busy = {
            event.tick
            for event in drums
            if {"hand_high", "hand_low", "ghost_detail"}.intersection(
                event.semantic_roles
            )
        }
        events = tuple(
            self._resolve_event(
                event,
                next_event=riff.events[(index + 1) % len(riff.events)],
                index=index,
                count=len(riff.events),
                phrase_ticks=riff.phrase_ticks,
                arrangement_period=arrangement.period_ticks,
                anchors=anchors,
                busy=busy,
                rhythm_id=rhythm_id,
                context=context,
            )
            for index, event in enumerate(riff.events)
        )
        if events and all(event.link_to_next != "none" for event in events):
            raise ValueError(f"resolved bass riff {riff.riff_id!r} has no release")
        return replace(riff, events=events)

    @staticmethod
    def _resolve_event(
        source: BassRiffEvent,
        *,
        next_event: BassRiffEvent,
        index: int,
        count: int,
        phrase_ticks: int,
        arrangement_period: int,
        anchors: set[int],
        busy: set[int],
        rhythm_id: str,
        context: BassContext,
    ) -> BassRiffEvent:
        gap = (next_event.tick - source.tick) % phrase_ticks or phrase_ticks
        phase = source.tick % arrangement_period
        is_approach = source.role == "chromatic_approach"
        duration = source.duration_ticks
        velocity = source.velocity
        accent = source.accent
        accent_amount = 0.65 if accent else 0.0
        link = "none"
        gate_policy = "authored_detached"
        glide_ms = 0.0

        if (
            not is_approach
            and source.role == "chord_tone"
            and phase in anchors
            and context.family not in ("latin", "four_floor")
        ):
            velocity = min(112, velocity + 3)
            accent = True
            accent_amount = max(0.45, accent_amount)

        if is_approach:
            accent = False
            accent_amount = 0.0
            velocity = min(78, velocity)
            duration = min(duration, _even_ticks(gap - 2))
        elif context.profile in ("old", "concert") and rhythm_id in (
            "slow_ballad",
            "six_eight_ballad",
            "waltz",
            "country_waltz",
        ):
            duration = _even_ticks(gap * 0.90)
            gate_policy = "long_breath_with_releases"
        elif context.profile in ("son", "brazil", "hand") and phase in busy and gap >= 48:
            duration = min(duration, _even_ticks(gap * 0.65))
            gate_policy = "space_for_hand_percussion"
        elif context.profile in ("tight", "sc-electro", "found") and context.family in (
            "funk",
            "breaks",
        ):
            duration = min(duration, _even_ticks(gap * 0.68))
            gate_policy = "short_syncopated_attack"
        elif context.profile in ("metal", "found") and context.family == "odd":
            duration = min(duration, _even_ticks(gap * 0.55))
            gate_policy = "space_between_metal_resonances"

        if (
            rhythm_id in ("salsa", "son_clave_3_2", "mambo")
            and source.tick % 384 == 288
            and not is_approach
        ):
            duration = _even_ticks(gap - 4)
            gate_policy = "tumbao_anticipation_carries_bar"

        if (
            rhythm_id in ("slow_ballad", "six_eight_ballad", "waltz")
            and context.profile in ("old", "concert")
            and not is_approach
            and next_event.pitch_offset == source.pitch_offset
            and not next_event.accent
            and gap <= 192
            and index % 2 == 0
        ):
            link = "tie"
            duration = gap
            gate_policy = "same_pitch_tie"

        if (
            is_approach
            and rhythm_id
            in ("house", "techno", "trance", "garage_2step", "drum_and_bass", "breakbeat")
            and (context.profile.startswith("sc-") or context.profile in ("tight", "found", "metal"))
            and gap <= 32
        ):
            link = "legato_glide"
            duration = gap
            glide_ms = 45.0 if rhythm_id == "drum_and_bass" else 70.0
            gate_policy = "capability_dependent_connection"

        duration = min(duration, gap)
        fallback_duration = duration
        target_index = -1
        target_cycle = 0
        if link != "none":
            target_index = (index + 1) % count
            target_cycle = 1 if index == count - 1 else 0
            fallback_duration = min(source.duration_ticks, _even_ticks(gap - 2))

        return replace(
            source,
            duration_ticks=duration,
            velocity=velocity,
            accent=accent,
            slide_to_next=False,
            link_to_next=link,
            accent_amount=accent_amount,
            gate_policy=gate_policy,
            glide_time_ms=glide_ms,
            fallback_duration_ticks=fallback_duration,
            link_target_index=target_index,
            link_target_cycle_offset=target_cycle,
        )


def _even_ticks(value: int | float) -> int:
    return max(2, int(value) // 2 * 2)


def load_sc_bass_articulation(path: Path) -> ScBassArticulationResolver:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("unsupported SC bass articulation contexts")
    contexts: dict[tuple[str, str], BassContext] = {}
    for row in raw.get("contexts", ()):
        if not isinstance(row, dict):
            raise ValueError("SC bass articulation context must be an object")
        key = (str(row["kit_id"]), str(row["rhythm_id"]))
        context = BassContext(str(row["profile"]), str(row["family"]))
        if not all((*key, context.profile, context.family)) or key in contexts:
            raise ValueError(f"invalid or duplicate SC bass context {key!r}")
        contexts[key] = context
    if len(contexts) != 810:
        raise ValueError(f"SC bass articulation requires 810 contexts, got {len(contexts)}")
    return ScBassArticulationResolver(contexts)
