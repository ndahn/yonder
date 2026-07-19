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
    RandomSequenceContainer,
    SwitchContainer,
    LayerContainer,
    MusicRandomSequenceContainer,
)
from yonder.types.base_types import MusicRanSeqPlaylistItem
from yonder.enums import (
    PropID,
    MarkerId,
    ClipAutomationType,
    RandomMode,
    RandomSequenceMode,
)
from yonder.util import logger

from .voice import VoiceBuilder, Voice
from .stream_source import StreamSource
from .playback_control import PlaybackControl


class Player:
    def __init__(self):
        self.voices: dict[int, Voice] = []
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
                builder = VoiceBuilder(StreamSource(path))
            elif isinstance(leaf_node, MusicTrack):
                # TODO what to do with tracks that have multiple sources?
                path = bnk.get_wem_path(
                    leaf_node.source_ids[0], leaf_node.sources[0].source_type
                )
                trims = leaf_node.get_trims()
                builder = VoiceBuilder(
                    StreamSource(path, True, begin_trim=trims[0], end_trim=trims[1])
                )

                for clip in leaf_node.clip_items:
                    if clip.auto_type in (
                        ClipAutomationType.Volume,
                        ClipAutomationType.FadeIn,
                        ClipAutomationType.FadeOut,
                    ):
                        builder.mod[PropID.Volume].clips.append(clip)
                    elif clip.auto_type == ClipAutomationType.HPF:
                        builder.mod[PropID.HPF].clips.append(clip)
                    elif clip.auto_type == ClipAutomationType.LPF:
                        builder.mod[PropID.LPF].clips.append(clip)
                    else:
                        # Clips don't support pitch
                        raise ValueError(
                            f"Unsupported ClipAutomationType {clip.auto_type}"
                        )

            for node_idx in range(len(branch)):
                node = bnk[branch[node_idx]]
                self._node_map.setdefault(node.id, []).append(builder)

                # Collect anything from the node that will influence playback
                builder.collect_modifiers(bnk, node)

                if isinstance(node, MusicSegment):
                    builder.src.loop_start = (
                        node.get_marker_pos(MarkerId.LoopStart) / 1000.0
                    )
                    builder.src.loop_end = (
                        node.get_marker_pos(MarkerId.LoopEnd) / 1000.0
                    )

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
                    if node.id in controllers:
                        ctrl = controllers[node.id]
                    else:
                        new_ctrl = PlaybackControl([])
                        weight = 50000

                        if isinstance(node, RandomSequenceContainer):
                            if node.random_mode_enum == RandomMode.Standard:
                                new_ctrl.playback_mode = "random"
                            else:
                                new_ctrl.playback_mode = "shuffle"

                            # Weights; we know that there is always at least a valid leaf node
                            next_node_id = branch[node_idx + 1]
                            for item in node.playlist:
                                if item.play_id == next_node_id:
                                    weight = item.weight
                                    break
                        elif isinstance(node, MusicRandomSequenceContainer):
                            if node.root_ers_type in (
                                RandomSequenceMode.ContinuousSequence,
                                RandomSequenceMode.StepSequence,
                            ):
                                new_ctrl.playback_mode = "playlist"
                            else:
                                new_ctrl.playback_mode = "random"

                            next_node_id = branch[node_idx + 1]
                            for item in node.playlist_items:
                                if item.segment_id == next_node_id:
                                    weight = item.weight
                                    break
                        elif isinstance(node, SwitchContainer):
                            new_ctrl.playback_mode = "select"
                        elif isinstance(node, LayerContainer):
                            new_ctrl.playback_mode = "parallel"

                        ctrl.add_child(new_ctrl, weight)
                        controllers[node.id] = new_ctrl
                        ctrl = controllers[node.id]

            # Add the voice to whatever is the leaf controller
            voice = builder.build()
            ctrl.add_child(voice)
            voices[leaf_id] = voice

        # build one pyo chain per leaf and register it as a mixer voice
        for idx, voice in enumerate(voices.values()):
            if voice.audiofile is None:
                continue

            tail = voice._build()
            voice.stop()
            self._mixer.addInput(idx, tail)
            self._mixer.setAmp(idx, 0, 1.0)

        self.voices = voices
        self._ctrl = self._build_control_tree(bnk, root)
        return self

    def _build_control_tree(self, bnk: Soundbank, root: int | HIRCNode) -> PlaybackControl:
        if isinstance(root, HIRCNode):
            root = root.id

        def as_one(playable) -> PlaybackControl:
            # A bare list should play its items in parallel
            if isinstance(playable, list):
                if len(playable) == 1:
                    return playable[0]
    
                return PlaybackControl(playable, "parallel")

            return playable

        def build_playlist_item(playlist: nx.DiGraph, item_id: int):
            item: MusicRanSeqPlaylistItem = playlist.nodes[item_id]["item"]
            child_ids = list(playlist.successors(item_id))

            if not child_ids:
                # leaf item (could also be an empty group)
                segment = build(item.segment_id)
                return as_one(segment) if segment else None

            child_ctrls = []
            for cid in child_ids:
                ctrl = build_playlist_item(playlist, cid)
                if ctrl:
                    child_ctrls.append((cid, ctrl))

            if not child_ctrls:
                return None

            weights = None
            if item.ers_type_enum in (
                RandomSequenceMode.ContinuousSequence,
                RandomSequenceMode.StepSequence,
            ):
                # TODO step: play one then wait instead of auto-advance
                mode = "playlist"
            else:
                # standard-vs-shuffle is the item's own flag, not part of ers_type
                mode = "shuffle" if item.shuffle else "random"
                if item.use_weight:
                    # weights sit on the child items
                    weights = [playlist.nodes[cid]["item"].weight for cid, _ in child_ctrls]

            # TODO loop_base/min/max
            return PlaybackControl([c for _, c in child_ctrls], mode, weights)

        def build(nid: Hash):
            if nid in self.voices:
                return self.voices[nid]

            node = bnk.get(nid)
            if not node:
                return None

            # MRSCs have tree-like playlist structures
            if isinstance(node, MusicRandomSequenceContainer):
                playlist = node.get_playlist_tree()
                return build_playlist_item(playlist, node.playlist_items[0].playlist_item_id)

            children = getattr(node, "children", None)
            if not children:
                return None

            child_ctrls = []
            for cid in children:
                sub = build(cid)
                if sub:
                    child_ctrls.append((cid, sub))
            
            if not child_ctrls:
                return None

            if not isinstance(
                node, (RandomSequenceContainer, SwitchContainer, LayerContainer)
            ):
                # prevent nested lists that would cause issues
                flat = []
                for _, sub in child_ctrls:
                    if isinstance(sub, list):
                        flat.extend(sub)
                    else:
                        flat.append(sub)

                return flat

            # Don't flatten, or the current container controller would suddenly see more 
            # children than the node actually has
            kept = [(cid, as_one(sub)) for cid, sub in child_ctrls]
            playables = [c for _, c in kept]

            if isinstance(node, RandomSequenceContainer):
                if node.random_mode_enum == RandomMode.Standard:
                    mode = "random"
                else:
                    mode = "shuffle"

                # weights keyed per child id, aligned with children actually kept
                wmap = {p.play_id: p.weight for p in node.playlist}
                weights = [wmap.get(cid, 50000) for cid, _ in kept]
                return PlaybackControl(playables, mode, weights)

            if isinstance(node, SwitchContainer):
                return PlaybackControl(playables, "select")

            # LayerContainer, events
            return PlaybackControl(playables, "parallel")

        return as_one(build(root))

    def __getitem__(self, idx: int) -> Voice:
        return self.voices[idx]

    def __len__(self) -> int:
        return len(self.voices)
