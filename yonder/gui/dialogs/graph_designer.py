from typing import Any, Callable
from dataclasses import dataclass
import webbrowser
import networkx as nx
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.types import HIRCNode
from yonder.gui.localization import µ
from yonder.util import logger
from yonder.gui import style
from yonder.gui.widgets import (
    DpgItem,
    GraphLayout,
    add_node_palette,
    yay,
)
from yonder.gui.designer import (
    GraphDesignerNode,
    designer_node_categories,
)


@dataclass
class GraphNode:
    pos: tuple[float, float]
    type_name: str


class graph_designer_dialog(DpgItem):
    """A node editor for assembling new HIRC hierarchies by hand.

    Nodes are added from the palette on the left, the "Add" menu, or by right
    clicking the canvas, and are wired up by dragging between their terminals.
    Every terminal holds at most one link; containers that can take more than
    one child grow a new slot whenever the last free one is used.

    Nothing is written to the soundbank until "Create" is pressed, at which
    point every node turns into an actual `HIRCNode`, the links are applied as
    parent/child relations, and the whole batch is added to the bank.

    The designer only knows about node types that have a `GraphDesignerNode`
    registered for them; everything else is shown greyed out.

    Parameters
    ----------
    bnk : Soundbank
        Target soundbank; used for ID allocation and duplicate checking.
    callback : callable
        Called as ``callback(nodes)`` with all created nodes on success.
    title : str
        Window title bar label.
    tag : int or str, optional
        Explicit tag; auto-generated if None. Existing item is deleted first.
    """

    def __init__(
        self,
        bnk: Soundbank,
        callback: Callable[[list[HIRCNode]], None],
        *,
        title: str = "Graph Designer",
        tag: str = None,
    ) -> None:
        if tag and dpg.does_item_exist(tag):
            dpg.delete_item(tag)

        super().__init__(tag)

        self._bnk = bnk
        self._callback = callback

        self._g = nx.DiGraph()
        self._spawn_pos: tuple[float, float] = (40.0, 40.0)
        self._palette: add_node_palette = None
        self._palette_shown: bool = True
        self._build(title)

    def destroy(self):
        if self._palette:
            self._palette.destroy()

        self._delete_item(self._t("context"))
        self._delete_item(self._t("handler_reg"))

    # === Build =========================================================

    def _build(self, title: str) -> None:
        with dpg.window(
            width=900,
            height=600,
            label=title,
            menubar=True,
            no_saved_settings=True,
            tag=self.tag,
            on_close=self._on_close,
        ):
            with dpg.menu_bar():
                with dpg.menu(label=µ("Add", "menu")):
                    self._build_add_menu()

                self._build_templates_menu()

                with dpg.menu(label=µ("Graph", "menu")):
                    dpg.add_menu_item(
                        label=µ("Auto Layout", "menu"),
                        callback=self.auto_layout,
                    )
                    dpg.add_menu_item(
                        label=µ("Delete Selected", "menu"),
                        shortcut="del",
                        callback=self.delete_selection,
                    )
                    dpg.add_separator()
                    dpg.add_menu_item(
                        label=µ("Clear", "menu"),
                        callback=self.clear,
                    )

            with dpg.group(horizontal=True):
                self._palette = add_node_palette(
                    designer_node_categories,
                    lambda s, a, u: self.add_node(a),
                    get_icon=lambda t, e: t.icon,
                    get_color=lambda t, e: t.color,
                    width=180,
                    height=-60,
                    autosize_y=False,
                    tag=self._t("palette"),
                )

                with dpg.child_window(
                    width=-1, height=-60, border=False, tag=self._t("canvas_container")
                ):
                    dpg.add_node_editor(
                        callback=self._on_link_nodes,
                        delink_callback=self._on_unlink_nodes,
                        minimap=True,
                        minimap_location=dpg.mvNodeMiniMap_Location_BottomRight,
                        tag=self._t("canvas"),
                    )

                # For some reason the node editor ignores themes bound to it directly
                dpg.bind_item_theme(
                    self._t("canvas_container"), style.themes.node_editor
                )

            dpg.add_text(show=False, tag=self._t("notification"), color=style.red)

            with dpg.group(horizontal=True):
                dpg.add_button(
                    label=µ("Create", "button"),
                    callback=self._on_okay,
                    tag=self._t("button_okay"),
                )
                dpg.add_button(
                    label="?",
                    callback=lambda s, a, u: webbrowser.open(u),
                    user_data="https://ndahn.github.io/yonder/tools/graph_designer/",
                )
                with dpg.tooltip(dpg.last_item()):
                    dpg.add_text("https://ndahn.github.io/yonder/tools/graph_designer/")

        # NOTE node editor doesn't accept popups at the moment
        with dpg.window(
            popup=True,
            show=False,
            tag=self._t("context"),
        ):
            self._build_add_menu()
            dpg.add_separator()
            self._build_templates_menu()

        with dpg.handler_registry(tag=self._t("handler_reg")):
            dpg.add_mouse_click_handler(callback=self._on_mouse_click)
            dpg.add_key_press_handler(
                dpg.mvKey_Delete, callback=self._on_delete_pressed
            )

    def _build_add_menu(self) -> None:
        """Menu items for every known node type, grouped like the palette."""
        for category, node_types in designer_node_categories.items():
            with dpg.menu(label=µ(category)):
                for designer_node in node_types:
                    dpg.add_menu_item(
                        label=designer_node.node_type.__name__,
                        enabled=designer_node is not None,
                        callback=lambda s, a, u: self.add_node(u),
                        user_data=designer_node,
                    )

        dpg.add_separator()

        dpg.add_menu_item(
            label=µ("Palette"),
            callback=self._toggle_nodes_panel,
        )

    def _build_templates_menu(self) -> None:
        with dpg.menu(label=µ("Templates", "menu")):
            # TODO prebuilt graphs (simple sound, bgm, ...)
            dpg.add_menu_item(label=µ("(none yet)"), enabled=False)

    # === Helpers =======================================================

    def _get_node(self, nid: int) -> GraphDesignerNode:
        data = self._g.nodes.get(nid)
        return data["node"] if data else None

    def _get_input_terminal_for(self, dpg_item: int) -> tuple[GraphDesignerNode, str]:
        for nid, data in self._g.nodes(data=True):
            node: GraphDesignerNode = data["node"]
            label = node.get_input_label(dpg_item)
            if label:
                return (node, label)

        return (None, None)

    def _get_output_terminal_for(self, dpg_item: int) -> tuple[GraphDesignerNode, str]:
        for nid, data in self._g.nodes(data=True):
            node: GraphDesignerNode = data["node"]
            label = node.get_output_label(dpg_item)
            if label:
                return (node, label)

        return (None, None)

    def _get_node_for_item(self, dpg_item: int | str) -> GraphDesignerNode:
        """Resolve a dpg node widget back to its designer node."""
        if not isinstance(dpg_item, str):
            dpg_item = dpg.get_item_alias(dpg_item)

        try:
            nid, kind = dpg_item.split("#")
            if kind != "NODE":
                return None
        except (AttributeError, ValueError):
            return None

        return self._get_node(int(nid))

    def _get_edge_at(self, nid: int, label: str, is_input: bool) -> tuple[int, int]:
        """The edge occupying a terminal, if any. Terminals are 1:1."""
        if is_input:
            for src, dst, data in self._g.in_edges(nid, data=True):
                if data["input"] == label:
                    return (src, dst)
        else:
            for src, dst, data in self._g.out_edges(nid, data=True):
                if data["output"] == label:
                    return (src, dst)

        return None

    def _get_edge_for_link(self, link: Any) -> tuple[int, int]:
        """Resolve whatever dpg hands us for a link to an edge in our graph."""
        if isinstance(link, (list, tuple)):
            # Some dpg versions report links as their two attributes
            source, _ = self._get_output_terminal_for(link[0])
            target, _ = self._get_input_terminal_for(link[1])
            if source and target and self._g.has_edge(source.nid, target.nid):
                return (source.nid, target.nid)

            return None

        for src, dst, data in self._g.edges(data=True):
            if data["link"] == link:
                return (src, dst)

        return None

    def _remove_edge(self, src: int, dst: int) -> None:
        if not self._g.has_edge(src, dst):
            return

        data = self._g.edges[src, dst]
        if dpg.does_item_exist(data["link"]):
            dpg.delete_item(data["link"])

        self._g.remove_edge(src, dst)
        self._notify_connections(self._get_node(src))
        self._notify_connections(self._get_node(dst))

    def _get_terminal_map(
        self, node: GraphDesignerNode
    ) -> tuple[dict[str, GraphDesignerNode], dict[str, GraphDesignerNode]]:
        # Children are attached in terminal order, which decides e.g. the
        # playlist order of a container
        def link_order(edge: tuple[int, int, dict]) -> tuple[int, int]:
            src, _, data = edge
            return (src, self._get_node(src).terminal_index(data["output"], False))

        edges = sorted(self._g.edges(node.nid, data=True), key=link_order)

        input_map = {}
        output_map = {}

        for src, dst, data in edges:
            input_map[data["input"]] = self._get_node(src)
            output_map[data["output"]] = self._get_node(dst)

        return input_map, output_map

    def _notify_connections(self, node: GraphDesignerNode) -> None:
        """Let a node adjust its terminals to the links it currently has."""
        if not node or not dpg.does_item_exist(node.node_tag):
            return

        input_map, output_map = self._get_terminal_map(node)
        node.notify_connections(input_map, output_map)

    def _link_allowed(
        self,
        source: GraphDesignerNode,
        output: str,
        target: GraphDesignerNode,
        input: str,
    ) -> bool:
        if source is target:
            self.show_message(µ("A node cannot be linked to itself", "msg"))
            return False

        if self._g.has_edge(source.nid, target.nid):
            self.unlink_terminal(target, input, True)

        if nx.has_path(self._g, target.nid, source.nid):
            self.show_message(µ("Link would create a cycle", "msg"))
            return False

        if not (
            source.link_valid(source, output, target, input)
            and target.link_valid(source, output, target, input)
        ):
            self.show_message(
                µ(
                    "{source}:{output} cannot be linked to {target}:{input}", "msg"
                ).format(
                    source=source.title,
                    output=output,
                    target=target.title,
                    input=input,
                )
            )
            return False

        return True

    def _canvas_pos(self, global_pos: tuple[float, float]) -> tuple[float, float]:
        """Convert a global mouse position to node editor coordinates."""
        ox, oy = dpg.get_item_rect_min(self._t("canvas"))
        return (max(global_pos[0] - ox, 0.0), max(global_pos[1] - oy, 0.0))

    def _cascade(self, pos: tuple[float, float]) -> tuple[float, float]:
        """Where the next node goes if the user didn't pick a spot."""
        x, y = pos[0] + 30.0, pos[1] + 30.0
        if y > 400.0:
            return (40.0, 40.0)

        return (x, y)

    # === DPG callbacks =================================================

    def _toggle_nodes_panel(self) -> None:
        if self._palette_shown:
            dpg.hide_item(self._t("palette"))
            self._palette_shown = False
        else:
            dpg.show_item(self._t("palette"))
            self._palette_shown = True

    def _on_close(self) -> None:
        # Clear first so the nodes get a chance to release their tags
        self.clear()
        self._delete_item(self.tag)
        self.destroy()

    def _on_mouse_click(
        self, sender: str, button: tuple[float, float, int], user_data: Any
    ) -> None:
        if dpg.is_item_hovered(self._t("canvas")):
            if button == dpg.mvMouseButton_Left:
                # Need to split, otherwise a previous pos might be returned
                dpg.split_frame()
                self._spawn_pos = dpg.get_mouse_pos(local=True)

            elif button == dpg.mvMouseButton_Right:
                # Prevent opening context menu while hovering one of the nodes
                for node in dpg.get_item_children(self._t("canvas"), slot=1):
                    if dpg.is_item_hovered(node):
                        return

                dpg.configure_item(
                    self._t("context"), pos=dpg.get_mouse_pos(local=False), show=True
                )

    def _on_delete_pressed(self, sender: str, key: int, user_data: Any) -> None:
        if not dpg.does_item_exist(self._t("canvas")):
            # Dialog is gone, get rid of the stale handlers
            self._delete_item(self._t("handler_reg"))
            return

        if not dpg.is_item_hovered(self._t("canvas")):
            return

        focused = dpg.get_focused_item()
        if focused and "Input" in dpg.get_item_type(focused):
            # Don't eat the key while someone is editing a node's widgets
            return

        self.delete_selection()

    def _on_link_nodes(self, sender: str, app_data: Any, user_data: Any) -> None:
        dpg_src, dpg_dst = app_data

        source, output = self._get_output_terminal_for(dpg_src)
        if not source:
            return

        target, input = self._get_input_terminal_for(dpg_dst)
        if not target:
            return

        if not self._link_allowed(source, output, target, input):
            return

        # Terminals are 1:1, so whatever was connected before gets dropped
        for edge in (
            self._get_edge_at(source.nid, output, False),
            self._get_edge_at(target.nid, input, True),
        ):
            if edge:
                self._remove_edge(*edge)

        link = dpg.add_node_link(
            source.get_output_terminal(output),
            target.get_input_terminal(input),
            parent=self._t("canvas"),
        )
        self._g.add_edge(
            source.nid,
            target.nid,
            link=link,
            output=output,
            input=input,
        )

        self._notify_connections(source)
        self._notify_connections(target)
        self.show_message()

    def _on_unlink_nodes(self, sender: str, app_data: Any, user_data: Any) -> None:
        edge = self._get_edge_for_link(app_data)
        if edge:
            self._remove_edge(*edge)
        elif dpg.does_item_exist(app_data):
            dpg.delete_item(app_data)

    def _on_okay(self) -> None:
        try:
            nodes = self.build_nodes()
        except ValueError as e:
            self.show_message(str(e))
            return
        except Exception as e:
            logger.exception(f"Failed to create graph: {e}")
            self.show_message(str(e))
            return

        logger.info(µ("Created {count} nodes", "log").format(count=len(nodes)))
        self._callback(nodes)
        self._on_close()
        yay()

    # === Public ========================================================

    def add_node(
        self, designer_node: type[GraphDesignerNode], pos: tuple[float, float] = None
    ) -> GraphDesignerNode:
        """Add a new node of the given HIRC type to the canvas."""
        pos = pos or self._spawn_pos
        node = designer_node(self._bnk, self._bnk.new_id())
        node.set_unlink_handler(self.unlink_terminal)
        self._g.add_node(node.nid, type=designer_node.node_type, node=node)
        node.build(self._t("canvas"), pos)
        self._spawn_pos = self._cascade(pos)

        self.show_message()
        return node

    def unlink_terminal(
        self, node: GraphDesignerNode, label: str, is_input: bool
    ) -> None:
        """Drop the link on one of a node's terminals, e.g. before removing it.

        Nodes call this through the handler they get in `add_node`, so they can
        rearrange their terminals without leaving edges behind.
        """
        if node.nid not in self._g:
            return

        edge = self._get_edge_at(node.nid, label, is_input)
        if edge:
            self._remove_edge(*edge)

    def remove_node(self, node: GraphDesignerNode) -> None:
        """Remove a node and all links attached to it."""
        if node.nid not in self._g:
            return

        for src, dst in list(self._g.in_edges(node.nid)) + list(
            self._g.out_edges(node.nid)
        ):
            self._remove_edge(src, dst)

        self._g.remove_node(node.nid)
        node.destroy()

    def delete_selection(self) -> None:
        """Remove all selected links and nodes."""
        canvas = self._t("canvas")

        for link in dpg.get_selected_links(canvas):
            edge = self._get_edge_for_link(link)
            if edge:
                self._remove_edge(*edge)

        for item in dpg.get_selected_nodes(canvas):
            node = self._get_node_for_item(item)
            if node:
                self.remove_node(node)

        dpg.clear_selected_links(canvas)
        dpg.clear_selected_nodes(canvas)

    def clear(self) -> None:
        """Remove everything from the canvas."""
        for node in [data["node"] for _, data in self._g.nodes(data=True)]:
            self.remove_node(node)

        self._g.clear()
        self._spawn_pos = (40.0, 40.0)
        self.show_message()

    def auto_layout(self) -> None:
        """Arrange the nodes left to right, parents before their children."""
        if not self._g:
            return

        layout: GraphLayout[GraphNode] = GraphLayout(
            lambda nid, pos: GraphNode(pos, self._g.nodes[nid]["type"].__name__),
            self._g,
            horizontal=True,
            node_spacing=280.0,
        )
        if not layout:
            return

        positions = [n.pos for n in layout.nodes.values()]
        ox = 40.0 - min(p[0] for p in positions)
        oy = 40.0 - min(p[1] for p in positions)

        for nid, gnode in layout.nodes.items():
            node = self._get_node(nid)
            if node and dpg.does_item_exist(node.node_tag):
                dpg.set_item_pos(node.node_tag, (gnode.pos[0] + ox, gnode.pos[1] + oy))

    def build_nodes(self) -> list[HIRCNode]:
        """Turn the graph into HIRC nodes and add them to the soundbank.

        Raises
        ------
        ValueError
            If the graph is empty or any of its nodes is not ready to be built.
        """
        if not self._g:
            raise ValueError(µ("There is nothing to create", "msg"))

        names: set[str] = set()
        for nid, data in self._g.nodes(data=True):
            node: GraphDesignerNode = data["node"]

            msg = node.validate(self._bnk)
            if msg:
                raise ValueError(msg)

            if node.name:
                if node.name in names:
                    raise ValueError(
                        µ("{name} is used more than once", "msg").format(name=node.name)
                    )
                names.add(node.name)

        created: list[HIRCNode] = []

        for nid in nx.topological_sort(self._g):
            input_map, output_map = self._get_terminal_map(node)
            ret = self._get_node(nid).make_node(self._bnk, input_map, output_map)
            if isinstance(ret, (list, tuple)):
                created.extend(ret)
            else:
                created.append(ret)

        self._bnk.add_nodes(*created)
        return created

    def show_message(self, msg: str = None, color: style.RGBA = style.red) -> None:
        """Show or hide the notification label. Pass ``msg=None`` to hide."""
        if not msg:
            dpg.hide_item(self._t("notification"))
            return

        dpg.configure_item(
            self._t("notification"),
            default_value=msg,
            color=color,
            show=True,
        )
