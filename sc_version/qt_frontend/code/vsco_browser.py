from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sample_programs import articulation_program_id, load_vsco_programs


@dataclass(frozen=True, slots=True)
class VscoBrowserChoice:
    program_id: str
    family: str
    variant: str
    articulation: str


def _art(program: str, articulation: str) -> str:
    return articulation_program_id(program, articulation)


def _group(
    family: str,
    variant: str,
    articulations: tuple[tuple[str, str], ...],
) -> tuple[VscoBrowserChoice, ...]:
    return tuple(
        VscoBrowserChoice(program_id, family, variant, articulation)
        for articulation, program_id in articulations
    )


# Presentation metadata, not audio policy. Every pitched source in the
# installed VSCO bank appears exactly once. Key-switch programs are preferred
# where they expose the same recordings as standalone source entries.
_CHOICES = (
    *_group("Bassoon", "Solo", (("Staccato", "sample.vsco.bassoonstac"), ("Sustain", "sample.vsco.bassoonsus"), ("Vibrato", "sample.vsco.bassoonvib"))),
    *_group("Cello", "Ensemble", (("Sustain", "sample.vsco.celloens-ks"), ("Tremolo", _art("sample.vsco.celloens-ks", "c-6-tremolo")), ("Pizzicato", _art("sample.vsco.celloens-ks", "d-6-pizzicato")), ("Spiccato", _art("sample.vsco.celloens-ks", "d6-spiccato")), ("Quiet sustain", "sample.vsco.celloenssusvib-quiet"))),
    *_group("Clarinet", "Solo", (("Sustain", "sample.vsco.clarinet-ks"), ("Staccato", _art("sample.vsco.clarinet-ks", "c-2-staccato")))),
    *_group("Contrabass", "Solo", (("Sustain", "sample.vsco.contrabass-ks"), ("Vibrato", _art("sample.vsco.contrabass-ks", "c-6-sustain-vibrato")), ("Spiccato", _art("sample.vsco.contrabass-ks", "d-6-spiccato")), ("Tremolo", _art("sample.vsco.contrabass-ks", "d6-tremolo")), ("Pizzicato", _art("sample.vsco.contrabass-ks", "e6-pizzicato")), ("Quiet vibrato", "sample.vsco.contrabasssusvb-quiet"))),
    *_group("French horn", "Solo", (("Sustain", "sample.vsco.fhornsus"), ("Staccato", "sample.vsco.fhornstac"), ("Muted", "sample.vsco.fhornmute"))),
    *_group("Flute", "Solo", (("Sustain", "sample.vsco.flute-ks"), ("Vibrato", _art("sample.vsco.flute-ks", "c-2-sustain-vibrato")), ("Expressive", _art("sample.vsco.flute-ks", "d2-expression-vibrato")), ("Staccato", _art("sample.vsco.flute-ks", "d-2-staccato")))),
    *_group("Glockenspiel", "Standard", (("Normal", "sample.vsco.glockenspiel"),)),
    *_group("Harp", "Standard", (("Normal", "sample.vsco.harp"),)),
    *_group("Marimba", "Standard", (("Normal", "sample.vsco.marimba"),)),
    *_group("Oboe", "Solo", (("Sustain", "sample.vsco.oboesusnv"), ("Vibrato", "sample.vsco.oboesusvib"), ("Staccato", "sample.vsco.oboestac"))),
    *_group("Organ", "Loud", (("Manual", "sample.vsco.organloud"), ("Pedal", "sample.vsco.organloudpedal"))),
    *_group("Organ", "Quiet", (("Manual", "sample.vsco.organquiet"), ("Pedal", "sample.vsco.organquietpedal"))),
    *_group("Piccolo", "Solo", (("Sustain", "sample.vsco.piccolosus"), ("Staccato", "sample.vsco.piccolostac"))),
    *_group("Solo violin", "Solo", (("Sustain", "sample.vsco.sviolin-ks"), ("Tremolo", _art("sample.vsco.sviolin-ks", "c-2-tremolo")), ("Pizzicato", _art("sample.vsco.sviolin-ks", "d-2-pizzicato")), ("Spiccato", _art("sample.vsco.sviolin-ks", "d2-spiccato")), ("Quiet sustain", "sample.vsco.sviolinvib-quiet"))),
    *_group("Timpani", "Standard", (("Hit", "sample.vsco.timpani"), ("Roll", "sample.vsco.timpanirolls"))),
    *_group("Trombone", "Solo", (("Sustain", "sample.vsco.trombonesus"), ("Vibrato", "sample.vsco.trombonevib"), ("Staccato", "sample.vsco.trombonestac"))),
    *_group("Trumpet", "Open", (("Sustain", "sample.vsco.trumpetsus"), ("Vibrato", "sample.vsco.trumpetsusvib"), ("Staccato", "sample.vsco.trumpetstac"))),
    *_group("Trumpet", "Harmon mute", (("Sustain", "sample.vsco.trumpetharmonmutesus"),)),
    *_group("Trumpet", "Straight mute", (("Sustain", "sample.vsco.trumpetstraightmutesus"),)),
    *_group("Tuba", "Solo", (("Sustain", "sample.vsco.tuba-ks"), ("Staccato", _art("sample.vsco.tuba-ks", "c-6-staccato")))),
    *_group("Tubular bells", "Standard", (("Normal", "sample.vsco.tubularbells"),)),
    *_group("Piano", "Upright", (("Normal", "sample.vsco.uprightpiano"),)),
    *_group("Piano", "VS Upright", (("Normal", "sample.vsco.vsupright1"),)),
    *_group("Viola", "Ensemble", (("Sustain", "sample.vsco.violaens-ks"), ("Tremolo", _art("sample.vsco.violaens-ks", "c-2-tremolo")), ("Pizzicato", _art("sample.vsco.violaens-ks", "d-2-pizzicato")), ("Spiccato", _art("sample.vsco.violaens-ks", "d2-spiccato")), ("Quiet sustain", "sample.vsco.violaenssusvib-quiet"))),
    *_group("Violin", "Ensemble", (("Sustain", "sample.vsco.violinens-ks"), ("Tremolo", _art("sample.vsco.violinens-ks", "c-2-tremolo")), ("Pizzicato", _art("sample.vsco.violinens-ks", "d-2-pizzicato")), ("Spiccato", _art("sample.vsco.violinens-ks", "d2-spiccato")), ("Quiet sustain", "sample.vsco.violinenssusvib-quiet"))),
    *_group("Xylophone", "Standard", (("Normal", "sample.vsco.xylophone"),)),
)


