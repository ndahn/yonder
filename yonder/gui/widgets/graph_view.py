from typing import Any, Callable
import math
import networkx as nx
from dataclasses import dataclass
from dearpygui import dearpygui as dpg

from yonder import Soundbank, HIRCNode
from yonder.gui import style
from yonder.gui.localization import µ
from yonder.gui.helpers import estimate_drawn_text_size
from .dpg_item import DpgItem


@dataclass
class GraphNode:
    """layout + display info for one visible node."""

    label: str  # full "type (id)" description, used for tooltips/popups
    short_label: str  # 1-4 letter tag drawn inside the node marker
    pos: tuple[float, float]
    hidden: list[int]  # sibling branch ids collapsed under this node


class add_graph_widget(DpgItem):
    """An interactive directed-graph widget.

    Renders a ``Soundbank`` subtree as a node-edge diagram using a
    ``dpg.custom_series`` inside a plot. Nodes are laid out on a radial
    half-ring: the root sits at the center, each generation forms a wider
    ring around it (opening downward when vertical, rightward when
    horizontal), and siblings share their parent's angular wedge in
    proportion to subtree size - so a chain of single-child nodes forms a
    straight ray. Left-clicking a node selects and highlights it; hovering
    shows a tooltip with the node type and ID.

    Nodes with more than ``max_children`` children only show a single
    branch at a time, drawn with a "+N" badge instead of a type label.
    Right-clicking such a node opens a popup to pick which branch to
    reveal. The currently shown branches, and the current selection, can
    also be driven manually so the widget can be used breadcrumb-style:

    - ``select_branch(parent_id, child_id)`` reveal a specific branch
    - ``reset_branch(parent_id)`` / ``reset_branches()`` revert to defaults
    - ``get_branches(parent_id)`` / ``get_selected_branch(parent_id)`` inspect state
    - ``select_node(node_id)`` highlight a node, expanding branches to reveal it

    Parameters
    ----------
    bnk : Soundbank
        Soundbank used to resolve node IDs and type names.
    root : HIRCNode
        Root node whose subtree is displayed.
    on_node_selected : callable, optional
        Called as ``on_node_selected(tag, node_id, user_data)`` on left click.
    node_color : callable, optional
        Called as ``node_color(node_id)``, returning an RGBA color tuple to
        use as that node's fill, or None to fall back to the default color.
    children_only : bool
        Pass ``children_only`` to ``bnk.get_subtree``.
    horizontal : bool
        Lay out generations left-to-right when True, top-to-bottom when False.
    max_children : int
        Nodes with more children than this only show one branch at a time.
    node_spacing : float
        Radial distance in plot units between successive rings (generations).
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
        bnk: Soundbank = None,
        root: int | HIRCNode = None,
        on_node_selected: Callable[[str, int | HIRCNode, Any], None] = None,
        *,
        children_only: bool = True,
        horizontal: bool = False,
        max_children: int = 4,
        node_spacing: float = 60.0,
        node_color: Callable[[int], tuple[int, int, int, int]] = None,
        width: int = 400,
        height: int = 400,
        tag: str = None,
        user_data: Any = None,
    ) -> None:
        super().__init__(tag)

        self._bnk = bnk
        self._root = root
        self._on_node_selected = on_node_selected
        self._node_color = node_color
        self._children_only = children_only
        self._horizontal = horizontal
        self._max_children = max_children
        self._node_spacing = node_spacing
        self._user_data = user_data

        # Mutable render state
        self._g: nx.DiGraph = None  # full fetched subtree
        self._visible_g: nx.DiGraph = None  # subtree with branches collapsed
        self._layout: dict[int, GraphNode] = {}
        self._branch_selection: dict[int, int] = {}  # parent id -> chosen child id
        self._hidden_branches: dict[
            int, list[int]
        ] = {}  # parent id -> collapsed siblings
        self._current_highlight: int = -1  # hovered node this frame
        self._selected_node: int = -1  # persistently selected node
        self._force_redraw: bool = (
            False  # redraw next frame even without mouse activity
        )
        self._handler_reg: str = None

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
        if dpg.does_item_exist(self._t("branch_popup")):
            dpg.delete_item(self._t("branch_popup"))

    # === Build =========================================================

    def _t(self, suffix: str) -> str:
        """build a unique, namespaced dpg tag for this widget."""
        return f"{self._tag}_{suffix}"

    def _build(self, width: int, height: int) -> None:
        with dpg.plot(
            no_mouse_pos=True,
            no_menus=True,
            no_frame=True,
            no_title=True,
            width=width,
            height=height,
            tag=self._tag,
        ):
            dpg.add_plot_axis(
                dpg.mvXAxis,
                tag=self._t("xaxis"),
                no_highlight=True,
                no_label=True,
                no_tick_labels=True,
                no_tick_marks=True,
                no_gridlines=True,
                no_menus=True,
            )
            dpg.add_plot_axis(
                dpg.mvYAxis,
                tag=self._t("yaxis"),
                no_highlight=True,
                no_label=True,
                no_tick_labels=True,
                no_tick_marks=True,
                no_gridlines=True,
                no_menus=True,
            )

        dpg.bind_item_theme(self._tag, style.themes.player_plot)

        with dpg.handler_registry() as reg:
            dpg.add_mouse_click_handler(
                button=dpg.mvMouseButton_Left, callback=self._on_mouse_click
            )
            dpg.add_mouse_click_handler(
                button=dpg.mvMouseButton_Right, callback=self._on_mouse_right_click
            )
        self._handler_reg = reg

    # === Helpers =======================================================

    def _describe(self, nid: int) -> str:
        """human-readable label for a node: its type and id."""
        node = self._bnk.get(nid)
        type_name = node.type_name if node else µ("(not found)")
        return f"{type_name} ({nid})"

    def _short_label(self, nid: int) -> str:
        """bracketed 1-4 letter abbreviation drawn inside a node marker."""
        node = self._bnk.get(nid)
        return f"[{node.type_name_short}]" if node else "[?]"

    def _build_visible_subgraph(self) -> nx.DiGraph:
        """collapse branches with too many children down to the selected one."""
        visible = nx.DiGraph()
        self._hidden_branches.clear()

        roots = [n for n in self._g if self._g.in_degree(n) == 0]
        visible.add_nodes_from(roots)
        stack = list(roots)

        while stack:
            node = stack.pop()
            children = list(self._g.successors(node))

            if len(children) > self._max_children:
                chosen = self._branch_selection.get(node, children[0])
                self._hidden_branches[node] = [c for c in children if c != chosen]
                children = [chosen]

            for child in children:
                visible.add_edge(node, child)
                stack.append(child)

        return visible

    def _leaf_counts(self, g: nx.DiGraph) -> dict[int, int]:
        """number of leaf descendants under each node, used to size wedges."""
        counts: dict[int, int] = {}
        for nid in reversed(list(nx.topological_sort(g))):
            children = list(g.successors(nid))
            counts[nid] = sum(counts[c] for c in children) if children else 1
        return counts

    def _polar_to_pos(self, radius: float, theta: float) -> tuple[float, float]:
        """convert (radius, angle) to plot coords. theta=0 is straight ahead."""
        if self._horizontal:
            return radius * math.cos(theta), radius * math.sin(theta)
        return radius * math.sin(theta), -radius * math.cos(theta)

    def _place(
        self,
        g: nx.DiGraph,
        nid: int,
        depth: int,
        lo: float,
        hi: float,
        leaves: dict[int, int],
        layout: dict[int, GraphNode],
    ) -> None:
        """give nid a ring position, then split its wedge among its children."""
        theta = (lo + hi) / 2
        layout[nid] = GraphNode(
            label=self._describe(nid),
            short_label=self._short_label(nid),
            pos=self._polar_to_pos(depth * self._node_spacing, theta),
            hidden=self._hidden_branches.get(nid, []),
        )

        children = list(g.successors(nid))
        total = leaves[nid] or 1
        cur = lo
        for child in children:
            share = (hi - lo) * leaves[child] / total
            self._place(g, child, depth + 1, cur, cur + share, leaves, layout)
            cur += share

    def _make_layout(self, g: nx.DiGraph) -> dict[int, GraphNode]:
        """place nodes on a half-ring: depth -> radius, subtree size -> angle.

        Roots sit at the center; each generation forms a wider ring around
        it, opening downward (vertical) or rightward (horizontal). Siblings
        share their parent's wedge proportional to subtree size, so a chain
        of single-child nodes forms a straight ray.
        """
        layout: dict[int, GraphNode] = {}
        if g.number_of_nodes() == 0:
            return layout

        leaves = self._leaf_counts(g)
        roots = [n for n in g if g.in_degree(n) == 0]
        total = sum(leaves[r] for r in roots) or 1

        half_sweep = math.pi / 4  # 45 degrees either side of center
        lo = -half_sweep

        for root in roots:
            share = 2 * half_sweep * leaves[root] / total
            self._place(g, root, 0, lo, lo + share, leaves, layout)
            lo += share

        return layout

    # === DPG callbacks =================================================

    def _on_mouse_click(self) -> None:
        if not dpg.does_item_exist(self._tag):
            # Widget destroyed; remove the stale handler registry
            dpg.delete_item(self._handler_reg)
            return

        if not dpg.is_item_hovered(self._tag) or self._current_highlight <= 0:
            return

        self.select_node(self._current_highlight)

        if self._on_node_selected:
            self._on_node_selected(self._tag, self._current_highlight, self._user_data)

    def _on_mouse_right_click(self) -> None:
        if not dpg.does_item_exist(self._tag):
            return

        if not dpg.is_item_hovered(self._tag) or self._current_highlight <= 0:
            return

        if self._hidden_branches.get(self._current_highlight):
            self._open_branch_popup(self._current_highlight)

    def _open_branch_popup(self, node_id: int) -> None:
        """let the user pick which child branch to reveal under node_id."""
        popup = self._t("branch_popup")
        if dpg.does_item_exist(popup):
            dpg.delete_item(popup)

        mouse_x, mouse_y = dpg.get_mouse_pos(local=False)
        current = self.get_selected_branch(node_id)

        with dpg.window(
            tag=popup,
            popup=True,
            no_title_bar=True,
            autosize=True,
            pos=(mouse_x, mouse_y),
        ):
            for child in self._g.successors(node_id):
                dpg.add_selectable(
                    label=self._describe(child),
                    default_value=child == current,
                    callback=self._on_branch_picked,
                    user_data=(node_id, child, popup),
                )

    def _on_branch_picked(self, sender: str, value: bool, user_data: tuple) -> None:
        parent_id, child_id, popup = user_data
        dpg.delete_item(popup)
        self.select_branch(parent_id, child_id)

    def _render_graph(
        self, sender: str, series_data: list, node_indices: dict[int, int]
    ) -> None:
        # Save some cpu cycles when no updates are needed
        if not (dpg.is_item_visible(self._tag) or self._force_redraw):
            return

        self._force_redraw = False
        self._current_highlight = 0

        helper_data = series_data[0]
        transformed_x = series_data[1]
        transformed_y = series_data[2]
        mouse_x = helper_data["MouseX_PixelSpace"]
        mouse_y = helper_data["MouseY_PixelSpace"]

        dpg.delete_item(sender, children_only=True, slot=2)
        dpg.push_container_stack(sender)
        dpg.configure_item(sender, tooltip=False)

        # Draw edges
        for src, dst in self._visible_g.edges:
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
                thickness=2,
                tag=self._t(f"edge_{src}_{dst}"),
            )

        # Draw nodes
        node_r = 21
        font_size = 18
        for nid in self._visible_g:
            idx = node_indices[nid]
            px = transformed_x[idx]
            py = transformed_y[idx]
            gnode = self._layout[nid]
            color = self._node_color(nid) if self._node_color else None

            if gnode.hidden:
                # grouped node: badge with hidden-branch count, no type label
                text = f"+{len(gnode.hidden)}"
                fill = color or style.purple
            else:
                text = gnode.short_label
                fill = color or style.pink

            dpg.draw_circle((px, py), node_r, fill=fill)

            tw, th = estimate_drawn_text_size(len(text), font_size=font_size)
            dpg.draw_text(
                # TODO Seems like our font size estimates are completely off right now :)
                (px - tw / 4, py - th / 3),
                text,
                size=font_size,
                color=style.white,
            )

            hovered = self._current_highlight <= 0 and (
                px - node_r - 2 <= mouse_x <= px + node_r + 2
                and py - node_r - 2 <= mouse_y <= py + node_r + 2
            )
            if hovered:
                self._current_highlight = nid
                dpg.configure_item(sender, tooltip=True)
                tooltip = gnode.label
                if gnode.hidden:
                    tooltip += f"  (+{len(gnode.hidden)} more)"
                dpg.set_value(self._t("tooltip"), tooltip)

            # ring for hover and/or a persistent selection
            if hovered or nid == self._selected_node:
                dpg.draw_circle((px, py), node_r + 4, color=style.white)

        dpg.pop_container_stack()

    # === Public ========================================================

    def regenerate(
        self,
        bnk: Soundbank = None,
        root: int | HIRCNode = None,
        selection: int | HIRCNode = -1,
    ) -> None:
        """Re-fetch the subtree from the soundbank and redraw.

        Clears any manual branch selections, since they reference node
        ids from the previous subtree.
        """
        if isinstance(selection, HIRCNode):
            selection = selection.id
        elif selection is None:
            selection = -1

        if (
            bnk in (None, self._bnk)
            and root in (None, self._root)
            and selection in (-1, self._selected_node)
        ):
            # Everything is the same
            return

        if bnk:
            self._bnk = bnk

        if root:
            self._root = root

        if not self._bnk or not self._root:
            # Bank or root missing, can't work yet
            return

        self._g = self._bnk.get_subtree(self._root, self._children_only, True)
        self._branch_selection.clear()
        self._selected_node = selection
        self._rebuild()

        if selection > 0:
            self.select_branch_from_node(selection)

    def select_branch(self, parent_id: int, child_id: int) -> None:
        """Reveal a specific child branch under parent_id and redraw."""
        self._branch_selection[parent_id] = child_id
        self._rebuild()

    def reset_branch(self, parent_id: int) -> None:
        """Clear a manual branch choice, reverting to the default (first) child."""
        self._branch_selection.pop(parent_id, None)
        self._rebuild()

    def reset_branches(self) -> None:
        """Clear all manual branch choices."""
        self._branch_selection.clear()
        self._rebuild()

    def get_branches(self, parent_id: int) -> list[int]:
        """Return all child node ids available under parent_id."""
        if self._g is None:
            return []
        return list(self._g.successors(parent_id))

    def get_selected_branch(self, parent_id: int) -> int:
        """Return the currently visible child id for a given parent."""
        children = self.get_branches(parent_id)
        return self._branch_selection.get(parent_id, children[0] if children else -1)

    def select_branch_from_node(self, node_id: int) -> None:
        """Select node_id, expanding any collapsed branches along the way.

        Walks node_id's ancestors in the full subtree and, for each one
        that's currently collapsed, picks the branch leading to node_id -
        so it becomes visible even if it started out hidden in a group.
        """
        if self._g is not None and node_id in self._g:
            parents, children = self._ancestor_chain(node_id)
            for parent, child in zip(parents, children):
                self._branch_selection[parent] = child
            self._rebuild()

        self._selected_node = node_id
        self._force_redraw = True

    def select_node(self, node_id: int) -> None:
        """Select node_id without rebuilding the graph."""
        self._selected_node = node_id
        self._force_redraw = True

    def _ancestor_chain(self, node_id: int) -> tuple[list[int], list[int]]:
        """parents and children, in order, from node_id's root down to it."""
        chain = [node_id]
        current = node_id
        while True:
            preds = list(self._g.predecessors(current))
            if not preds:
                break
            current = preds[0]
            chain.append(current)

        chain.reverse()
        return chain[:-1], chain[1:]

    def _rebuild(self) -> None:
        """Recompute the visible subgraph and layout, then redraw the plot."""
        if self._g is None:
            return

        dpg.delete_item(self._t("yaxis"), children_only=True, slot=1)

        self._visible_g = self._build_visible_subgraph()
        self._layout = self._make_layout(self._visible_g)

        if not self._layout:
            return

        node_ids = list(self._layout.keys())
        x = [self._layout[n].pos[0] for n in node_ids]
        y = [self._layout[n].pos[1] for n in node_ids]
        node_indices = {nid: idx for idx, nid in enumerate(node_ids)}

        with dpg.custom_series(
            x,
            y,
            2,
            callback=self._render_graph,
            tooltip=False,
            user_data=node_indices,
            parent=self._t("yaxis"),
        ):
            dpg.add_text("", tag=self._t("tooltip"))

        dpg.split_frame()
        dpg.fit_axis_data(self._t("xaxis"))
        dpg.fit_axis_data(self._t("yaxis"))
