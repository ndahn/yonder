from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import networkx as nx
import pyo

from yonder import Soundbank, HIRCNode
from yonder.types import MusicTrack, Sound, MusicTrack
from yonder.types.base_types import RTPC, StateGroup, ClipAutomation
from yonder.types.mixins import PropertyMixin, StateMixin
from yonder.enums import PropID, RtpcAccum


@dataclass
class Track:
    audiofile: Path = None
    properties: dict[PropID, float] = field(default_factory=dict)
    rtpc: dict[RTPC, float] = field(default_factory=dict)
    states: dict[StateGroup, float] = field(default_factory=dict)
    clips: dict[ClipAutomation, float] = field(default_factory=dict)


class Mixer:
    def __init__(self):
        self._default_fade_time = 0.05

        self._server = pyo.Server().boot()
        self._gate = pyo.SigTo(value=1.0, time=self._default_fade_time)

    def __del__(self):
        self._server.stop()
        self._server.shutdown()
        self._server = None

    def start(self) -> None:
        self._server.start()

    def stop(self) -> None:
        self._server.stop()

    def set_volume(self, vol: float) -> None:
        self._gate.setValue(vol, time=self._default_fade_time)

    def set_muted(self, muted: bool) -> None:
        self._gate.setValue(0.0 if muted else 1.0, time=self._default_fade_time)

    def fade(self, target_vol: float, duration: float) -> None:
        self._gate.setValue(target_vol, time=duration)

    def from_hierarchy(
        self, bnk: Soundbank, root: int | HIRCNode, full_tree: bool = True
    ) -> Mixer:
        self.stop()

        if isinstance(root, HIRCNode):
            root = root.id

        if full_tree:
            root, tree = next(bnk.find_event_subgraphs_for(root))
        else:
            tree = bnk.get_subtree(root)

        leafs = [n for (n, d) in tree.out_degree if d == 0]
        tracks: dict[int, Track] = {}

        for branch in nx.all_simple_paths(tree, root, leafs):
            leaf_id = branch[-1]

            if leaf_id not in tracks:
                track = Track()
                leaf_node = bnk.get(leaf_id)
                if leaf_node:
                    if isinstance(leaf_node, Sound):
                        track.audiofile = bnk.get_wem_path(
                            leaf_node.source_id, leaf_node.bank_source_data.source_type
                        )
                    elif isinstance(leaf_node, MusicTrack):
                        # TODO
                        pass

            track = tracks[leaf_id]

            for nid in branch:
                node = bnk[nid]
                if isinstance(node, PropertyMixin):
                    for bundle in node.properties:
                        if bundle.prop_enum not in track.properties:
                            track.properties[bundle.prop_enum] = bundle.value
                        else:
                            track.properties[bundle.prop_enum] += bundle.value

                if isinstance(node, StateMixin):
                    # TODO collect states
                    pass

                # TODO create mixin
                if hasattr(node, "rtpcs"):
                    # TODO collect rtpcs
                    pass

                if isinstance(node, MusicTrack):
                    # TODO collect clip automations
                    pass

                # TODO check for looping
                # TODO add pyo track

