from typing import Literal
from pathlib import Path
import shutil
import subprocess

# NOTE need to manually install audioop-lts
from pydub import AudioSegment, silence

from yonder import Soundbank
from yonder.util import logger


def import_wems(bnk: Soundbank, wems: list[Path]) -> None:
    from yonder.node_types import WwiseNode
    
    for wem in wems:
        if not wem.name.endswith(".wem"):
            continue

        # We allow adding additional info to the wem filename to make them easier to handle
        if "_" in wem.name:
            for part in wem.name.split("_"):
                try:
                    wem_id = int(part)
                    break
                except ValueError:
                    pass
            wem_id = int(wem_id)
        else:
            wem_id = int(wem.stem)

        # Copy to the correct location
        stream_path_rel = Path(f"wem/{str(wem_id)[:2]}/{wem.name}")
        if str(wem).endswith(str(stream_path_rel)):
            # Handle streamed sounds
            target_path = bnk.bnk_dir.parent / stream_path_rel
        else:
            target_path = bnk.bnk_dir / f"{wem_id}.wem"

        shutil.copy(wem, target_path)

        # Update memory sizes
        wem_nodes = list(bnk.query(f"'**/source_id'={wem_id}"))
        wem_size = target_path.stat().st_size
        for node in wem_nodes:
            if isinstance(node, WwiseNode):
                attr_paths = node.resolve_path("**/media_information")
                for _, media_info in attr_paths:
                    # Music tracks have multiple sources, so check if this is the right one
                    if media_info.get("source_id") == wem_id:
                        media_info["in_memory_media_size"] = wem_size


def get_wem_metadata(wem: Path) -> float:
    # Graciously taken from https://github.com/hcs64/ww2ogg/blob/master/src/wwriff.cpp
    filesize = wem.stat().st_size
    with wem.open("rb") as f:
        data: bytes = f.read(4)
        if data.decode() != "RIFF":
            raise ValueError(f"Unexpected RIFF header {data}")

        # File size
        riff_size = int.from_bytes(f.read(4), "little") + 8
        if riff_size > filesize:
            # Truncated file, but we don't really care as long as we can get the metadata
            pass

        data = f.read(4)
        if data.decode() != "WAVE":
            raise ValueError(f"Unexpected WAVE header {data}")

        offset = 12
        fmt_section = -1
        fmt_len = 0

        while offset < riff_size:
            f.seek(offset)
            data = f.read(4)
            chunk_size = int.from_bytes(f.read(4), "little")

            if data.decode() == "fmt ":
                fmt_section = offset + 8
                fmt_len = chunk_size
                break

            offset += 8 + chunk_size

        if fmt_section < 0:
            raise ValueError("Could not locate fmt section")

        f.seek(fmt_section)

        data = int.from_bytes(f.read(2), "little")
        if data != 0xFFFF:
            raise ValueError(f"Expected 0xffff marker, got {data}")

        channels = int.from_bytes(f.read(2), "little")
        sample_rate = int.from_bytes(f.read(4), "little")
        avg_bps = int.from_bytes(f.read(4), "little")

        data = int.from_bytes(f.read(4), "little")
        if data != 0x0:
            raise ValueError(f"Expected 0x0000, got {data}")

        fmt_extra_len = int.from_bytes(f.read(2), "little")
        if fmt_len - 0x12 != fmt_extra_len:
            raise ValueError(f"Bad fmt extra length {fmt_extra_len}")

        if fmt_len - 0x12 >= 2:
            # unk
            f.read(2)
            if fmt_len - 0x12 >= 6:
                # subtype
                f.read(4)

        if fmt_len == 0x28:
            data = f.read(16)
            signature = bytearray(data)
            if signature != bytes(
                [1, 0, 0, 0, 0, 0, 0x10, 0, 0x80, 0, 0, 0xAA, 0, 0x38, 0x9B, 0x71]
            ):
                raise ValueError(f"Expected signature not found, got {signature}")

        samples = int.from_bytes(f.read(4), "little")

    meta = {
        "channels": channels,
        "sample_rate": sample_rate,
        "avg_bps": avg_bps,
        "samples": samples,
        "duration": samples / sample_rate,
        "filesize": filesize,
        "in_memory_size": len(wem.read_bytes()),
    }
    return meta


def set_volume(wav: Path, volume: float, *, out_file: Path = None) -> Path:
    audio: AudioSegment = AudioSegment.from_file(wav)
    audio = audio.apply_gain(volume)
    audio.export(str(out_file or wav), format="wav")
    return out_file


