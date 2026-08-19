from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass, field

from yonder import Soundbank, HIRCNode
from yonder.types.mixins import PropertyMixin
from yonder.enums import PropID


@dataclass
class PlayContext:
    bank: Soundbank
    vgmstream_exe: Path = None
    wem_search_paths: list[Path] = field(default_factory=list)

    properties: dict[PropID, float] = field(default_factory=dict)
    rtpcs: dict[int, int] = field(default_factory=dict)
    states: dict[int, int] = field(default_factory=dict)

    def merge(self, node: HIRCNode | PlayContext) -> PlayContext:
        properties = dict(self.properties)
        rtpcs = dict(self.rtpcs)
        states = dict(self.states)

        if isinstance(node, HIRCNode):
            if isinstance(node, PropertyMixin):
                for prop in node.properties:
                    if prop.prop_enum.is_accumulating():
                        properties.setdefault(prop.prop_enum, 0.0)
                        properties[prop.prop_enum] += prop.value
                    else:
                        properties[prop.prop_enum] = prop.value

        elif isinstance(node, PlayContext):
            if self.bank != node.bank:
                raise ValueError("Cannot merge play contexts with different banks")

            for prop, val in node.properties.items():
                if prop in properties and prop.is_accumulating():
                    properties[prop] += val
                else:
                    properties[prop] = val

            rtpcs = dict(self.rtpcs).update(node.rtpcs)
            states = dict(self.states).update(node.states)

        else:
            raise TypeError(f"Invalid merge object {node}")

        return PlayContext(self.bank, properties, rtpcs, states)
