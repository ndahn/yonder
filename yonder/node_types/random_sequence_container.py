from dataclasses import dataclass, field
from typing import ClassVar

from .soundbank import _HIRCNodeBody
from .rewwise_base_types import NodeBaseParams, Children


@dataclass
class PlaylistItem:
    play_id: int
    weight: int = 50


@dataclass
class Playlist:
    count: int = 0
    items: list[PlaylistItem] = field(default_factory=list)


@dataclass
class RandomSequenceContainer(_HIRCNodeBody):
    body_type: ClassVar[int] = 5
    node_base_params: NodeBaseParams = field(default_factory=NodeBaseParams)
    loop_count: int = 0
    loop_mod_min: int = 0
    loop_mod_max: int = 0
    transition_time: float = 0.0
    transition_time_mod_min: float = 0.0
    transition_time_mod_max: float = 0.0
    avoid_repeat_count: int = 0
    transition_mode: int = 0
    random_mode: int = 0
    mode: int = 0
    flags: int = 0
    children: Children = field(default_factory=Children)
    playlist: Playlist = field(default_factory=Playlist)
