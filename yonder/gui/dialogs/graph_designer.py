from typing import Any, Callable
from dataclasses import dataclass
import networkx as nx
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
from yonder.util import logger
from yonder.gui import style
from yonder.gui.icons import Icons
from yonder.gui.widgets import DpgItem, GraphLayout, add_node_blocks, add_graph_widget
from yonder.gui.widgets.graph_designer_nodes import GraphDesignerNode, RSCNode


@dataclass
class GraphNode:
    pos: tuple[float, float]
    type_name: str


class graph_designer_dialog(DpgItem):
    def __init__(
        self,
        bnk: Soundbank,
        callback: Callable[[HIRCNode], None],
        *,
        title: str = "Graph Designer",
        tag: str = None,
    ) -> None:
        super().__init__(tag)

        self._bnk = bnk
        self._callback = callback

        self._g = nx.DiGraph()
        self._layout: GraphLayout[GraphNode] = GraphLayout(self._store_node, None)
        self._highlighted_node: int = None

        self._build(title)

    def destroy(self):
        self._delete_item(self._t("context_popup"))

    def _build(self, title: str) -> None:
        with dpg.window(
            width=600,
            height=500,
            label=title,
            tag=self.tag,
            on_close=lambda s, a, u: dpg.delete_item(s),
        ):
            dpg.add_node_editor(
                callback=self._on_link_nodes,
                delink_callback=self._on_unlink_nodes,
                tag=self._t("canvas"),
            )

            with dpg.popup(
                self._t("canvas"),
                min_size=(100, 20),
                tag=self._t("context_popup"),
            ):
                with dpg.menu(label=µ("Sounds")):
                    dpg.add_menu_item(
                        label="RandomSequenceContainer",
                        callback=None,
                    )
                    dpg.add_menu_item(
                        label="LayerContainer",
                        callback=None,
                    )
                    dpg.add_menu_item(
                        label="SwitchContainer",
                        callback=None,
                    )
                    dpg.add_menu_item(
                        label="Sound",
                        callback=None,
                    )

                with dpg.menu(label=µ("Music")):
                    dpg.add_menu_item(
                        label="MusicRandomSequenceContainer",
                        callback=None,
                    )
                    dpg.add_menu_item(
                        label="MusicSwitchContainer",
                        callback=None,
                    )
                    dpg.add_menu_item(
                        label="MusicSegment",
                        callback=None,
                    )
                    dpg.add_menu_item(
                        label="MusicTrack",
                        callback=None,
                    )

                with dpg.menu(label=µ("Playback")):
                    dpg.add_menu_item(
                        label="Event",
                        callback=None,
                    )
                    dpg.add_menu_item(
                        label="Action",
                        callback=None,
                    )

                with dpg.menu(label=µ("Effects")):
                    dpg.add_menu_item(
                        label="Attenuation",
                        callback=None,
                    )
                    dpg.add_menu_item(
                        label="Effect",
                        callback=None,
                    )
                    dpg.add_menu_item(
                        label="LFOModulator",
                        callback=None,
                    )
                    dpg.add_menu_item(
                        label="TimeModulator",
                        callback=None,
                    )

    def _get_input_node_for(self, dpg_item: int) -> tuple[GraphDesignerNode, str]:
        for nid, data in self._g.nodes(data=True):
            node: GraphDesignerNode = data["node"]
            terminal = node.get_input_label(dpg_item)
            if terminal:
                return (node, terminal)

        return (None, None)

    def _get_output_node_for(self, dpg_item: int) -> tuple[GraphDesignerNode, str]:
        for nid, data in self._g.nodes(data=True):
            node: GraphDesignerNode = data["node"]
            terminal = node.get_output_label(dpg_item)
            if terminal:
                return (node, terminal)

        return (None, None)

    def _on_link_nodes(self, sender: str, app_data: Any, user_data: Any) -> None:
        dpg_src, dpg_dst = app_data

        source, output = self._get_output_node_for(dpg_src)
        if not source:
            return

        target, input = self._get_input_node_for(dpg_dst)
        if not target:
            return

        if not self._is_link_valid(source.node_type, target.node_type):
            return

        if source.link_valid(source, output, target, input) and target.link_valid(
            source, output, target, input
        ):
            for edge, data in self._g.out_edges(source.nid, data=True):
                if data["dpg_src"] == dpg_src:
                    # TODO remove
                    pass

            for edge, data in self._g.in_edges(target.nid, data=True):
                if data["dpg_dst"] == dpg_dst:
                    # TODO remove
                    pass

            # TODO unlink previous inputs to dpg_dst
            dpg.add_node_link(dpg_src, dpg_dst)
            self._g.add_edge(
                source.nid,
                target.nid,
                dpg_src=dpg_src,
                output=output,
                dpg_dst=dpg_dst,
                input=input,
            )

    def _on_unlink_nodes(self, sender: str, app_data: Any, user_data: Any) -> None:
        dpg_src, dpg_dst = app_data
        source, _ = self._get_output_node_for(dpg_src)
        target, _ = self._get_input_node_for(dpg_dst)
        
        # TODO is there a case where the source->target pair is not unique?
        self._g.remove_edge(source.nid, target.nid)

    def _add_random_sequence_container(self) -> None:
        node = RSCNode(self._bnk.new_id())

        self._g.add_node(
            node.nid,
            type=RandomSequenceContainer,
            node=node,
        )

    def _is_link_valid(self, source: type, target: type) -> None:
        if source is Event and not target:
            return True

        if source is Action and target is Event:
            return True

        if hasattr(source, "parent") and (
            target is Action or hasattr(target, "children")
        ):
            return True

        # TODO effects, busses, attenuations, etc
        return False
