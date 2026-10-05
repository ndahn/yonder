from __future__ import annotations
from typing import Any, Callable
from copy import deepcopy
from dataclasses import dataclass, field, replace
from dearpygui import dearpygui as dpg

from yonder import Soundbank
from yonder.hash import random_hash
from yonder.enums import RandomSequenceMode, RandomMode
from yonder.types.base_types import MusicRanSeqPlaylistItem
from yonder.gui.localization import µ
from .dpg_item import DpgItem
from .select_node import add_select_node


# TODO move to MRSC and use in e.g. playback playlist state
@dataclass
class PlaylistTreeItem:
    item: MusicRanSeqPlaylistItem
    parent: PlaylistTreeItem = None
    children: list[PlaylistTreeItem] = field(default_factory=list)

    @classmethod
    def new(
        cls, ers_base_type: RandomSequenceMode = RandomSequenceMode.ContinuousSequence
    ) -> PlaylistTreeItem:
        return PlaylistTreeItem(
            MusicRanSeqPlaylistItem(0, random_hash(), ers_type=ers_base_type.value)
        )

    @classmethod
    def from_playlist(cls, playlist: list[MusicRanSeqPlaylistItem]) -> PlaylistTreeItem:
        """flat list -> tree (recursive descent)"""
        it = iter(playlist)

        def take(parent: PlaylistTreeItem) -> PlaylistTreeItem:
            node = PlaylistTreeItem(replace(next(it)), parent)
            # Each node is immediately followed by its entire subtree. Once this returns the
            # iterator will have advanced to the next node belonging to us.
            node.children = [take(node) for _ in range(node.item.child_count)]
            return node

        return take(None)

    def to_wwise_playlist(self, n: PlaylistTreeItem) -> list[MusicRanSeqPlaylistItem]:
        """tree -> flat list (pre-order), child_count rebuilt from the tree"""

        def flatten(node: PlaylistTreeItem) -> list[MusicRanSeqPlaylistItem]:
            node.item.child_count = len(node.children)
            out = [node.item]
            for c in node.children:
                out += flatten(c)
            return out

        return flatten(self.item)

    def copy(self) -> PlaylistTreeItem:
        return deepcopy(self)

    def is_leaf(self) -> bool:
        return not self.children

    def __str__(self) -> str:
        def delve(n: PlaylistTreeItem, level: int) -> str:
            if n.is_leaf():
                s = " " * level * 2 + str(n.item.segment_id) + "\n"
            else:
                s = (
                    " " * level * 2
                    + f"{n.item.ers_type_enum.name} | {n.item.random_mode_enum.name}\n"
                )

                for child in n.children:
                    s += delve(child, level + 1)

            return s

        return delve(self, 0)


