from dataclasses import dataclass, field
from typing import ClassVar
from field_properties import field_property

from .structure import HIRCNode
from .rewwise_base_types import NodeBaseParams, Children, PropBundle
from yonder.enums import PropID, RandomMode
from .mixins import PropertyMixin, ContainerMixin


@dataclass
class PlaylistItem:
    play_id: int
    weight: int = 50000

    def get_references(self) -> list[tuple[str, int]]:
        return [("play_id", self.play_id)]


@dataclass
class Playlist:
    count: int = field_property(init=False, raw=True)
    items: list[PlaylistItem] = field(default_factory=list)

    @field_property
    def get_count(self) -> int:
        return len(self.items)


@dataclass
class RandomSequenceContainer(PropertyMixin, ContainerMixin, HIRCNode):
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
        avoid_repeat_count: int = 0,
        loop_count: int = 0,
        random_mode: RandomMode = RandomMode.Random,
        props: dict[PropID, float] = None,
        parent: int = 0,
    ) -> "RandomSequenceContainer":
        super().__init__(nid)
        obj = cls(
            avoid_repeat_count=avoid_repeat_count,
            loop_count=loop_count,
            random_mode=random_mode.value,
        )

        if nodes:
            for node in nodes:
                obj.add_child(node)

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

    def add_child(self, child_id: int) -> None:
        super().add_child(child_id)
        self.playlist.items.append(PlaylistItem(child_id))

    def remove_child(self, child_id: int) -> None:
        super().remove_child(child_id)
        for idx, item in enumerate(self.playlist.items):
            if item.play_id == child_id:
                self.playlist.items.pop(idx)
                break
