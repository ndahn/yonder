from pathlib import Path
import csv
import shutil
import argparse

from yonder import Soundbank
from yonder.types import Event, Action, ActionType, Sound, MusicTrack
from yonder.types.base_types import BankSourceData
from yonder.util import logger


def collect_sources(bnk: Soundbank, event_names: list[str]) -> list[BankSourceData]:
    """Find all WEM IDs associated with the specified events"""
    sources: dict[str, list[str]] = {}

    for evt_name in event_names:
        evt: Event = bnk.get(evt_name)
        if not evt:
            continue

        for aid in evt.actions:
            act: Action = bnk.get(aid)
            if not act or act.action_type_enum != ActionType.Play:
                continue

            tree = bnk.get_subtree(act, True, False)
            for nid in tree:
                n = bnk.get(nid)
                if not n:
                    continue

                if isinstance(n, Sound):
                    sources.setdefault(evt_name, []).append(n.bank_source_data)
                elif isinstance(n, MusicTrack):
                    sources.setdefault(evt_name, []).extend(n.sources)

    return sources


def export_wems(
    bnk: Soundbank,
    sources: dict[str, list[BankSourceData]],
    destination: Path,
    prefix: str = None,
) -> None:
    if prefix is None:
        prefix = ""

    destination.mkdir(parents=True, exist_ok=True)

    for evt_name, evt_sources in sources.items():
        for src in evt_sources:
            wem = bnk.get_wem_path(src.source_id, src.source_type)
            if wem:
                wwise_id = evt_name.split("_", maxsplit=1)[-1]
                new_name = f"{prefix}{wwise_id}_{wem.stem}.wem"
                shutil.copy(wem, destination / new_name)
            else:
                logger.warning(f"Wem {src.source_id} ({src.source_type}) for event {evt_name} is missing")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("bank")
    p.add_argument("input", type=Path)
    p.add_argument("-p", "--prefix", type=str, default=None)
    p.add_argument("-e", "--evttype", type=str, default="v")
    p.add_argument("-s", "--srcpath", type=Path, default=Path("E:/SteamLibrary/steamapps/common/ELDEN RING/Game/sd/"))
    p.add_argument("-o", "--output", type=Path, default=None)

    args = p.parse_args()

    if not args.output:
        args.output = Path(__file__).parent / "export"


    events: list[str] = []
    with open(args.input) as f:
        dialect = csv.Sniffer().sniff(f.read(1024))
        f.seek(0)
        reader = csv.reader(f, dialect)
        
        # skip header
        next(reader, None)
        for row in reader:
            events.append(f"Play_{args.evttype}{row[0]}")

    bnk = Soundbank.load(args.bank)
    sources = collect_sources(bnk, events)
    logger.info(
        f"Collected {sum(len(x) for x in sources.values())} wems for {len(events)} events"
    )
    export_wems(bnk, sources, args.output, args.prefix)
    logger.info(f"Done! Wems exported to {args.output}")



if __name__ == "__main__":
    main()


events = [
    "Play_v301804000",
    "Play_v301805000",
    "Play_v301802000",
    "Play_v301802010",
    "Play_v301802020",
    "Play_v301803000",
    "Play_v301803010",
    "Play_v301803020",
    "Play_v301806000",
    "Play_v301806010",
    "Play_v301806020",
    "Play_v301807000",
    "Play_v301807010",
    "Play_v301807020",
    "Play_v301013000",
    "Play_v301013010",
    "Play_v301013020",
    "Play_v301014000",
    "Play_v301014010",
    "Play_v301014020",
    "Play_v301012000",
    "Play_v301012010",
    "Play_v301012020",
    "Play_v301012030",
    "Play_v301012040",
    "Play_v301012050",
    "Play_v301012060",
    "Play_v301012070",
    "Play_v301011000",
    "Play_v301011010",
    "Play_v301011020",
    "Play_v301011030",
    "Play_v301011040",
    "Play_v301011050",
    "Play_v301058000",
    "Play_v301058010",
    "Play_v301054000",
    "Play_v301054010",
    "Play_v301054020",
    "Play_v301054030",
    "Play_v301054040",
    "Play_v301054050",
    "Play_v301057000",
    "Play_v301057010",
    "Play_v301057020",
    "Play_v301057030",
    "Play_v301020000",
    "Play_v301020010",
    "Play_v301020020",
    "Play_v301020030",
    "Play_v301020040",
    "Play_v301020050",
    "Play_v301020060",
    "Play_v301020070",
    "Play_v301020080",
    "Play_v301024000",
    "Play_v301021000",
    "Play_v301021010",
    "Play_v301021020",
    "Play_v301021030",
    "Play_v301021040",
    "Play_v301023000",
    "Play_v301023010",
    "Play_v301023020",
    "Play_v301023030",
    "Play_v301023040",
    "Play_v301022000",
    "Play_v301022010",
    "Play_v301022020",
    "Play_v301022030",
    "Play_v301025000",
    "Play_v301025010",
    "Play_v301025020",
    "Play_v301025030",
    "Play_v301025040",
    "Play_v301030000",
    "Play_v301030010",
    "Play_v301030020",
    "Play_v301030100",
    "Play_v301030110",
    "Play_v301030120",
    "Play_v301035000",
    "Play_v301031000",
    "Play_v301031010",
    "Play_v301031020",
    "Play_v301031030",
    "Play_v301031040",
    "Play_v301031050",
    "Play_v301031060",
    "Play_v301034000",
    "Play_v301034010",
    "Play_v301034020",
    "Play_v301032000",
    "Play_v301033000",
    "Play_v301033010",
    "Play_v301033020",
    "Play_v301033030",
    "Play_v301036000",
    "Play_v301036010",
    "Play_v301036020",
    "Play_v301036030",
    "Play_v301037000",
    "Play_v301037010",
    "Play_v301050000",
    "Play_v301050010",
    "Play_v301050020",
    "Play_v301050030",
    "Play_v301050040",
    "Play_v301050050",
    "Play_v301050060",
    "Play_v301050070",
    "Play_v301050080",
    "Play_v301053000",
    "Play_v301053010",
    "Play_v301051000",
    "Play_v301051010",
    "Play_v301051050",
    "Play_v301051060",
    "Play_v301051070",
    "Play_v301052000",
    "Play_v301052010",
    "Play_v301052020",
    "Play_v301055000",
    "Play_v301056000",
    "Play_v301056010",
    "Play_v301056020",
    "Play_v301056030",
    "Play_v301056040",
    "Play_v301056050",
    "Play_v301056060",
    "Play_v301800000",
    "Play_v301801000",
    "Play_v301801010",
    "Play_v301026000",
    "Play_v301026010",
    "Play_v301026020",
    "Play_v301026030",
    "Play_v301026040",
    "Play_v301026100",
    "Play_v301026110",
    "Play_v301026120",
    "Play_v301026130",
    "Play_v301026140",
    "Play_v301027000",
    "Play_v301027010",
    "Play_v301054100",
    "Play_v301054150",
    "Play_v301054160",
    "Play_v301054170",
    "Play_v301054180",
]
