from dataclasses import dataclass, field
from typing import ClassVar

from .soundbank import _HIRCNodeBody


@dataclass
class Event(_HIRCNodeBody):
    body_type: ClassVar[int] = 4
    action_count: int = 0
    actions: list[int] = field(default_factory=list)
