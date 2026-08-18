from dataclasses import dataclass, field

from yonder import Soundbank
from yonder.enums import PropID


@dataclass
class PlayContext:
    bank: Soundbank
    
    properties: dict[PropID, float] = field(default_factory=dict)
    rtpcs: dict[int, int] = field(default_factory=dict)
    states: dict[int, int] = field(default_factory=dict)

    # TODO subscribe to changes
