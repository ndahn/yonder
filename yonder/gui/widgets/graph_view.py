from typing import Any, Callable
import networkx as nx
from dearpygui import dearpygui as dpg

from yonder import Soundbank, Node
from yonder.gui import style
from yonder.gui.helpers import estimate_drawn_text_size


def add_graph_widget(
    bnk: Soundbank,
    root: Node,
    on_node_selected: Callable[[str, int | Node, Any], None] = None,
    *,
    children_only: bool = True,
    horizontal: bool = True,
    width: int = 400,
    height: int = 400,
    tag: str = None,
    user_data: Any = None,
) -> str:
    if not tag:
        tag = dpg.generate_uuid()

    g: nx.DiGraph = None
    layout: dict[int, tuple[int, int, int, int, str]] = {}
    current_highlight: int = -1

    def get_label(nid: int) -> str:
        node = bnk.get(nid)
        if node:
            return str(nid)
        return f"({nid})"

    # TODO layout needs some improvement for layers with multiple nodes
    def make_layout(g: nx.DiGraph) -> dict[int, tuple[int, int, str]]:
        offset = 0
        layer_separation = 40 if horizontal else 25
        layout: dict[int, tuple[int, int, str]] = {}

        for generation, layer in enumerate(nx.topological_generations(g)):
            labels = dict(sorted((nid, get_label(nid)) for nid in layer))
            max_len = max(len(v) for v in labels.values())
            txt_w, txt_h = estimate_drawn_text_size(max_len, font_size=12)

            for idx, (nid, label) in enumerate(labels.items()):
                if nid in layout:
                    continue

                if horizontal:
                    px = offset + layer_separation
                    py = (idx - len(layer) / 2) * (txt_h + 5)
                else:
                    px = (idx - len(layer) / 2) * (txt_w + 5)
                    py = offset + layer_separation

                layout[nid] = (generation, px, py, txt_w, txt_h, label)

            offset += txt_w if horizontal else txt_h

        return layout

    def render_graph(sender: str, app_data: list, node_indices: dict[int, int]) -> None:
        # NOTE this will crash if breakpoints are set anywhere in here!
        nonlocal current_highlight

        # Save some cpu cycles when no updates are needed
        if not (
            dpg.is_mouse_button_down(dpg.mvMouseButton_Left)
            or dpg.is_item_hovered(dpg.get_item_parent(f"{tag}_canvas"))
        ):
            return

        current_highlight = 0

        dpg_data = app_data[0]
        transformed_x = app_data[1]
        transformed_y = app_data[2]
        # transformed_w = app_data[3]
        # transformed_h = app_data[4]
        mouse_x = dpg_data["MouseX_PixelSpace"]
        mouse_y = dpg_data["MouseY_PixelSpace"]

        dpg.delete_item(sender, children_only=True, slot=2)
        dpg.push_container_stack(sender)
        dpg.configure_item(sender, tooltip=False)

        # Draw edges
        for src, dst in g.edges:
            sx = transformed_x[node_indices[src]]
            sy = transformed_y[node_indices[src]]
            dx = transformed_x[node_indices[dst]]
            dy = transformed_y[node_indices[dst]]

            if horizontal:
                mx = sx
                my = dy
            else:
                mx = dx
                my = sy

            dpg.draw_bezier_quadratic(
                (sx, sy),
                (mx, my),
                (dx, dy),
                color=style.purple.but(a=127),
                tag=f"{tag}_edge_{src}_{dst}",
            )

        # Draw nodes
        for i, nid in enumerate(g):
            idx = node_indices[nid]
            px = transformed_x[idx]
            py = transformed_y[idx]
            # pw = transformed_w[idx]
            # ph = transformed_h[idx]

            node_r = 10
            node = bnk.get(nid)
            label = node.type if node else "(external)"
            # TODO font_size does not match with the font we're using
            pw, ph = estimate_drawn_text_size(len(label), font_size=12)

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
            dpg.draw_circle(
                (px, py),
                node_r,
                fill=style.pink,
            )

            # Node highlight
            if current_highlight <= 0 and (
                px - node_r - 2 <= mouse_x <= px + node_r + 2
                and py - node_r - 2 <= mouse_y <= py + node_r + 2
            ):
                current_highlight = nid
                dpg.draw_circle(
                    (px, py),
                    14,
                    color=style.white,
                )
                dpg.configure_item(sender, tooltip=True)
                dpg.set_value(f"{tag}_canvas_tooltip", f"{label} ({nid})")

    def regenerate() -> None:
        nonlocal layout, g

        dpg.delete_item(f"{tag}_canvas_yaxis", children_only=True, slot=1)

        # TODO could limit the number of nodes, but worst case there are some glitches.
        # Even then the user will quickly realize that a deeper node will be more useful
        g = bnk.get_subtree(root, children_only)
        layout = make_layout(g)
        _, x, y, w, h, _ = map(list, list(zip(*layout.values())))
        node_indices = {nid: idx for idx, nid in enumerate(layout.keys())}

        with dpg.custom_series(
            x,
            y,
            2,
            # TODO pass w and h once https://github.com/hoffstadt/DearPyGui/pull/2616 is merged
            callback=render_graph,
            tooltip=False,
            user_data=node_indices,
            parent=f"{tag}_canvas_yaxis",
        ):
            dpg.add_text("", tag=f"{tag}_canvas_tooltip")

        dpg.split_frame()
        dpg.fit_axis_data(f"{tag}_canvas_yaxis")

    def on_mouse_click() -> None:
        if not on_node_selected:
            return

        if not dpg.does_item_exist(f"{tag}_canvas"):
            # Assume this widget has been destroyed
            dpg.delete_item(handler_reg)
            return

        if not dpg.is_item_hovered(f"{tag}_canvas"):
            return

        if current_highlight > 0:
            on_node_selected(tag, current_highlight, user_data)

    with dpg.plot(
        no_box_select=True,
        no_mouse_pos=True,
        no_menus=True,
        width=width,
        height=height,
        tag=f"{tag}_canvas",
    ):
        dpg.add_plot_axis(
            dpg.mvXAxis,
            # no_gridlines=True,
            no_highlight=True,
            no_label=True,
            no_tick_labels=True,
            no_tick_marks=True,
            no_menus=True,
        )
        dpg.add_plot_axis(
            dpg.mvYAxis,
            # no_gridlines=True,
            no_highlight=True,
            no_label=True,
            no_tick_labels=True,
            no_tick_marks=True,
            no_menus=True,
            tag=f"{tag}_canvas_yaxis",
        )

    with dpg.handler_registry() as handler_reg:
        dpg.add_mouse_click_handler(callback=on_mouse_click)

    regenerate()
