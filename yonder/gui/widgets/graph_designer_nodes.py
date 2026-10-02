from __future__ import annotations
from typing import Any, ClassVar
from dataclasses import dataclass, field
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.types import (
    HIRCNode,
    Action,
    ActorMixer,
    Attenuation,
    AuxiliaryBus,
    Bus,
    DialogueEvent,
    EffectCustom,
    EffectShareSet,
    Event,
    LayerContainer,
    LFOModulator,
    MusicRandomSequenceContainer,
    MusicSegment,
    MusicSwitchContainer,
    MusicTrack,
    RandomSequenceContainer,
    Sound,
    SwitchContainer,
    TimeModulator,
)
from yonder.enums import PlaybackMode
from yonder.gui.localization import µ
from yonder.gui import style
from yonder.gui.icons import Icons


@dataclass
class GraphDesignerNode:
    node_type: ClassVar[type[HIRCNode]] = None
    nid: int
    inputs: dict[int, str] = field(init=False, default_factory=dict)
    outputs: dict[int, str] = field(init=False, default_factory=dict)

    def get_input_label(self, dpg_item_id: str | int) -> str:
        if isinstance(dpg_item_id, str):
            dpg_item_id = dpg.get_alias_id(dpg_item_id)

        return self.inputs.get(dpg_item_id)

    def get_input_dpg(self, label: str) -> int:
        for dpg_id, terminal in self.inputs.items():
            if terminal == label:
                return dpg_id

        return None
    
    def get_output_label(self, dpg_item_id: str | int) -> str:
        if isinstance(dpg_item_id, str):
            dpg_item_id = dpg.get_alias_id(dpg_item_id)

        return self.outputs.get(dpg_item_id)

    def get_output_dpg(self, label: str) -> int:
        for dpg_id, terminal in self.outputs.items():
            if terminal == label:
                return dpg_id

        return None

    def link_valid(
        self,
        source: GraphDesignerNode,
        output: str,
        target: GraphDesignerNode,
        input: str,
    ) -> bool:
        return False

    def regenerate(self, parent: str | int) -> None:
        pass

    def make_node(self, bnk: Soundbank) -> Any:
        pass


@dataclass
class RSCNode(GraphDesignerNode):
    node_type: ClassVar[type[HIRCNode]] = RandomSequenceContainer
    mode: PlaybackMode = PlaybackMode.Random
    items: list[int] = field(default_factory=list)

    def regenerate(self, parent: str | int) -> None:
        with dpg.node(label="RSC", tag=self._t(f"node_{self.nid}", parent=parent)):
            with dpg.node_attribute(attribute_type=dpg.mvNode_Attr_Static):
                dpg.add_combo(
                    [p.name for p in PlaybackMode],
                    label=µ("Mode"),
                )

            # Inputs
            for inp in self.inputs:
                with dpg.add_node_attribute():
                    self._inputs[inp] = dpg.add_text(µ(inp))

            # Outputs
            for out in self.outputs:
                with dpg.node_attribute(attribute_type=dpg.mvNode_Attr_Output):
                    self._outputs[out] = dpg.add_text(µ(out))

    def make_node(self, bnk: Soundbank) -> RandomSequenceContainer:
        return RandomSequenceContainer.new(
            self.nid,
            self.items,
            playback_mode=self.mode,
        )

    @property
    def inputs(self) -> list[str]:
        return ("Playback", "Action")

    @property
    def outputs(self) -> tuple[str]:
        return (f"Item {i}" for i in range(len(self.items) + 1))

    def link_valid(
        self,
        source: GraphDesignerNode,
        output: str,
        target: GraphDesignerNode,
        input: str,
    ) -> bool:
        if source is target:
            return False

        if source is self:
            if output.startswith("Item") and input == "Playback":
                return True

        elif target is self:
            pass

        else:
            raise ValueError("on_link called for node not participating in link")

        return False
