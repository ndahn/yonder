from __future__ import annotations
from dataclasses import dataclass, field
from typing import ClassVar

from .hirc_node import HIRCNode
from .base_types import NodeBaseParams, Children, PropBundle, Playlist, PlaylistItem, RTPC
from yonder.enums import PropID, RandomMode, PlaybackMode
from .mixins import PropertyMixin


@dataclass
class RandomSequenceContainer(PropertyMixin, HIRCNode):
    body_type: ClassVar[int] = 5
    node_base_params: NodeBaseParams = field(default_factory=NodeBaseParams)
    loop_count: int = 1
    loop_mod_min: int = 0
    loop_mod_max: int = 0
    transition_time: float = 1000.0
    transition_time_mod_min: float = 0.0
    transition_time_mod_max: float = 0.0
    avoid_repeat_count: int = 1
    transition_mode: int = 0
    random_mode: int = 0
    mode: int = 0
    flags: int = 18
    children: Children = field(default_factory=Children)
    playlist: Playlist = field(default_factory=Playlist)

    @classmethod
    def new(
        cls,
        nid: int | str,
        nodes: int | list[int],
        playback_mode: PlaybackMode = PlaybackMode.Random,
        random_mode: RandomMode = RandomMode.Standard,
        loop_count: int = 1,
        avoid_repeat_count: int = 0,
        props: dict[PropID, float] = None,
        parent: int = 0,
    ) -> RandomSequenceContainer:
        obj = cls(
            nid,
            mode=playback_mode.value,
            random_mode=random_mode.value,
            loop_count=loop_count,
            avoid_repeat_count=avoid_repeat_count,
        )

        if nodes:
            for node in nodes:
                obj.add_playlist_item(node)

        if props:
            for prop, val in props.items():
                obj.set_property(prop, val)

        obj.parent = parent
        return obj

    @property
    def parent(self) -> int:
        return self.node_base_params.direct_parent_id

    @parent.setter
    def parent(self, new_parent: int) -> None:
        self.node_base_params.direct_parent_id = new_parent

    @property
    def properties(self) -> list[PropBundle]:
        return self.node_base_params.node_initial_params.prop_initial_values

    @property
    def rtpcs(self) -> list[RTPC]:
        return self.node_base_params.initial_rtpc.rtpcs

    @property
    def mode_enum(self) -> PlaybackMode:
        return PlaybackMode(self.mode)

    @property
    def random_mode_enum(self) -> RandomMode:
        return RandomMode(self.random_mode)

    def add_playlist_item(self, child_id: int) -> None:
        self.children.add(child_id)
        self.playlist.items.append(PlaylistItem(child_id))

    def remove_playlist_item(self, child_id: int) -> None:
        self.children.pop(child_id, missing_ok=True)
        for idx, item in enumerate(self.playlist.items):
            if item.play_id == child_id:
                self.playlist.items.pop(idx)
                break
