"""Batch-import edited NPC voice lines into soundbanks. Counterpart of export_npcs.py.

Usage: python import_npc.py [--fresh] [ZIP_OR_DIR_OR_NAME ...]

Expects wav files named like the wems written by export_npcs.py, e.g.
    white_mask_varre_vc301_v301011000_283303893.wav
i.e. <anything>_<soundbank>_<event>_<wem ID>. Only the last three parts are used, so
the NPC part of the name may be shortened. The wavs are looked up in
    data/import/*.zip
(folders inside the zips don't matter). Pass a zip, a folder of wavs, or the start of
a zip name (e.g. white_mask_varre) to import only some of them.

For every soundbank the wavs belong to, this will
    - convert the wavs to wems (Wwise)
    - place the wems in mod/sd/enus/wem/, using the same wem IDs as the original sounds
    - update the sounds in the soundbank and write it to mod/sd/enus/<bank>.bnk

Unpacked soundbanks are cached in data/banks, so multiple NPCs sharing a soundbank
(e.g. vcmain) accumulate. Use --fresh to start again from the game's soundbanks.
"""

from pathlib import Path
from typing import NamedTuple
import argparse
import re
import shutil
import zipfile

from yonder import Soundbank
from yonder.types import Sound
from yonder.enums import SourceType
from yonder.util import logger, unpack_soundbank, repack_soundbank, get_temp_dir, externals_dir
from yonder.wem import wav2wem

# === settings ===

bnk2json = externals_dir() / "rewwise" / "bnk2json.exe"
wwise_exe = Path(
    "E:/Games/Elden Ring/Modding/Tools/Wwise2025.1.2.8976/Authoring/x64/Release/bin/WwiseConsole.exe"
)
game_dir = Path("E:/SteamLibrary/steamapps/common/ELDEN RING/Game/sd")

mod = "star0everyone"

# === helpers ===

mod_root_dir = Path(__file__).parent.parent.parent / "projects" / mod
data_dir = mod_root_dir / "data"
import_dir = data_dir / "import"
banks_dir = data_dir / "banks"

mod_sd_dir = mod_root_dir / "mod" / "sd" / "enus"

# <anything>_<soundbank>_<event>_<wem ID>, see export_wems()
audio_pattern = re.compile(r"(?P<name>.+)_(?P<bank>vc[a-z0-9]+)_(?P<event>[vw]\d+)_(?P<wem>\d+)")


class VoiceLine(NamedTuple):
    wav: Path
    bank_id: str
    event: str
    wem_id: int


def find_sources(selection: list[str]) -> list[Path]:
    """Resolves the command line arguments to zip files or folders"""
    if not selection:
        return sorted(import_dir.glob("*.zip"))

    sources: list[Path] = []
    for arg in selection:
        path = Path(arg)
        if path.exists():
            sources.append(path)
            continue

        matches = sorted(import_dir.glob(f"{arg}*.zip"))
        if not matches:
            logger.warning(f"Nothing to import for '{arg}'")
        sources.extend(matches)

    return sources


def collect_wavs(source: Path, destination: Path) -> list[Path]:
    """Copies all wavs of a zip or folder into a single flat folder (needed for wav2wem)"""
    destination.mkdir(parents=True, exist_ok=True)
    wavs: list[Path] = []

    if source.is_dir():
        for wav in sorted(source.rglob("*.wav")):
            wavs.append(Path(shutil.copy(wav, destination / wav.name)))
        return wavs

    with zipfile.ZipFile(source) as zf:
        for info in zf.infolist():
            name = Path(info.filename)
            if info.is_dir() or name.suffix.lower() != ".wav":
                continue

            target = destination / name.name
            with zf.open(info) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            wavs.append(target)

    return wavs


def parse_voice_lines(wavs: list[Path]) -> dict[str, list[VoiceLine]]:
    """Groups wavs by the soundbank they belong to"""
    by_bank: dict[str, list[VoiceLine]] = {}

    for wav in wavs:
        match = audio_pattern.fullmatch(wav.stem)
        if not match:
            logger.warning(f"Skipping {wav.name}, expected <name>_<bank>_<event>_<wem ID>.wav")
            continue

        line = VoiceLine(wav, match["bank"], match["event"], int(match["wem"]))
        by_bank.setdefault(line.bank_id, []).append(line)

    return by_bank


