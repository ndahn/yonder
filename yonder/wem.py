from __future__ import annotations
from typing import Literal, TYPE_CHECKING
from pathlib import Path
import shutil
import subprocess

# suppress pydub warning about ffmpeg/avconv, we don't need the encoder
import warnings
warnings.filterwarnings("ignore", message="^.*find ffmpeg or avconv.*$")

# NOTE need to manually install audioop-lts
from pydub import AudioSegment, silence

from yonder.util import logger

if TYPE_CHECKING:
    from yonder import Soundbank


WWISE_VORBIS_TAG = 0xFFFF        # wwise's private "packed vorbis" marker
WAVE_FORMAT_EXTENSIBLE = 0xFFFE  # standard ms tag; real codec is the subformat guid
PCM_SUBFORMAT_GUID = bytes([1, 0, 0, 0, 0, 0, 0x10, 0, 0x80, 0, 0, 0xAA, 0, 0x38, 0x9B, 0x71])


def import_wems(bnk: Soundbank, wems: list[Path]) -> None:
    from yonder import HIRCNode
    from yonder.types.base_types import MediaInformation

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
        stream_path_rel = f"wem/{str(wem_id)[:2]}/{wem.name}"
        if str(wem).endswith(str(stream_path_rel)):
            # Handle streamed sounds
            target_path = bnk.bnk_dir.parent / stream_path_rel
        else:
            target_path = bnk.bnk_dir / f"{wem_id}.wem"

        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(wem, target_path)

        # Update memory sizes
        wem_nodes = list(bnk.query(f"'**/source_id'={wem_id}"))
        wem_size = target_path.stat().st_size
        for node in wem_nodes:
            if isinstance(node, HIRCNode):
                attr_paths = node.glob("**/media_information")
                media_info: MediaInformation

                for _, media_info in attr_paths:
                    # Music tracks have multiple sources, so check if this is the right one
                    if media_info.source_id == wem_id:
                        media_info.in_memory_media_size = wem_size


def get_wem_metadata(wem: Path) -> dict:
    filesize = wem.stat().st_size
    
    with wem.open("rb") as f:
        if f.read(4) != b"RIFF":
            raise ValueError("Unexpected RIFF header")

        riff_size = int.from_bytes(f.read(4), "little") + 8
        if f.read(4) != b"WAVE":
            raise ValueError("Unexpected WAVE header")

        # locate fmt and data chunks (data needed to size pcm streams)
        fmt_offset = fmt_len = -1
        data_offset = data_len = -1
        offset = 12

        while offset < riff_size:
            f.seek(offset)
            chunk_id = f.read(4)
            chunk_size = int.from_bytes(f.read(4), "little")

            if chunk_id == b"fmt ":
                fmt_offset, fmt_len = offset + 8, chunk_size
            elif chunk_id == b"data":
                data_offset, data_len = offset + 8, chunk_size

            offset += 8 + chunk_size

        if fmt_offset < 0:
            raise ValueError("Could not locate fmt section")

        f.seek(fmt_offset)
        codec_tag = int.from_bytes(f.read(2), "little")
        channels = int.from_bytes(f.read(2), "little")
        sample_rate = int.from_bytes(f.read(4), "little")
        avg_bps = int.from_bytes(f.read(4), "little")
        block_align = int.from_bytes(f.read(2), "little")
        bits_per_sample = int.from_bytes(f.read(2), "little")

        if codec_tag == WWISE_VORBIS_TAG:
            # wwise's packed-vorbis layout, sample count lives in the following vorb chunk;
            # block_align and bit_per_sample are not used in this case
            if block_align != 0 or bits_per_sample != 0:
                raise ValueError("Expected zeroed block align / bits per sample")

            fmt_extra_len = int.from_bytes(f.read(2), "little")

            if fmt_len - 0x12 != fmt_extra_len:
                raise ValueError(f"Bad fmt extra length {fmt_extra_len}")

            if fmt_extra_len >= 2:
                f.read(2)  # unk
                if fmt_extra_len >= 6:
                    f.read(4)  # subtype

            if fmt_len == 0x28:
                signature = f.read(16)
                if signature != PCM_SUBFORMAT_GUID:
                    raise ValueError(f"Expected signature not found, got {signature!r}")

            samples = int.from_bytes(f.read(4), "little")
            codec = "vorbis"

        elif codec_tag == WAVE_FORMAT_EXTENSIBLE:
            # standard extensible pcm layout, duration comes from the data chunk size
            if data_offset < 0:
                raise ValueError("Could not locate data section")

            if block_align == 0 or bits_per_sample == 0:
                raise ValueError("Unexpected zeroed block align / bits per sample")

            samples = data_len // block_align
            codec = "pcm"

        else:
            raise ValueError(f"Unexpected format tag {codec_tag:#06x}")

    return {
        "channels": channels,
        "sample_rate": sample_rate,
        "avg_bps": avg_bps,
        "samples": samples,
        "duration": samples / sample_rate,
        "filesize": filesize,
        "codec": codec,
    }


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
    audio = audio[: int(length)]
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

    logger.info(f"Converting {len(waves)} wave files to wem")

    source_lines = []
    for wav in waves:
        if not wav.is_file():
            logger.error(f"FileNotFound: {wav}")
            continue

        source_lines.append(
            f'<Source Path="{wav.absolute()}" Conversion="{conversion}"/>'
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
            subprocess.check_call(
                [str(wwise_exe), "create-new-project", str(wproj_path), "--quiet"]
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Creating wwise project failed: {e.output}")
            raise e

    # Convert the wav files by passing the wsources list to wwise
    try:
        subprocess.check_call(
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
            # TODO sometimes fails when run from python, but fine from terminal?
            subprocess.check_call(
                [
                    str(vgmstream_exe),
                    "-i",  # ignore looping
                    "-o",
                    str(target),
                    str(wem),
                ],
                stdout=subprocess.DEVNULL,
            )
            out_files.append(target)
        except subprocess.CalledProcessError as e:
            logger.error(f"Conversion failed ({e.returncode}):\n{e.output}")
            out_files.append(None)

    return out_files
