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
from yonder.gui.localization import µ
from yonder.util import logger
from yonder.gui import style
from yonder.gui.icons import Icons
from yonder.gui.widgets import DpgItem, GraphLayout, add_node_blocks, add_graph_widget


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
        self._delete_item(self._t("mouse_handler_reg"))
        self._delete_item(self._t("canvas_resize_reg"))

    def _build(self, title: str) -> None:
        with dpg.window(
            width=600,
            height=500,
            label=title,
            tag=self.tag,
            on_close=lambda s, a, u: dpg.delete_item(s),
        ):
            with dpg.group(horizontal=True):
                add_node_blocks(tag=self._t("blocks"))

                # Current version of dpg does not expose drag_callback for child_windows
                with dpg.group(
                    payload_type="node_type",
                    drag_callback=self._on_payload_drag,
                    drop_callback=self._on_payload_drop,
                ):
                    with dpg.child_window(
                        autosize_x=True,
                        autosize_y=True,
                        tag=self._t("canvas_container"),
                    ):
                        with dpg.drawlist(400, 400, tag=self._t("canvas")):
                            dpg.add_draw_node(tag=self._t("canvas_root"))

        with dpg.item_handler_registry(tag=self._t("canvas_resize_reg")):
            dpg.add_item_resize_handler(callback=self._on_canvas_resize)

        dpg.bind_item_handler_registry(
            self._t("canvas_container"), self._t("canvas_resize_reg")
        )

    def _store_node(self, nid: int, pos: tuple[float, float]):
        tp: type[HIRCNode] = self._g.nodes[nid]["type"]
        return GraphNode(pos, tp.__name__)

    def regenerate(self) -> None:
        self._layout.regenerate(self._g)

        margin = 3
        icon_w = 24
        icon_h = 24

        for nid, info in self._layout.nodes.items():
            dpg_id = self._t(f"node_{nid}")
            if dpg.does_item_exist(dpg_id):
                dpg.configure_item(dpg_id, pos=info.pos)
            else:
                color = style.type_colors.get(info.type_name, style.white)
                icon = Icons.get_type_icon_tag(info.type_name)

                with dpg.draw_node(tag=dpg_id, parent=self._t("canvas_root")):
                    dpg.draw_rectangle(
                        info.pos,
                        (
                            info.pos[0] + icon_w + margin * 2,
                            info.pos[1] + icon_h + margin * 2,
                        ),
                        color=style.white,
                        fill=style.dark_grey,
                        tag=self._t(f"node_{nid}_bg"),
                    )

                    dpg.draw_image(
                        icon,
                        # Respect the border
                        (info.pos[0] + margin + 1, info.pos[1] + margin + 1),
                        (info.pos[0] + icon_w, info.pos[1] + icon_h),
                        color=color,
                    )

    def _on_canvas_resize(self) -> None:
        w, h = dpg.get_item_rect_size(self._t("canvas_container"))
        dpg.configure_item(self._t("canvas"), width=w - 20, height=h - 20)

    def _set_highlight(self, node: int) -> None:
        # TODO manage two modes: hovered and current drop target
        if self._highlighted_node:
            dpg.configure_item(
                self._t(f"node_{self._highlighted_node}_bg"),
                thickness=1,
                color=style.white,
            )

        self._highlighted_node = node
        
        if node:
            dpg.configure_item(
                self._t(f"node_{node}_bg"),
                thickness=2,
                color=style.light_green,
            )

    def _is_drop_target_valid(self, payload: type, target: type) -> None:
        if payload is Event and not target:
            return True

        if payload is Action and target is Event:
            return True

        if hasattr(payload, "parent") and (
            target is Action or hasattr(target, "children")
        ):
            return True

        # TODO effects, busses, attenuations, etc
        return False

    def _on_payload_drag(self, sender: str, payload: Any) -> None:
        min_dist = 10e6
        closest: int = None

        # TODO
        mx, my = dpg.get_drawing_mouse_pos()

        # We generally expect less than 10 nodes here, so brute forcing it is fine
        for n in self._g:
            pos = self._layout[n].pos
            dist = pos[0] ** 2 + pos[1] ** 2
            if dist < min_dist:
                closest = n
                min_dist = dist

        if min_dist > 600:
            closest = None

        self._set_highlight(closest)

    def _on_payload_drop(self, sender: str, payload: type[HIRCNode]) -> None:
        source = self._highlighted_node
        source_type = self._g.nodes(source)["type"] if source else None

        if not self._is_drop_target_valid(payload, source_type):
            return

        nid = self._bnk.new_id()
        self._g.add_node(nid, type=payload)

        if source:
            self._g.add_edge(source, nid)

        self.regenerate()
