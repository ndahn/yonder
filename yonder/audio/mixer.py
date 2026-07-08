from __future__ import annotations
import networkx as nx
import pyo

from yonder import Soundbank, HIRCNode
from yonder.types import MusicTrack
from yonder.types.base_types import RTPC, StateGroup, ClipAutomation
from yonder.types.mixins import PropertyMixin, StateMixin
from yonder.enums import PropID, RtpcAccum


class Mixer:
    @classmethod
    def from_hierarchy(cls, bnk: Soundbank, root: int | HIRCNode, full_tree: bool = True) -> Mixer:
        if isinstance(root, HIRCNode):
            root = root.id

        if full_tree:
            root, tree = next(bnk.find_event_subgraphs_for(root))
        else:
            tree = bnk.get_subtree(root)

        leafs = [n for (n, d) in tree.out_degree if d == 0]
        tracks = []

        for branch in nx.all_simple_paths(tree, root, leafs):
            properties: dict[PropID, float] = {}
            rtpc: dict[RTPC, float] = {}
            states: dict[StateGroup, float] = {}
            clips: dict[ClipAutomation, float] = {}

            for nid in branch:
                node = bnk[nid]
                if isinstance(node, PropertyMixin):
                    for bundle in node.properties:
                        if bundle.prop_enum not in properties:
                            properties[bundle.prop_enum] = bundle.value
                        else:
                            properties[bundle.prop_enum] += bundle.value

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



    def __init__(self):
        pass
