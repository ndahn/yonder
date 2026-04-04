from dataclasses import dataclass, field
from typing import ClassVar

from .soundbank import _HIRCNodeBody
from .rewwise_base_types import MusicTransNodeParams


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


@dataclass
class MusicRandomSequenceContainer(_HIRCNodeBody):
    body_type: ClassVar[int] = 13
    music_trans_node_params: MusicTransNodeParams = field(
        default_factory=MusicTransNodeParams
    )
    playlist_item_count: int = 0
    playlist_items: list[MusicRanSeqPlaylistItem] = field(default_factory=list)
