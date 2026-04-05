from dataclasses import dataclass, field
from typing import ClassVar

from .structure import HIRCNode


@dataclass
class TodoObject(HIRCNode):
    body_type: ClassVar[int] = 0
    data: list[int] = field(default_factory=list)
