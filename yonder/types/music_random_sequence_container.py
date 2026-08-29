from __future__ import annotations
from typing import ClassVar
from dataclasses import dataclass, field
import networkx as nx
import pyo

from yonder.hash import global_id_generator, Hash
from yonder.enums import PropID, CurveInterpolation, SyncType, RandomSequenceMode
from yonder.util import logger
from yonder.audio import PlayContext
from yonder.audio.mrsc_playlist_state import PlaylistState
from .hirc_node import HIRCNode, PyoState
from .base_types import (
    MusicRanSeqPlaylistItem,
    MusicTransNodeParams,
    PropBundle,
    Children,
    MusicTransitionRule,
    RTPC,
    StateChunk,
)
from .mixins import PropertyMixin, RtpcMixin, StateMixin


@dataclass(repr=False, eq=False)
class MusicRandomSequenceContainer(StateMixin, RtpcMixin, PropertyMixin, HIRCNode):
    body_type: ClassVar[int] = 13
    music_trans_node_params: MusicTransNodeParams = field(
        default_factory=MusicTransNodeParams
    )
    playlist_item_count: int = 0
    playlist_items: list[MusicRanSeqPlaylistItem] = field(default_factory=list)

    @classmethod
    def new(
        cls,
        nid: Hash,
        playlist: list[int, list[int]] = None,
        ers_type: RandomSequenceMode = RandomSequenceMode.ContinuousSequence,
        props: dict[PropID, float] = None,
        parent: int | HIRCNode = 0,
    ) -> MusicRandomSequenceContainer:
        if playlist:
            items = cls.make_playlist(playlist, ers_type=ers_type)
        else:
            items = []

        obj = cls(nid, playlist_items=items)

        obj.music_trans_node_params.music_node_params.children.items = [
            p.segment_id for p in items if p.segment_id > 0
        ]

        if props:
            for prop, val in props.items():
                obj.set_property(prop, val)

        obj.parent = parent
        return obj

    @property
    def transition_rules(self) -> list[MusicTransitionRule]:
        return self.music_trans_node_params.transition_rules

    @property
    def parent(self) -> int:
        return self.music_trans_node_params.music_node_params.node_base_params.direct_parent_id

    @parent.setter
    def parent(self, new_parent: int | HIRCNode) -> None:
        if isinstance(new_parent, HIRCNode):
            new_parent = new_parent.id
        self.music_trans_node_params.music_node_params.node_base_params.direct_parent_id = new_parent

    @property
    def children(self) -> Children:
        return self.music_trans_node_params.music_node_params.children

    @property
    def properties(self) -> list[PropBundle]:
        return self.music_trans_node_params.music_node_params.node_base_params.node_initial_params.prop_initial_values

    @property
    def rtpcs(self) -> list[RTPC]:
        return self.music_trans_node_params.music_node_params.node_base_params.initial_rtpc.rtpcs

    @property
    def states(self) -> StateChunk:
        return (
            self.music_trans_node_params.music_node_params.node_base_params.state_chunk
        )

    def set_playlist(
        self,
        items: list,
        ers_type: RandomSequenceMode = RandomSequenceMode.ContinuousSequence,
    ) -> None:
        playlist = self.make_playlist(items, ers_type)
        self.playlist_items = playlist
        self.music_trans_node_params.music_node_params.children.items = [
            p.segment_id for p in playlist if p.segment_id > 0
        ]

    @property
    def root_ers_type(self) -> RandomSequenceMode:
        if not self.playlist_items:
            return RandomSequenceMode.ContinuousSequence

        return self.playlist_items[0].ers_type_enum

    def get_playlist_tree(self) -> nx.DiGraph:
        g = nx.DiGraph()
        idx = 0

        while idx < len(self.playlist_items):
            item = self.playlist_items[idx]
            g.add_node(item.playlist_item_id, item=item)

            for child in self.playlist_items[idx + 1 : idx + 1 + item.child_count]:
                g.add_node(child.playlist_item_id, item=child)
                g.add_edge(
                    item.playlist_item_id,
                    child.playlist_item_id,
                    mode=item.ers_type_enum,
                )
            idx += item.child_count + 1

        return g

    @staticmethod
    def make_playlist(
        items: list,
        ers_type: RandomSequenceMode = RandomSequenceMode.ContinuousSequence,
    ) -> list[MusicRanSeqPlaylistItem]:
        def assemble(
            item: int | list | tuple,
            playlist: list[MusicRanSeqPlaylistItem],
            parent_id: int,
        ) -> None:
            if isinstance(item, int):
                playlist.append(
                    MusicRanSeqPlaylistItem(
                        item,
                        global_id_generator(),
                        ers_type=RandomSequenceMode.Inherit.value,
                        parent=parent_id,
                    )
                )
            else:
                if isinstance(item[0], RandomSequenceMode):
                    group_ers = item[0]
                    item = item[1:]
                elif isinstance(item, list):
                    group_ers = RandomSequenceMode.ContinuousSequence
                else:
                    group_ers = RandomSequenceMode.ContinuousRandom

                group_node = MusicRanSeqPlaylistItem(
                    0,
                    global_id_generator(),
                    ers_type=group_ers.value,
                    parent=parent_id,
                )
                playlist.append(group_node)
                for child in item:
                    assemble(child, playlist, group_node.playlist_item_id)

        playlist = [MusicRanSeqPlaylistItem(0, 0, ers_type=ers_type.value)]
        for child in items:
            assemble(child, playlist, playlist[-1].playlist_item_id)

        return playlist

    def add_playlist_item(
        self,
        playlist_item_id: int,
        segment_id: int | HIRCNode,
        weight: int = 50000,
        use_weight: bool = False,
        shuffle: bool = False,
        avoid_repeat_count: int = 0,
        loop_base: bool = False,
        ers_type: RandomSequenceMode = RandomSequenceMode.Inherit,
        parent: int | MusicRanSeqPlaylistItem = 0,
    ) -> MusicRanSeqPlaylistItem:
        """Associates a segment with this playlist for random/sequential playback. A playlist is actually a flattened tree structure where children inherit settings from their parents. Use the parent parameter to associate child items to their parents.

        Parameters
        ----------
        playlist_item_id : int
            Unique playlist item ID.
        segment_id : int | Node
            Segment node ID.
        weight : int, default=50000
            Relative weight for random selection.
        use_weight : bool, default=False
            Whether to use weight when shuffling. Always True for the first playlist item.
        avoid_repeat : int, default=0
            Number of recent items to avoid repeating.
        ers_type : RandomSequenceMode, default=RandomSequenceMode.Inherit
            Playlist playback type.
        parent : int, default=0
            Which playlist item to associate the new item with (0 - root).
        """
        if isinstance(parent, MusicRanSeqPlaylistItem):
            parent = parent.playlist_item_id

        if isinstance(segment_id, HIRCNode):
            segment_id = segment_id.id

        parent = int(parent)
        segment_id = int(segment_id)

        if len(self.playlist_items) == 0:
            if parent > 0:
                raise ValueError("parent cannot be set for first playlist item")

            if ers_type == RandomSequenceMode.Inherit:
                ers_type = RandomSequenceMode.ContinuousSequence

            use_weight = True

        new_item = MusicRanSeqPlaylistItem(
            segment_id,
            playlist_item_id,
            ers_type=ers_type.value,
            loop_base=1 if loop_base else 0,
            weight=weight,
            use_weight=1 if use_weight else 0,
            avoid_repeat_count=avoid_repeat_count,
            shuffle=1 if shuffle else 0,
        )

        if parent > 0:
            # Insert after parent
            for idx, item in enumerate(self.playlist_items):
                if item.playlist_item_id == parent:
                    insert_idx = idx + 1
                    parent_item = item
                    break
            else:
                raise ValueError(f"No playlist item with key {parent}")

            insert_idx += parent_item.child_count
            self.playlist_items.insert(insert_idx, new_item)
            parent_item.child_count += 1
        else:
            self.playlist_items.append(new_item)

        if segment_id > 0:
            self.children.add(segment_id)

        return new_item

    def attach(self, other: int | HIRCNode) -> None:
        if isinstance(other, HIRCNode):
            if other.parent not in (0, self.id):
                logger.warning(
                    f"{other} is already parented to {other.parent} and will be detached"
                )
            other.parent = self.id
            other = other.id

        pid = self.playlist_items[-1] + 1 if self.playlist_items else 0
        self.add_playlist_item(pid, int(other))

        logger.warning("Don't forget to adjust the new playlist item details!")

    def detach(self, other: int | HIRCNode) -> None:
        if isinstance(other, HIRCNode):
            other = other.id

        if other in self.children:
            self.children.remove(other)

            indices = []
            for idx, item in enumerate(self.playlist_items):
                if item.segment_id:
                    indices.append(idx)

            for idx in reversed(indices):
                self.playlist_items.pop(idx)

    def get_references(self, true_children_only: bool = True) -> list[tuple[str, int]]:
        ret = super().get_references()

        if true_children_only:
            # Some vanilla soundbanks have leftover transition rules that will result
            # in misleading warnings and mess up our gui's tree structure
            ret = [
                (p, i)
                for p, i in ret
                if "transition_rule" not in p or i in self.children
            ]

        return ret

    def _build_pyo(self, my_pyo: PyoState) -> pyo.InputFader:
        sig = pyo.Sig(0)
        my_pyo.cache["pyo_placeholder"] = sig
        return pyo.InputFader(sig)

    def play(self, ctx: PlayContext) -> None:
        if not self.playlist_items:
            return

        my_pyo = self.pyo(ctx)
        if my_pyo.playing:
            return

        my_pyo.playing = True
        self._play_next(ctx)

    def _play_next(self, ctx: PlayContext) -> None:
        my_pyo = self.pyo(ctx)
        if not my_pyo.playing:
            return

        ctx = my_pyo.ctx
        fader: pyo.InputFader = my_pyo.playback

        state: PlaylistState = my_pyo.cache.get("playlist_state")
        if not state:
            playlist = self.get_playlist_tree()
            state = PlaylistState(playlist)
            my_pyo.cache["playlist_state"] = state

        item = state.current_item
        prev_node = None
        if item:
            prev_node = ctx.bank.get(item.segment_id)

        while not state.finished:
            item = state.get_next_item()
            if not item:
                break

            node = ctx.bank.get(item.segment_id)
            if node:
                # Full transition support is a bit much for yonder, but we can do crossfades
                # TODO crossfade curves if we want to be fancy
                rule = self.music_trans_node_params.get_transition_rule(prev_node, node)
                xfade = (
                    max(
                        [
                            rule.source_transition_rule.transition_time,
                            rule.destination_transition_rule.transition_time,
                            50,
                        ]
                    )
                    / 1000
                )

                # TODO Not respecting Step modes, but should be fine for now
                node.register_end_trigger(ctx, self._play_next, xfade, 1)
                node.play(ctx)
                fader.setInput(node.pyo(ctx).playback, xfade)

                # Wait for the fader to finish
                if prev_node:
                    prev_node.release_pyo(ctx, xfade + 0.1)

                break
            else:
                logger.warning(f"Segment {item.segment_id} not found, skipping")

        if state.finished:
            fader.setInput(my_pyo.cache["pyo_placeholder"])