REDUNDANT_SOURCE_PROGRAMS = frozenset({
    "sample.vsco.celloenspizz", "sample.vsco.celloensspic", "sample.vsco.celloenssusvib", "sample.vsco.celloenstrem",
    "sample.vsco.clarinetstac", "sample.vsco.clarinetsus",
    "sample.vsco.contrabasspizz", "sample.vsco.contrabassspic", "sample.vsco.contrabasssusnv", "sample.vsco.contrabasssusvb", "sample.vsco.contrabasstrem",
    "sample.vsco.fluteexpvib", "sample.vsco.flutestac", "sample.vsco.flutesusnv", "sample.vsco.flutesusvib",
    "sample.vsco.sviolinpizz", "sample.vsco.sviolinspic", "sample.vsco.sviolintrem", "sample.vsco.sviolinvib",
    "sample.vsco.tubastac", "sample.vsco.tubasus",
    "sample.vsco.violaenspizz", "sample.vsco.violaensspic", "sample.vsco.violaenssusvib", "sample.vsco.violaenstrem",
    "sample.vsco.violinenspizz", "sample.vsco.violinensspic", "sample.vsco.violinenssusvib", "sample.vsco.violinenstrem",
})


def load_vsco_browser(path: Path) -> tuple[VscoBrowserChoice, ...]:
    """Return a compact, curated view containing every pitched VSCO source."""

    programs = {item.program_id: item for item in load_vsco_programs(path)}
    missing = sorted({choice.program_id for choice in _CHOICES} - programs.keys())
    if missing:
        raise ValueError(f"VSCO browser references unknown programs: {', '.join(missing)}")
    source_programs = {item.source_program_id for item in programs.values()}
    represented = {programs[choice.program_id].source_program_id for choice in _CHOICES}
    expected = source_programs - {"sample.vsco.gm-styleperc"}
    if represented | REDUNDANT_SOURCE_PROGRAMS != expected:
        missing_sources = sorted(expected - represented - REDUNDANT_SOURCE_PROGRAMS)
        extra_sources = sorted((represented | REDUNDANT_SOURCE_PROGRAMS) - expected)
        raise ValueError(
            "VSCO browser source coverage mismatch; "
            f"missing={missing_sources}, extra={extra_sources}"
        )
    identities = [choice.program_id for choice in _CHOICES]
    if len(identities) != len(set(identities)):
        raise ValueError("VSCO browser contains duplicate program choices")
    return _CHOICES
