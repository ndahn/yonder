from typing import Any, Callable
from dearpygui import dearpygui as dpg

from yonder import lookup_name, calc_hash
from yonder.types.base_types import DecisionTreeNode
from yonder.gui import style
from yonder.gui.helpers import estimate_drawn_text_size
from yonder.gui.localization import µ
from .dpg_item import DpgItem


_arg_column_size = 160
_header_height = 20
_row_height = 28
_node_radius = 5
_plus_radius = 8
_padding = 10
_font_size = 18


# TODO panning not working, popups not closing


class add_decision_tree(DpgItem):
    def __init__(
        self,
        root: DecisionTreeNode,
        arguments: list[int],
        on_tree_changed: Callable[[], None] = None,
        *,
        on_leaf_selected: Callable[[DecisionTreeNode, Any], None] = None,
        width: int = 640,
        height: int = 360,
        tag: str = 0,
        parent: str = 0,
        user_data: Any = None,
    ):
        super().__init__(tag)

        self._tree = root
        self._arguments = arguments
        self._on_tree_changed = on_tree_changed
        self._on_leaf_selected = on_leaf_selected
        self._user_data = user_data

        self._width = width
        self._height = height
        self._offset = [_padding, _padding]
        self._drag_origin = None
        self._positions: dict[int, float] = {}
        self._leaf_order: list[DecisionTreeNode] = []

        # hover / hit-test state, since draw items get no native hover or
        # click handling - everything below is resolved manually
        self._node_regions: list[
            tuple[int, DecisionTreeNode, int, tuple[float, float]]
        ] = []
        self._hover_header = -1
        self._hover_node_id = 0
        self._hover_node = None

        self._build(parent)

    def __del__(self):
        self._close_popup()
        self._delete_item(self._t("handler_registry"))
        self._delete_item(self._t("input_registry"))
        super().__del__()

    def _build(self, parent: str | int) -> None:
        with dpg.child_window(
            tag=self.tag,
            parent=parent,
            width=self._width,
            height=self._height,
            no_scrollbar=True,
        ):
            with dpg.drawlist(self._width, self._height, tag=self._t("drawlist")):
                dpg.draw_rectangle(
                    (0, 0),
                    (self._width, self._height),
                    fill=style.light_grey,
                    tag=self._t("bg"),
                )
                # draw_node (not draw_layer) so apply_transform works, for panning
                with dpg.draw_node(tag=self._t("content")):
                    pass
                with dpg.draw_node(tag=self._t("overlay")):
                    pass

        self._redraw()

        with dpg.item_handler_registry(tag=self._t("handler_registry")):
            dpg.add_item_resize_handler(callback=self._on_resize)

        with dpg.handler_registry(tag=self._t("input_registry")):
            dpg.add_mouse_move_handler(callback=self._on_mouse_move)
            dpg.add_mouse_drag_handler(
                button=dpg.mvMouseButton_Left, callback=self._on_drag
            )
            dpg.add_mouse_release_handler(callback=self._on_release)
            dpg.add_mouse_click_handler(
                button=dpg.mvMouseButton_Left, callback=self._on_left_click
            )
            dpg.add_mouse_click_handler(
                button=dpg.mvMouseButton_Right, callback=self._on_right_click
            )

    def _apply_pan(self) -> None:
        matrix = dpg.create_translation_matrix((self._offset[0], self._offset[1], 0))
        dpg.apply_transform(self._t("content"), matrix)
        dpg.apply_transform(self._t("overlay"), matrix)

    def _content_size(self) -> tuple[float, float]:
        w = len(self._arguments) * _arg_column_size
        h = len(self._leaf_order) * _row_height + _header_height
        return w, h

    def _clamp_offset(self) -> None:
        content_w, content_h = self._content_size()

        min_x = min(_padding, self._width - content_w - _padding)
        min_y = min(_padding, self._height - content_h - _padding)

        self._offset[0] = min(_padding, max(min_x, self._offset[0]))
        self._offset[1] = min(_padding, max(min_y, self._offset[1]))

    # ------------------------------------------------------------ drawing

    def _redraw(self) -> None:
        dpg.delete_item(self._t("content"), children_only=True)
        self._node_regions.clear()
        self._leaf_order.clear()
        self._hover_header = -1
        self._hover_node_id = 0
        self._hover_node = None

        if self._arguments:
            self._layout()

            dpg.push_container_stack(self._t("content"))
            try:
                self._draw_columns()
                self._draw_headers()
                for child in sorted(self._tree.children, key=lambda c: c.name):
                    self._draw_node(child, 0, None)
            finally:
                dpg.pop_container_stack()

        self._clamp_offset()
        self._apply_pan()
        self._redraw_overlay()

    def _redraw_overlay(self) -> None:
        dpg.delete_item(self._t("overlay"), children_only=True)

        dpg.push_container_stack(self._t("overlay"))
        try:
            if self._hover_header >= 0:
                self._draw_header_hover(self._hover_header)
            if self._hover_node is not None:
                _, node, level, pos = self._hover_node
                dpg.draw_circle(pos, _node_radius + 3, color=style.white)
        finally:
            dpg.pop_container_stack()

    def _layout(self) -> None:
        # assign every node a vertical slot
        # leafs get sequential rows
        # branch nodes are centered over their (sorted) children
        self._positions.clear()
        self._leaf_order.clear()
        last_level = len(self._arguments) - 1

        def visit(node: DecisionTreeNode, level: int) -> float:
            if level == last_level:
                y = len(self._leaf_order) * _row_height
                self._leaf_order.append(node)
            else:
                children = sorted(node.children, key=lambda c: c.name)
                ys = [visit(c, level + 1) for c in children]
                y = sum(ys) / len(ys) if ys else len(self._leaf_order) * _row_height
            self._positions[id(node)] = y
            return y

        for child in sorted(self._tree.children, key=lambda c: c.name):
            visit(child, 0)

    def _draw_columns(self) -> None:
        _, content_h = self._content_size()
        content_h = max(content_h, self._height)

        for i in range(len(self._arguments)):
            x = i * _arg_column_size
            fill = style.light_grey if i % 2 == 0 else style.light_grey.mix(style.white)
            dpg.draw_rectangle((x, 0), (x + _arg_column_size, content_h), fill=fill)

    def _draw_headers(self) -> None:
        header_color = style.light_grey.mix(style.white)

        for i, arg in enumerate(self._arguments):
            x = i * _arg_column_size
            label = lookup_name(arg, f"#{arg}")
            tw, th = estimate_drawn_text_size(len(label), font_size=_font_size)

            dpg.draw_rectangle(
                (x, 0), (x + _arg_column_size, _header_height), fill=header_color
            )
            dpg.draw_text(
                (x + (_arg_column_size - tw) / 2, (_header_height - th) / 2),
                label,
                size=_font_size,
            )

    def _draw_header_hover(self, col: int) -> None:
        x = col * _arg_column_size
        dpg.draw_rectangle(
            (x, 0), (x + _arg_column_size, _header_height), color=style.white
        )
        self._draw_plus(x)
        self._draw_plus(x + _arg_column_size)

    def _draw_plus(self, x: float) -> None:
        cy = _header_height / 2
        dpg.draw_circle((x, cy), _plus_radius, fill=style.white)
        tw, th = estimate_drawn_text_size(1, font_size=_font_size)
        dpg.draw_text((x - tw / 2, cy - th / 2), "+", size=_font_size)

    def _draw_node(
        self, node: DecisionTreeNode, level: int, parent_pos: tuple[float, float] = None
    ) -> None:
        is_leaf = level == len(self._arguments) - 1
        x = level * _arg_column_size
        y = _header_height + _padding + self._positions[id(node)]
        node_x = x + _padding if is_leaf else x + _arg_column_size / 2
        pos = (node_x, y)

        if parent_pos is not None:
            self._draw_connector(parent_pos, pos, x)

        label = "*" if node.key == 0 else node.name
        if is_leaf:
            color = style.white if node.node_id else style.light_grey
        else:
            color = style.light_grey if node.key == 0 else style.white

        dpg.draw_circle(pos, _node_radius, fill=color)
        self._node_regions.append((id(node), node, level, pos))

        if is_leaf:
            dpg.draw_text((node_x + _node_radius + 4, y - 8), label, size=_font_size)
        else:
            tw, _ = estimate_drawn_text_size(len(label), font_size=_font_size)
            dpg.draw_text(
                (node_x - tw / 2, y - _node_radius - 22), label, size=_font_size
            )

            for child in sorted(node.children, key=lambda c: c.name):
                self._draw_node(child, level + 1, pos)

    def _draw_connector(
        self, p1: tuple[float, float], p2: tuple[float, float], child_col_x: float
    ) -> None:
        # elbow connector; siblings share the same mid_x so their lines merge.
        # inset from the column boundary so it isn't sitting right on the seam
        # between two columns' background fills
        mid_x = child_col_x + _padding
        dpg.draw_line(p1, (mid_x, p1[1]), color=style.white)
        dpg.draw_line((mid_x, p1[1]), (mid_x, p2[1]), color=style.white)
        dpg.draw_line((mid_x, p2[1]), p2, color=style.white)

    # ---------------------------------------------------------- hit-testing

    def _hit_test_node(self, x: float, y: float):
        for entry in self._node_regions:
            _, node, level, pos = entry
            if (pos[0] - x) ** 2 + (pos[1] - y) ** 2 <= (_node_radius + 3) ** 2:
                return entry
        return None

    def _hit_test_plus(self, x: float, y: float) -> tuple[int, str]:
        col = self._hover_header
        cy = _header_height / 2
        left_x = col * _arg_column_size
        right_x = (col + 1) * _arg_column_size

        if (left_x - x) ** 2 + (cy - y) ** 2 <= _plus_radius**2:
            return col, "left"
        if (right_x - x) ** 2 + (cy - y) ** 2 <= _plus_radius**2:
            return col, "right"
        return None

    def _local_mouse_pos(self) -> tuple[float, float]:
        x, y = dpg.get_drawing_mouse_pos()
        return x - self._offset[0], y - self._offset[1]

    # ---------------------------------------------------------- interaction

    def _on_resize(self, sender: str, size: tuple[int, int], user_data: Any) -> None:
        self._width, self._height = size
        dpg.configure_item(self._t("drawlist"), width=size[0], height=size[1])
        dpg.configure_item(self._t("bg"), pmax=size)
        self._clamp_offset()
        self._apply_pan()

    def _on_mouse_move(self, sender: str, app_data: Any, user_data: Any) -> None:
        if not dpg.is_item_hovered(self.tag):
            self._set_hover(-1, None)
            return

        x, y = self._local_mouse_pos()
        col = int(x // _arg_column_size)
        header = (
            col
            if (0 <= y <= _header_height and 0 <= col < len(self._arguments))
            else -1
        )
        node = self._hit_test_node(x, y) if header == -1 else None

        self._set_hover(header, node)

    def _set_hover(self, header: int, region) -> None:
        node_id = region[0] if region else 0
        if header == self._hover_header and node_id == self._hover_node_id:
            return

        self._hover_header = header
        self._hover_node_id = node_id
        self._hover_node = region
        self._redraw_overlay()

    def _on_drag(
        self, sender: str, app_data: tuple[int, float, float], user_data: Any
    ) -> None:
        # TODO: only pan when the drag starts on empty background, not on a node
        if not dpg.is_item_hovered(self.tag):
            return

        if self._drag_origin is None:
            self._drag_origin = tuple(self._offset)

        _, dx, dy = app_data
        self._offset[0] = self._drag_origin[0] + dx
        self._offset[1] = self._drag_origin[1] + dy
        self._clamp_offset()
        self._apply_pan()

    def _on_release(self, sender: str, app_data: Any, user_data: Any) -> None:
        self._drag_origin = None

    def _on_left_click(self, sender: str, app_data: Any, user_data: Any) -> None:
        if not dpg.is_item_hovered(self.tag):
            return

        # a click on the canvas always dismisses any open popup first
        self._close_popup()

        x, y = self._local_mouse_pos()

        if self._hover_header >= 0:
            plus = self._hit_test_plus(x, y)
            if plus is not None:
                self._on_add_column(sender, None, plus)
            return

        if self._hover_node is not None and self._on_leaf_selected:
            _, node, level, _ = self._hover_node
            if level == len(self._arguments) - 1:
                self._on_leaf_click(sender, None, node)

    def _on_right_click(self, sender: str, app_data: Any, user_data: Any) -> None:
        if not dpg.is_item_hovered(self.tag):
            return

        if self._hover_header >= 0:
            self._open_header_popup(self._hover_header)
        elif self._hover_node is not None:
            _, node, level, _ = self._hover_node
            self._open_node_popup(node, level)

    def _on_leaf_click(
        self, sender: str, app_data: Any, node: DecisionTreeNode
    ) -> None:
        self._on_leaf_selected(node, self._user_data)

    # -------------------------------------------------------- popup window

    def _open_popup(self, build: Callable[[], None]) -> None:
        # single reusable window under a fixed tag: opening one always closes
        # any previous one first, so there can never be more than one
        self._close_popup()

        with dpg.window(
            tag=self._t("popup"),
            pos=dpg.get_mouse_pos(local=False),
            no_title_bar=True,
            no_resize=True,
            no_collapse=True,
            autosize=True,
        ):
            build()

    def _close_popup(self) -> None:
        self._delete_item(self._t("popup"))

    def _open_header_popup(self, col: int) -> None:
        arg = self._arguments[col]

        def build() -> None:
            dpg.add_input_text(
                default_value=lookup_name(arg, f"#{arg}"),
                callback=self._on_header_renamed,
                user_data=col,
            )
            dpg.add_button(
                label=µ("Delete layer"), callback=self._on_delete_column, user_data=col
            )

        self._open_popup(build)

    def _on_header_renamed(self, sender: str, value: str, col: int) -> None:
        self._arguments[col] = calc_hash(value)
        self._close_popup()
        self._notify_changed()

    def _on_delete_column(self, sender: str, app_data: Any, col: int) -> None:
        self._close_popup()
        self._remove_column(col)
        self._notify_changed()

    def _on_add_column(
        self, sender: str, app_data: Any, user_data: tuple[int, str]
    ) -> None:
        col, side = user_data
        pos = col if side == "left" else col + 1
        name = f"{µ('New Argument')} {len(self._arguments)}"  # TODO: nicer naming/uniqueness
        self._insert_column(pos, calc_hash(name))
        self._notify_changed()

    def _insert_column(self, pos: int, arg_hash: int) -> None:
        # insert a new decision level at `pos`: every existing node at that
        # depth gets a single wildcard child that inherits its old children
        def delve(node: DecisionTreeNode, level: int) -> None:
            if level == pos:
                node.children = [DecisionTreeNode(0, children=node.children)]
            elif level < pos:
                for child in node.children:
                    delve(child, level + 1)

        delve(self._tree, 0)
        self._arguments.insert(pos, arg_hash)

    def _remove_column(self, pos: int) -> None:
        # splice the level out: each node at that depth is replaced by its
        # wildcard branch's children (non-wildcard branches are dropped)
        def delve(node: DecisionTreeNode, level: int) -> None:
            if level == pos:
                wildcard = next((c for c in node.children if c.key == 0), None)
                node.children = wildcard.children if wildcard else []
            elif level < pos:
                for child in node.children:
                    delve(child, level + 1)

        delve(self._tree, 0)
        self._arguments.pop(pos)

    def _open_node_popup(self, node: DecisionTreeNode, level: int) -> None:
        from yonder.gui.widgets.hash_widget import (
            add_hash_widget,
        )  # avoid circular import

        is_leaf = level == len(self._arguments) - 1
        arg_name = lookup_name(self._arguments[level], f"#{level}")
        val_name = "*" if node.key == 0 else lookup_name(node.key, "<?>")

        def build() -> None:
            dpg.add_text(arg_name)
            add_hash_widget(
                node.key,
                self._on_node_key_changed,
                horizontal=False,
                initial_string=val_name,
                string_label=µ("Value"),
                width=100,
                user_data=node,
            )

            if not is_leaf:
                dpg.add_button(
                    label=µ("Add child"), callback=self._on_add_child, user_data=node
                )

            dpg.add_button(
                label=µ("Delete"),
                callback=self._on_delete_node,
                user_data=(node, level),
            )

        self._open_popup(build)

    def _on_node_key_changed(
        self, sender: str, value: int, node: DecisionTreeNode
    ) -> None:
        # TODO: merge with an existing sibling instead of allowing a duplicate key
        node.key = value
        self._close_popup()
        self._notify_changed()

    def _on_add_child(self, sender: str, app_data: Any, node: DecisionTreeNode) -> None:
        if any(c.key == 0 for c in node.children):
            self._close_popup()
            return  # a wildcard child already exists on this layer

        node.children.append(DecisionTreeNode(0))
        self._close_popup()
        self._notify_changed()

    def _on_delete_node(
        self, sender: str, app_data: Any, info: tuple[DecisionTreeNode, int]
    ) -> None:
        from yonder.gui.dialogs.choice_dialog import simple_choice_dialog

        node, level = info
        self._close_popup()
        simple_choice_dialog(
            µ("Delete this node and all of its children?"),
            [µ("Yes"), µ("No")],
            self._on_delete_node_confirmed,
            title=µ("Delete node"),
            user_data=node,
        )

    def _on_delete_node_confirmed(
        self, sender: str, choice: int, node: DecisionTreeNode
    ) -> None:
        if choice != 0:
            return

        self._remove_node(self._tree, node)
        self._notify_changed()

    def _remove_node(self, parent: DecisionTreeNode, target: DecisionTreeNode) -> bool:
        for child in parent.children:
            if child is target:
                parent.children.remove(child)
                return True

            if self._remove_node(child, target):
                return True

        return False

    def _notify_changed(self) -> None:
        self._redraw()
        if self._on_tree_changed:
            self._on_tree_changed()
