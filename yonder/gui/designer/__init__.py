from .graph_designer_node import (
    GraphDesignerNode,
    can_reference,
    get_designer_node,
    get_designer_nodes,
)

# Need to import these so they register with the lookup table
from .amx_node import AMXNode
from .action_node import ActionNode
from .event_node import EventNode
from .lc_node import LCNode
from .mrsc_node import MRSCNode
from .msc_node import MSCNode
from .ms_node import MSNode
from .mt_node import MTNode
from .reference_node import ReferenceNode
from .rsc_node import RSCNode
from .sc_node import SCNode
from .sound_node import SoundNode


designer_node_categories: dict[str, list[type[GraphDesignerNode]]] = {
    "Sounds": [
        RSCNode,
        SCNode,
        LCNode,
        SoundNode,
    ],
    "Music": [
        MRSCNode,
        MSCNode,
        MSNode,
        MTNode,
    ],
    "Playback": [
        EventNode,
        ActionNode,
        AMXNode,
    ],
    "Effects": [
        # Attenuation,
        # EffectShareSet,
        # EffectCustom,
        # Bus,
        # AuxiliaryBus,
        # LFOModulator,
        # TimeModulator,
        # DialogueEventNode,
        ReferenceNode,
    ],
}
