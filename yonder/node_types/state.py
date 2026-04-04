from dataclasses import dataclass, field
from typing import ClassVar

from .soundbank import _HIRCNodeBody


@dataclass
class State(_HIRCNodeBody):
    body_type: ClassVar[int] = 1
    entry_count: int = 0
    parameters: list[int] = field(default_factory=list)
    values: list[float] = field(default_factory=list)
