from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication


ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = ROOT / "code"
sys.path.insert(0, str(CODE_DIR))

import main as omnichord  # noqa: E402
from amy_serial import AmySerialClient, load_amy_config  # noqa: E402
from test_control import TestControlServer  # noqa: E402


def main() -> int:
    args = omnichord.parse_arguments()

    defaults = omnichord.load_defaults(omnichord.CONFIG_DIR / "defaults.json")
    chords = omnichord.load_chords(omnichord.MUSIC_DIR / "chords.csv")
    (
        synths,
        legacy_chord_synth_index,
        legacy_strum_synth_index,
        legacy_bass_synth_index,
    ) = omnichord.load_synth_catalog(omnichord.INSTRUMENT_DIR / "synths.json")
    rhythms = omnichord.load_rhythm_catalog(omnichord.MUSIC_DIR / "rhythms.json")
    intonation_eq = omnichord.load_intonation_table(omnichord.MUSIC_DIR / "intonation_eq.json")
    intonation_harm = omnichord.load_intonation_table(omnichord.MUSIC_DIR / "intonation_harm.json")
    intonation_jv = omnichord.load_intonation_table(omnichord.MUSIC_DIR / "intonation_jv.json")

    synth_index_by_key = {synth.key: index for index, synth in enumerate(synths)}

    def startup_synth_index(role: str, fallback_index: int) -> int:
        key = str(defaults.get("synths", {}).get(role, ""))
        return synth_index_by_key.get(key, fallback_index)

    amy_config = load_amy_config(args.amy_config.expanduser().resolve())
    if args.serial_port is not None:
        amy_config["serial"]["port"] = args.serial_port
    if args.serial_baud is not None:
        amy_config["serial"]["baud"] = args.serial_baud

    address_map = {
        "chord_state": args.chord_state_address,
        "manual_chord": args.chord_manual_address,
        "chord_amp": args.chord_amp_address,
        "strum_amp": args.strum_amp_address,
        "bass_amp": args.bass_amp_address,
        "percussion_amp": args.percussion_amp_address,
        "chord_synth": args.chord_synth_address,
        "chord_params": args.chord_params_address,
        "strum_synth": args.strum_synth_address,
        "strum_params": args.strum_params_address,
        "bass_synth": args.bass_synth_address,
        "bass_params": args.bass_params_address,
        "bass_running": args.bass_running_address,
        "strum_note": args.strum_note_address,
        "rhythm_config": args.rhythm_config_address,
        "rhythm_running": args.rhythm_running_address,
        "rhythm_chord_enabled": args.rhythm_chord_enabled_address,
        "panic": args.panic_address,
    }

    app = QCoreApplication(sys.argv)
    app.setApplicationName("Qt Omnichord headless integration test")

    amy_client = AmySerialClient(config=amy_config, addresses=address_map)
    backend = omnichord.InstrumentBackend(
        chords=chords,
        synths=synths,
        rhythms=rhythms,
        intonation_eq=intonation_eq,
        intonation_harm=intonation_harm,
        intonation_jv=intonation_jv,
        default_chord_synth_index=startup_synth_index("chord", legacy_chord_synth_index),
        default_strum_synth_index=startup_synth_index("strum", legacy_strum_synth_index),
        default_bass_synth_index=startup_synth_index("bass", legacy_bass_synth_index),
        defaults=defaults,
        client=amy_client,
        chord_state_address=args.chord_state_address,
        chord_manual_address=args.chord_manual_address,
        chord_amp_address=args.chord_amp_address,
        strum_amp_address=args.strum_amp_address,
        bass_amp_address=args.bass_amp_address,
        percussion_amp_address=args.percussion_amp_address,
        chord_synth_address=args.chord_synth_address,
        chord_params_address=args.chord_params_address,
        strum_synth_address=args.strum_synth_address,
        strum_params_address=args.strum_params_address,
        bass_synth_address=args.bass_synth_address,
        bass_params_address=args.bass_params_address,
        bass_running_address=args.bass_running_address,
        strum_note_address=args.strum_note_address,
        rhythm_config_address=args.rhythm_config_address,
        rhythm_running_address=args.rhythm_running_address,
        rhythm_chord_enabled_address=args.rhythm_chord_enabled_address,
        panic_address=args.panic_address,
        debug_enabled=(args.debug or args.debug_file is not None),
        debug_file=args.debug_file,
    )

    port = int(os.environ.get("OMNICHORD_TEST_API_PORT", "18765"))
    test_server = TestControlServer(backend, port)
    print(
        f"Test control API: http://127.0.0.1:{test_server.port}",
        file=sys.stderr,
        flush=True,
    )

    backend.send_initial_state()
    try:
        return app.exec()
    finally:
        test_server.close()
        amy_client.close()


if __name__ == "__main__":
    raise SystemExit(main())
