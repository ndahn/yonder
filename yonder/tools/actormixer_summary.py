from dataclasses import dataclass, field, asdict
from pathlib import Path
import json
import shutil
import networkx as nx
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from yonder import Soundbank
from yonder.types import ActorMixer, State
from yonder.enums import PropID, RtpcType
from yonder.util import unpack_soundbank


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

        for amx in self.actormixers:
            g.add_node(amx.nid, data=amx)
            if amx.parent > 0:
                g.add_edge(amx.parent, amx.nid)

        return g

    def get_effective_values(self, target_amx_id: int) -> AmxData:
        target_amx = self.actormixers[target_amx_id]
        tree = self.tree
        root = next(
            n for n in nx.ancestors(tree, target_amx_id) if tree.in_degree(n) == 0
        )
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
                    PropID.Volume,
                    PropID.LPF,
                    PropID.HPF,
                    PropID.Pitch,
                    PropID.LFE,
                    PropID.MakeUpGain,
                    PropID.GameAuxSendHPF,
                    PropID.GameAuxSendLPF,
                    PropID.GameAuxSendVolume,
                    PropID.UserAuxSendHPF0,
                    PropID.UserAuxSendHPF1,
                    PropID.UserAuxSendHPF2,
                    PropID.UserAuxSendHPF3,
                    PropID.UserAuxSendLPF0,
                    PropID.UserAuxSendLPF1,
                    PropID.UserAuxSendLPF2,
                    PropID.UserAuxSendLPF3,
                    PropID.UserAuxSendVolume0,
                    PropID.UserAuxSendVolume1,
                    PropID.UserAuxSendVolume2,
                    PropID.UserAuxSendVolume3,
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

        return result


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


def load_actormixer_summary(summary_json: Path) -> AmxSummary:
    raw: list[dict] = json.load(summary_json.open())
    data: list[AmxData] = [AmxData(**d) for d in raw]

    # Fix up property keys
    for d in data:
        d.properties = {PropID[k]: v for k, v in d.properties.items()}

    return AmxSummary({s.nid: s} for s in data)


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
