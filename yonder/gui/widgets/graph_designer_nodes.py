from __future__ import annotations
from typing import Any, ClassVar
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


class GraphDesignerNode:
    node_type: ClassVar[type[HIRCNode]] = None

    def __init__(self, nid: str | int = 0):
        self.nid = nid or dpg.generate_uuid()

    def _make_tag(self, is_input: bool, label: str, suffix: str = None) -> str:
        return f"{self.nid}#{'IN' if is_input else 'OUT'}#{label}#{suffix or ''}"

    def get_input_label(self, dpg_item_id: str | int) -> str:
        if isinstance(dpg_item_id, int):
            dpg_item_id = dpg.get_item_alias(dpg_item_id)

        try:
            tag, in_out, label, *_ = dpg_item_id.split("#")
            if int(tag) != self.nid:
                return None

            if in_out != "IN":
                return None
        except ValueError:
            return None

        return label

    def get_input_terminal(self, label: str) -> int:
        return self._make_tag(True, label)

    def get_output_label(self, dpg_item_id: str | int) -> str:
        if isinstance(dpg_item_id, int):
            dpg_item_id = dpg.get_item_alias(dpg_item_id)

        try:
            tag, in_out, label, *_ = dpg_item_id.split("#")
            if int(tag) != self.nid:
                return None

            if in_out != "OUT":
                return None
        except ValueError:
            return None

        return label

    def get_output_terminal(self, label: str) -> int:
        return self._make_tag(False, label)

    def link_valid(
        self,
        source: GraphDesignerNode,
        output: str,
        target: GraphDesignerNode,
        input: str,
    ) -> bool:
        return False

    def build(self, parent: str | int) -> None:
        pass

    def make_node(self, bnk: Soundbank) -> Any:
        pass


class RSCNode(GraphDesignerNode):
    node_type: ClassVar[type[HIRCNode]] = RandomSequenceContainer

    def __init__(
        self,
        mode: PlaybackMode = PlaybackMode.Random,
        items: list[int] = None,
        nid: str | int = 0,
    ):
        super().__init__(nid=nid)

        self.mode = mode
        self.items: list[int] = items or []

    def build(self, parent: str | int) -> None:
        with dpg.node(label="RSC", tag=self.nid, parent=parent):
            with dpg.node_attribute(attribute_type=dpg.mvNode_Attr_Static):
                dpg.add_combo(
                    [p.name for p in PlaybackMode],
                    default_value=PlaybackMode.Random.name,
                    fit_width=True,
                    label=µ("Mode"),
                )

            # Inputs
            for inp in ("Playback", "Action"):
                with dpg.node_attribute(
                    attribute_type=dpg.mvNode_Attr_Input, tag=self._make_tag(True, inp)
                ):
                    dpg.add_text(µ(inp))

            # Outputs
            for i in range(len(self.items) + 1):
                out = f"Item{i}"
                with dpg.node_attribute(
                    attribute_type=dpg.mvNode_Attr_Output, tag=self._make_tag(False, out)
                ):
                    dpg.add_text(µ(out))

    def make_node(self, bnk: Soundbank) -> RandomSequenceContainer:
        return RandomSequenceContainer.new(
            self.nid,
            self.items,
            playback_mode=self.mode,
        )

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
            return True

        else:
            raise ValueError("on_link called for node not participating in link")

        return False
