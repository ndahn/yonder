from typing import Generator, Callable
from difflib import SequenceMatcher
import pyperclip
from collections import deque
from dearpygui import dearpygui as dpg

from yonder import HIRCNode
from yonder.util import logger
from yonder.gui import style
from yonder.gui.helpers import dpg_section
from yonder.gui.localization import µ
from yonder.gui.widgets import DpgItem


class compare_nodes_dialog(DpgItem):
    def __init__(
        self,
        node_a: HIRCNode = None,
        node_b: HIRCNode = None,
        pin_callback: Callable[[HIRCNode], None] = None,
        jump_callback: Callable[[HIRCNode], None] = None,
        *,
        title: str = "Compare Nodes",
        tag: str = 0,
    ):
        super().__init__(tag)

        self._node_a = node_a
        self._node_b = node_b
        self._pin_callback = pin_callback
        self._jump_callback = jump_callback
        self._sync_frame = 0

        self._build(title)
        self.update()

    def _build(self, title: str) -> None:
        with dpg.window(label=title, width=700, height=500, tag=self.tag):
            with dpg.group(horizontal=True):
                dpg.add_button(label=µ("Swap"), callback=self.swap)
                dpg.add_button(label=µ("Update"), callback=self.update)
                dpg.add_checkbox(
                    label=µ("Line numbers"),
                    default_value=True,
                    callback=self.update,
                    tag=self._t("line_numbers"),
                )
                dpg.add_checkbox(
                    label=µ("Differences only"),
                    default_value=False,
                    callback=self.update,
                    tag=self._t("differences_only"),
                )
                dpg.add_input_int(
                    label=µ("Context"),
                    default_value=1,
                    min_value=0,
                    min_clamped=True,
                    width=100,
                    callback=self.update,
                    tag=self._t("diff_context"),
                )

            with dpg.group(horizontal=True):
                with dpg.child_window(
                    autosize_y=True,
                    resizable_x=True,
                    width=330,
                    no_scrollbar=True,
                    tag=self._t("left"),
                ):
                    dpg_section(
                        "", style.muted_blue, spacer=0, tag=self._t("node_a_title")
                    )
                    dpg.add_group(tag=self._t("node_a_lines"))

                with dpg.child_window(
                    autosize_x=True,
                    autosize_y=True,
                    tag=self._t("right"),
                ):
                    dpg_section(
                        "", style.muted_rose, spacer=0, tag=self._t("node_b_title")
                    )
                    dpg.add_group(tag=self._t("node_b_lines"))

                self._make_context_menu(self._t("node_a_lines"), True)
                self._make_context_menu(self._t("node_b_lines"), False)

                with dpg.item_handler_registry():
                    dpg.add_item_scroll_handler(callback=self._sync_scroll_l2r)
                dpg.bind_item_handler_registry(self._t("left"), dpg.last_container())

                with dpg.item_handler_registry():
                    dpg.add_item_scroll_handler(callback=self._sync_scroll_r2l)
                dpg.bind_item_handler_registry(self._t("right"), dpg.last_container())

    def _make_context_menu(self, parent: str, is_left: bool) -> None:
        def select() -> HIRCNode:
            if is_left and self._node_a:
                return self._node_a
            elif not is_left and self._node_b:
                return self._node_b
            return None

        def pin() -> None:
            node = select()
            if node:
                self._pin_callback(node)

        def jump_to() -> None:
            node = select()
            if node:
                self._jump_callback(node)

        def copy() -> None:
            node = select()
            if node:
                pyperclip.copy(node.json())
                logger.info(µ("Copied node {node} to clipboard").format(node))

        with dpg.popup(parent, min_size=(100, 20)):
            if self._pin_callback:
                dpg.add_menu_item(
                    label=µ("Pin"),
                    callback=pin,
                )

            if self._jump_callback:
                dpg.add_menu_item(
                    label=µ("Jump to"),
                    callback=jump_to,
                )

            dpg.add_menu_item(
                label=µ("Copy"),
                callback=copy,
            )

    def _sync_scroll_l2r(self) -> None:
        if not self._node_a or not self._node_b:
            return

        # Prevent sync callback bouncing
        frame = dpg.get_frame_count()
        if frame == self._sync_frame:
            return

        self._sync_frame = frame
        pos = dpg.get_y_scroll(self._t("left"))
        dpg.set_y_scroll(self._t("right"), pos, when=dpg.mvSetScrollFlags_Both)

    def _sync_scroll_r2l(self) -> None:
        if not self._node_a or not self._node_b:
            return

        # Prevent sync callback bouncing
        frame = dpg.get_frame_count()
        if frame == self._sync_frame:
            return

        self._sync_frame = frame
        pos = dpg.get_y_scroll(self._t("right"))
        dpg.set_y_scroll(self._t("left"), pos, when=dpg.mvSetScrollFlags_Both)

    def _iter_lines(
        self, left: list[str], right: list[str]
    ) -> Generator[tuple[str, str, str]]:
        """Yield (left_line, right_line, change_type) for each diff position.

        change_type is one of: 'equal', 'replace', 'insert', 'delete'
        Inserted lines have left=None; deleted lines have right=None.
        """
        matcher = SequenceMatcher(None, left, right, autojunk=False)

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            left_chunk = left[i1:i2]
            right_chunk = right[j1:j2]

            if tag == "equal":
                for l, r in zip(left_chunk, right_chunk):
                    yield l, r, "equal"

            elif tag == "replace":
                # pair up as many lines as possible, then drain the longer side
                for l, r in zip(left_chunk, right_chunk):
                    yield l, r, "replace"
                for l in left_chunk[len(right_chunk) :]:
                    yield l, None, "delete"
                for r in right_chunk[len(left_chunk) :]:
                    yield None, r, "insert"

            elif tag == "delete":
                for l in left_chunk:
                    yield l, None, "delete"

            elif tag == "insert":
                for r in right_chunk:
                    yield None, r, "insert"

    def _get_change_color(self, change_type: str) -> style.RGBA:
        return {
            "equal": style.white,
            "replace": style.light_blue,
            "insert": style.light_green,
            "delete": style.light_red,
        }[change_type]

    def update(self) -> None:
        lines_a = self._t("node_a_lines")
        dpg.delete_item(lines_a, children_only=True)
        if self._node_a:
            dpg.set_value(self._t("node_a_title"), str(self._node_a))

        lines_b = self._t("node_b_lines")
        dpg.delete_item(lines_b, children_only=True)
        if self._node_b:
            dpg.set_value(self._t("node_b_title"), str(self._node_b))

        line_numbers = dpg.get_value(self._t("line_numbers"))
        differences_only = dpg.get_value(self._t("differences_only"))
        diff_context = dpg.get_value(self._t("diff_context"))
        idx_a = 0
        idx_b = 0

        def put_line(idx: int, line: str, color: style.RGBA, parent: str) -> int:
            with dpg.group(horizontal=True, parent=parent):
                if line_numbers and line:
                    dpg.add_text(f"{idx:3}", color=style.light_grey)
                    idx += 1

                dpg.add_text(line or "", color=color)
            
            return idx

        if not self._node_a or not self._node_b:
            if self._node_a:
                for line in self._node_a.json().splitlines():
                    idx_a = put_line(idx_a, line, style.white, lines_a)
            elif self._node_b:
                for line in self._node_b.json().splitlines():
                    idx_b = put_line(idx_b, line, style.white, lines_b)
            return

        json_a = self._node_a.json().splitlines()
        json_b = self._node_b.json().splitlines()
        prev = deque(maxlen=diff_context)

        for line_a, line_b, change_type in self._iter_lines(json_a, json_b):
            if differences_only:
                if change_type == "equal":
                    prev.append(line_a)
                    continue

                color = self._get_change_color("equal")
                for i, line in enumerate(prev):
                    put_line(idx_a - len(prev) + i, line, color, lines_a)
                    put_line(idx_b - len(prev) + i, line, color, lines_b)

                prev.clear()

            color = self._get_change_color(change_type)
            idx_a = put_line(idx_a, line_a, color, lines_a)
            idx_b = put_line(idx_b, line_b, color, lines_b)
            
    def swap(self) -> None:
        self._node_a, self._node_b = self._node_b, self._node_a
        self.update()

    @property
    def node_a(self) -> HIRCNode:
        return self._node_a

    @node_a.setter
    def node_a(self, val: HIRCNode) -> None:
        self._node_a = val
        self.update()

    @property
    def node_b(self) -> HIRCNode:
        return self._node_b

    @node_b.setter
    def node_b(self, val: HIRCNode) -> None:
        self._node_b = val
        self.update()
