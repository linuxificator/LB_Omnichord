from __future__ import annotations

from pathlib import Path
import struct
import sys
import tempfile
import unittest
import wave


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from sfz_manifest_compiler import (  # noqa: E402
    _midi_note,
    compile_vsco_manifest,
    parse_sfz,
)


class SfzManifestCompilerTests(unittest.TestCase):
    @staticmethod
    def _append_smpl_loop(
        path: Path,
        *,
        root_key: int,
        start: int,
        end_inclusive: int,
    ) -> None:
        payload = struct.pack(
            "<9I6I",
            0,
            0,
            0,
            root_key,
            0,
            0,
            0,
            1,
            0,
            1,
            0,
            start,
            end_inclusive,
            0,
            0,
        )
        chunk = b"smpl" + struct.pack("<I", len(payload)) + payload
        source = path.read_bytes()
        path.write_bytes(
            source[:4]
            + struct.pack("<I", len(source) - 8 + len(chunk))
            + source[8:]
            + chunk
        )

    def test_note_names_follow_sfz_middle_c_convention(self) -> None:
        self.assertEqual(_midi_note("c4", -1), 60)
        self.assertEqual(_midi_note("d#2", -1), 39)
        self.assertEqual(_midi_note("Bb0", -1), 22)

    def test_scopes_and_multiple_opcodes_are_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "fixture.sfz"
            path.write_text(
                """
<control> default_path=Samples\\
<global> ampeg_release=0.7
<group> sw_last=c2 sw_label=Sustain
<region> sample=one.wav lokey=60 hikey=62 pitch_keycenter=61 lovel=0 hivel=63
<region> sample=two.wav lovel=64 hivel=127
""".strip()
                + "\n",
                encoding="utf-8",
            )
            regions = parse_sfz(path)
            self.assertEqual(len(regions), 2)
            self.assertEqual(regions[0].values["default_path"], "Samples\\")
            self.assertEqual(regions[1].values["ampeg_release"], "0.7")
            self.assertEqual(regions[1].values["sw_label"], "Sustain")

    def test_unrecognized_opcode_is_a_build_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "fixture.sfz"
            path.write_text("<region> sample=one.wav mystery=1\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unsupported opcode mystery"):
                parse_sfz(path)

    def test_complete_vsco_shape_with_synthetic_bank(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            samples = root / "Samples"
            samples.mkdir()
            sample_path = samples / "one.wav"
            with wave.open(str(sample_path), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(48000)
                output.writeframes(struct.pack("<16h", *range(16)))
            mapping = (
                "<control> default_path=Samples\\\n"
                "<region> sample=one.wav lokey=60 hikey=60 pitch_keycenter=60\n"
            )
            for index in range(75):
                (root / f"Program-{index:02}.sfz").write_text(
                    mapping,
                    encoding="utf-8",
                )
            manifest = compile_vsco_manifest(root)
            self.assertEqual(len(manifest["programs"]), 75)
            self.assertEqual(len(manifest["regions"]), 75)
            self.assertEqual(len(manifest["files"]), 1)
            self.assertEqual(manifest["files"][0]["decoded_bytes"], 64)
            self.assertEqual(manifest["coverage"][0]["disposition"], "mapped-region")

    def test_embedded_wav_loop_is_inventoried_but_not_silently_activated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sample_path = root / "looped.wav"
            with wave.open(str(sample_path), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(48000)
                output.writeframes(struct.pack("<16h", *range(16)))
            self._append_smpl_loop(
                sample_path,
                root_key=64,
                start=0,
                end_inclusive=15,
            )
            mapping = (
                "<region> sample=looped.wav lokey=64 hikey=64 "
                "pitch_keycenter=64\n"
            )
            for index in range(75):
                (root / f"Program-{index:02}.sfz").write_text(
                    mapping,
                    encoding="utf-8",
                )

            manifest = compile_vsco_manifest(root)

        sample = manifest["files"][0]
        self.assertEqual(sample["embedded_root_key"], 64)
        self.assertEqual(
            sample["embedded_loops"],
            [
                {
                    "mode": "forward",
                    "start_frame": 0,
                    "end_frame_exclusive": 16,
                    "fraction": 0,
                    "play_count": 0,
                    "playback_disposition": "ignored-whole-file-loop",
                }
            ],
        )
        self.assertEqual(manifest["regions"][0]["loop"], {"mode": "none"})


if __name__ == "__main__":
    unittest.main()
