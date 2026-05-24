from pathlib import Path
import shutil

from yonder import Soundbank
from yonder.types import Event, Action, ActionType, Sound, MusicTrack
from yonder.types.base_types import BankSourceData
from yonder.util import logger


def collect_sources(bnk: Soundbank, event_names: list[str]) -> dict[str, list[BankSourceData]]:
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
    event_names: list[str],
    destination: Path,
    *,
    prefix: str = None,
) -> None:
    if prefix is None:
        prefix = ""

    sources = collect_sources(bnk, event_names)
    destination.mkdir(parents=True, exist_ok=True)

    for evt_name, evt_sources in sources.items():
        for src in evt_sources:
            wem = bnk.get_wem_path(src.source_id, src.source_type)
            if wem:
                wwise_id = evt_name.split("_", maxsplit=1)[-1]
                new_name = f"{prefix}{wwise_id}_{wem.stem}.wem"
                shutil.copy(wem, destination / new_name)
            else:
                logger.warning(
                    f"Wem {src.source_id} ({src.source_type}) for event {evt_name} is missing"
                )