def create_prefetch_snippet(
    wav: Path, length: float = 200, *, out_file: Path = None
) -> Path:
    if not out_file:
        out_file = wav.parent / f"{wav.stem}_snippet.wav"

    audio: AudioSegment = AudioSegment.from_file(str(wav))
    audio = audio[:int(length)]
    audio.export(str(out_file), format="wav")
    return Path(out_file)


def trim_silence(
    wav: Path,
    threshold: float = None,
    *,
    min_silence_length: float = 500,
    start_end_tolerance: float = 500,
    out_file: Path = None,
) -> Path:
    audio: AudioSegment = AudioSegment.from_file(str(wav))

    if not threshold:
        threshold = audio.dBFS

    quiets = silence.detect_silence(
        audio,
        min_silence_len=min_silence_length,
        silence_thresh=threshold,
    )
    start = 0
    end = len(audio)

    # A quiet section close to the beginning
    if quiets and quiets[0][0] <= start_end_tolerance:
        start = quiets[0][1]

    # A quiet section close to the end
    if len(quiets) > 1 and quiets[-1][1] >= len(audio) - start_end_tolerance:
        end = quiets[-1][0]

    audio = audio[start:end]
    audio.export(str(out_file or wav), format="wav")
    return Path(out_file or wav)


def wav2wem(
    wwise_exe: Path,
    waves: list[Path] | Path,
    out_dir: Path = None,
    conversion: Literal["PCM", "Vorbis Quality High"] = "Vorbis Quality High",
    keep_proj_dir: bool = False,
) -> list[Path]:
    if isinstance(waves, Path):
        waves = [waves]

    wav_dir = waves[0].parent
    if not out_dir:
        out_dir = wav_dir

    source_lines = []
    for wav in waves:
        if not wav.is_file():
            logger.error(f"FileNotFound: {wav}")
            continue

        # NOTE as long as all paths are absolute this should be fine
        source_lines.append(
            f'<Source Path="{wav.resolve()}" Conversion="{conversion}"/>'
        )

    # Create a list of files to convert
    # Thanks to https://github.com/EternalLeo/sound2wem for the template!
    wsources_path = wav_dir / "list.wsources"
    wsources_path.write_text(
        f"""\
<?xml version="1.0" encoding="UTF-8"?>
<ExternalSourcesList SchemaVersion="1" Root="{wav_dir}">
	{"\n".join(source_lines)}
</ExternalSourcesList>
"""
    )

    # Create a wwise project if it doesn't exist yet
    # NOTE parent folder and project file MUST have the same name!
    wproj_path = wav_dir / "yonder_wav2wem/yonder_wav2wem.wproj"
    if not wproj_path.is_file():
        try:
            subprocess.check_output(
                [str(wwise_exe), "create-new-project", str(wproj_path), "--quiet"]
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Creating wwise project failed: {e.output}")
            raise e

    # Convert the wav files by passing the wsources list to wwise
    try:
        subprocess.check_output(
            [
                str(wwise_exe),
                "convert-external-source",
                str(wproj_path),
                "--source-file",
                str(wsources_path),
                "--output",
                str(out_dir),
                "--quiet",
            ]
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"Conversion failed: {e.output}")
        raise e

    # Generated files will be stored in a Windows folder (on Windows)
    wwise_out_dir = out_dir / "Windows"
    for file in wwise_out_dir.glob("*"):
        (out_dir / file.name).unlink(missing_ok=True)
        shutil.move(file, out_dir)

    # Cleanup
    wsources_path.unlink()
    shutil.rmtree(wwise_out_dir)
    if not keep_proj_dir:
        shutil.rmtree(wproj_path.parent)

    return [out_dir / f"{f.stem}.wem" for f in waves]


def wem2wav(
    vgmstream_exe: Path,
    wems: list[Path] | Path,
    out_dir: Path = None,
) -> list[Path]:
    if isinstance(wems, Path):
        wems = [wems]

    if not out_dir:
        out_dir = wems[0].parent

    out_files = []

    for wem in wems:
        try:
            if not wem.is_file():
                logger.error(f"FileNotFound: {wem}")
                out_files.append(None)
                continue

            target = out_dir / (wem.stem + ".wav")
            subprocess.check_output(
                [
                    str(vgmstream_exe),
                    "-i",  # ignore looping
                    "-o",
                    str(target),
                    str(wem),
                ]
            )
            out_files.append(target)
        except subprocess.CalledProcessError as e:
            logger.error(f"Conversion failed ({e.returncode}):\n{e.output}")
            out_files.append(None)

    return out_files
