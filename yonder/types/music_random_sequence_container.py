from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar

from yonder.hash import global_id_generator, Hash
from yonder.enums import PropID, CurveInterpolation, SyncType
from yonder.util import logger
from .hirc_node import HIRCNode
from .base_types import (
    MusicRanSeqPlaylistItem,
    MusicTransNodeParams,
    PropBundle,
    Children,
    MusicTransitionRule,
    MusicTransSrcRule,
    MusicTransDstRule,
    RTPC,
)
from .mixins import PropertyMixin


@dataclass(repr=False)
class MusicRandomSequenceContainer(PropertyMixin, HIRCNode):
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
        root_ers_type: int = 0,
        props: dict[PropID, float] = None,
        parent: int | HIRCNode = 0,
    ) -> MusicRandomSequenceContainer:
        if playlist:
            items = cls.make_playlist(playlist, root_ers_type=root_ers_type)
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

    def set_playlist(self, items: list, root_ers_type: int = 0) -> None:
        playlist = self.make_playlist(items, root_ers_type)
        self.playlist_items = playlist
        self.music_trans_node_params.music_node_params.children.items = [
            p.segment_id for p in playlist if p.segment_id > 0
        ]

    @staticmethod
    def make_playlist(
        items: list, root_ers_type: int = 0
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
                        ers_type=4294967295,
                        parent=parent_id,
                    )
                )
            else:
                group_ers = 0 if isinstance(item, list) else 1
                group_node = MusicRanSeqPlaylistItem(
                    0,
                    global_id_generator(),
                    ers_type=group_ers,
                    parent=parent_id,
                )
                playlist.append(group_node)
                for child in item:
                    assemble(child, playlist, group_node.playlist_item_id)

        playlist = [MusicRanSeqPlaylistItem(0, 0, ers_type=root_ers_type)]
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
        avoid_repeat_count: int = 1,
        loop_base: bool = False,
        ers_type: int = 4294967295,
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
        ers_type : int, default=0
            Playlist playback type (0 - sequence, 1 - random, 2 - shuffle, 4294967295 - inherit).
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

            if ers_type == 4294967295:
                ers_type = 0

            use_weight = True

        new_item = MusicRanSeqPlaylistItem(
            segment_id,
            playlist_item_id,
            ers_type=ers_type,
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

    def add_transition_rule(
        self,
        source_ids: int | list[int] = -1,
        dest_ids: int | list[int] = -1,
        sync_type: SyncType = SyncType.Immediate,
        source_transition_time: int = 0,
        source_fade_offset: int = 0,
        source_fade_curve: CurveInterpolation = CurveInterpolation.Linear,
        source_play_post_exit: bool = False,
        dest_transition_time: int = 0,
        dest_fade_offset: int = 0,
        dest_fade_curve: CurveInterpolation = CurveInterpolation.Linear,
        dest_play_pre_entry: bool = False,
        transition_segment: int = 0,
    ) -> MusicTransitionRule:
        """Add a transition rule between segments.

        Parameters
        ----------
        source_ids : int | list[int], default = -1
            Source segment IDs (-1 = any).
        dest_ids : int | list[int], default = -1
            Destination segment IDs (-1 = any).
        source_transition_time : int, default=0
            Source fade out time in ms.
        source_fade_offset : int, default=0
            Delay in ms before the source starts fading out.
        source_fade_curve : str, default=CurveInterpolation.Linear
            Source fade out curve type.
        sync_type : SyncType, default=SyncType.Immediate
            Marker sync type.
        dest_transition_time : int, default=0
            Destination fade out time in ms.
        dest_fade_offset : int, default=0
            Delay in ms before the destination starts fading in.
        dest_fade_curve : str, default=CurveInterpolation.Linear
            Destination fade in curve type.
        transition_segment: int | Node, default=0
            A MusicSegment to play during the transition.
        """
        if isinstance(source_ids, int):
            source_ids = [source_ids]

        if isinstance(dest_ids, int):
            dest_ids = [dest_ids]

        rule = MusicTransitionRule(
            source_ids=source_ids,
            destination_ids=dest_ids,
            source_transition_rule=MusicTransSrcRule(
                transition_time=source_transition_time,
                fade_curve=source_fade_curve,
                fade_offet=source_fade_offset,
                sync_type=sync_type,
                play_post_exit=1 if source_play_post_exit else 0,
            ),
            destination_transition_rule=MusicTransDstRule(
                transition_time=dest_transition_time,
                fade_curve=dest_fade_curve,
                fade_offet=dest_fade_offset,
                play_pre_entry=1 if dest_play_pre_entry else 0,
            ),
        )

        if transition_segment:
            rule.transition_object.segment_id = transition_segment

        self.music_trans_node_params.transition_rules.append(rule)
        return rule

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
