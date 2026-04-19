from typing import Any, Callable
import networkx as nx
from dearpygui import dearpygui as dpg

from yonder import Soundbank, HIRCNode
from yonder.gui import style
from yonder.gui.localization import µ
from yonder.gui.helpers import estimate_drawn_text_size
from .dpg_item import DpgItem


class add_graph_widget(DpgItem):
    """An interactive directed-graph widget for Dear PyGui.

    Renders a ``Soundbank`` subtree as a node-edge diagram using a
    ``dpg.custom_series`` inside a plot. Nodes are clickable; hovering
    shows a tooltip with the node type and ID.

    Parameters
    ----------
    bnk : Soundbank
        Soundbank used to resolve node IDs and type names.
    root : HIRCNode
        Root node whose subtree is displayed.
    on_node_selected : callable, optional
        Called as ``on_node_selected(tag, node_id, user_data)`` on click.
    children_only : bool
        Pass ``children_only`` to ``bnk.get_subtree``.
    horizontal : bool
        Lay out generations left-to-right when True, top-to-bottom when False.
    width : int
        Pixel width of the plot.
    height : int
        Pixel height of the plot.
    tag : int or str
        Explicit tag; auto-generated if None.
    user_data : any
        Passed through to ``on_node_selected``.
    """

    def __init__(
        self,
        bnk: Soundbank,
        root: HIRCNode,
        on_node_selected: Callable[[str, int | HIRCNode, Any], None] = None,
        *,
        children_only: bool = True,
        horizontal: bool = True,
        width: int = 400,
        height: int = 400,
        tag: int | str = None,
        user_data: Any = None,
    ) -> None:
        super().__init__(tag or dpg.generate_uuid())

        self._bnk = bnk
        self._root = root
        self._on_node_selected = on_node_selected
        self._children_only = children_only
        self._horizontal = horizontal
        self._user_data = user_data

        # Mutable render state
        self._g: nx.DiGraph = None
        self._layout: dict[int, tuple] = {}
        self._current_highlight: int = -1
        self._handler_reg: int | str = None

        self._build(width, height)
        self.regenerate()

    def __del__(self) -> None:
        self.destroy()

    def destroy(self) -> None:
        """Delete DPG items owned by this widget."""
        if dpg.does_item_exist(self._tag):
            dpg.delete_item(self._tag)
        if self._handler_reg and dpg.does_item_exist(self._handler_reg):
            dpg.delete_item(self._handler_reg)

    # === Build =========================================================

    def _build(self, width: int, height: int) -> None:
        tag = self._tag
        with dpg.plot(
            no_mouse_pos=True,
            no_menus=True,
            width=width,
            height=height,
            tag=tag,
        ):
            dpg.add_plot_axis(
                dpg.mvXAxis,
                tag=f"{tag}_xaxis",
                no_highlight=True,
                no_label=True,
                no_tick_labels=True,
                no_tick_marks=True,
                no_menus=True,
            )
            dpg.add_plot_axis(
                dpg.mvYAxis,
                tag=f"{tag}_yaxis",
                no_highlight=True,
                no_label=True,
                no_tick_labels=True,
                no_tick_marks=True,
                no_menus=True,
            )

        with dpg.handler_registry() as reg:
            dpg.add_mouse_click_handler(callback=self._on_mouse_click)
        self._handler_reg = reg

    # === Helpers =======================================================

    def _get_label(self, nid: int) -> str:
        return str(nid) if self._bnk.get(nid) else f"({nid})"

    # TODO layout needs some improvement for layers with multiple nodes
    def _make_layout(self, g: nx.DiGraph) -> dict[int, tuple]:
        offset = 0
        layer_separation = 40 if self._horizontal else 30
        layout: dict[int, tuple] = {}

        for generation, layer in enumerate(nx.topological_generations(g)):
            labels = {nid: self._get_label(nid) for nid in layer}
            max_len = max(len(v) for v in labels.values())
            txt_w, txt_h = estimate_drawn_text_size(max_len, font_size=12)

            for idx, (nid, label) in enumerate(labels.items()):
                if nid in layout:
                    continue
                if self._horizontal:
                    px = offset + layer_separation
                    py = (idx - len(layer) / 2) * (txt_h + 5)
                else:
                    px = (idx - len(layer) / 2) * (txt_w + 5)
                    py = offset + layer_separation
                layout[nid] = (generation, px, py, txt_w, txt_h, label)

            offset += txt_w if self._horizontal else txt_h

        return layout

    # === DPG callbacks =================================================

    def _on_mouse_click(self) -> None:
        if not self._on_node_selected:
            return

        if not dpg.does_item_exist(self._tag):
            # Widget destroyed; remove the stale handler registry
            dpg.delete_item(self._handler_reg)
            return

        if not dpg.is_item_hovered(self._tag):
            return

        if self._current_highlight > 0:
            self._on_node_selected(self._tag, self._current_highlight, self._user_data)

    def _render_graph(
        self, sender: str, series_data: list, node_indices: dict[int, int]
    ) -> None:
        # NOTE this will crash if breakpoints are set anywhere in here!

        # Save some cpu cycles when no updates are needed
        if not (
            dpg.is_mouse_button_down(dpg.mvMouseButton_Left)
            or dpg.is_item_hovered(dpg.get_item_parent(self._tag))
        ):
            return

        self._current_highlight = 0
        tag = self._tag

        helper_data = series_data[0]
        transformed_x = series_data[1]
        transformed_y = series_data[2]
        # transformed_w = series_data[3]
        # transformed_h = series_data[4]
        mouse_x = helper_data["MouseX_PixelSpace"]
        mouse_y = helper_data["MouseY_PixelSpace"]

        dpg.delete_item(sender, children_only=True, slot=2)
        dpg.push_container_stack(sender)
        dpg.configure_item(sender, tooltip=False)

        # Draw edges
        for src, dst in self._g.edges:
            sx = transformed_x[node_indices[src]]
            sy = transformed_y[node_indices[src]]
            dx = transformed_x[node_indices[dst]]
            dy = transformed_y[node_indices[dst]]

            mx, my = (sx, dy) if self._horizontal else (dx, sy)

            dpg.draw_bezier_quadratic(
                (sx, sy),
                (mx, my),
                (dx, dy),
                color=style.purple.but(a=127),
                tag=f"{tag}_edge_{src}_{dst}",
            )

        # Draw nodes
        node_r = 10
        for nid in self._g:
            idx = node_indices[nid]
            px = transformed_x[idx]
            py = transformed_y[idx]

            node = self._bnk.get(nid)
            label = node.type_name if node else µ("(not found)", node=node)
            # TODO font_size does not match with the font we're using
            _, ph = estimate_drawn_text_size(len(label), font_size=12)

            # Node label
            offset_y = 40
            dpg.draw_polyline(
                [(px, py), (px + 20, py + offset_y), (px + 100, py + offset_y)],
                color=style.white,
            )
            dpg.draw_text(
                (px + 35, py + offset_y - ph),
                label,
                size=18,
                color=style.pink,
                tag=f"{tag}_node_label_{nid}",
            )
            # Node marker
            dpg.draw_circle((px, py), node_r, fill=style.pink)

            # Node highlight
            if self._current_highlight <= 0 and (
                px - node_r - 2 <= mouse_x <= px + node_r + 2
                and py - node_r - 2 <= mouse_y <= py + node_r + 2
            ):
                self._current_highlight = nid
                dpg.draw_circle((px, py), 14, color=style.white)
                dpg.configure_item(sender, tooltip=True)
                dpg.set_value(f"{tag}_tooltip", f"{label} ({nid})")

        dpg.pop_container_stack()

    # === Public ========================================================

    def regenerate(self) -> None:
        """Rebuild the graph from the soundbank and re-fit the plot axes."""
        tag = self._tag
        dpg.delete_item(f"{tag}_yaxis", children_only=True, slot=1)

        # TODO could limit the number of nodes, but worst case there are some glitches.
        # Even then the user will quickly realize that a deeper node will be more useful
        self._g = self._bnk.get_subtree(self._root, self._children_only, True)
        self._layout = self._make_layout(self._g)
        _, x, y, w, h, _ = map(list, zip(*self._layout.values()))
        node_indices = {nid: idx for idx, nid in enumerate(self._layout.keys())}

        with dpg.custom_series(
            x,
            y,
            2,
            # TODO pass w and h once https://github.com/hoffstadt/DearPyGui/pull/2616 is merged
            callback=self._render_graph,
            tooltip=False,
            user_data=node_indices,
            parent=f"{tag}_yaxis",
        ):
            dpg.add_text("", tag=f"{tag}_tooltip")

        dpg.split_frame()
        dpg.fit_axis_data(f"{tag}_yaxis")
