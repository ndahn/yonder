from dataclasses import dataclass, field
from typing import ClassVar

from yonder.hash import global_id_generator
from .structure import _HIRCNodeBody, HIRCNode
from .rewwise_base_types import (
    MusicNodeParams,
    MusicTransNodeParams,
    PropBundle,
    Children,
)
from .rewwise_enums import PropID
from .mixins import PropertyMixin, ContainerMixin


@dataclass
class MusicRanSeqPlaylistItem:
    segment_id: int
    playlist_item_id: int = 0
    child_count: int = 0
    ers_type: int = 0
    loop_base: int = 0
    loop_min: int = 0
    loop_max: int = 0
    weight: int = 50
    avoid_repeat_count: int = 0
    use_weight: int = 0
    shuffle: int = 0

    def get_references(self) -> list[tuple[str, int]]:
        return [("segment_id", self.segment_id)]


@dataclass
class MusicRandomSequenceContainer(PropertyMixin, ContainerMixin, _HIRCNodeBody):
    body_type: ClassVar[int] = 13
    music_node_params: MusicNodeParams = field(default_factory=MusicNodeParams)
    music_trans_node_params: MusicTransNodeParams = field(
        default_factory=MusicTransNodeParams
    )
    playlist_item_count: int = 0
    playlist_items: list[MusicRanSeqPlaylistItem] = field(default_factory=list)

    @classmethod
    def new(
        cls,
        nid: int | str,
        playlist: list[int, list[int]],
        root_ers_type: int = 0,
        props: dict[PropID, float] = None,
        parent: int = 0,
    ) -> "HIRCNode[MusicRandomSequenceContainer]":
        if playlist:
            items = cls.make_playlist(playlist, root_ers_type=root_ers_type)
        else:
            items = []

        obj = HIRCNode(
            nid,
            cls(
                playlist_items=items,
            ),
        )

        obj.body.music_node_params.children.items = [
            p.segment_id for p in items if p.segment_id > 0
        ]

        if props:
            for prop, val in props.items():
                obj.body.set_property(prop, val)

        obj.body.parent = parent
        return obj

    @property
    def parent(self) -> int:
        return self.music_node_params.node_base_params.direct_parent_id

    @parent.setter
    def parent(self, new_parent: int) -> None:
        self.music_node_params.node_base_params.direct_parent_id = new_parent

    @property
    def children(self) -> Children:
        return self.music_node_params.children

    @property
    def properties(self) -> list[PropBundle]:
        return self.music_node_params.node_base_params.node_initial_params.prop_initial_values

    def set_playlist(self, items: list, root_ers_type: int = 0) -> None:
        playlist = self.make_playlist(items, root_ers_type)
        self.playlist_items = playlist
        self.music_node_params.children.items = [
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
