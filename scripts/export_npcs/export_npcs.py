"""Batch-export the voice lines of NPCs from the soundbanks.

Usage: python export_npc.py [--all] [CHR_ID[=name] ...]

CHR_ID is the number following the `t` in the ESD file names (t301006000.py -> 301).
Every ESD script starting with it is scanned, so NPCs with multiple talk scripts
are handled automatically. A longer ID like 000003000 selects a single script, which
is useful for NPCs that share the generic `000` prefix.

The output folder is named after the NPC in npcs_er.yaml (e.g. "White Mask Varré" ->
white_mask_varre). Use the optional =name to override it, or if the ID is not in the
yaml (c<CHR_ID> by default). --all exports every NPC in the yaml.

Expects the exported ESDs and TalkParam in <mod>/data, i.e.
    data/esd/t*.py
    data/talkparam.csv
and creates one folder per NPC and soundbank in data/audio, e.g.
    data/audio/white_mask_varre_vc301/{subtitles.csv, talkparam.csv, wems/, white_mask_varre_wems.zip}
"""

from pathlib import Path
import argparse
import csv
import re
import unicodedata
import zipfile
import yaml
import shutil
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from yonder import Soundbank
from yonder.export import collect_sources, export_wems
from yonder.util import logger, unpack_soundbank


# === settings ===

vgmstream = Path("E:/Games/Elden Ring/Modding/Tools/vgmstream-win64/vgmstream-cli.exe")
bnk2json = Path(__file__).parent.parent / "external" / "rewwise" / "bnk2json.exe"
game_dir = Path("E:/SteamLibrary/steamapps/common/ELDEN RING/Game/sd")

mod = "star0everyone"

# === helpers ===

npcs_file = Path(__file__).parent / "npcs_er.yaml"
data_dir = Path(__file__).parent / mod / "data"
esd_dir = data_dir / "esd"
audio_dir = data_dir / "export"

# ESDStudio writes every TalkToPlayer line as a comment: # talk:<TalkParam ID>:"<text>"
talk_pattern = re.compile(r'^\s*#\s*talk:(\d+):"(.*)"\s*$')

_banks: dict[str, Soundbank] = {}


def load_npcs() -> dict[str, str]:
    """Maps chr IDs to folder names, e.g. 301 -> white_mask_varre"""
    with npcs_file.open(encoding="utf-8") as f:
        full_names: dict[str, str] = yaml.safe_load(f)

    names: dict[str, str] = {}
    for chr_id, full_name in full_names.items():
        # "Rennala, Queen of the Full Moon" -> rennala
        short = unicodedata.normalize("NFKD", full_name.split(",")[0])
        short = short.encode("ascii", "ignore").decode()
        names[chr_id] = re.sub(r"[^a-z0-9]+", "_", short.lower()).strip("_")

    # NPCs that share a name (e.g. ghosts) must not share a folder
    duplicates = {name for name in names.values() if list(names.values()).count(name) > 1}
    return {
        chr_id: f"{name}_{chr_id}" if name in duplicates else name
        for chr_id, name in names.items()
    }


def zip_wems(path: Path, wems: list[Path]):
    folder = path.stem
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for wem in wems:
            zf.write(wem, f"{folder}/{wem.name}")


def load_talkparam() -> dict[int, int]:
    """Maps TalkParam row IDs to voice IDs"""
    voice_ids: dict[int, int] = {}
    with (data_dir / "talkparam.csv").open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        # Smithbox adds a trailing comma to the header only
        width = len(header) - (header[-1] == "")
        col = {name: i for i, name in enumerate(header)}

        # Some texts contain line breaks, which split a row into multiple lines
        pending: list[str] = []
        for row in reader:
            if pending:
                row = pending[:-1] + [pending[-1] + " " + row[0]] + row[1:]
            if len(row) < width:
                pending = row
                continue
            pending = []

            voice_id = int(row[col["voiceId_female"]])
            if voice_id <= 0:
                voice_id = int(row[col["voiceId"]])
            voice_ids[int(row[col["ID"]])] = voice_id
    return voice_ids


def find_talks(chr_id: str) -> dict[int, str]:
    """Maps TalkParam row IDs to subtitles for all ESD scripts of an NPC"""
    scripts = sorted(esd_dir.glob(f"t{chr_id}*.py"))
    if not scripts:
        logger.warning(f"No ESD scripts found for {chr_id}")

    talks: dict[int, str] = {}
    for script in scripts:
        for line in script.read_text(encoding="utf-8").splitlines():
            if match := talk_pattern.match(line):
                talks.setdefault(int(match[1]), match[2])

    return talks


