from dataclasses import dataclass, field, asdict
from pathlib import Path
import json
import shutil
import networkx as nx
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from yonder import Soundbank
from yonder.types import ActorMixer, State
from yonder.enums import PropID, RtpcType, Game
from yonder.util import unpack_soundbank, resource_dir, logger


@dataclass
class AmxData:
    nid: int
    bank: str
    parent: int = 0

    # Only list stuff that's set on this specific AMX
    bus: int = 0
    aux1: int = 0
    aux2: int = 0
    aux3: int = 0
    aux4: int = 0

    properties: dict[PropID, float] = field(default_factory=dict)
    rtpcs: dict[int, tuple[RtpcType, int]] = field(default_factory=dict)
    states: dict[int, dict[int, dict[PropID, float]]] = field(default_factory=dict)


@dataclass(frozen=True)
class AmxSummary:
    actormixers: dict[int, AmxData] = field(default_factory=dict)

    @property
    def tree(self) -> nx.DiGraph:
        g = nx.DiGraph()

        for nid, amx in self.actormixers.items():
            g.add_node(nid, data=amx)
            if amx.parent > 0:
                g.add_edge(amx.parent, nid)

        return g

    def get_effective_values(self, target_amx_id: int) -> tuple[int, AmxData]:
        target_amx = self.actormixers.get(target_amx_id)
        if not target_amx:
            logger.warning(
                f"Could not find ActorMixer {target_amx_id} in game data, wrong game selected?"
            )
            return 0, AmxData(target_amx_id, 0)

        tree = self.tree
        root = target_amx_id
        while parents := list(tree.predecessors(root)):
            root = parents[0]

        result = AmxData(target_amx_id, target_amx.bank)

        for amxid in nx.shortest_path(tree, root, target_amx_id):
            amx = self.actormixers[amxid]

            if amx.bus > 0:
                result.bus = amx.bus

            if amx.aux1 > 0:
                result.aux1 = amx.aux1

            if amx.aux2 > 0:
                result.aux2 = amx.aux2

            if amx.aux3 > 0:
                result.aux3 = amx.aux3

            if amx.aux4 > 0:
                result.aux4 = amx.aux4

            for prop, val in amx.properties.items():
                if prop in (
                    # Derived from the comments in wwiser's AkRTPC_ParameterID_135
                    # https://github.com/bnnm/wwiser/blob/master/wwiser/parser/wdefs.py
                    PropID.LFE,
                    PropID.Pitch,
                    PropID.LPF,
                    PropID.HPF,
                    PropID.BusVolume,
                    PropID.InitialDelay,
                    PropID.MakeUpGain,
                    PropID.MidiTransposition,
                    PropID.MidiVelocityOffset,
                    PropID.PlaybackSpeed,
                    PropID.MuteRatio,
                ):
                    result.properties.setdefault(prop, 0.0)
                    result.properties[prop] += val
                else:
                    result.properties[prop] = val

            result.rtpcs.update(amx.rtpcs)

            for group_id, states in amx.states.items():
                result.states.setdefault(group_id, {})
                for state, effects in states.items():
                    result.states[group_id][state] = effects

        return (root, result)


def build_actormixer_summary(bnk: Soundbank) -> AmxSummary:
    amx_data: dict[int, AmxData] = {}
    all_amx = bnk.query("type=ActorMixer")
    amx: ActorMixer

    for amx in all_amx:
        data = AmxData(
            amx.id,
            bnk.name,
            amx.parent,
            amx.node_base_params.override_bus_id,
            amx.node_base_params.aux_params.aux1,
            amx.node_base_params.aux_params.aux2,
            amx.node_base_params.aux_params.aux3,
            amx.node_base_params.aux_params.aux4,
            {p.prop_enum: p.value for p in amx.properties},
            {r.id: (r.rtpc_type, r.param_id) for r in amx.rtpcs},
        )

        if amx.states.state_group_chunks:
            state_props: list[PropID] = [
                p.property for p in amx.states.state_property_info
            ]

            for chunk in amx.states.state_group_chunks:
                effects: dict[int, dict[PropID, float]] = {}

                for state in chunk.states:
                    obj: State = bnk.get(state.state_instance_id)
                    # Need the state object to see what values are applied
                    if obj:
                        state_props: dict[PropID, float] = {}
                        for idx, prop in enumerate(state_props):
                            val = obj.get_param(idx)
                            if val is not None:
                                state_props[prop] = val

                        if state_props:
                            effects[state.state_id] = state_props

                if effects:
                    data.states[chunk.state_group_id] = effects

        amx_data[amx.id] = data

    return AmxSummary(amx_data)


def build_game_actormixer_summary(game_path: Path, bnk2json_exe: Path) -> AmxSummary:
    summary = {}
    banks = list(game_path.glob("**/*.bnk"))

    with logging_redirect_tqdm():
        with tqdm(banks) as t:
            for bnk_file in t:
                t.set_description(bnk_file.stem)
                bnk_dir = bnk_file.parent / bnk_file.stem

                unpacked = False
                if not bnk_dir.is_dir():
                    bnk_file = unpack_soundbank(bnk2json_exe, bnk_file)
                    unpacked = True

                bnk = Soundbank.load(bnk_file)
                summary |= build_actormixer_summary(bnk).actormixers

                if unpacked:
                    shutil.rmtree(bnk_dir)

    return AmxSummary(summary)


def load_actormixer_summary(game: Game) -> AmxSummary:
    if game == Game.EldenRing:
        json_path = resource_dir() / "gamedata" / "er" / "amx.json"
    elif game == Game.Nightreign:
        json_path = resource_dir() / "gamedata" / "nr" / "amx.json"
    else:
        raise ValueError(f"Game {game} is not supported yet")

    raw: list[dict] = json.load(json_path.open())
    data: list[AmxData] = [AmxData(**d) for d in raw]

    # Fix up property keys
    for d in data:
        d.properties = {PropID[k]: v for k, v in d.properties.items()}

    return AmxSummary({s.nid: s for s in data})


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <bnk2json.exe> <path/to/game/sd> <outfile.json>")
        sys.exit(1)

    bnk2json_exe = Path(sys.argv[1])
    game_path = Path(sys.argv[2])
    outfile = Path(sys.argv[3])

    summary = build_game_actormixer_summary(game_path, bnk2json_exe)

    # I prefer serializing enums by names
    data = list(summary.actormixers.values())
    for amx in data:
        amx.properties = {k.name: v for k, v in amx.properties.items()}

    raw = [asdict(s) for s in data]
    json.dump(raw, outfile.open("w"), indent=2)
