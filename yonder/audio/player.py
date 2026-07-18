from __future__ import annotations
import networkx as nx

# If there is no official wheel yet:
# pip install -i https://test.pypi.org/simple/ pyo
import pyo

from yonder import Soundbank, HIRCNode, Hash
from yonder.types import (
    Sound,
    MusicTrack,
    MusicSegment,
    State,
    Attenuation,
    RandomSequenceContainer,
    SwitchContainer,
    LayerContainer,
    MusicRandomSequenceContainer,
)
from yonder.types.base_types import RTPC
from yonder.types.mixins import PropertyMixin, StateMixin
from yonder.enums import (
    PropID,
    MarkerId,
    ClipAutomationType,
    CurveParameters,
    RandomMode,
    RandomSequenceMode,
)
from yonder.util import logger
from yonder.game import GameObjects

from .voice import Voice, StateCtrl
from .stream_source import StreamSource
from .playback_control import PlaybackControl


class Player:
    def __init__(self):
        self.voices: list[Voice] = []
        self._ctrl: PlaybackControl = None
        self._node_map: dict[int, list[Voice]] = {}

        self._server = pyo.Server().boot()
        # mixes the voice branches; time smooths per-voice amp changes
        self._mixer = pyo.Mixer(outs=1, chnls=1, time=self._default_fade_time)
        # final volume adjustment
        self._gate = pyo.SigTo(value=1.0, time=self._default_fade_time)
        # master chain: mixer -> gate -> dac
        self._master = self._mixer[0] * self._gate
        self._master.out()

        self._server.start()

    def __del__(self):
        self._server.stop()
        self._server.shutdown()
        self._server = None

    def stop(self) -> None:
        if self._ctrl:
            self._ctrl.stop()

    def play(self) -> None:
        self._ctrl.play()

    @property
    def playing(self) -> bool:
        return self._ctrl._playing

    @property
    def pos(self) -> float:
        # TODO
        pass

    def seek(self, pos: float) -> None:
        # TODO
        pass

    def set_volume(self, vol: float, time: float = 0.05) -> None:
        self._gate.setValue(vol, time=time)

    def set_muted(self, muted: bool) -> None:
        self._gate.setValue(0.0 if muted else 1.0, time=0.05)

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

        # TODO states may also affect SwitchContainers which are part of playback control

    def from_hierarchy(
        self, bnk: Soundbank, root: int | HIRCNode, full_tree: bool = False
    ) -> Player:
        self.stop()
        self._node_map.clear()
        self.voices.clear()
        self._ctrl = None

        if isinstance(root, HIRCNode):
            root = root.id

        if full_tree:
            root, tree = next(bnk.find_event_subgraphs_for(root))
        else:
            tree = bnk.get_subtree(root, True)

        leafs = [n for (n, d) in tree.out_degree if d == 0]
        voices: dict[int, Voice] = {}
        master_ctrl = PlaybackControl([], playback_mode="parallel")
        controllers: dict[int, PlaybackControl] = {}

        for branch in nx.all_simple_paths(tree, root, leafs):
            leaf_id = branch[-1]
            ctrl = master_ctrl

            if leaf_id in voices:
                logger.warning(
                    f"Player will ignore secondary paths to {leaf_id} ({branch})"
                )
                continue

            leaf_node = bnk.get(leaf_id)

            if isinstance(leaf_node, Sound):
                path = bnk.get_wem_path(
                    leaf_node.source_id, leaf_node.bank_source_data.source_type
                )
                voice = Voice(StreamSource(path))
            elif isinstance(leaf_node, MusicTrack):
                # TODO what to do with tracks that have multiple sources?
                path = bnk.get_wem_path(
                    leaf_node.source_ids[0], leaf_node.sources[0].source_type
                )
                trims = leaf_node.get_trims()
                voice = Voice(
                    StreamSource(path, True, begin_trim=trims[0], end_trim=trims[1])
                )

                for clip in leaf_node.clip_items:
                    if clip.auto_type in (
                        ClipAutomationType.Volume,
                        ClipAutomationType.FadeIn,
                        ClipAutomationType.FadeOut,
                    ):
                        voice.mod[PropID.Volume].clips.append(clip)
                    elif clip.auto_type == ClipAutomationType.HPF:
                        voice.mod[PropID.HPF].clips.append(clip)
                    elif clip.auto_type == ClipAutomationType.LPF:
                        voice.mod[PropID.LPF].clips.append(clip)
                    else:
                        # Clips don't support pitch
                        raise ValueError(
                            f"Unsupported ClipAutomationType {clip.auto_type}"
                        )

            voices[leaf_id] = voice

            for branch_idx in range(len(branch)):
                node = bnk[branch[branch_idx]]
                self._node_map.setdefault(node.id, []).append(voice)

                # Collect anything from the node that will influence playback
                self._collect_modifiers(bnk, node, voice)

                if isinstance(node, MusicSegment):
                    voice.src.loop_start = (
                        node.get_marker_pos(MarkerId.LoopStart) / 1000.0
                    )
                    voice.src.loop_end = node.get_marker_pos(MarkerId.LoopEnd) / 1000.0

                # Playback control for different container types
                if isinstance(
                    node,
                    (
                        RandomSequenceContainer,
                        MusicRandomSequenceContainer,
                        SwitchContainer,
                        LayerContainer,
                    ),
                ):
                    if node.id not in controllers:
                        new_ctrl = PlaybackControl([])
                        ctrl.add_child(new_ctrl)
                        controllers[node.id] = new_ctrl
                        ctrl = controllers[node.id]

                        if isinstance(node, RandomSequenceContainer):
                            if node.random_mode_enum == RandomMode.Standard:
                                ctrl.playback_mode = "random"
                            else:
                                ctrl.playback_mode = "shuffle"

                            # Weights; we know that there is always at least a valid leaf node
                            next_node_id = branch[branch_idx + 1]
                            for item in node.playlist:
                                if item.play_id == next_node_id:
                                    ctrl.weights[-1] = item.weight
                                    break
                        elif isinstance(node, MusicRandomSequenceContainer):
                            if node.root_ers_type in (
                                RandomSequenceMode.ContinuousSequence,
                                RandomSequenceMode.StepSequence,
                            ):
                                ctrl.playback_mode = "playlist"
                            else:
                                ctrl.playback_mode = "random"

                            next_node_id = branch[branch_idx + 1]
                            for item in node.playlist_items:
                                if item.segment_id == next_node_id:
                                    ctrl.weights[-1] = item.weight
                                    break
                        elif isinstance(node, SwitchContainer):
                            ctrl.playback_mode = "select"
                        elif isinstance(node, LayerContainer):
                            ctrl.playback_mode = "parallel"

            # Add the voice to whatever is the leaf controller
            ctrl.children.add_child(voice)

        # build one pyo chain per leaf and register it as a mixer voice
        for idx, voice in enumerate(voices.values()):
            if voice.audiofile is None:
                continue

            tail = voice._build()
            voice.stop()
            self._mixer.addInput(idx, tail)
            self._mixer.setAmp(idx, 0, 1.0)

        self.voices = list(voices.values())
        self._ctrl = master_ctrl
        return self

    def _collect_modifiers(self, bnk: Soundbank, node: HIRCNode, voice: Voice) -> None:
        atten: Attenuation = None

        # Properties
        if isinstance(node, PropertyMixin):
            for bundle in node.properties:
                if bundle.prop_enum in voice.mod:
                    voice.mod[bundle.prop_enum].value += bundle.value
                elif bundle.prop_enum == PropID.Loop:
                    voice.src.loop = True
                elif bundle.prop_enum == PropID.LoopStart:
                    voice.src.loop_start = bundle.value / 1000.0
                elif bundle.prop_enum == PropID.LoopEnd:
                    # TODO verify that this is always positive
                    voice.src.loop_end = bundle.value / 1000.0
                elif bundle.prop_enum == PropID.AttenuationID:
                    atten = bnk.get(int(bundle.value))
                # Other properties to consider:
                # - Probability
                else:
                    # Other properties are ignored for now
                    pass

        # States
        if isinstance(node, StateMixin):
            # Find out which param idx controls the property
            for prop in (PropID.Volume, PropID.LPF, PropID.HPF, PropID.Pitch):
                prop_idx = None
                accum = None
                for idx, prop_info in enumerate(node.states.state_property_info):
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

                            voice.mod[prop].states.append(
                                StateCtrl(
                                    chunk.state_group_id,
                                    state_value,
                                    adjust,
                                    accum,
                                )
                            )

        # RTPCs
        if hasattr(node, "rtpcs"):
            rtpc: RTPC
            for rtpc in node.rtpcs:
                param = GameObjects.RTPCParameter(rtpc.param_id).name

                # TODO provide a better way to compare these
                if param == "Pitch":
                    voice.mod[PropID.Pitch].rtpcs.append(rtpc)
                elif param == "HPF":
                    voice.mod[PropID.HPF].rtpcs.append(rtpc)
                elif param == "LPF":
                    voice.mod[PropID.LPF].rtpcs.append(rtpc)
                elif param == "Volume":
                    voice.mod[PropID.Volume].rtpcs.append(rtpc)
                else:
                    # Unknown param
                    pass

        # Attenuations
        if atten:
            for param, prop in [
                (CurveParameters.VolumeDry, PropID.Volume),
                (CurveParameters.HPF, PropID.HPF),
                (CurveParameters.LPF, PropID.LPF),
            ]:
                curve_idx = atten.curves_to_use[param.value]
                if curve_idx >= 0 and curve_idx < len(atten.curves):
                    curve = atten.curves[curve_idx]
                    voice.mod[prop].attenuations.append(curve)

    def __getitem__(self, idx: int) -> Voice:
        return self.voices[idx]

    def __len__(self) -> int:
        return len(self.voices)
