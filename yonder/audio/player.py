from __future__ import annotations
import networkx as nx
from pathlib import Path
import time
import atexit

# If there is no official wheel yet:
# pip install -i https://test.pypi.org/simple/ pyo
import pyo

from yonder import Soundbank, HIRCNode, Hash, calc_hash
from yonder.types import (
    Sound,
    MusicTrack,
    RandomSequenceContainer,
    SwitchContainer,
    LayerContainer,
    MusicRandomSequenceContainer,
)
from yonder.types.base_types import MusicRanSeqPlaylistItem
from yonder.enums import (
    PropID,
    ClipAutomationType,
    RandomMode,
    RandomSequenceMode,
)
from yonder.wem import wem2wav
from yonder.util import logger

from .voice import VoiceBuilder, Voice
from .stream_source import StreamSource
from .playback_control import PlaybackControl, SwitchManager


class Player:
    def __init__(
        self,
        bnk: Soundbank,
        entrypoint: HIRCNode,
        vgmstream_exe: Path | str,
        full_tree: bool = True,
    ):
        if not isinstance(entrypoint, HIRCNode):
            entrypoint = bnk[entrypoint]

        self.entrypoint = entrypoint
        self.voices: dict[int, Voice] = {}
        self._ctrl: PlaybackControl = None
        self._switch_ctrls: dict[int, PlaybackControl] = {}
        self._node_map: dict[int, list[Voice]] = {}

        # NOTE crashes on some systems with input enabled, but we don't need it
        self._server: pyo.Server = pyo.Server(duplex=0)
        self._server.deactivateMidi()
        self._server.boot()
        # mixes the voice branches; time smooths per-voice amp changes
        self._mixer = pyo.Mixer(outs=1, chnls=1, time=0.05)
        # final volume adjustment
        self._gate = pyo.SigTo(value=1.0, time=0.05)
        # master chain: mixer -> gate -> dac
        self._master = self._mixer[0] * self._gate
        self._master.out()

        self._server.start()
        # Important for proper exit
        atexit.register(self.close)

        self._from_hierarchy(bnk, entrypoint, vgmstream_exe, full_tree)

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def close(self) -> None:
        if self._ctrl:
            self._ctrl.stop()

        if self._server.getIsStarted():
            self._server.stop()
            # Allow the server to drain all buffers and callbacks
            time.sleep(0.25)

        if self._server.getIsBooted():
            self._server.shutdown()

        atexit.unregister(self.close)

    @property
    def playing(self) -> bool:
        return self._ctrl.isPlaying()

    @property
    def duration(self) -> float:
        """Playable duration of the voices this player currently controls. Will be `inf` if any voices are looping or randomized.

        Returns
        -------
        float
            Playable duration in seconds.
        """
        return self._ctrl.duration

    @property
    def pos(self) -> float:
        return self._ctrl.pos

    def seek(self, pos: float) -> float:
        return self._ctrl.seek(pos)

    def play(self, dur: float = 0, delay: float = 0) -> None:
        self._ctrl.play(dur, delay)

    def stop(self, wait: float = 0) -> None:
        if self._ctrl:
            self._ctrl.stop(wait)

    def set_volume(self, vol: float, time: float = 0.05) -> None:
        self._gate.time = time
        self._gate.value = vol

    def set_muted(self, muted: bool) -> None:
        self._gate.time = 0.05
        self._gate.value = 0.0 if muted else 1.0

    def set_state_params(
        self,
        rtpc_params: dict[Hash, float] = None,
        active_states: dict[Hash, Hash] = None,
        distance: float = 0.0,
    ) -> None:
        for voices in self._node_map.values():
            for voice in voices:
                voice.set_state_params(
                    rtpc_params=rtpc_params,
                    active_states=active_states,
                    distance=distance,
                )

        # NOTE switches and states are not the same, but for now there's little reason
        # to distinguish between them and track what each SwitchContainer listens to
        for key, val in active_states.items():
            key = calc_hash(key)
            val = calc_hash(val)
            for ctrl in self._switch_ctrls.get(key, []):
                ctrl.selector.state = val

    def _from_hierarchy(
        self,
        bnk: Soundbank,
        root: HIRCNode,
        vgmstream_exe: str,
        full_tree: bool = False,
    ) -> Player:
        self.stop()
        self.voices.clear()
        self._mixer.clear()
        self._ctrl = None
        self._node_map.clear()

        if isinstance(root, HIRCNode):
            root = root.id

        if full_tree:
            root = next(bnk.find_events_for(root, True))

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

            leaf_node = bnk.get(leaf_id)

            if isinstance(leaf_node, Sound):
                wem = bnk.get_wem_path(
                    leaf_node.source_id, leaf_node.bank_source_data.source_type
                )
                wav = wem2wav(vgmstream_exe, wem)[0]

                if not wav or not wav.is_file():
                    logger.error(f"Failed to create wav for {leaf_node}")
                    continue

                builder = VoiceBuilder(StreamSource(wav))
            elif isinstance(leaf_node, MusicTrack):
                # TODO what to do with tracks that have multiple sources?
                wem = bnk.get_wem_path(
                    leaf_node.source_ids[0], leaf_node.sources[0].source_type
                )
                wav = wem2wav(vgmstream_exe, wem)[0]

                if not wav or not wav.is_file():
                    logger.error(f"Failed to create wav for {leaf_node}")
                    continue

                trims = leaf_node.get_trims()
                builder = VoiceBuilder(
                    StreamSource(wav, True, begin_trim=trims[0], end_trim=trims[1])
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
            else:
                logger.debug(f"Unhandled leaf node {leaf_node}")
                continue

            for node_idx in range(len(branch)):
                node = bnk[branch[node_idx]]
                builder.collect_modifiers(bnk, node)

            voice = builder.build()
            voices[leaf_id] = voice

            for nid in branch:
                self._node_map.setdefault(nid, []).append(voice)

        # build one pyo chain per leaf and register it as a mixer voice
        for idx, voice in enumerate(voices.values()):
            voice.stop()
            self._mixer.addInput(idx, voice.tail)
            self._mixer.setAmp(idx, 0, 1.0)

        self.voices = voices
        self._build_control_tree(bnk, root)
        return self

    def _build_control_tree(
        self, bnk: Soundbank, root: int | HIRCNode, full_tree: bool = False
    ) -> PlaybackControl:
        if isinstance(root, HIRCNode):
            root = root.id

        if full_tree:
            root = next(bnk.find_events_for(root))

        tree = bnk.get_subtree(root, True)
        switch_ctrls: dict[int, PlaybackControl] = {}

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
                    weights = [
                        playlist.nodes[cid]["item"].weight for cid, _ in child_ctrls
                    ]

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
                return build_playlist_item(
                    playlist, node.playlist_items[0].playlist_item_id
                )

            children = tree.successors(nid)
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
                ctrl = PlaybackControl(playables, "switch")

                switch_map = {}
                for switch in node.switch_groups:
                    indices = []
                    for nid in switch.nodes:
                        try:
                            indices.append(node.children.items.index(nid))
                        except ValueError:
                            continue

                    switch_map[switch.switch_id] = indices

                selector: SwitchManager = ctrl.selector
                selector.switch_map = switch_map
                selector.default_state = node.default_switch

                switch_ctrls.setdefault(node.group_id, []).append(ctrl)

            # LayerContainer, events
            return PlaybackControl(playables, "parallel")

        self._ctrl = as_one(build(root))
        self._switch_ctrls = switch_ctrls

    def __getitem__(self, idx: int) -> Voice:
        return self.voices[idx]

    def __len__(self) -> int:
        return len(self.voices)