def get_bank(bank_id: str) -> Soundbank:
    """Loads the working copy of a soundbank, unpacking it from the game first if necessary"""
    bank_dir = banks_dir / bank_id
    if not (bank_dir / "soundbank.json").is_file():
        game_bnk = game_dir / "enus" / f"{bank_id}.bnk"
        if not game_bnk.is_file():
            raise FileNotFoundError(f"Soundbank {game_bnk} does not exist")

        banks_dir.mkdir(parents=True, exist_ok=True)
        # Repacking expects the original .bnk next to the unpacked folder
        shutil.copy(game_bnk, banks_dir / game_bnk.name)
        unpack_soundbank(bnk2json, banks_dir / game_bnk.name)

    return Soundbank.load(bank_dir)


def replace_sounds(bnk: Soundbank, line: VoiceLine, wem: Path) -> int:
    """Points all sounds of a voice line that play the original wem to the new wem.

    Returns the number of updated sounds.
    """
    event = f"Play_{line.event}"
    if event not in bnk:
        logger.warning(f"{bnk.name}: Event {event} not found")
        return 0

    sounds: list[Sound] = [
        s
        for s in bnk.query(node_type=Sound, start_from=bnk[event].id)
        if s.source_id == line.wem_id
    ]
    if not sounds:
        logger.warning(f"{bnk.name}: Event {event} has no sound using wem {line.wem_id}")
        return 0

    # Voice lines are streamed from sd/<language>/wem/<first two digits>/. The wem keeps
    # its ID so that it replaces the original, but all of its data lives in that file.
    target = mod_sd_dir / "wem" / str(line.wem_id)[:2] / f"{line.wem_id}.wem"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(wem, target)
    size = target.stat().st_size

    for sound in sounds:
        source = sound.bank_source_data
        source.source_type = SourceType.Streaming
        source.media_information.in_memory_media_size = size

    # A prefetch snippet (or embedded wem) of the old sound would not match the new audio
    (bnk.bnk_dir / f"{line.wem_id}.wem").unlink(missing_ok=True)
    return len(sounds)


def write_bank(bnk: Soundbank) -> Path:
    """Saves and repacks a soundbank into the mod folder"""
    bnk.save(backup=False)
    packed = repack_soundbank(bnk2json, bnk.bnk_dir)
    Path(str(packed) + ".bak").unlink(missing_ok=True)

    mod_sd_dir.mkdir(parents=True, exist_ok=True)
    return Path(shutil.copy(packed, mod_sd_dir / packed.name))


# === import ===


def import_source(source: Path) -> None:
    work_dir = get_temp_dir() / "import_npc" / source.stem
    shutil.rmtree(work_dir, ignore_errors=True)

    try:
        wavs = collect_wavs(source, work_dir / "wav")
        lines = parse_voice_lines(wavs)
        if not lines:
            logger.warning(f"{source.name}: No voice lines found")
            return

        logger.info(f"{source.name}: Converting {len(wavs)} wavs")
        wem_dir = work_dir / "wem"
        wem_dir.mkdir()
        wav2wem(wwise_exe, [line.wav for bank_lines in lines.values() for line in bank_lines], wem_dir)

        for bank_id, bank_lines in lines.items():
            bnk = get_bank(bank_id)

            replaced = 0
            for line in bank_lines:
                wem = wem_dir / f"{line.wav.stem}.wem"
                if not wem.is_file():
                    logger.warning(f"{bank_id}: Conversion of {line.wav.name} failed")
                    continue

                replaced += replace_sounds(bnk, line, wem) > 0

            if replaced:
                bnk_file = write_bank(bnk)
                logger.info(f"{source.name}: {replaced}/{len(bank_lines)} voice lines imported into {bnk_file}")
            else:
                logger.warning(f"{source.name}: No voice lines imported into {bank_id}")
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description="Batch-import edited NPC voice lines")
    parser.add_argument(
        "sources",
        nargs="*",
        metavar="ZIP_OR_DIR_OR_NAME",
        help="what to import, default is every zip in data/import",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="discard cached soundbanks and start from the game's",
    )
    args = parser.parse_args()

    sources = find_sources(args.sources)
    if not sources:
        parser.error(f"nothing to import, put zips with wav files in {import_dir}")

    if args.fresh:
        shutil.rmtree(banks_dir, ignore_errors=True)

    for source in sources:
        logger.info(f"=== {source.name} ===")
        import_source(source)

    logger.info("Done!")


if __name__ == "__main__":
    main()
