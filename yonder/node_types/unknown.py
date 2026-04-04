from dataclasses import dataclass, field
from typing import ClassVar

from .soundbank import _HIRCNodeBody


@dataclass
class TodoObject(_HIRCNodeBody):
    body_type: ClassVar[int] = 0
    data: list[int] = field(default_factory=list)
