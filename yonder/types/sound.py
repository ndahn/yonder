from dataclasses import dataclass, field
from typing import ClassVar
from pathlib import Path

from yonder.wem import get_wem_metadata
from .structure import HIRCNode
from .base_types import (
    NodeBaseParams,
    BankSourceData,
    PropBundle,
    MediaInformation,
)
from yonder.enums import SourceType, PropID
from .mixins import PropertyMixin


@dataclass
class Sound(PropertyMixin, HIRCNode):
    body_type: ClassVar[int] = 2
    bank_source_data: BankSourceData = field(default_factory=BankSourceData)
    node_base_params: NodeBaseParams = field(default_factory=NodeBaseParams)

    @classmethod
    def new(
        cls,
        nid: int | str,
        wem: Path = None,
        source_type: SourceType = SourceType.Embedded,
        props: dict[PropID, float] = None,
        parent: int = 0,
    ) -> "Sound":
        super().__init__(nid)
        obj = cls()

        if wem:
            obj.set_source_from_wem(wem, source_type)

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
    def source_id(self) -> int:
        return self.bank_source_data.media_information.source_id

    def set_source_from_wem(
        self,
        wem: Path,
        source_type: SourceType = SourceType.Embedded,
    ) -> BankSourceData:
        wem_id = wem.stem
        meta = get_wem_metadata(wem)
        size = meta["in_memory_size"]

        self.set_source(
            wem_id,
            size,
            source_type=source_type,
        )

    def set_source(
        self,
        source_id: int,
        media_size: int,
        source_type: SourceType = SourceType.Embedded,
    ) -> BankSourceData:
        self.bank_source_data = BankSourceData(
            source_type=source_type,
            media_information=MediaInformation(source_id, media_size),
        )