class add_music_playlist_editor(DpgItem):
    def __init__(
        self,
        playlist: PlaylistTreeItem,
        on_value_changed: Callable[[str, PlaylistTreeItem, Any], None],
        *,
        label: str = None,
        compact: bool = False,
        tag: str | int = 0,
        user_data: Any = None,
    ) -> None:
        super().__init__(tag)

        self.playlist = playlist.copy()
        self._on_value_changed = on_value_changed
        self._user_data = user_data
        self._ctx_row: str = None

        self._build(label, compact)

    def destroy(self):
        self._delete_item(self._t("context"))
        self._delete_item(self._t("mouse_handler_reg"))

    def _build(self, label: str, compact: bool) -> None:
        with dpg.table(
            label=label,
            header_row=False,
            policy=dpg.mvTable_SizingFixedFit,
            borders_outerH=not compact,
            borders_outerV=not compact,
            no_host_extendX=compact,
            no_pad_innerX=False,
            no_pad_outerX=compact,
            tag=self.tag,
        ):
            dpg.add_table_column(width_stretch=not compact, init_width_or_weight=100)
            dpg.add_table_column(
                label=µ("Mode"), width_stretch=not compact, init_width_or_weight=100
            )
            dpg.add_table_column(label=µ("Weight"), init_width_or_weight=30)
            dpg.add_table_column(label=µ("Loops"), init_width_or_weight=30)

        with dpg.window(
            popup=True,
            show=False,
            min_size=(80, 20),
            tag=self._t("context"),
        ):
            dpg.add_menu_item(label=µ("Add Child"), callback=self._add_child)
            dpg.add_menu_item(label=µ("Add Sibling"), callback=self._add_sibling)
            dpg.add_menu_item(label=µ("Delete"), callback=self._delete_node)

        with dpg.handler_registry(tag=self._t("mouse_handler_reg")):
            dpg.add_mouse_click_handler(
                dpg.mvMouseButton_Right, callback=self._on_right_click
            )

        self.regenerate()

    def regenerate(self) -> None:
        dpg.delete_item(self.tag, slot=1, children_only=True)

        todo = [(0, self.playlist)]
        while todo:
            level, node = todo.pop(0)
            self._make_row(node, level)
            todo = [(level + 1, child) for child in node.children] + todo

    def _make_row(self, node: PlaylistTreeItem, level: int) -> None:
        item = node.item

        def make_cb(key: str, transformer: Callable = None) -> Callable:
            def cb(sender: str, value: Any, user_data: Any) -> None:
                if transformer:
                    value = transformer(value)
                
                setattr(item, key, value)

                if self._on_value_changed:
                    self._on_value_changed(self.tag, self.playlist, self._user_data)

            return cb

        with dpg.table_row(parent=self.tag, user_data=node):
            # Top level node should always be a branch
            if node != self.playlist and node.is_leaf():
                # Leaf node with segment ID
                dpg.add_input_text(
                    default_value=str(item.segment_id),
                    decimal=True,
                    indent=level * 7,
                    width=-1,
                    callback=make_cb("segment_id"),
                    payload_type="playlist_item",
                    drop_callback=self._on_item_drop,
                    user_data=node,
                )
                with dpg.drag_payload(
                    parent=dpg.last_item(), drag_data=node, payload_type="playlist_item"
                ):
                    dpg.add_text(
                        f"{item.segment_id} | W={item.weight} | L={item.loop_min}"
                    )

                # Mode placeholder
                dpg.add_text()
            else:
                # Branch node with playback modes and more children
                dpg.add_combo(
                    [r.name for r in RandomSequenceMode],
                    default_value=item.ers_type_enum.name,
                    indent=level * 7,
                    width=-1,
                    callback=make_cb("ers_type", lambda v: RandomSequenceMode[v].value),
                    payload_type="playlist_item",
                    drop_callback=self._on_item_drop,
                    user_data=node,
                )
                with dpg.drag_payload(
                    parent=dpg.last_item(), drag_data=node, payload_type="playlist_item"
                ):
                    dpg.add_text(
                        f"{item.segment_id} | W={item.weight} | L={item.loop_min}"
                    )

                # Children randomization
                dpg.add_combo(
                    [m.name for m in RandomMode],
                    default_value=(
                        RandomMode.Shuffle if item.shuffle else RandomMode.Standard
                    ).name,
                    width=-1,
                    callback=make_cb(
                        "shuffle", lambda v: 1 if v == RandomMode.Shuffle else 0
                    ),
                )

            # Common properties
            dpg.add_drag_int(
                default_value=item.weight,
                min_value=1,
                max_value=1000,
                width=-1,
                callback=make_cb("weight"),
            )
            with dpg.tooltip(dpg.last_item()):
                dpg.add_text(µ("Weight"))

            dpg.add_drag_int(
                default_value=item.loop_min,
                min_value=0,
                max_value=100,
                width=-1,
                callback=make_cb("loop_min"),
            )
            with dpg.tooltip(dpg.last_item()):
                dpg.add_text(µ("Loops"))

    def _on_item_drop(
        self, drop_target: str, node: PlaylistTreeItem, user_data: Any
    ) -> None:
        if not node.parent:
            return

        target_item: PlaylistTreeItem = dpg.get_item_user_data(drop_target)
        if target_item is node:
            return

        node.parent.children = [c for c in node.parent.children if c is not node]

        if target_item.is_leaf():
            # Insert the item after the target
            target_idx = target_item.parent.children.index(target_item) + 1
            target_item.parent.children.insert(target_idx, node)
            node.parent = target_item.parent
        else:
            # Append to the branch children
            target_item.children.append(node)
            node.parent = target_item

        if self._on_value_changed:
            self._on_value_changed(self.tag, self.playlist, self._user_data)

        self.regenerate()

    def _on_right_click(self) -> None:
        self._ctx = None
        for row in dpg.get_item_children(self.tag, slot=1):
            for child in dpg.get_item_children(row, slot=1):
                try:
                    if dpg.is_item_hovered(child):
                        self._ctx_row = row
                        mx, my = dpg.get_mouse_pos(local=False)
                        dpg.configure_item(self._t("context"), pos=(mx, my), show=True)
                        return
                except KeyError:
                    continue

    def _add_child(self) -> None:
        if not self._ctx_row:
            return

        node: PlaylistTreeItem = dpg.get_item_user_data(self._ctx_row)
        new = PlaylistTreeItem.new(RandomSequenceMode.Inherit)

        # Can't be a leaf node if it has children, but we can transfer it to the new child
        new.item.segment_id = node.item.segment_id
        node.item.segment_id = 0
        node.children.append(new)
        new.parent = node

        if self._on_value_changed:
            self._on_value_changed(self.tag, self.playlist, self._user_data)

        self.regenerate()

    def _add_sibling(self) -> None:
        if not self._ctx_row:
            return

        node: PlaylistTreeItem = dpg.get_item_user_data(self._ctx_row)
        new = PlaylistTreeItem.new(RandomSequenceMode.Inherit)

        if node.parent:
            node.parent.children.append(new)
            new.parent = node.parent

            if self._on_value_changed:
                self._on_value_changed(self.tag, self.playlist, self._user_data)

            self.regenerate()

    def _delete_node(self) -> None:
        if not self._ctx_row:
            return

        node: PlaylistTreeItem = dpg.get_item_user_data(self._ctx_row)

        if node.parent:
            node.parent.children = [c for c in node.parent.children if c is not node]
        
        if self._on_value_changed:
            self._on_value_changed(self.tag, self.playlist, self._user_data)
        
        self.regenerate()