def get_bank_id(voice_id: int) -> str:
    """Voice IDs are prefixed with the ID of their soundbank. Everything else is in vcmain"""
    # DLC voice IDs have 10 digits and the soundbank is offset by 3
    if voice_id >= 1_000_000_000:
        voice_id = voice_id // 10 + 300_000_000

    if voice_id >= 100_000_000:
        bank_id = f"vc{voice_id // 1_000_000}"
        if (game_dir / "enus" / f"{bank_id}.bnk").is_file():
            return bank_id

    return "vcmain"


def get_event_name(voice_id: int) -> str:
    if voice_id >= 1_000_000_000:
        # DLC lines use w (to avoid collisions?)
        return f"Play_w{str(voice_id)[1:]}"
    return f"Play_v{voice_id}"


def get_bank(bank_id: str) -> Soundbank:
    if bank_id not in _banks:
        bnk_path = game_dir / "enus" / bank_id
        if not bnk_path.is_dir():
            bnk_path = unpack_soundbank(bnk2json, bnk_path.parent / f"{bank_id}.bnk")
        _banks[bank_id] = Soundbank.load(bnk_path)
    return _banks[bank_id]


def write_subtitles(path: Path, refs: list[int], talks: dict[int, str]):
    lines = []
    for ref in refs:
        text = talks[ref].replace('"', '""')
        lines.append(f'{ref}, "{text}"')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_talkparam(path: Path, refs: list[int], voice_ids: dict[int, int]):
    lines = ["ID,voiceId_female"]
    lines.extend(f"{ref},{voice_ids[ref]}" for ref in refs)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# === export ===


def export_npc(chr_id: str, name: str, voice_ids: dict[int, int], zip: bool = False):
    talks = find_talks(chr_id)
    logger.info(f"Found {len(talks)} talk lines")

    # ESD references a TalkParam by its row ID...
    unknown = [ref for ref in talks if ref not in voice_ids]
    if unknown:
        logger.warning(f"{name}: {len(unknown)} lines have no TalkParam row: {unknown}")

    # ... and the TalkParam contains the voice ID. We assume that everything
    # setup in ESD is also used in-game
    by_bank: dict[str, list[int]] = {}
    for ref in talks:
        voice_id = voice_ids.get(ref, -1)
        if voice_id > 0:
            by_bank.setdefault(get_bank_id(voice_id), []).append(ref)

    if not by_bank:
        logger.warning(f"{name}: No voice lines found")
        return

    for bank_id, refs in by_bank.items():
        prefix = f"{name}_{bank_id}"
        base_dir = audio_dir / prefix
        base_dir.mkdir(parents=True, exist_ok=True)

        write_subtitles(base_dir / "subtitles.csv", refs, talks)
        write_talkparam(base_dir / "talkparam.csv", refs, voice_ids)

        bnk = get_bank(bank_id)
        events = list(dict.fromkeys(get_event_name(voice_ids[ref]) for ref in refs))
        found = collect_sources(bnk, events)
        missing = [evt for evt in events if evt not in found]

        output = base_dir / "wems"
        copied, _ = export_wems(bnk, events, output, prefix=f"{prefix}_")
        logger.info(f"{prefix}: {len(copied)} wems exported to {output}")

        if copied and zip:
            archive = base_dir / f"{name}_wems.zip"
            zip_wems(archive, copied)
            shutil.rmtree(output)
            logger.info(f"{prefix}: Zipped wems to {archive}")

        missing_file = base_dir / f"{prefix}_missing.txt"
        if missing:
            logger.warning(f"{prefix}: {len(missing)} events not found in {bank_id}")
            missing_file.write_text("\n".join(missing))
        else:
            missing_file.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Batch-export NPC voice lines")
    parser.add_argument(
        "npcs",
        nargs="*",
        metavar="CHR_ID[=name]",
        help="NPCs to export",
    )
    parser.add_argument("--all", action="store_true", help="export all NPCs in npcs_er.yaml")
    parser.add_argument("--zip", action="store_true", help="zip NPC wem folders")
    args = parser.parse_args()

    logger.info("Loading NPCs...")
    npcs = load_npcs()
    selection: dict[str, str] = dict(npcs) if args.all else {}

    for arg in args.npcs:
        chr_id, _, name = arg.partition("=")
        # A single script (t301006000) falls back to the name of its NPC (301)
        selection[chr_id] = name or npcs.get(chr_id) or npcs.get(chr_id[:3]) or f"c{chr_id}"

    if not selection:
        parser.error("specify at least one CHR_ID or --all")

    logger.info("Reading TalkParam...")
    voice_ids = load_talkparam()

    with logging_redirect_tqdm():
        for chr_id, name in tqdm(selection.items()):
            logger.info(f"=== {name} ({chr_id}) ===")
            export_npc(chr_id, name, voice_ids, zip=args.zip)

    logger.info("Done!")


if __name__ == "__main__":
    main()
