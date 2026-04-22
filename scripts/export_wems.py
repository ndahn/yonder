from pathlib import Path
import shutil
import networkx as nx

from yonder import Soundbank
from yonder.util import logger


def collect_wems(bnk: Soundbank, event_names: list[str]):
    """Find all WEM IDs associated with the specified events"""
    wems: dict[str, list[str]] = {}

    for evt_name in event_names:
        try:
            evt = bnk[evt_name]
            actions = [bnk[aid] for aid in evt["actions"]]
        except Exception:
            continue

        for act in actions:
            tree = bnk.get_subtree(act, True, False)
            sounds = nx.get_node_attributes(tree, "wem")
            wems.setdefault(evt_name, []).extend(sounds.values())

    return wems


def export_wems(
    wems: dict[str, list[str]],
    sd_dir: str,
    destination: str,
) -> None:
    """Locate collected WEM sounds and copy them to a direcory, optionally renaming them according to their events."""
    file_map: dict[str, Path] = {}
    wem2evt = {}

    for key, wem_files in wems.items():
        if len(wem_files) > 1:
            logger.warning(f"event {key} has multiple wem files: {wem_files}")

        for wf in wem_files:
            if wf in wem2evt:
                logger.warning(
                    f"wem {wf} is already associated with event {wem2evt[wf]}"
                )
                continue

            wem2evt[wf] = key

    candidates = Path(sd_dir).rglob("**/*.wem")
    for path in candidates:
        wem_id = int(path.stem)
        if wem_id in wem2evt:
            # TODO handle prefetch files
            file_map[wem_id] = path

    if len(file_map) < len(wem2evt):
        logger.warning(
            f"{len(wem2evt) - len(file_map)}/{len(wem2evt)} wems are missing:\n{[set(wem2evt.keys()).difference(file_map.keys())]}"
        )

    # Collect the WEMS in one place and rename them according to their events
    destination: Path = Path(destination)
    if not destination.exists():
        destination.mkdir(parents=True)

    logger.info(f"Gathering {len(file_map)} WEMs into {destination}")
    for wem_id, path in file_map.items():
        event: str = wem2evt[wem_id]
        wwise_id = event.split("_", maxsplit=1)[-1]
        shutil.copy(path, str(destination / f"{wwise_id}_{path.stem}.wem"))


if __name__ == "__main__":
    sd_dir = Path("E:/SteamLibrary/steamapps/common/ELDEN RING/Game/sd")
    destination = Path("E:/Games/ER_Modding/Commissions/voicemod/audio/varre/wems")
    bnk_dir = Path("../test/vc301/").absolute()
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

    bnk = Soundbank.load(bnk_dir)
    wems = collect_wems(bnk, events)
    logger.info(
        f"Collected {sum(len(x) for x in wems.values())} wems for {len(events)} events"
    )

    export_wems(wems, sd_dir, destination)
