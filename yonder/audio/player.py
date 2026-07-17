from __future__ import annotations
import networkx as nx

# If there is no official wheel yet:
# pip install -i https://test.pypi.org/simple/ pyo
import pyo

from yonder import Soundbank, HIRCNode, Hash
from yonder.types import Sound, MusicTrack, MusicSegment, State
from yonder.types.base_types import RTPC
from yonder.types.mixins import PropertyMixin, StateMixin
from yonder.enums import (
    PropID,
    MarkerId,
    ClipAutomationType,
)
from yonder.util import logger
from yonder.game import GameObjects
from .voice import Voice, StateCtrl


class Player:
    def __init__(self):
        self._default_fade_time = 0.05
        self._voices: list[Voice] = []
        self._node_map: dict[int, list[Voice]] = {}

        self._server = pyo.Server().boot()
        # mixes the voice branches; time smooths per-voice amp changes
        self._mixer = pyo.Mixer(outs=1, chnls=1, time=self._default_fade_time)
        # final volume adjustment
        self._gate = pyo.SigTo(value=1.0, time=self._default_fade_time)
        # master chain: mixer -> gate -> dac
        self._master = self._mixer[0] * self._gate
        self._master.out()

    def __del__(self):
        self._server.stop()
        self._server.shutdown()
        self._server = None

    def start(self) -> None:
        self._server.start()

    def stop(self) -> None:
        self._server.stop()

    def play(self) -> None:
        for voice in self._voices:
            voice.start()

    def set_volume(self, vol: float) -> None:
        self._gate.setValue(vol, time=self._default_fade_time)

    def set_muted(self, muted: bool) -> None:
        self._gate.setValue(0.0 if muted else 1.0, time=self._default_fade_time)

    def fade(self, target_vol: float, duration: float) -> None:
        self._gate.setValue(target_vol, time=duration)

    def set_node_params(
        self,
        nid: HIRCNode | Hash,
        rtpc_params: dict[Hash, float] = None,
        active_states: dict[Hash, list[Hash]] = None,
        distance: float = 0.0,
        angle: float = 0.0,
    ) -> None:
        for voice in self._node_map.get(nid, []):
            voice.update(
                rtpc_params=rtpc_params,
                active_states=active_states,
                distance=distance,
                angle=angle,
            )

    def from_hierarchy(
        self, bnk: Soundbank, root: int | HIRCNode, full_tree: bool = False
    ) -> Player:
        self.stop()
        self._node_map.clear()
        self._voices.clear()

        if isinstance(root, HIRCNode):
            root = root.id

        if full_tree:
            root, tree = next(bnk.find_event_subgraphs_for(root))
        else:
            tree = bnk.get_subtree(root, True)

        leafs = [n for (n, d) in tree.out_degree if d == 0]
        voices: dict[int, Voice] = {}

        for branch in nx.all_simple_paths(tree, root, leafs):
            leaf_id = branch[-1]

            if leaf_id in voices:
                logger.warning(
                    f"Player will ignore secondary paths to {leaf_id} ({branch})"
                )
                continue

            voice = Voice()
            voices[leaf_id] = voice
            leaf_node = bnk.get(leaf_id)
            self._node_map.setdefault(leaf_id, []).append(voice)

            if isinstance(leaf_node, Sound):
                voice.audiofile = bnk.get_wem_path(
                    leaf_node.source_id, leaf_node.bank_source_data.source_type
                )
            elif isinstance(leaf_node, MusicTrack):
                # TODO what to do with tracks that have multiple sources?
                voice.audiofile = bnk.get_wem_path(
                    leaf_node.source_ids[0], leaf_node.sources[0].source_type
                )
                voice.ctx.loop = True

                # TODO trims
                for clip in leaf_node.clip_items:
                    if clip.auto_type in (
                        ClipAutomationType.Volume,
                        ClipAutomationType.FadeIn,
                        ClipAutomationType.FadeOut,
                    ):
                        voice.ctx.properties[PropID.Volume].clips.append(clip)
                    elif clip.auto_type == ClipAutomationType.HPF:
                        voice.ctx.properties[PropID.HPF].clips.append(clip)
                    elif clip.auto_type == ClipAutomationType.LPF:
                        voice.ctx.properties[PropID.LPF].clips.append(clip)
                    else:
                        # Clips don't support pitch
                        raise ValueError(
                            f"Unsupported ClipAutomationType {clip.auto_type}"
                        )

            voice = voices[leaf_id]

            for nid in reversed(branch[:-1]):
                node = bnk[nid]
                self._node_map.setdefault(nid, []).append(voice)

                # Collect properties
                if isinstance(node, PropertyMixin):
                    for bundle in node.properties:
                        if bundle.prop_enum in voice.ctx.properties:
                            voice.ctx.properties[bundle.prop_enum] += bundle.value
                        elif bundle.prop_enum == PropID.Loop:
                            voice.ctx.loop = True
                        else:
                            # Other properties are ignored for now
                            pass

                # Collect states
                if isinstance(node, StateMixin):
                    # Find out which param idx controls the property
                    for prop in (PropID.Volume, PropID.LPF, PropID.HPF, PropID.Pitch):
                        prop_idx = None
                        accum = None
                        for idx, prop_info in enumerate(
                            node.states.state_property_info
                        ):
                            if prop_info.property == prop:
                                prop_idx = idx
                                accum = prop_info.accum_type
                                break
                        else:
                            continue

                        # Property found, look for states that affect it
                        for chunk in node.states.state_group_chunks:
                            for state_value in chunk.states:
                                state: State = bnk.get(state_value.state_instance_id)
                                if state:
                                    if state.has_param_for(prop_idx):
                                        adjust = state.get_param(prop_idx)
                                    elif state.has_default():
                                        adjust = state.get_default()
                                    else:
                                        continue

                                    voice.ctx.properties[prop].states.append(
                                        StateCtrl(
                                            chunk.state_group_id,
                                            state_value,
                                            adjust,
                                            accum,
                                        )
                                    )

                # Collect rtpcs
                if hasattr(node, "rtpcs"):
                    rtpc: RTPC
                    for rtpc in node.rtpcs:
                        param = GameObjects.RTPCParameter(rtpc.param_id).name

                        # TODO make a better way to compare these
                        if param == "Pitch":
                            voice.ctx.properties[PropID.Pitch].rtpcs.append(rtpc)
                        elif param == "HPF":
                            voice.ctx.properties[PropID.HPF].rtpcs.append(rtpc)
                        elif param == "LPF":
                            voice.ctx.properties[PropID.LPF].rtpcs.append(rtpc)
                        elif param == "Volume":
                            voice.ctx.properties[PropID.Volume].rtpcs.append(rtpc)
                        else:
                            # Unknown param
                            pass

                # TODO Collect attenuations

                if isinstance(node, MusicSegment):
                    voice.ctx.loop_start = (
                        node.get_marker_pos(MarkerId.LoopStart) / 1000.0
                    )
                    voice.ctx.loop_end = node.get_marker_pos(MarkerId.LoopEnd) / 1000.0

        # build one pyo chain per leaf and register it as a mixer voice
        for idx, voice in enumerate(voices.values()):
            if voice.audiofile is None:
                continue

            tail = voice._build()
            voice.stop()
            self._mixer.addInput(idx, tail)
            self._mixer.setAmp(idx, 0, 1.0)

        self._voices = list(voices.values())
        return self

    def __getitem__(self, idx: int) -> Voice:
        return self._voices[idx]

    def __len__(self) -> int:
        return len(self._voices)
